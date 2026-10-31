from __future__ import annotations

"""Native job-board discovery using the reviewed MIT scraper source.

The subprocess isolation/retry pattern is adapted from QuickApply (MIT).  JobSpy
itself is MIT-licensed.  Keeping it in a subprocess prevents one scraper crash
or noisy logging stream from taking down the FastAPI process.
"""

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Iterable
from .discovery_diagnostics import emit


@dataclass
class JobSpyResult:
    url: str
    title: str
    snippet: str
    source: str
    provider_key: str
    query: str
    prefetched: dict[str, Any]


def available() -> bool:
    from importlib.util import find_spec
    return all(find_spec(name) is not None for name in ('requests','curl_cffi','bs4','markdownify'))


def supported_sites() -> set[str]:
    from .job_board_worker import SITES
    return set(SITES)


def _text(v: Any) -> str:
    if v is None:
        return ''
    s = str(v).strip()
    return '' if s.lower() == 'nan' else s


def _invoke(payload: dict[str, Any], timeout: int) -> list[dict[str, Any]]:
    p = subprocess.run(
        [sys.executable, '-m', 'app.job_board_worker', json.dumps(payload, ensure_ascii=False)],
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or '').strip()[-1200:] or 'JobSpy subprocess failed')
    if not p.stdout.strip():
        return []
    rows = json.loads(p.stdout)
    if not rows and any(word in (p.stderr or "").lower() for word in ("error", "429", "captcha", "blocked")):
        raise RuntimeError((p.stderr or "").strip()[-1200:])
    return rows


def _run_retry(payload: dict[str, Any], timeout: int) -> list[dict[str, Any]]:
    delays = (4, 12)
    last: Exception | None = None
    for idx in range(len(delays) + 1):
        try:
            return _invoke(payload, timeout)
        except Exception as exc:
            last = exc
            txt = str(exc).lower()
            retryable = isinstance(exc, subprocess.TimeoutExpired) or any(x in txt for x in ('timeout', 'connection', 'temporarily', '429', 'rate limit', 'remote disconnected'))
            if idx >= len(delays) or not retryable:
                raise
            time.sleep(delays[idx])
    if last:
        raise last
    return []


def discover(profile: dict[str, Any], report=None) -> Iterable[JobSpyResult]:
    if not profile.get('jobspy_enabled', False) or not available():
        return
    sites = [str(x).strip().lower() for x in profile.get('jobspy_sites', []) if str(x).strip()]
    if not sites:
        sites = ['indeed', 'linkedin', 'google']
    supported = supported_sites()
    for site in sites:
        if site not in supported:
            emit(report,'jobspy_'+site,'jobspy','unavailable',error='Native adapters do not support '+site)
    sites = [site for site in sites if site in supported]
    if not sites:return
    roles = [str(x).strip() for x in profile.get('preferred_roles', []) if str(x).strip()]
    locations = [str(x).strip() for x in profile.get('locations', []) if str(x).strip()] or ['']
    if (profile.get('pfe') or {}).get('enabled'):
        from .pfe import settings, DIRECTIONS
        cfg=settings(profile)
        roles=['stage '+DIRECTIONS[key][0] for key in (cfg['directions'] or list(DIRECTIONS))]
        locations=cfg['locations'] or ['France']
    if not roles:
        return
    results_wanted = max(1, min(200, int(profile.get('jobspy_results_wanted', 20))))
    hours_old = max(0, int(profile.get('jobspy_hours_old', 168) or 0))
    country = str(profile.get('jobspy_country_indeed') or profile.get('country') or 'worldwide').strip()
    timeout = max(30, min(240, int(profile.get('jobspy_timeout_seconds', 90))))
    linkedin_desc = bool(profile.get('jobspy_linkedin_fetch_description', False))
    failures = {site: 0 for site in sites}
    suspended = set()

    for role in roles[:12]:
        for location in locations[:5]:
            for requested_site in sites:
                if requested_site in suspended:
                    continue
                payload = {
                    'sites': [requested_site],
                    'job_type': 'internship' if (profile.get('pfe') or {}).get('enabled') else None,
                    'search_term': role,
                    'google_search_term': f'{role} jobs {location}'.strip(),
                    'location': location,
                    'results_wanted': results_wanted,
                    'hours_old': hours_old,
                    'country_indeed': country,
                    'linkedin_fetch_description': linkedin_desc,
                }
                emit(report, 'jobspy_' + requested_site, 'jobspy', 'running', query=f'{role} / {location}')
                try:
                    rows = _run_retry(payload, timeout)
                except Exception as exc:
                    failures[requested_site] += 1
                    emit(report, 'jobspy_' + requested_site, 'jobspy', 'failed', error=str(exc))
                    if failures[requested_site] >= 3:
                        suspended.add(requested_site)
                        emit(report, 'jobspy_' + requested_site, 'jobspy', 'suspended')
                    continue
                failures[requested_site] = 0
                emit(report, 'jobspy_' + requested_site, 'jobspy', 'success' if rows else 'empty', results=len(rows))
                for row in rows:
                    title = _text(row.get('title') or row.get('TITLE'))
                    company = _text(row.get('company') or row.get('company_name') or row.get('COMPANY'))
                    job_url = _text(row.get('job_url_direct') or row.get('job_url') or row.get('JOB_URL'))
                    if not title or not job_url:
                        continue
                    site = _text(row.get('site') or row.get('SITE')).lower() or 'unknown'
                    location_text = _text(row.get('location') or row.get('LOCATION'))
                    desc = _text(row.get('description') or row.get('DESCRIPTION'))
                    job_type = _text(row.get('job_type'))
                    salary_bits = [
                        _text(row.get('min_amount')),
                        _text(row.get('max_amount')),
                        _text(row.get('currency')),
                        _text(row.get('interval')),
                    ]
                    salary = ' '.join(x for x in salary_bits if x)
                    date_posted = _text(row.get('date_posted') or row.get('DATE_POSTED'))[:10]
                    prefetched = {
                        'title': title,
                        'company': company,
                        'location': location_text,
                        'body': desc,
                        'description': desc,
                        'employment_type': job_type,
                        'date_posted': date_posted,
                        'salary': salary,
                        'structured_json': '',
                        'fetch_mode': 'jobspy',
                    }
                    snippet = ' · '.join(x for x in [company, location_text, job_type] if x)
                    yield JobSpyResult(
                        url=job_url,
                        title=title,
                        snippet=snippet,
                        source=site,
                        provider_key=f'jobspy_{site}',
                        query=f'jobspy:{role}:{location}',
                        prefetched=prefetched,
                    )
