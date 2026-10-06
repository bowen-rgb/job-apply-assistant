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
from .human_review import can_prepare
from .form_scanner import instrument_and_scan
from .profile_store import load_profile_raw, runtime_profile, select_resume_for_job
from .worker_runtime import check_cancelled, Cancelled
from .cover_letter import generate_letter, letter_paths, generation_error
from .application_form import (wait_for_form_scope, consent_pending, accept_confirmed_privacy,
                               requires_combined_packet, build_application_packet)

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
        'application_step', 'application_tab_id',
    }
    sets = ['application_status=?', 'last_application_at=CURRENT_TIMESTAMP', 'updated_at=CURRENT_TIMESTAMP']
    args: list[object] = [status]
    if 'application_step' in extra:
        sets.append('application_step_at=CURRENT_TIMESTAMP')
    for key, value in extra.items():
        if key in allowed:
            sets.append(f'{key}=?')
            args.append(value)
    tracker = 'prepared' if status in {'prefilled','needs_human'} else ('submitted' if status in {'submitted','submitted_verified'} else '')
    if status in {'error', 'cancelled'}:
        tracker = 'saved'
    if tracker:
        sets.append('tracker_stage=?')
        args.append(tracker)
    args.append(job_id)
    with connect() as c:
        # Human confirmation is authoritative, even if a cancelled worker
        # completes or fails late. Preserve the recruiter pipeline as well.
        changed = c.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id=? AND application_status NOT IN ('submitted','submitted_verified','withdrawn')", tuple(args)).rowcount
        if tracker and changed:
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


def main(job_id: int, *, privacy_confirmed: bool = False):
    raw_profile = load_profile_raw()
    profile = runtime_profile(raw_profile)
    with connect() as c:
        row = c.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise ValueError('job not found')
        job = dict(row)

    # Recheck in the worker as well: a new AI review may have started after
    # the HTTP handler/queue accepted the launch.
    if not can_prepare(job):
        _record(job_id, 'apply_error', 'Human confirmation required')
        _update_status(job_id, 'error')
        raise ValueError('Human confirmation required')

    resume_path, resume_meta = select_resume_for_job(job, raw_profile)
    profile['resume_path'] = str(resume_path) if resume_path else ''
    _update_status(job_id, 'opening', application_step='connecting', application_tab_id='', fill_audit_path='')
    _record(job_id, 'opening', f"URL: {job.get('url','')}")

    with sync_playwright() as p:
        page = None
        context = None
        mode = 'cdp'
        try:
            check_cancelled()
            if not resume_path or not resume_path.is_file():
                raise ValueError('Aucun CV sélectionné. Activez un CV avant le pré-remplissage.')
            browser, context, mode = _open_browser(p, profile)
            if raw_profile.get('application', {}).get('generate_cover_letter', True):
                _update_status(job_id, 'preparing_letter', application_step='letter')
                letter = generate_letter(context, job, raw_profile, resume_path, profile.get('chatgpt_web_reviewer', {}))
                profile['cover_letter_text'] = letter['letter']
                profile['cover_letter_path'] = str(letter_paths(job_id)[1])
            check_cancelled()
            # Resume the same job's open dialog after the user accepts its charter.
            original_url = job['url'].split('?')[0].rstrip('/')
            _update_status(job_id, 'opening', application_step='opening_form')
            page = next((tab for tab in reversed(context.pages)
                         if not tab.is_closed() and tab.url.split('?')[0].rstrip('/') == original_url), None)
            if page is None:
                page = context.new_page()
                try:
                    session = context.new_cdp_session(page)
                    target = session.send('Target.getTargetInfo')['targetInfo']['targetId']
                    session.detach()
                    _update_status(job_id, 'opening', application_tab_id=target)
                except Exception:
                    pass
                page.goto(job['url'], wait_until='domcontentloaded', timeout=45000)
            elif any('/oneClick/finalize' in frame.url for frame in page.frames):
                # A prior attempt imported only the CV. Start a fresh import so
                # the complete packet is uploaded before the final-submit step.
                page.reload(wait_until='domcontentloaded')
            try:
                session = context.new_cdp_session(page)
                target = session.send('Target.getTargetInfo')['targetInfo']['targetId']
                session.detach()
                _update_status(job_id, 'opening', application_tab_id=target)
            except Exception:
                pass
            page.wait_for_timeout(1000)
            try:
                html = page.content()
            except Exception:
                html = ''
            ats = detect_ats(page.url, html) or job.get('ats') or 'generic'
            adapter = get_adapter(ats)
            _update_status(job_id, 'preparing', application_step='finding_form', apply_adapter=adapter.info.key, ats=ats)

            adapter.prepare(page)
            form_scope = wait_for_form_scope(page)
            if form_scope is None and consent_pending(page) and privacy_confirmed:
                accept_confirmed_privacy(page)
                form_scope = wait_for_form_scope(page)
            if form_scope is None:
                if consent_pending(page):
                    _update_status(job_id, 'needs_human', application_step='privacy')
                    _record(job_id, 'privacy_consent_required', 'Le site demande votre accord à la charte de données personnelles. Acceptez-la dans la fenêtre de candidature, puis relancez le pré-remplissage.')
                    return
                raise ValueError('Le formulaire de candidature n’est pas encore accessible. Aucun document n’a été joint.')
            letter_error = ''
            check_cancelled()
            packet = None
            upload_path = resume_path
            if profile.get('cover_letter_path') and requires_combined_packet(form_scope):
                packet = build_application_packet(resume_path, Path(profile['cover_letter_path']),
                                                 ROOT / 'data' / 'application_packets' / f'job_{job_id}_cv_et_lettre.pdf')
                upload_path = Path(packet['path'])
            _update_status(job_id, 'preparing', application_step='filling')
            report = adapter.fill(form_scope, profile, upload_path, job)
            if packet and 'resume' in report.get('filled', []):
                report['filled'].append('cover_letter_file')
                report['actions'].append({'field': 'cover_letter_file', 'strategy': 'combined_cv_letter_pdf',
                                          'filename': upload_path.name, 'confidence': 100})
            # Some ATS portals import the CV first, then render the full form.
            if 'resume' in report.get('filled', []) and ('/consent' in form_scope.url or 'cover_letter_file' not in report.get('filled', [])):
                page.wait_for_timeout(2500)
                next_scope = wait_for_form_scope(page, timeout_seconds=45,
                                                exclude_url=form_scope.url if '/consent' in form_scope.url else None)
                if next_scope is not None:
                    form_scope = next_scope
                    second = adapter.fill(form_scope, profile, upload_path, job)
                    for key in ('filled', 'actions', 'skipped_sensitive', 'skipped_ambiguous', 'errors'):
                        report.setdefault(key, []).extend(second.get(key, []))
                    report['filled'] = list(dict.fromkeys(report.get('filled', [])))
            if letter_error:
                report['errors'].append('cover_letter: ' + letter_error)
            report['deterministic_passes'] = 1
            _update_status(job_id, 'preparing', application_step='checking')
            snapshot = instrument_and_scan(form_scope)
            unanswered, sensitive_unanswered, ordinary_unanswered = _required(snapshot)

            # Mature ATS fillers benefit from a second scan/fill pass because
            # answering one field can reveal another React/conditional field.
            # This pass is still deterministic and retains all sensitive/legal
            # guards; the agent only runs afterwards if needed.
            if ordinary_unanswered:
                page.wait_for_timeout(800)
                second = adapter.fill(form_scope, profile, upload_path, job)
                if second.get('filled') or second.get('actions'):
                    for key in ('filled','actions','skipped_sensitive','skipped_ambiguous','errors'):
                        report.setdefault(key, []).extend(second.get(key, []))
                    report['filled'] = list(dict.fromkeys(report.get('filled', [])))
                    report['deterministic_passes'] = 2
                snapshot = instrument_and_scan(form_scope)
                unanswered, sensitive_unanswered, ordinary_unanswered = _required(snapshot)

            agent_trace = None
            agent_cfg = profile.get('agent_fallback', {}) or {}
            reviewer_cfg = profile.get('chatgpt_web_reviewer', {}) or {}
            should_agent = bool(raw_profile.get('application', {}).get('assisted_form_navigation', False)
                                and agent_cfg.get('enabled', False) and reviewer_cfg.get('enabled', True)) and (
                (adapter.info.mode == 'agent-assisted' and agent_cfg.get('run_for_agent_assisted_ats', True))
                or (ordinary_unanswered and agent_cfg.get('run_when_required_unanswered', True))
            )

            if should_agent and not sensitive_unanswered:
                try:
                    _update_status(job_id, 'preparing', application_step='assisted', agent_status='RUNNING')
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

            check_cancelled()
            now = datetime.now(timezone.utc).isoformat()
            audit = {
                'job_id': job_id,
                'url': job.get('url', ''),
                'page_url_after_prepare': page.url,
                'form_url': form_scope.url,
                'ats_detected': ats,
                'adapter': adapter.info.__dict__,
                'resume': {
                    'id': (resume_meta or {}).get('id', ''),
                    'label': (resume_meta or {}).get('label', ''),
                    'auto_routed': bool(raw_profile.get('application', {}).get('auto_resume_routing', False)),
                },
                'report': report,
                'documents': {
                    'resume_available': bool(resume_path and resume_path.is_file()),
                    'resume_attached': 'resume' in report.get('filled', []),
                    'letter_generated': bool(profile.get('cover_letter_text')),
                    'letter_attached': 'cover_letter_file' in report.get('filled', []),
                    'letter_text_filled': 'cover_letter_text' in report.get('filled', []),
                    'letter_error': letter_error,
                    'attachment_mode': 'combined_pdf' if packet else 'separate_documents',
                    'application_packet': packet,
                },
                'agent': {
                    'enabled': bool(agent_cfg.get('enabled', True)),
                    'triggered': should_agent,
                    'result': (agent_trace or {}).get('result', ''),
                    'reason': (agent_trace or {}).get('reason', ''),
                    'steps': len((agent_trace or {}).get('steps', [])),
                    'trace_path': (agent_trace or {}).get('trace_path', ''),
                },
                'required_unanswered_count': len(unanswered),
                'required_unanswered_labels': [f.get('label') or f.get('name') or f.get('type', '') for f in unanswered],
                'sensitive_or_legal_unanswered_count': len(sensitive_unanswered),
                'captured_at': now,
                'final_submit_performed_by_script': False,
            }
            audit_dir = ROOT / 'data' / 'application_audits'
            snap_dir = ROOT / 'data' / 'form_snapshots'
            audit_path = audit_dir / f'job_{job_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            snap_path = snap_dir / f'job_{job_id}.json'
            _write_json(audit_path, audit)
            if not audit['documents']['letter_attached']:
                try:
                    (audit_dir / f'job_{job_id}_form.html').write_text(form_scope.content(), encoding='utf-8')
                except Exception:
                    pass
            _write_json(snap_path, snapshot)

            letter_missing = bool(profile.get('cover_letter_path') and not {'cover_letter_file', 'cover_letter_text'}.intersection(report.get('filled', [])))
            needs_human = bool(unanswered or letter_error or letter_missing or not resume_path or 'resume' not in report.get('filled', []) or (agent_trace and agent_trace.get('result') in {'HANDOFF', 'ERROR'}))
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
                application_step='handoff',
                apply_adapter=adapter.info.key,
                fill_audit_path=str(audit_path),

            )
            _record(job_id, status, summary)

            check_cancelled()
            print('Application prepared. Review is optional and explicitly requested.')

            print(f'ATS adapter: {adapter.info.label} ({adapter.info.mode})')
            if agent_trace:
                print(f'Agent fallback: {agent_trace.get("result")} in {len(agent_trace.get("steps", []))} step(s).')
            if resume_meta:
                print(f'Resume: {resume_meta.get("label") or resume_meta.get("original_name")}')
            print(f'Deterministic auto-fill: {report.get("filled") or "none"}. Required unanswered: {len(unanswered)}.')
            print('Final submission remains manual. The agent is hard-blocked from clicking final Submit.')

            # CDP application tab remains open for manual review and submission.
        except Cancelled:
            if mode != 'cdp' and page is not None and not page.is_closed():
                page.close()
            _update_status(job_id, 'cancelled')
            _record(job_id, 'cancelled', 'Stopped by user')
        except Exception as exc:
            _update_status(job_id, 'error')
            _record(job_id, 'apply_error', generation_error(exc))
            raise
        finally:
            if context is not None and mode != 'cdp':
                try:
                    context.close()
                except Exception:
                    pass


if __name__ == '__main__':
    main(int(sys.argv[1]), privacy_confirmed='--privacy-confirmed' in sys.argv[2:])
