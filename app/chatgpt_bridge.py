from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from filelock import FileLock
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

ROOT = Path(__file__).resolve().parent.parent
CHATGPT_LOCK = FileLock(str(ROOT / 'data' / 'chatgpt-web.lock'))


def _find_prompt(page):
    selectors = [
        '#prompt-textarea',
        '[data-testid="prompt-textarea"]',
        'textarea[placeholder*="Message" i]',
        'textarea[placeholder*="Envoyer" i]',
        'div[contenteditable="true"]',
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).last
            if loc.count() and loc.is_visible():
                return loc
        except Exception:
            pass
    try:
        loc = page.get_by_role('textbox').last
        if loc.count() and loc.is_visible():
            return loc
    except Exception:
        pass
    return None


def _set_prompt(locator, prompt: str):
    try:
        locator.fill(prompt)
        return
    except Exception:
        pass
    locator.click()
    for key in ('Control+A', 'Meta+A'):
        try:
            locator.press(key)
        except Exception:
            pass
    try:
        locator.press('Backspace')
    except Exception:
        pass
    locator.type(prompt, delay=0)


def _assistant_messages(page) -> list[str]:
    selectors = [
        '[data-message-author-role="assistant"]',
        'article[data-turn="assistant"]',
        'article:has([data-message-author-role="assistant"])',
        '[data-testid^="conversation-turn-"]',
        'main article',
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel)
            n = loc.count()
            if n:
                out = []
                for i in range(n):
                    txt = loc.nth(i).inner_text(timeout=1200).strip()
                    if txt:
                        out.append(txt)
                if out:
                    return out
        except Exception:
            pass
    return []


def _is_generating(page) -> bool:
    for rx in [re.compile(r'stop generating', re.I), re.compile(r'arrêter', re.I), re.compile(r'^stop$', re.I)]:
        try:
            b = page.get_by_role('button', name=rx).first
            if b.count() and b.is_visible():
                return True
        except Exception:
            pass
    return False


def extract_json(text: str) -> dict[str, Any]:
    text = (text or '').strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.I)
    text = re.sub(r'\s*```$', '', text)
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError('No valid JSON object found in ChatGPT response')


def _matches_purpose(obj: Any, purpose: str) -> bool:
    if not isinstance(obj, dict):
        return False
    if purpose == 'final-review':
        return str(obj.get('verdict', '')).upper().strip() in {'APPLY', 'SKIP', 'HUMAN_REVIEW'}
    if purpose == 'job-agent':
        return str(obj.get('status', '')).upper().strip() in {'CONTINUE', 'HANDOFF', 'DONE'}
    return True


def _extract_json_for_purpose(text: str, purpose: str) -> dict[str, Any] | None:
    raw = (text or '').strip()
    if not raw:
        return None
    decoder = json.JSONDecoder()
    found = None
    for m in re.finditer(r'\{', raw):
        try:
            obj, _ = decoder.raw_decode(raw[m.start():])
        except Exception:
            continue
        if _matches_purpose(obj, purpose):
            found = obj
    return found


def _page_json(page, purpose: str) -> dict[str, Any] | None:
    # Fast path: known assistant/turn containers.
    for sel in (
        '[data-message-author-role="assistant"]',
        '[data-testid^="conversation-turn-"]',
        'article',
        'main',
        'body',
    ):
        try:
            loc = page.locator(sel)
            n = min(loc.count(), 80)
            for i in range(max(0, n - 12), n):
                try:
                    obj = _extract_json_for_purpose(loc.nth(i).inner_text(timeout=1000), purpose)
                    if obj is not None:
                        return obj
                except Exception:
                    pass
        except Exception:
            pass
    return None


def ask_chatgpt_json(context, prompt: str, cfg: dict[str, Any], *, purpose: str = 'job-agent') -> dict[str, Any]:
    """Use an already-authenticated ChatGPT web session as a JSON planner/reviewer.

    The shared browser context is controlled through CDP by the caller. This helper opens a
    temporary ChatGPT tab and never touches the application tab. It deliberately does not
    use undocumented network endpoints: the integration remains a visible browser workflow.
    """
    chat_url = cfg.get('url', 'https://chatgpt.com/')
    timeout_s = max(30, int(cfg.get('timeout_seconds', 180)))
    keep_open = bool(cfg.get('keep_chat_tab_open', False))

    with CHATGPT_LOCK.acquire(timeout=max(300, timeout_s + 120)):
        page = context.new_page()
        try:
            page.goto(chat_url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(1600)
            box = _find_prompt(page)
            if box is None:
                raise RuntimeError('ChatGPT prompt box not found. Log in to chatgpt.com in the shared Chrome profile.')

            before = _assistant_messages(page)
            _set_prompt(box, prompt)
            box.press('Enter')

            deadline = time.time() + timeout_s
            response = ''
            last = ''
            stable = 0
            while time.time() < deadline:
                page.wait_for_timeout(1000)

                # ChatGPT web changes its message DOM periodically. Prefer a
                # complete typed JSON object visible anywhere in the recent
                # conversation over relying on one assistant selector.
                obj = _page_json(page, purpose)
                if obj is not None:
                    return obj

                msgs = _assistant_messages(page)
                if len(msgs) > len(before):
                    response = msgs[-1]
                elif msgs and msgs[-1] not in before:
                    response = msgs[-1]
                if response and response == last and not _is_generating(page):
                    stable += 1
                else:
                    stable = 0
                last = response
                if response and stable >= 2:
                    obj = _extract_json_for_purpose(response, purpose)
                    if obj is not None:
                        return obj

            obj = _page_json(page, purpose)
            if obj is not None:
                return obj
            if response:
                obj = _extract_json_for_purpose(response, purpose)
                if obj is not None:
                    return obj
            raise PlaywrightTimeoutError(f'No ChatGPT response detected for {purpose}')
        finally:
            if not keep_open:
                try:
                    page.close()
                except Exception:
                    pass
