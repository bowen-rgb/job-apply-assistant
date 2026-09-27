from __future__ import annotations

"""Cross-source job identity and source-variant helpers.

Design inspired by QuickApply's MIT-licensed ``app/job_dedupe.py``.  The
implementation here is adapted for this project's SQLite schema and supports
configurable dedupe scope instead of forcing one global policy.
"""

import hashlib
import json
import re
import unicodedata
from typing import Any


def normalize_identity_text(value: Any) -> str:
    text = unicodedata.normalize('NFKC', str(value or '')).lower()
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _location_bucket(value: str) -> str:
    """Return a stable, deliberately coarse location bucket.

    Job boards frequently disagree on punctuation/postal details.  Keeping the
    first comma-separated components preserves city/region distinctions without
    making tiny address differences defeat deduplication.
    """
    text = normalize_identity_text(value)
    if not text:
        return ''
    parts = [x.strip() for x in text.split(',') if x.strip()]
    return '|'.join(parts[:2]) if parts else text


def build_job_dedupe_key(*, title: str, company: str, location: str = '', scope: str = 'title_company_location') -> str:
    title_n = normalize_identity_text(title)
    company_n = normalize_identity_text(company)
    if not title_n:
        return ''
    if not company_n:
        # Search snippets often omit company.  Do not merge all same-title jobs.
        return ''
    parts = [title_n, company_n]
    if scope != 'title_company':
        parts.append(_location_bucket(location))
    stable = '|'.join(parts)
    return hashlib.sha1(stable.encode('utf-8', errors='ignore')).hexdigest()


SOURCE_PRIORITY = {
    'greenhouse_board': 0,
    'ashby_board': 0,
    'lever_board': 0,
    'company': 1,
    'france_travail': 2,
    'hellowork': 3,
    'wttj': 3,
    'plany': 3,
    'cityone': 3,
    'indeed': 5,
    'linkedin': 6,
    'glassdoor': 7,
    'jobspy_indeed': 8,
    'jobspy_linkedin': 9,
    'jobspy_glassdoor': 10,
    'jobspy_google': 11,
    'global': 50,
}


def source_priority(provider_key: str) -> int:
    return SOURCE_PRIORITY.get(normalize_identity_text(provider_key).replace(' ', '_'), 20)


def make_source_variant(provider_key: str, source: str, url: str, query: str = '') -> dict[str, str]:
    return {
        'provider_key': str(provider_key or '').strip(),
        'source': str(source or '').strip(),
        'url': str(url or '').strip(),
        'query': str(query or '').strip(),
    }


def load_variants(raw: str | None) -> list[dict[str, str]]:
    try:
        data = json.loads(raw or '[]')
    except Exception:
        data = []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    if isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                continue
            v = make_source_variant(row.get('provider_key', ''), row.get('source', ''), row.get('url', ''), row.get('query', ''))
            key = (v['provider_key'].lower(), v['url'])
            if not v['url'] or key in seen:
                continue
            seen.add(key)
            out.append(v)
    return sorted(out, key=lambda x: (source_priority(x['provider_key']), x['provider_key'], x['url']))


def merge_variants(raw: str | None, *variants: dict[str, Any]) -> str:
    rows = load_variants(raw)
    rows.extend(make_source_variant(v.get('provider_key', ''), v.get('source', ''), v.get('url', ''), v.get('query', '')) for v in variants)
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for v in rows:
        key = (v['provider_key'].lower(), v['url'])
        if not v['url'] or key in seen:
            continue
        seen.add(key)
        out.append(v)
    out.sort(key=lambda x: (source_priority(x['provider_key']), x['provider_key'], x['url']))
    return json.dumps(out, ensure_ascii=False)


def pick_primary_variant(raw: str | None, fallback: dict[str, Any] | None = None) -> dict[str, str]:
    rows = load_variants(raw)
    if fallback:
        rows = load_variants(merge_variants(json.dumps(rows), fallback))
    return rows[0] if rows else make_source_variant('', '', '', '')
