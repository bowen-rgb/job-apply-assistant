from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_policy import SENSITIVE_OR_LEGAL_RX


def norm(s: str) -> str:
    s = unicodedata.normalize('NFD', s or '')
    return ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn').lower()


SENSITIVE_RX = SENSITIVE_OR_LEGAL_RX
PII_RX = re.compile(
    r'first.?name|last.?name|pr[eé]nom|nom|email|mail|phone|t[eé]l[eé]phone|mobile|address|adresse|postal|zip|linkedin|cv|resume',
    re.I,
)

FIELD_RULES: tuple[tuple[str, str], ...] = (
    (r'\b(prenom|first.?name|given.?name)\b', 'first_name'),
    (r'\b(nom de famille|last.?name|family.?name|surname)\b', 'last_name'),
    (r'\b(nom complet|full.?name|your name)\b', '__full_name__'),
    (r'\b(email|e-mail|courriel|mail)\b', 'email'),
    (r'\b(phone|telephone|tel|mobile|portable)\b', 'phone'),
    (r'\b(adresse|address|street address|address line 1)\b', 'address_line1'),
    (r'\b(code postal|postal.?code|zip)\b', 'postal_code'),
    (r'\b(ville|city|localite|town)\b', 'city'),
    (r'\b(linkedin)\b', 'linkedin'),
    (r'\b(portfolio|site web|website|personal site)\b', 'portfolio'),
    (r'\b(poste actuel|current title|job title|titre du poste)\b', 'current_title'),
    (r'\b(entreprise actuelle|current company|employer|company)\b', 'current_company'),
    (r'\b(annees? d.experience|years? of experience|experience years)\b', 'years_experience'),
    (r'\b(ecole|school|universite|university|college)\b', 'school'),
    (r'\b(diplome|degree|qualification)\b', 'degree'),
    (r'\b(domaine d.etudes|field of study|major)\b', 'field_of_study'),
    (r'\b(annee de diplome|graduation year|year of graduation)\b', 'graduation_year'),
    (r'\b(disponibilite|disponible|availability)\b', 'availability_text'),
    (r'\b(date de debut|start date|available from|disponible a partir)\b', 'availability_start_date'),
)


def label_for(page, loc, idx: int) -> str:
    bits: list[str] = []
    for attr in ('aria-label', 'placeholder'):
        try:
            val = loc.get_attribute(attr) or ''
            if val:
                bits.append(val)
        except Exception:
            pass
    try:
        el_id = loc.get_attribute('id') or ''
        if el_id:
            lab = page.locator(f'label[for="{el_id}"]').first
            if lab.count():
                txt = lab.inner_text(timeout=500).strip()
                if txt:
                    bits.insert(0, txt)
    except Exception:
        pass
    try:
        parent_label = loc.locator('xpath=ancestor::label[1]').first
        if parent_label.count():
            txt = parent_label.inner_text(timeout=500).strip()
            if txt:
                bits.insert(0, txt)
    except Exception:
        pass
    try:
        name = loc.get_attribute('name') or ''
        if name:
            bits.append(name)
    except Exception:
        pass
    return ' | '.join(dict.fromkeys([b.strip() for b in bits if b.strip()])) or f'field_{idx}'


def safe_descriptor(page, loc, idx: int) -> tuple[str, str]:
    label = label_for(page, loc, idx)
    name = ''
    try:
        name = loc.get_attribute('name') or ''
    except Exception:
        pass
    return label, norm(label + ' ' + name)


def _fill_if_empty(loc, value: Any) -> bool:
    if value is None or str(value) == '':
        return False
    try:
        if str(loc.input_value()).strip():
            return False
    except Exception:
        pass
    try:
        loc.fill(str(value))
        return True
    except Exception:
        return False


def _match_saved_answer(desc: str, profile: dict) -> tuple[str, str] | None:
    for item in profile.get('saved_answers', []) or []:
        if not isinstance(item, dict) or item.get('autofill', True) is False:
            continue
        patterns = item.get('match') or item.get('patterns') or ''
        if isinstance(patterns, str):
            patterns = [x.strip() for x in re.split(r'[\n,;]+', patterns) if x.strip()]
        value = item.get('value', '')
        if not value:
            continue
        for pattern in patterns or []:
            try:
                if re.search(pattern, desc, re.I):
                    return str(value), str(item.get('label') or pattern)
            except re.error:
                if norm(str(pattern)) in desc:
                    return str(value), str(item.get('label') or pattern)
    return None


def fill_exact_selectors(page, mapping: dict[str, list[str]], profile: dict, report: dict) -> None:
    """Fill ATS-specific deterministic text selectors before generic matching."""
    full_name = ' '.join(x for x in [profile.get('first_name', ''), profile.get('last_name', '')] if x).strip()
    for key, selectors in mapping.items():
        value = full_name if key == '__full_name__' else profile.get(key, '')
        if value in (None, ''):
            continue
        for selector in selectors:
            try:
                loc = page.locator(selector).first
                if not loc.count() or not loc.is_visible() or loc.is_disabled():
                    continue
                desc = norm(' '.join([
                    selector,
                    loc.get_attribute('name') or '',
                    loc.get_attribute('id') or '',
                    loc.get_attribute('aria-label') or '',
                ]))
                if SENSITIVE_RX.search(desc):
                    report['skipped_sensitive'].append(desc[:180])
                    continue
                if _fill_if_empty(loc, value):
                    report['filled'].append(key)
                    report['actions'].append({'field': key, 'strategy': 'ats_selector', 'selector': selector, 'confidence': 100})
                    break
            except Exception as exc:
                report['errors'].append(f'{key}:{selector}:{exc}'[:300])


LETTER_RX = re.compile(r'cover.?letter|lettre|motivation|supporting.?letter', re.I)
RESUME_RX = re.compile(r'\bcv\b|r[eé]sum[eé]|curriculum', re.I)


def upload_resume(page, resume_path: Path | None, selectors: list[str] | None, report: dict) -> None:
    if not resume_path or not resume_path.exists():
        report['errors'].append('resume: Aucun CV disponible dans le profil')
        return
    tried: set[str] = set()
    for selector in selectors or []:
        if selector in tried:
            continue
        tried.add(selector)
        try:
            loc = page.locator(selector).first
            if loc.count():
                descriptor = label_for(page, loc, 0) + ' ' + (loc.get_attribute('name') or '')
                if LETTER_RX.search(descriptor):
                    continue
                loc.set_input_files(str(resume_path))
                report['filled'].append('resume')
                report['actions'].append({'field': 'resume', 'strategy': 'ats_selector', 'selector': selector, 'confidence': 100})
                return
        except Exception as exc:
            report['errors'].append(f'resume:{selector}:{exc}'[:300])

    files = page.locator('input[type="file"]')
    for i in range(min(files.count(), 30)):
        try:
            inp = files.nth(i)
            label = label_for(page, inp, i)
            attrs = ' '.join([
                label,
                inp.get_attribute('name') or '',
                inp.get_attribute('id') or '',
                inp.get_attribute('accept') or '',
            ])
            if LETTER_RX.search(attrs):
                continue
            if RESUME_RX.search(attrs) or (files.count() == 1 and re.search(r'\.pdf|application/pdf|\.docx?', attrs, re.I)):
                inp.set_input_files(str(resume_path))
                report['filled'].append('resume')
                report['actions'].append({'field': 'resume', 'strategy': 'generic_file', 'selector': label[:180], 'confidence': 90})
                return
        except Exception as exc:
            report['errors'].append(f'resume_generic:{exc}'[:300])


def upload_cover_letter(page, path: Path | None, report: dict) -> None:
    if not path or not path.is_file():
        return
    files = page.locator('input[type="file"]')
    for index in range(min(files.count(), 30)):
        field = files.nth(index)
        descriptor = label_for(page, field, index) + ' ' + (field.get_attribute('name') or '')
        if LETTER_RX.search(descriptor):
            try:
                field.set_input_files(str(path))
                report['filled'].append('cover_letter_file')
                report['actions'].append({'field': 'cover_letter_file', 'strategy': 'label_rule', 'confidence': 95})
            except Exception as exc:
                report['errors'].append(f'cover_letter:{exc}'[:300])


def generic_fill(page, profile: dict, resume_path: Path | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        'filled': [],
        'actions': [],
        'skipped_sensitive': [],
        'skipped_ambiguous': [],
        'errors': [],
    }
    full_name = ' '.join(x for x in [profile.get('first_name', ''), profile.get('last_name', '')] if x).strip()
    locs = page.locator('input, textarea, select')
    count = min(locs.count(), 260)
    for i in range(count):
        loc = locs.nth(i)
        try:
            if not loc.is_visible() or loc.is_disabled():
                continue
            tag = loc.evaluate('(e)=>e.tagName.toLowerCase()')
            typ = (loc.get_attribute('type') or tag).lower()
            if typ in {'hidden', 'password', 'checkbox', 'radio', 'submit', 'button', 'file'}:
                continue
            label, desc = safe_descriptor(page, loc, i)
            if SENSITIVE_RX.search(label + ' ' + desc):
                report['skipped_sensitive'].append(label[:220])
                continue

            if typ == 'email' and _fill_if_empty(loc, profile.get('email', '')):
                report['filled'].append('email')
                report['actions'].append({'field': 'email', 'strategy': 'native_type', 'selector': label[:180], 'confidence': 100})
                continue
            if typ == 'tel' and _fill_if_empty(loc, profile.get('phone', '')):
                report['filled'].append('phone')
                report['actions'].append({'field': 'phone', 'strategy': 'native_type', 'selector': label[:180], 'confidence': 100})
                continue
            if typ == 'date' and re.search(r'\b(disponib|available|start|debut)\b', desc, re.I):
                if _fill_if_empty(loc, profile.get('availability_start_date', '')):
                    report['filled'].append('availability_start_date')
                    report['actions'].append({'field': 'availability_start_date', 'strategy': 'native_date', 'selector': label[:180], 'confidence': 95})
                    continue

            if tag == 'select':
                if re.search(r'\b(pays|country)\b', desc):
                    country = profile.get('country', '')
                    if country:
                        try:
                            loc.select_option(label=re.compile(rf'^{re.escape(str(country))}$', re.I))
                            report['filled'].append('country')
                            report['actions'].append({'field': 'country', 'strategy': 'generic_select', 'selector': label[:180], 'confidence': 95})
                            continue
                        except Exception:
                            pass
                report['skipped_ambiguous'].append(label[:220])
                continue

            matched = False
            if tag in {'textarea', 'input'} and LETTER_RX.search(desc) and profile.get('cover_letter_text'):
                if _fill_if_empty(loc, profile['cover_letter_text']):
                    report['filled'].append('cover_letter_text')
                    report['actions'].append({'field': 'cover_letter_text', 'strategy': 'job_specific_letter', 'confidence': 95})
                continue
            for rx, key in FIELD_RULES:
                if re.search(rx, desc, re.I):
                    value = full_name if key == '__full_name__' else profile.get(key, '')
                    if _fill_if_empty(loc, value):
                        report['filled'].append(key)
                        report['actions'].append({'field': key, 'strategy': 'label_rule', 'selector': label[:180], 'confidence': 90})
                    matched = True
                    break
            if matched:
                continue

            saved = _match_saved_answer(desc, profile)
            if saved:
                value, label_name = saved
                if _fill_if_empty(loc, value):
                    report['filled'].append(f'saved:{label_name}')
                    report['actions'].append({'field': f'saved:{label_name}', 'strategy': 'saved_answer', 'selector': label[:180], 'confidence': 85})
                continue

            if typ in {'text', 'textarea', 'url', 'number'}:
                report['skipped_ambiguous'].append(label[:220])
        except Exception as exc:
            report['errors'].append(f'field_{i}:{exc}'[:300])

    upload_resume(page, resume_path, None, report)
    upload_cover_letter(page, Path(profile['cover_letter_path']) if profile.get('cover_letter_path') else None, report)
    report['filled'] = list(dict.fromkeys(report['filled']))
    report['skipped_sensitive'] = list(dict.fromkeys(report['skipped_sensitive']))
    report['skipped_ambiguous'] = list(dict.fromkeys(report['skipped_ambiguous']))[:80]
    return report


def safe_form_snapshot(page) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    locs = page.locator('input, textarea, select')
    count = min(locs.count(), 200)
    for i in range(count):
        loc = locs.nth(i)
        try:
            if not loc.is_visible():
                continue
            tag = loc.evaluate('(e)=>e.tagName.toLowerCase()')
            typ = (loc.get_attribute('type') or tag).lower()
            if typ in {'hidden', 'password'}:
                continue
            label = label_for(page, loc, i)
            name = loc.get_attribute('name') or ''
            required = bool(loc.evaluate('(e)=>Boolean(e.required || e.getAttribute("aria-required")==="true")'))
            answered = False
            if typ in {'checkbox', 'radio'}:
                try:
                    answered = loc.is_checked()
                except Exception:
                    pass
            elif typ == 'file':
                try:
                    answered = bool(loc.evaluate('(e)=>e.files && e.files.length'))
                except Exception:
                    pass
            else:
                try:
                    answered = bool(str(loc.input_value()).strip())
                except Exception:
                    pass
            item: dict[str, Any] = {
                'label': label[:350],
                'name': name[:180],
                'type': typ[:40],
                'required': required,
                'answered': answered,
                'sensitive_or_legal': bool(SENSITIVE_RX.search(label + ' ' + name)),
                'pii_field': bool(PII_RX.search(label + ' ' + name)),
            }
            if tag == 'select':
                try:
                    opts = loc.locator('option').all_inner_texts()[:30]
                    item['options'] = [x.strip()[:160] for x in opts if x.strip()]
                except Exception:
                    pass
            fields.append(item)
        except Exception:
            pass
    return {
        'page_url': page.url,
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'privacy_note': 'Typed field values are not included. Only labels, field types, required/answered flags and select option text are provided.',
        'fields': fields,
    }


def generic_click_apply(page) -> bool:
    """Click only a clear *entry* control from a job-description page.

    If the page already looks like an application form, do nothing. Final-submit wording is
    intentionally excluded even if some sites also use it as an entry CTA.
    """
    try:
        likely_form_fields = page.locator(
            'input[type="email"], input[type="tel"], input[type="file"], '
            'input[name*="first" i], input[name*="last" i], textarea'
        )
        visible = 0
        for i in range(min(likely_form_fields.count(), 12)):
            try:
                visible += 1 if likely_form_fields.nth(i).is_visible() else 0
            except Exception:
                pass
        if visible >= 2:
            return False
    except Exception:
        pass

    patterns = [
        r'^postuler$', r'^candidater$', r'^je postule$', r'^apply now$', r'^apply$',
        r'^start application$', r'^begin application$', r'^commencer la candidature$',
    ]
    for p in patterns:
        rx = re.compile(p, re.I)
        for role in ('button', 'link'):
            try:
                loc = page.get_by_role(role, name=rx).first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=3000)
                    page.wait_for_timeout(900)
                    return True
            except Exception:
                pass
    return False


def generic_confirmation(page) -> tuple[bool, str]:
    url = (page.url or '').lower()
    if any(x in url for x in ('/thank', '/thanks', '/submitted', '/confirmation', 'application-complete')):
        return True, f'confirmation_url:{page.url}'
    try:
        text = page.locator('body').inner_text(timeout=1200)[:12000]
    except Exception:
        text = ''
    patterns = (
        r'thank you for (?:your )?(?:application|applying)',
        r'application (?:has been )?submitted',
        r'we have received your application',
        r'merci (?:pour|d[’\']avoir).*candidature',
        r'candidature (?:a bien [eé]t[eé]|est) (?:envoy[eé]e|re[cç]ue|soumise)',
        r'nous avons bien re[cç]u votre candidature',
    )
    for rx in patterns:
        if re.search(rx, text, re.I | re.S):
            return True, f'confirmation_text:{rx}'
    return False, ''
