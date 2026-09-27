from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

# This module is a Python adaptation of ideas used by the MIT-licensed
# devdattatalele/auto-apply universal field/dropdown handling. See THIRD_PARTY_NOTICES.md.

OPTION_SELECTORS = [
    '[role="option"]',
    '.select__option',
    '.select2-results__option',
    '[class*="menu"] [class*="option"]',
    '[class*="listbox"] [class*="option"]',
    'li[class*="option"]',
    '.dropdown-item',
    'div[data-value]',
    '[class*="MenuItem"]',
]


def fuzzy_score(needle: str, haystack: str) -> float:
    a = (needle or '').strip().lower()
    b = (haystack or '').strip().lower()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.82
    aw = set(re.findall(r'[\wÀ-ÿ]+', a))
    bw = set(re.findall(r'[\wÀ-ÿ]+', b))
    token = len(aw & bw) / max(1, len(aw | bw))
    seq = SequenceMatcher(None, a, b).ratio()
    return max(token * 0.72, seq * 0.68)


def _best_option(options: list[tuple[Any, str]], desired: str, min_score: float = 0.38):
    best = None
    score = 0.0
    for obj, text in options:
        s = fuzzy_score(desired, text)
        if s > score:
            best, score = (obj, text), s
    if best and score >= min_score:
        return best[0], best[1], score
    return None, '', score


def select_native(loc, desired: str) -> tuple[bool, str, str, float]:
    try:
        opts = loc.locator('option')
        values = []
        for i in range(min(opts.count(), 200)):
            o = opts.nth(i)
            text = (o.inner_text(timeout=300) or '').strip()
            value = o.get_attribute('value') or ''
            if text:
                values.append((value, text))
        value, text, score = _best_option(values, desired)
        if value is not None:
            try:
                loc.select_option(value=value)
            except Exception:
                loc.select_option(label=text)
            return True, text, 'native-select-fuzzy', score
    except Exception:
        pass
    return False, '', 'native-select-failed', 0.0


def select_custom(page, loc, desired: str) -> tuple[bool, str, str, float]:
    """Conservative custom combobox handler.

    It opens the control, scans visible ARIA/CSS options, picks the strongest fuzzy match and
    requires a modest confidence threshold. It does not blindly arrow through dozens of choices.
    """
    try:
        loc.scroll_into_view_if_needed()
    except Exception:
        pass
    try:
        page.keyboard.press('Escape')
    except Exception:
        pass
    try:
        loc.click(timeout=1800)
    except Exception:
        return False, '', 'custom-open-failed', 0.0
    page.wait_for_timeout(350)

    # Searchable comboboxes often benefit from typing a short prefix.
    try:
        tag = loc.evaluate('(e)=>e.tagName.toLowerCase()')
        if tag in {'input', 'textarea'}:
            try:
                loc.fill('')
                loc.type(desired[:24], delay=35)
                page.wait_for_timeout(600)
            except Exception:
                pass
    except Exception:
        pass

    candidates: list[tuple[Any, str]] = []
    seen = set()
    for sel in OPTION_SELECTORS:
        try:
            xs = page.locator(sel)
            for i in range(min(xs.count(), 120)):
                o = xs.nth(i)
                if not o.is_visible():
                    continue
                txt = (o.inner_text(timeout=300) or '').strip()
                key = txt.lower()
                if not txt or len(txt) > 180 or key in seen:
                    continue
                seen.add(key)
                candidates.append((o, txt))
        except Exception:
            pass

    obj, text, score = _best_option(candidates, desired)
    if obj is None:
        try:
            page.keyboard.press('Escape')
        except Exception:
            pass
        return False, '', 'custom-no-match', score
    try:
        obj.click(timeout=1800)
        page.wait_for_timeout(400)
        return True, text, 'custom-option-fuzzy', score
    except Exception:
        return False, text, 'custom-click-failed', score
