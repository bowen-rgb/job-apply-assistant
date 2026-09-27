from __future__ import annotations
import re
import unicodedata
from datetime import date


def norm(s: str) -> str:
    s = unicodedata.normalize('NFD', s or '')
    s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
    return s.lower()


def _iso_date(s: str) -> date | None:
    try:
        return date.fromisoformat((s or '')[:10])
    except Exception:
        return None


def _holiday_conflict(text: str) -> str:
    t = norm(text)
    patterns = [
        r'disponib\w*[^.\n]{0,60}(?:noel|fetes de fin d.annee)',
        r'(?:noel|fetes de fin d.annee)[^.\n]{0,60}(?:obligatoire|imperatif|requis|disponib)',
        r'travaill\w*[^.\n]{0,50}(?:noel|24 decembre|25 decembre|31 decembre)',
        r'renfort\s+(?:de\s+)?noel',
        r'periode\s+de\s+noel',
    ]
    for p in patterns:
        m = re.search(p, t, re.I)
        if m:
            return m.group(0)[:180]
    return ''


def _role_hits(text: str, profile: dict) -> list[str]:
    t = norm(text)
    hits = []
    for role in profile.get('preferred_roles', []):
        r = norm(role)
        if r and r in t:
            hits.append(role)
    aliases = profile.get('role_aliases', {})
    for canonical, vals in aliases.items():
        for v in vals:
            if norm(v) in t and canonical not in hits:
                hits.append(canonical)
                break
    return hits


def evaluate(job: dict, profile: dict):
    title = job.get('title', '')
    body = job.get('text') or job.get('body', '') or job.get('description', '')
    snippet = job.get('snippet', '')
    t = norm('\n'.join([title, body, snippet, job.get('employment_type', ''), job.get('location', '')]))
    reasons: list[str] = []
    flags: list[str] = []

    # Hard contract conflict. Avoid blanket keyword exclusion because a CDD listing can
    # mention CDI in boilerplate or company text.
    allowed_contracts = [norm(x) for x in profile.get('contracts', [])]
    employment = norm(job.get('employment_type', ''))
    if employment and allowed_contracts:
        if 'cdi' in employment and not any('cdi' == c for c in allowed_contracts):
            return -100, 'reject', 'contract_conflict:CDI', ['hard_contract_conflict']
        if ('stage' in employment or 'alternance' in employment) and not any(x in employment for x in allowed_contracts):
            return -95, 'reject', f'contract_conflict:{job.get("employment_type", "")}', ['hard_contract_conflict']

    # Explicit exclusion terms other than generic holiday words.
    for term in profile.get('exclude_terms', []):
        nt = norm(term)
        if not nt or nt in {'noel', 'christmas', 'fetes de fin d annee'}:
            continue
        if nt in t:
            return -100, 'reject', f'excluded:{term}', ['hard_exclusion']

    holiday = _holiday_conflict(body + '\n' + title)
    holiday_pref = str((profile.get('availability') or {}).get('holiday_work', 'flexible')).lower()
    if holiday and holiday_pref == 'no':
        return -100, 'reject', f'holiday_conflict:{holiday}', ['holiday_conflict']
    elif holiday:
        flags.append('holiday_requirement')

    expired_phrase = re.search(r"offre (?:n.est )?plus disponible|offre expir[eé]e|poste pourvu|candidatures? (?:close|ferm[eé]e)|position has been filled", t, re.I)
    if expired_phrase:
        return -95, 'expired', f'expired_phrase:{expired_phrase.group(0)}', ['expired']

    max_end = _iso_date(profile.get('max_end_date', ''))
    end = _iso_date(job.get('end_date', ''))
    valid = _iso_date(job.get('valid_through', ''))
    posted = _iso_date(job.get('date_posted', ''))
    today = date.today()
    if end and max_end and end > max_end:
        return -100, 'reject', f'end_after_max:{end.isoformat()}', ['end_date_conflict']
    if valid and valid < today:
        return -90, 'expired', f'expired:{valid.isoformat()}', ['expired']

    score = 0
    configured_roles = profile.get('preferred_roles', [])
    roles = _role_hits(title + '\n' + body, profile)
    if roles:
        score += min(42, 18 + 9 * min(3, len(roles)))
        reasons.append('role:' + ','.join(roles[:3]))
    elif configured_roles:
        flags.append('role_not_explicit')

    configured_contracts = profile.get('contracts', [])
    contract_hits = []
    for c in configured_contracts:
        if norm(c) in t:
            contract_hits.append(c)
    if contract_hits:
        score += min(25, 13 + 6 * min(2, len(contract_hits)))
        reasons.append('contract:' + ','.join(contract_hits[:2]))
    elif configured_contracts:
        flags.append('contract_unclear')

    include_hits = [x for x in profile.get('include_terms', []) if norm(x) and norm(x) in t]
    if include_hits:
        score += min(12, 4 * len(include_hits))
        reasons.append('wanted:' + ','.join(include_hits[:3]))

    industry_hits = [x for x in profile.get('industries', []) if norm(x) and norm(x) in t]
    if industry_hits:
        score += min(8, 4 * len(industry_hits))
        reasons.append('industry:' + ','.join(industry_hits[:2]))

    configured_locations = profile.get('locations', [])
    loc_hits = [x for x in configured_locations if norm(x) in t]
    if loc_hits:
        score += min(15, 8 + 4 * min(2, len(loc_hits)))
        reasons.append('location:' + ','.join(loc_hits[:2]))
    elif configured_locations:
        flags.append('location_unclear')

    if end:
        score += 15 if max_end else 5
        reasons.append('end_date:' + end.isoformat())
    elif max_end:
        flags.append('end_date_missing')
        score -= 6

    if posted:
        age = (today - posted).days
        if age > 90:
            score -= 25
            flags.append('stale_posting')
            reasons.append(f'posted_age:{age}d')
        elif age >= 0:
            score += 4
            reasons.append(f'posted_age:{age}d')
    elif job.get('date_posted'):
        reasons.append('date_posted_unparsed')
    if job.get('salary'):
        score += 2
    if job.get('structured_json'):
        score += 4
        reasons.append('structured_jobposting')

    # Penalize clearly long durations when no exact end date was found.
    if not end:
        m = re.search(r'\b(\d{1,2})\s*mois\b', t)
        if m:
            months = int(m.group(1))
            if months >= 4:
                score -= 35
                reasons.append(f'long_duration:{months}m')
                flags.append('duration_risk')
            elif months <= 3:
                score += 6
                reasons.append(f'short_duration:{months}m')

    score = max(-100, min(100, score))
    if score >= 65 and ('end_date_missing' not in flags or not max_end):
        decision = 'keep'
    elif score >= 38:
        decision = 'review'
    else:
        decision = 'low'

    reason = '; '.join(reasons + ([f'flags:{",".join(flags)}'] if flags else [])) or 'weak_match'
    return score, decision, reason, flags
