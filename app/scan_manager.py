from __future__ import annotations

import json
from copy import deepcopy
import threading
from contextvars import copy_context
import time
from datetime import datetime, timezone
from typing import Any

from .ats import detect_ats
from .db import connect
from .extractor import extract_job_document
from .job_identity import build_job_dedupe_key, merge_variants, pick_primary_variant, source_priority
from .scoring import evaluate
from .search_profiles import expand_runtime_profile
from .searcher import discover, fetch_html

_lock = threading.Lock()
_state: dict[str, Any] = {
    'running': False,
    'scan_id': None,
    'found': 0,
    'fetched': 0,
    'inserted': 0,
    'updated': 0,
    'errors': 0,
    'campaigns': 0,
    'current_campaign': '',
    'current_source': '',
    'current_title': '',
    'started_at': '',
    'finished_at': '',
    'message': '',
    'source_diagnostics': [],
}


def _set(**kwargs):
    with _lock:
        _state.update(kwargs)


def status() -> dict[str, Any]:
    with _lock:
        state = deepcopy(_state)
    if state['scan_id'] is None:
        with connect() as c:
            last = c.execute('SELECT * FROM scans ORDER BY id DESC LIMIT 1').fetchone()
        if last:
            state.update(scan_id=last['id'], **{key: last[key] for key in ('found', 'fetched', 'inserted', 'updated', 'errors', 'started_at', 'finished_at')})
            state['message'] = 'Previous scan interrupted' if last['status'] == 'running' else last['note']
            try:
                state['source_diagnostics'] = json.loads(last['diagnostics_json'] or '[]')
            except ValueError:
                pass
    return state


def _source_event(campaign, source, method, state, **details):
    with _lock:
        rows = _state['source_diagnostics']
        if method.startswith('web:'):
            rows[:] = [x for x in rows if not (x['campaign'] == campaign and x['source'] == source and x['method'] == 'web' and x['state'] == 'pending')]
        row = next((x for x in rows if (x['campaign'], x['source'], x['method']) == (campaign, source, method)), None)
        if row is None:
            row = dict(campaign=campaign, source=source, method=method, attempts=0, results=0, errors=0, state=state, last_error='')
            rows.append(row)
        if state in {'success', 'empty', 'failed', 'unavailable'}:
            row['attempts'] += 1
        row['results'] += details.get('results', 0)
        if state in {'failed', 'unavailable'}:
            row['errors'] += 1
            _state['errors'] += 1
            row['last_error'] = details.get('error', '')[:300]
        row['state'] = state if state == 'suspended' else 'partial' if row['results'] and row['errors'] else 'success' if row['results'] and state != 'running' else state
        if 'query' in details:
            row['last_query'] = details['query'][:500]
        if state == 'running':
            _state.update(current_source=source, message=f'Discovery · {campaign} · {method}')


def _insert_scan() -> int:
    with connect() as c:
        cur = c.execute("INSERT INTO scans(status,note) VALUES('running','')")
        return int(cur.lastrowid)


def _finish_scan(scan_id: int, state: dict[str, Any]):
    with connect() as c:
        c.execute(
            '''UPDATE scans SET status=?,found=?,fetched=?,inserted=?,updated=?,errors=?,note=?,diagnostics_json=?,finished_at=CURRENT_TIMESTAMP WHERE id=?''',
            ('done', state['found'], state['fetched'], state['inserted'], state['updated'], state['errors'], state.get('message',''), json.dumps(state['source_diagnostics'], ensure_ascii=False), scan_id),
        )


def _coalesce(primary: Any, fallback: Any) -> Any:
    if primary is None:
        return fallback
    if isinstance(primary, str) and not primary.strip():
        return fallback
    return primary


def _upsert_hit(hit, profile: dict, report=None) -> tuple[str, int | None]:
    """Fetch, normalize and cross-source-deduplicate one discovered job.

    Search snippets and JobSpy structured results are retained when a protected
    destination page cannot be fetched.  A later signed-in browser session can
    verify the page without losing the discovery event.
    """
    pre = dict(hit.prefetched or {})
    fetch_error = ''
    html = ''
    try:
        html, fetch_mode = fetch_html(hit.url, dynamic_fallback=bool(profile.get('dynamic_fetch_fallback', True)))
        if fetch_mode == 'static-blocked':
            raise RuntimeError('Job page blocked or unreadable')
        doc = extract_job_document(html, hit.url, fallback_title=hit.title, fallback_snippet=hit.snippet)
        payload = doc.to_dict()
        ats = detect_ats(hit.url, html)
        canonical_url = doc.canonical_url or hit.url
        fingerprint = doc.fingerprint
        title = _coalesce(doc.title, pre.get('title'))
        company = _coalesce(doc.company, pre.get('company'))
        location = _coalesce(doc.location, pre.get('location'))
        body = _coalesce(doc.text or doc.description, pre.get('body') or pre.get('description'))
        employment_type = _coalesce(doc.employment_type, pre.get('employment_type'))
        start_date = _coalesce(doc.start_date, pre.get('start_date'))
        end_date = _coalesce(doc.end_date, pre.get('end_date'))
        date_posted = _coalesce(doc.date_posted, pre.get('date_posted'))
        valid_through = _coalesce(doc.valid_through, pre.get('valid_through'))
        salary = _coalesce(doc.salary, pre.get('salary'))
        structured_json = doc.structured_json or pre.get('structured_json', '')
        payload.update({
            'title': title, 'company': company, 'location': location,
            'text': body, 'description': body, 'employment_type': employment_type,
            'start_date': start_date, 'end_date': end_date, 'date_posted': date_posted,
            'valid_through': valid_through, 'salary': salary,
        })
    except Exception as exc:
        fetch_error = str(exc)[:500]
        fetch_mode = str(pre.get('fetch_mode') or ('jobspy' if pre else 'search-snippet'))
        ats = detect_ats(hit.url, '')
        canonical_url = hit.url
        fingerprint = ''
        title = pre.get('title') or hit.title or 'Unverified job result'
        company = pre.get('company', '')
        location = pre.get('location', '')
        body = pre.get('body') or pre.get('description') or '\n'.join(x for x in [hit.title, hit.snippet] if x)
        employment_type = pre.get('employment_type', '')
        start_date = pre.get('start_date', '')
        end_date = pre.get('end_date', '')
        date_posted = pre.get('date_posted', '')
        valid_through = pre.get('valid_through', '')
        salary = pre.get('salary', '')
        structured_json = pre.get('structured_json', '')
        payload = {
            'title': title, 'company': company, 'location': location,
            'text': body, 'description': body, 'employment_type': employment_type,
            'start_date': start_date, 'end_date': end_date, 'date_posted': date_posted,
            'valid_through': valid_through, 'salary': salary, 'snippet': hit.snippet,
        }

    score, decision, reason, _flags = evaluate(payload, profile)
    if report:
        report(hit.provider_key, 'detail', 'failed' if fetch_error else 'success',
               results=0 if fetch_error else 1, error=fetch_error)
    if fetch_error:
        marker = 'unverified_prefetched' if pre else 'unverified_search_snippet'
        reason = (reason + '; ' if reason else '') + marker
    availability = 'expired' if decision == 'expired' else 'unknown'
    scope = str(profile.get('dedupe_scope') or 'title_company_location')
    dedupe_key = build_job_dedupe_key(title=title, company=company, location=location, scope=scope)
    campaign_id = str(profile.get('search_profile_id') or 'default')
    campaign_label = str(profile.get('search_profile_label') or 'Default')
    variant = {'provider_key': hit.provider_key, 'source': hit.source, 'url': hit.url, 'query': hit.query}

    with connect() as c:
        existing = None
        if canonical_url:
            existing = c.execute('SELECT * FROM jobs WHERE canonical_url=? LIMIT 1', (canonical_url,)).fetchone()
        if not existing:
            existing = c.execute('SELECT * FROM jobs WHERE url=? LIMIT 1', (hit.url,)).fetchone()
        if not existing and fingerprint:
            existing = c.execute("SELECT * FROM jobs WHERE fingerprint=? AND fingerprint<>'' LIMIT 1", (fingerprint,)).fetchone()
        if not existing and dedupe_key:
            existing = c.execute("SELECT * FROM jobs WHERE dedupe_key=? AND dedupe_key<>'' LIMIT 1", (dedupe_key,)).fetchone()

        if existing:
            old = dict(existing)
            variants_json = merge_variants(old.get('source_variants_json', '[]'), variant)
            primary = pick_primary_variant(variants_json, {
                'provider_key': old.get('provider_key', ''), 'source': old.get('source', ''),
                'url': old.get('url', ''), 'query': '',
            })
            # Prefer higher-quality source URL while never discarding alternates.
            new_is_primary = source_priority(hit.provider_key) <= source_priority(old.get('provider_key', ''))
            primary_url = hit.url if new_is_primary else old.get('url', hit.url)
            primary_provider = hit.provider_key if new_is_primary else old.get('provider_key', hit.provider_key)
            primary_source = hit.source if new_is_primary else old.get('source', hit.source)
            if primary.get('url') and source_priority(primary.get('provider_key', '')) < source_priority(primary_provider):
                primary_url, primary_provider, primary_source = primary['url'], primary['provider_key'], primary['source']

            # Keep the richer text/metadata instead of replacing a verified page with a thin snippet.
            body_value = body if not fetch_error or len(str(body or '')) >= len(str(old.get('body') or '')) else old.get('body', '')
            title_value = title or old.get('title', '')
            company_value = company or old.get('company', '')
            location_value = location or old.get('location', '')
            merged_payload = dict(payload, title=title_value, company=company_value, location=location_value,
                                  text=body_value, body=body_value,
                                  employment_type=employment_type or old.get('employment_type', ''),
                                  start_date=start_date or old.get('start_date', ''), end_date=end_date or old.get('end_date', ''),
                                  date_posted=date_posted or old.get('date_posted', ''), valid_through=valid_through or old.get('valid_through', ''),
                                  salary=salary or old.get('salary', ''), structured_json=structured_json or old.get('structured_json', ''))
            score, decision, reason, _flags = evaluate(merged_payload, profile)
            if fetch_error:
                reason += '; unverified_prefetched' if pre else '; unverified_search_snippet'
            availability = 'expired' if decision == 'expired' else 'unknown'
            c.execute(
                """UPDATE jobs SET
                   url=?, canonical_url=?, fingerprint=?, dedupe_key=?, source_variants_json=?,
                   search_profile_id=CASE WHEN search_profile_id='' THEN ? ELSE search_profile_id END,
                   search_profile_label=CASE WHEN search_profile_label='' THEN ? ELSE search_profile_label END,
                   title=?, company=?, location=?, source=?, provider_key=?, ats=?, snippet=?, body=?,
                   employment_type=?, start_date=?, end_date=?, date_posted=?, valid_through=?, salary=?,
                   structured_json=?, fetch_mode=?, availability_status=?, decision=?, score=?, reason=?,
                   last_seen_at=CURRENT_TIMESTAMP,last_checked_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (
                    primary_url, canonical_url or old.get('canonical_url',''), fingerprint or old.get('fingerprint',''),
                    dedupe_key or old.get('dedupe_key',''), variants_json, campaign_id, campaign_label,
                    title_value, company_value, location_value, primary_source, primary_provider, ats or old.get('ats',''),
                    (hit.snippet or old.get('snippet',''))[:2500], body_value,
                    employment_type or old.get('employment_type',''), start_date or old.get('start_date',''),
                    end_date or old.get('end_date',''), date_posted or old.get('date_posted',''),
                    valid_through or old.get('valid_through',''), salary or old.get('salary',''),
                    structured_json or old.get('structured_json',''), fetch_mode, availability, decision, score, reason,
                    existing['id'],
                ),
            )
            return 'updated', int(existing['id'])

        variants_json = merge_variants('[]', variant)
        cur = c.execute(
            """INSERT INTO jobs(
               url,canonical_url,fingerprint,dedupe_key,source_variants_json,search_profile_id,search_profile_label,
               title,company,location,source,provider_key,ats,snippet,body,employment_type,start_date,end_date,
               date_posted,valid_through,salary,structured_json,fetch_mode,availability_status,decision,score,reason)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                hit.url, canonical_url, fingerprint, dedupe_key, variants_json, campaign_id, campaign_label,
                title, company, location, hit.source, hit.provider_key, ats, hit.snippet[:2500], body,
                employment_type, start_date, end_date, date_posted, valid_through, salary, structured_json,
                fetch_mode, availability, decision, score, reason,
            ),
        )
        return 'inserted', int(cur.lastrowid)


def _worker(base_profile: dict, scan_id: int):
    try:
        campaigns = expand_runtime_profile(base_profile)
        _set(campaigns=len(campaigns))
        for campaign in campaigns:
            label = campaign.get('search_profile_label', 'Default')
            _set(current_campaign=label, message=f'Scanning campaign: {label}')
            report = lambda source, method, state, **details: _source_event(label, source, method, state, **details)
            for hit in discover(campaign, report=report):
                s = status()
                _set(
                    found=s['found'] + 1,
                    current_source=hit.provider_key or hit.source,
                    current_title=(hit.title or '')[:180],
                    message=f'Fetching · {label}',
                )
                try:
                    action, _ = _upsert_hit(hit, campaign, report=report)
                    s = status()
                    _set(
                        fetched=s['fetched'] + 1,
                        inserted=s['inserted'] + (1 if action == 'inserted' else 0),
                        updated=s['updated'] + (1 if action == 'updated' else 0),
                        message=f'Scanning · {label}',
                    )
                except Exception as exc:
                    s = status()
                    _set(errors=s['errors'] + 1, message=f'Fetch error: {str(exc)[:180]}')
                time.sleep(float(campaign.get('scan_delay_seconds', 0.25)))
    finally:
        finished = datetime.now(timezone.utc).isoformat()
        _set(running=False, finished_at=finished, current_source='', current_title='', current_campaign='', message='Scan finished')
        _finish_scan(scan_id, status())


def _start(profile: dict) -> dict[str, Any]:
    with _lock:
        if _state.get('running'):
            return dict(_state)
    scan_id = _insert_scan()
    _set(
        running=True, scan_id=scan_id, found=0, fetched=0, inserted=0, updated=0, errors=0,
        campaigns=0, current_campaign='', current_source='', current_title='',
        started_at=datetime.now(timezone.utc).isoformat(), finished_at='', message='Starting scan…',
        source_diagnostics=[],
    )
    threading.Thread(target=copy_context().run, args=(_worker, profile, scan_id), daemon=True, name=f'job-scan-{scan_id}').start()
    return status()


def start(*args, **kwargs):
    from .workspaces import LOCK, candidate_id, active_id
    with LOCK:
        if candidate_id() != active_id():
            raise ValueError("Candidate changed. Reload before continuing.")
        return _start(*args, **kwargs)
