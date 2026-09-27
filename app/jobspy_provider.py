from __future__ import annotations

"""Optional JobSpy-backed discovery provider.

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


RUNNER = r'''
import json, sys
from jobspy import scrape_jobs
p = json.loads(sys.argv[1])
frame = scrape_jobs(
    site_name=p["sites"],
    search_term=p["search_term"],
    google_search_term=p.get("google_search_term") or None,
    location=p["location"],
    results_wanted=p["results_wanted"],
    hours_old=p.get("hours_old") or None,
    country_indeed=p.get("country_indeed") or "worldwide",
    linkedin_fetch_description=bool(p.get("linkedin_fetch_description", False)),
    verbose=0,
)
rows = [] if frame is None else frame.to_dict(orient="records")
json.dump(rows, sys.stdout, default=str)
'''


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
    try:
        import importlib.util
        return importlib.util.find_spec('jobspy') is not None
    except Exception:
        return False


def _text(v: Any) -> str:
    if v is None:
        return ''
    s = str(v).strip()
    return '' if s.lower() == 'nan' else s


def _invoke(payload: dict[str, Any], timeout: int) -> list[dict[str, Any]]:
    p = subprocess.run(
        [sys.executable, '-c', RUNNER, json.dumps(payload, ensure_ascii=False)],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or '').strip()[-1200:] or 'JobSpy subprocess failed')
    if not p.stdout.strip():
        return []
    return json.loads(p.stdout)


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


def discover(profile: dict[str, Any]) -> Iterable[JobSpyResult]:
    if not profile.get('jobspy_enabled', False) or not available():
        return
    sites = [str(x).strip().lower() for x in profile.get('jobspy_sites', []) if str(x).strip()]
    if not sites:
        sites = ['indeed', 'linkedin', 'google']
    roles = [str(x).strip() for x in profile.get('preferred_roles', []) if str(x).strip()]
    locations = [str(x).strip() for x in profile.get('locations', []) if str(x).strip()] or ['']
    if not roles:
        return
    results_wanted = max(1, min(200, int(profile.get('jobspy_results_wanted', 20))))
    hours_old = max(0, int(profile.get('jobspy_hours_old', 168) or 0))
    country = str(profile.get('jobspy_country_indeed') or profile.get('country') or 'worldwide').strip()
    timeout = max(30, min(240, int(profile.get('jobspy_timeout_seconds', 90))))
    linkedin_desc = bool(profile.get('jobspy_linkedin_fetch_description', False))

    for role in roles[:8]:
        for location in locations[:5]:
            payload = {
                'sites': sites,
                'search_term': role,
                'google_search_term': f'{role} jobs {location}'.strip(),
                'location': location,
                'results_wanted': results_wanted,
                'hours_old': hours_old,
                'country_indeed': country,
                'linkedin_fetch_description': linkedin_desc,
            }
            try:
                rows = _run_retry(payload, timeout)
            except Exception:
                continue
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
