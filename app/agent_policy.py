from __future__ import annotations

import re
import unicodedata
from typing import Any


def norm(value: str) -> str:
    s = unicodedata.normalize('NFD', value or '')
    return ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn').lower().strip()


# These questions are never answered automatically. The rule is intentionally broader than
# strictly protected-class questions because legal declarations and immigration/work-permit
# statements can create material consequences when guessed.
SENSITIVE_OR_LEGAL_RX = re.compile(
    r'handicap|disabil|sant[eé]|medical|sexe|gender|genre|race|ethni|relig|syndicat|union|'
    r'polit|casier|criminal|conviction|orientation|sexual|grossesse|pregnan|veteran|'
    r'visa|sponsor|work.?permit|permis.?de.?travail|autorisation.?de.?travail|'
    r'legally.?authorized|right.?to.?work|citizenship|nationalit[eé]|attest|certif|declare|d[eé]clare|'
    r'background.?check|drug.?test|security.?clearance',
    re.I,
)

CAPTCHA_OR_MFA_RX = re.compile(
    r'captcha|recaptcha|hcaptcha|verification.?code|one.?time.?code|otp|2fa|mfa|authenticator|'
    r'code de verification|code de sécurité',
    re.I,
)

SUBMIT_RX = re.compile(
    r'(^|\b)(submit( application)?|send application|complete application|final submit|'
    r'envoyer( ma)? candidature|soumettre( la)? candidature|valider( ma)? candidature|'
    r'confirmer( ma)? candidature|postuler maintenant)($|\b)',
    re.I,
)

SAFE_NEXT_RX = re.compile(
    r'(^|\b)(next|continue|save and continue|continue application|suivant|continuer|poursuivre|'
    r'enregistrer et continuer|étape suivante|etape suivante)($|\b)',
    re.I,
)

ACCOUNT_RX = re.compile(
    r'create account|sign up|register|cr[eé]er.*compte|inscription|mot de passe|password|sign in|log in|connexion',
    re.I,
)


def field_is_sensitive(field: dict[str, Any]) -> bool:
    text = ' '.join(str(field.get(k, '')) for k in ('label', 'name', 'id', 'dom_id', 'aria_label', 'autocomplete'))
    return bool(field.get('sensitive_or_legal') or SENSITIVE_OR_LEGAL_RX.search(text))


def field_is_captcha_or_mfa(field: dict[str, Any]) -> bool:
    text = ' '.join(str(field.get(k, '')) for k in ('label', 'name', 'id', 'dom_id', 'aria_label', 'autocomplete'))
    return bool(CAPTCHA_OR_MFA_RX.search(text))


def button_kind(text: str) -> str:
    t = norm(text)
    if SUBMIT_RX.search(t):
        return 'submit'
    if ACCOUNT_RX.search(t):
        return 'account'
    if SAFE_NEXT_RX.search(t):
        return 'next'
    return 'other'


def resolve_value_ref(value_ref: str, profile: dict[str, Any]) -> Any:
    """Resolve only explicit, whitelisted profile references.

    The model returns references, not raw invented values. Saved-answer references are indexed,
    which keeps custom prose under the candidate's control.
    """
    ref = (value_ref or '').strip()
    direct = {
        'profile.first_name': 'first_name',
        'profile.last_name': 'last_name',
        'profile.full_name': '__full_name__',
        'profile.email': 'email',
        'profile.phone': 'phone',
        'profile.address_line1': 'address_line1',
        'profile.city': 'city',
        'profile.postal_code': 'postal_code',
        'profile.country': 'country',
        'profile.linkedin': 'linkedin',
        'profile.portfolio': 'portfolio',
        'profile.current_title': 'current_title',
        'profile.current_company': 'current_company',
        'profile.years_experience': 'years_experience',
        'profile.school': 'school',
        'profile.degree': 'degree',
        'profile.field_of_study': 'field_of_study',
        'profile.graduation_year': 'graduation_year',
        'profile.availability_text': 'availability_text',
        'profile.availability_start_date': 'availability_start_date',
    }
    if ref in direct:
        key = direct[ref]
        if key == '__full_name__':
            return ' '.join(x for x in [profile.get('first_name', ''), profile.get('last_name', '')] if x).strip()
        return profile.get(key, '')
    m = re.fullmatch(r'saved_answer\.(\d+)', ref)
    if m:
        idx = int(m.group(1))
        answers = profile.get('saved_answers', []) or []
        if 0 <= idx < len(answers):
            item = answers[idx]
            if isinstance(item, dict) and item.get('autofill', True) is not False:
                return item.get('value', '')
    return None


def available_value_refs(profile: dict[str, Any]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for ref in [
        'profile.first_name', 'profile.last_name', 'profile.full_name', 'profile.email', 'profile.phone',
        'profile.address_line1', 'profile.city', 'profile.postal_code', 'profile.country',
        'profile.linkedin', 'profile.portfolio', 'profile.current_title', 'profile.current_company',
        'profile.years_experience', 'profile.school', 'profile.degree', 'profile.field_of_study',
        'profile.graduation_year', 'profile.availability_text', 'profile.availability_start_date',
    ]:
        v = resolve_value_ref(ref, profile)
        if v not in (None, ''):
            # The planner sees only a concise description for high-PII facts.
            if ref in {'profile.email', 'profile.phone', 'profile.address_line1'}:
                refs[ref] = 'available'
            else:
                refs[ref] = str(v)[:180]
    for i, item in enumerate(profile.get('saved_answers', []) or []):
        if isinstance(item, dict) and item.get('value') and item.get('autofill', True) is not False:
            refs[f'saved_answer.{i}'] = str(item.get('label') or item.get('match') or f'Saved answer {i}')[:180]
    return refs
