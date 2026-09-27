from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from .agent_fallback import run_agent_loop
from .ats import detect_ats
from .ats_adapters import get_adapter
from .db import connect
from .form_scanner import instrument_and_scan
from .profile_store import load_profile_raw, runtime_profile, select_resume_for_job
from .review_launcher import launch_review

ROOT = Path(__file__).resolve().parent.parent


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _record(job_id: int, status: str, note: str = '') -> None:
    with connect() as c:
        c.execute('INSERT INTO applications(job_id,status,note) VALUES(?,?,?)', (job_id, status, note[:4000]))


def _update_status(job_id: int, status: str, **extra) -> None:
    allowed = {
        'apply_adapter', 'fill_audit_path', 'review_verdict', 'review_summary', 'ats',
        'agent_status', 'agent_steps', 'agent_trace_path',
    }
    sets = ['application_status=?', 'last_application_at=CURRENT_TIMESTAMP', 'updated_at=CURRENT_TIMESTAMP']
    args: list[object] = [status]
    for key, value in extra.items():
        if key in allowed:
            sets.append(f'{key}=?')
            args.append(value)
    tracker = 'prepared' if status in {'prefilled','needs_human'} else ('submitted' if status in {'submitted','submitted_verified'} else '')
    if tracker:
        sets.append('tracker_stage=?')
        args.append(tracker)
    args.append(job_id)
    with connect() as c:
        c.execute(f'UPDATE jobs SET {", ".join(sets)} WHERE id=?', tuple(args))
        if tracker:
            c.execute('INSERT INTO application_stage_events(job_id,stage,note) VALUES(?,?,?)', (job_id, tracker, f'Automation status: {status}'))


def _open_browser(p, profile: dict):
    mode = profile.get('browser_mode', 'cdp')
    if mode == 'cdp':
        browser = p.chromium.connect_over_cdp(profile.get('chrome_cdp_endpoint', 'http://127.0.0.1:9222'))
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        return browser, context, mode
    context = p.chromium.launch_persistent_context(
        str(ROOT / 'data' / 'browser-profile'),
        headless=False,
        viewport=None,
        args=['--start-maximized'],
    )
    return None, context, mode


def _required(snapshot: dict) -> tuple[list[dict], list[dict], list[dict]]:
    unanswered = [f for f in snapshot.get('fields', []) if f.get('required') and not f.get('answered')]
    sensitive = [f for f in unanswered if f.get('sensitive_or_legal') or f.get('captcha_or_mfa')]
    ordinary = [f for f in unanswered if not (f.get('sensitive_or_legal') or f.get('captcha_or_mfa'))]
    return unanswered, sensitive, ordinary


def main(job_id: int):
    raw_profile = load_profile_raw()
    profile = runtime_profile(raw_profile)
    with connect() as c:
        row = c.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise ValueError('job not found')
        job = dict(row)

    resume_path, resume_meta = select_resume_for_job(job, raw_profile)
    profile['resume_path'] = str(resume_path) if resume_path else ''
    _update_status(job_id, 'opening')
    _record(job_id, 'opening', f"URL: {job.get('url','')}")

    with sync_playwright() as p:
        browser, context, mode = _open_browser(p, profile)
        page = context.new_page()
        try:
            page.goto(job['url'], wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(1000)
            try:
                html = page.content()
            except Exception:
                html = ''
            ats = detect_ats(page.url, html) or job.get('ats') or 'generic'
            adapter = get_adapter(ats)
            _update_status(job_id, 'preparing', apply_adapter=adapter.info.key, ats=ats)

            adapter.prepare(page)
            page.wait_for_timeout(900)
            report = adapter.fill(page, profile, resume_path, job)
            report['deterministic_passes'] = 1
            snapshot = instrument_and_scan(page)
            unanswered, sensitive_unanswered, ordinary_unanswered = _required(snapshot)

            # Mature ATS fillers benefit from a second scan/fill pass because
            # answering one field can reveal another React/conditional field.
            # This pass is still deterministic and retains all sensitive/legal
            # guards; the agent only runs afterwards if needed.
            if ordinary_unanswered:
                page.wait_for_timeout(800)
                second = adapter.fill(page, profile, resume_path, job)
                if second.get('filled') or second.get('actions'):
                    for key in ('filled','actions','skipped_sensitive','skipped_ambiguous','errors'):
                        report.setdefault(key, []).extend(second.get(key, []))
                    report['filled'] = list(dict.fromkeys(report.get('filled', [])))
                    report['deterministic_passes'] = 2
                snapshot = instrument_and_scan(page)
                unanswered, sensitive_unanswered, ordinary_unanswered = _required(snapshot)

            agent_trace = None
            agent_cfg = profile.get('agent_fallback', {}) or {}
            reviewer_cfg = profile.get('chatgpt_web_reviewer', {}) or {}
            should_agent = bool(agent_cfg.get('enabled', True) and reviewer_cfg.get('enabled', True)) and (
                (adapter.info.mode == 'agent-assisted' and agent_cfg.get('run_for_agent_assisted_ats', True))
                or (ordinary_unanswered and agent_cfg.get('run_when_required_unanswered', True))
            )

            if should_agent and not sensitive_unanswered:
                try:
                    _update_status(job_id, 'preparing', agent_status='RUNNING')
                    _record(job_id, 'agent_running', f'ATS={ats}; required_unanswered={len(unanswered)}')
                    agent_trace = run_agent_loop(
                        page,
                        context=context,
                        job_id=job_id,
                        job=job,
                        profile=profile,
                        resume_path=resume_path,
                        ats=ats,
                        chat_cfg=reviewer_cfg,
                        agent_cfg=agent_cfg,
                    )
                    snapshot = instrument_and_scan(page)
                    unanswered, sensitive_unanswered, ordinary_unanswered = _required(snapshot)
                    _update_status(
                        job_id,
                        'preparing',
                        agent_status=agent_trace.get('result', ''),
                        agent_steps=len(agent_trace.get('steps', [])),
                        agent_trace_path=agent_trace.get('trace_path', ''),
                    )
                    _record(job_id, 'agent_' + str(agent_trace.get('result', '')).lower(), agent_trace.get('reason', ''))
                except Exception as exc:
                    agent_trace = {'result': 'ERROR', 'reason': str(exc), 'steps': []}
                    _update_status(job_id, 'preparing', agent_status='ERROR')
                    _record(job_id, 'agent_error', str(exc))

            now = datetime.now(timezone.utc).isoformat()
            audit = {
                'job_id': job_id,
                'url': job.get('url', ''),
                'page_url_after_prepare': page.url,
                'ats_detected': ats,
                'adapter': adapter.info.__dict__,
                'resume': {
                    'id': (resume_meta or {}).get('id', ''),
                    'label': (resume_meta or {}).get('label', ''),
                    'auto_routed': bool(raw_profile.get('application', {}).get('auto_resume_routing', False)),
                },
                'report': report,
                'agent': {
                    'enabled': bool(agent_cfg.get('enabled', True)),
                    'triggered': should_agent,
                    'result': (agent_trace or {}).get('result', ''),
                    'reason': (agent_trace or {}).get('reason', ''),
                    'steps': len((agent_trace or {}).get('steps', [])),
                    'trace_path': (agent_trace or {}).get('trace_path', ''),
                },
                'required_unanswered_count': len(unanswered),
                'sensitive_or_legal_unanswered_count': len(sensitive_unanswered),
                'captured_at': now,
                'final_submit_performed_by_script': False,
            }
            audit_dir = ROOT / 'data' / 'application_audits'
            snap_dir = ROOT / 'data' / 'form_snapshots'
            audit_path = audit_dir / f'job_{job_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            snap_path = snap_dir / f'job_{job_id}.json'
            _write_json(audit_path, audit)
            _write_json(snap_path, snapshot)

            needs_human = bool(sensitive_unanswered or (agent_trace and agent_trace.get('result') in {'HANDOFF', 'ERROR'} and unanswered))
            status = 'needs_human' if needs_human else 'prefilled'
            summary = (
                f'{adapter.info.label}: {len(report.get("filled", []))} deterministic field(s) filled; '
                f'agent={(agent_trace or {}).get("result", "not-run")}; '
                f'{len(unanswered)} required unanswered; '
                f'{len(sensitive_unanswered)} sensitive/legal required unanswered'
            )
            _update_status(
                job_id,
                status,
                apply_adapter=adapter.info.key,
                fill_audit_path=str(audit_path),
                review_verdict='QUEUED',
                review_summary=summary,
            )
            _record(job_id, status, summary)

            if reviewer_cfg.get('enabled', True):
                launch_review(job_id, str(snap_path))
                print('\nApplication prepared. ChatGPT Web final review queued.')
            else:
                print('\nApplication prepared. ChatGPT Web reviewer disabled.')

            print(f'ATS adapter: {adapter.info.label} ({adapter.info.mode})')
            if agent_trace:
                print(f'Agent fallback: {agent_trace.get("result")} in {len(agent_trace.get("steps", []))} step(s).')
            if resume_meta:
                print(f'Resume: {resume_meta.get("label") or resume_meta.get("original_name")}')
            print(f'Deterministic auto-fill: {report.get("filled") or "none"}. Required unanswered: {len(unanswered)}.')
            print('Final submission remains manual. The agent is hard-blocked from clicking final Submit.')

            # Keep observing the tab. If the candidate manually submits and the ATS displays a
            # recognizable confirmation, record it automatically. Never click Submit here.
            verified = False
            try:
                while True:
                    time.sleep(2)
                    if page.is_closed():
                        break
                    ok, evidence = adapter.confirmation(page)
                    if ok:
                        verified = True
                        _update_status(job_id, 'submitted_verified')
                        _record(job_id, 'submitted_verified', evidence)
                        print('Submission confirmation detected:', evidence)
                        break
            except KeyboardInterrupt:
                pass

            if not verified:
                with connect() as c:
                    current = c.execute('SELECT application_status FROM jobs WHERE id=?', (job_id,)).fetchone()
                    if current and current['application_status'] in {'opening', 'preparing'}:
                        c.execute("UPDATE jobs SET application_status='prefilled', updated_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,))
        except Exception as exc:
            _update_status(job_id, 'error')
            _record(job_id, 'apply_error', str(exc))
            raise
        finally:
            if mode != 'cdp':
                try:
                    context.close()
                except Exception:
                    pass


if __name__ == '__main__':
    main(int(sys.argv[1]))
