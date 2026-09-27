from __future__ import annotations

from copy import deepcopy
from typing import Any


def normalize_search_profiles(rows: Any) -> list[dict[str, Any]]:
    """Normalize user-defined search campaigns.

    A campaign only overrides discovery/scoring fields.  Identity, availability,
    safety rules and browser settings remain global candidate settings.
    """
    out: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return out
    seen: set[str] = set()
    for idx, row in enumerate(rows[:50]):
        if not isinstance(row, dict):
            continue
        key = str(row.get('id') or row.get('slug') or f'profile-{idx+1}').strip()[:80]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({
            'id': key,
            'label': str(row.get('label') or key).strip()[:120],
            'enabled': row.get('enabled', True) is not False,
            'roles': _clean_list(row.get('roles')),
            'locations': _clean_list(row.get('locations')),
            'contracts': _clean_list(row.get('contracts')),
            'industries': _clean_list(row.get('industries')),
            'include_terms': _clean_list(row.get('include_terms')),
            'exclude_terms': _clean_list(row.get('exclude_terms')),
            'sources': _clean_list(row.get('sources')),
            'jobspy_sites': _clean_list(row.get('jobspy_sites')),
            'results_wanted': _int(row.get('results_wanted'), 20, 1, 200),
            'hours_old': _int(row.get('hours_old'), 168, 0, 24 * 365),
            'country_indeed': str(row.get('country_indeed') or '').strip(),
            'resume_id': str(row.get('resume_id') or '').strip(),
        })
    return out


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [x.strip() for x in value.replace(',', '\n').splitlines()]
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for x in value:
        s = str(x or '').strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out[:100]


def _int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except Exception:
        return default
    return max(lo, min(hi, n))


def expand_runtime_profile(base: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one runtime profile per enabled campaign, or the base profile once.

    This follows the search-profile pattern used by mature job-search tools while
    preserving backwards compatibility for users who configure only the global
    target preferences.
    """
    rows = normalize_search_profiles(base.get('search_profiles', []))
    enabled = [x for x in rows if x.get('enabled', True)]
    if not enabled:
        x = deepcopy(base)
        x['search_profile_id'] = 'default'
        x['search_profile_label'] = 'Default'
        return [x]

    result: list[dict[str, Any]] = []
    for row in enabled:
        x = deepcopy(base)
        mapping = {
            'preferred_roles': 'roles',
            'locations': 'locations',
            'contracts': 'contracts',
            'industries': 'industries',
            'include_terms': 'include_terms',
            'exclude_terms': 'exclude_terms',
        }
        for target, source in mapping.items():
            if row.get(source):
                x[target] = list(row[source])
        if row.get('sources'):
            x['enabled_sources'] = list(row['sources'])
        if row.get('jobspy_sites'):
            x['jobspy_sites'] = list(row['jobspy_sites'])
        x['jobspy_results_wanted'] = row.get('results_wanted', x.get('jobspy_results_wanted', 20))
        x['jobspy_hours_old'] = row.get('hours_old', x.get('jobspy_hours_old', 168))
        if row.get('country_indeed'):
            x['jobspy_country_indeed'] = row['country_indeed']
        x['search_profile_id'] = row['id']
        x['search_profile_label'] = row['label']
        x['search_profile_resume_id'] = row.get('resume_id', '')
        result.append(x)
    return result
