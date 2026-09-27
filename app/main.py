from __future__ import annotations

import json
import tempfile
import urllib.request
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel

from .db import init_db, connect
from .browser import launch_apply
from .review_launcher import launch_review
from .batch_review_launcher import launch_batch_review
from .scan_manager import start as start_scan, status as scan_status
from .queue_manager import enqueue as queue_enqueue, start as queue_start, status as queue_status, remove as queue_remove, clear_finished as queue_clear_finished
from .scheduler import start_scheduler, status as scheduler_status
from .jobspy_provider import available as jobspy_available
from .providers import SOURCES, all_sources
from .ats_adapters import adapter_catalog
from .learnings import stats as learning_stats
from .profile_store import (
    ROOT,
    load_profile_raw,
    save_profile_raw,
    runtime_profile,
    list_resumes,
    add_resume,
    activate_resume,
    delete_resume,
    active_resume_path,
    update_resume_metadata,
    replace_profile_raw,
)

STATIC = ROOT / 'static'

app = FastAPI(title='Job Apply Assistant V8')
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', '[::1]', 'testserver'])

@app.middleware('http')
async def local_security(request: Request, call_next):
    client = request.client.host if request.client else ''
    if client not in {'127.0.0.1', '::1', 'localhost', 'testclient'}:
        return JSONResponse({'detail': 'Local access only'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    return response

app.mount('/static', StaticFiles(directory=STATIC), name='static')


class Decision(BaseModel):
    decision: str


class ResumePatch(BaseModel):
    label: str | None = None
    tags: list[str] | None = None


class ApplicationStatus(BaseModel):
    status: str


class QueueRequest(BaseModel):
    job_ids: list[int]
    priority: int = 100


class TrackPatch(BaseModel):
    stage: str
    note: str = ''
    followup_at: str = ''


@app.on_event('startup')
def startup():
    init_db()
    load_profile_raw()
    start_scheduler()


@app.get('/')
def index():
    return FileResponse(STATIC / 'index.html')


@app.get('/api/profile')
def get_profile():
    return load_profile_raw()


@app.put('/api/profile')
def put_profile(payload: dict):
    try:
        p = save_profile_raw(payload)
        return {'ok': True, 'profile': p}
    except Exception as exc:
        raise HTTPException(400, f'Invalid profile: {exc}')


@app.get('/api/profile/export')
def export_profile():
    data = json.dumps(load_profile_raw(), ensure_ascii=False, indent=2).encode('utf-8')
    return Response(data, media_type='application/json', headers={'Content-Disposition': 'attachment; filename=job-apply-profile.json'})


@app.post('/api/profile/import')
async def import_profile(file: UploadFile = File(...)):
    try:
        raw = await file.read()
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('Profile file is too large')
        payload = json.loads(raw.decode('utf-8'))
        p = replace_profile_raw(payload)
        return {'ok': True, 'profile': p}
    except Exception as exc:
        raise HTTPException(400, f'Invalid profile import: {exc}')


@app.get('/api/resumes')
def resumes():
    return list_resumes()


@app.post('/api/resumes/upload')
async def upload_resume(file: UploadFile = File(...), label: str = Form('')):
    name = file.filename or 'resume.pdf'
    suffix = Path(name).suffix.lower()
    if suffix not in {'.pdf', '.doc', '.docx'}:
        raise HTTPException(400, 'Only PDF, DOC and DOCX are accepted')
    data = await file.read()
    if not data:
        raise HTTPException(400, 'Empty file')
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(400, 'Resume is larger than 20 MB')
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        row = add_resume(tmp_path, name, label)
        tmp_path.unlink(missing_ok=True)
        return {'ok': True, 'resume': row, 'resumes': list_resumes()}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    finally:
        try:
            tmp_path.unlink(missing_ok=True)  # type: ignore[name-defined]
        except Exception:
            pass


@app.post('/api/resumes/{resume_id}/activate')
def set_active_resume(resume_id: str):
    try:
        activate_resume(resume_id)
        return {'ok': True, 'resumes': list_resumes()}
    except KeyError:
        raise HTTPException(404, 'Resume not found')


@app.patch('/api/resumes/{resume_id}')
def patch_resume(resume_id: str, payload: ResumePatch):
    try:
        row = update_resume_metadata(resume_id, payload.label, payload.tags)
        return {'ok': True, 'resume': row, 'resumes': list_resumes()}
    except KeyError:
        raise HTTPException(404, 'Resume not found')


@app.delete('/api/resumes/{resume_id}')
def remove_resume(resume_id: str):
    try:
        delete_resume(resume_id)
        return {'ok': True, 'resumes': list_resumes()}
    except KeyError:
        raise HTTPException(404, 'Resume not found')


@app.get('/api/health')
def health():
    raw = load_profile_raw()
    p = runtime_profile(raw)
    resume = active_resume_path(raw)
    cdp = p.get('chrome_cdp_endpoint', 'http://127.0.0.1:9222').rstrip('/')
    cdp_ok = False
    cdp_browser = ''
    try:
        with urllib.request.urlopen(cdp + '/json/version', timeout=1.5) as r:
            data = json.loads(r.read().decode('utf-8', errors='ignore'))
            cdp_ok = True
            cdp_browser = data.get('Browser', '')
    except Exception:
        pass
    try:
        import scrapling  # noqa: F401
        scrapling_ok = True
    except Exception:
        scrapling_ok = False
    try:
        import playwright  # noqa: F401
        playwright_ok = True
    except Exception:
        playwright_ok = False
    return {
        'profile_ok': True,
        'resume_ok': bool(resume and resume.exists()),
        'resume_path': str(resume or ''),
        'resume_count': len(list_resumes()),
        'cdp_ok': cdp_ok,
        'cdp_browser': cdp_browser,
        'scrapling_ok': scrapling_ok,
        'playwright_ok': playwright_ok,
        'jobspy_ok': jobspy_available(),
        'jobspy_enabled': bool(p.get('jobspy_enabled', True)),
        'reviewer_enabled': p.get('chatgpt_web_reviewer', {}).get('enabled', True),
        'agent_fallback_enabled': p.get('agent_fallback', {}).get('enabled', True),
        'learning_stats': learning_stats(),
        'ats_adapters': adapter_catalog(),
        'queue': queue_status(),
        'scheduler': scheduler_status(),
        'local_only': True,
    }


@app.get('/api/sources')
def sources():
    raw = load_profile_raw()
    auto = raw.get('automation', {})
    configured = auto.get('enabled_sources', None)
    enabled = set([s.key for s in SOURCES if s.enabled_by_default] if configured is None else configured)
    custom_keys = {s.key for s in all_sources(auto) if s.key.startswith('custom_')}
    enabled |= custom_keys
    rows = [
        {'key': s.key, 'label': s.label, 'domain': s.domain, 'enabled': s.key in enabled, 'custom': s.key.startswith('custom_')}
        for s in all_sources(auto)
    ]
    if auto.get('jobspy_enabled', True):
        known = {x['key'] for x in rows}
        for site in auto.get('jobspy_sites', []) or []:
            key = f'jobspy_{str(site).strip().lower()}'
            if key not in known:
                rows.append({'key': key, 'label': f'JobSpy · {str(site).strip().title()}', 'domain': '', 'enabled': True, 'custom': False, 'filter_only': True})
    return rows


@app.get('/api/jobs')
def jobs(decision: str | None = None, source: str | None = None):
    clauses = []
    args: list[object] = []
    if decision:
        clauses.append('decision=?')
        args.append(decision)
    if source:
        clauses.append('provider_key=?')
        args.append(source)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    order = " ORDER BY CASE user_action WHEN 'liked' THEN 0 WHEN 'skipped' THEN 6 ELSE CASE decision WHEN 'keep' THEN 1 WHEN 'review' THEN 2 WHEN 'new' THEN 3 WHEN 'low' THEN 4 ELSE 5 END END, score DESC, discovered_at DESC"
    with connect() as c:
        rows = c.execute("SELECT jobs.*,COALESCE((SELECT status FROM application_queue q WHERE q.job_id=jobs.id),'') AS queue_status FROM jobs" + where + order, tuple(args)).fetchall()
    return [dict(r) for r in rows]


@app.get('/api/stats')
def stats():
    with connect() as c:
        row = c.execute('''SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN decision='keep' THEN 1 ELSE 0 END),0) AS keep_n,
            COALESCE(SUM(CASE WHEN user_action='liked' THEN 1 ELSE 0 END),0) AS liked_n,
            COALESCE(SUM(CASE WHEN review_verdict='APPLY' THEN 1 ELSE 0 END),0) AS apply_n,
            COALESCE(SUM(CASE WHEN review_verdict='HUMAN_REVIEW' THEN 1 ELSE 0 END),0) AS human_n,
            COALESCE(SUM(CASE WHEN decision='expired' OR availability_status='expired' THEN 1 ELSE 0 END),0) AS expired_n,
            COALESCE(SUM(CASE WHEN application_status IN ('submitted','submitted_verified') THEN 1 ELSE 0 END),0) AS submitted_n
            FROM jobs''').fetchone()
    return dict(row)


@app.post('/api/search')
def search():
    state = start_scan(runtime_profile())
    return state


@app.get('/api/search/status')
def search_status():
    return scan_status()


@app.post('/api/jobs/{job_id}/decision')
def set_decision(job_id: int, payload: Decision):
    if payload.decision not in {'liked', 'skipped', 'clear_user_action', 'keep', 'review', 'low', 'reject', 'expired'}:
        raise HTTPException(400, 'invalid decision')
    with connect() as c:
        exists = c.execute('SELECT id FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not exists:
            raise HTTPException(404, 'job not found')
        if payload.decision in {'liked', 'skipped'}:
            c.execute('UPDATE jobs SET user_action=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (payload.decision, job_id))
        elif payload.decision == 'clear_user_action':
            c.execute("UPDATE jobs SET user_action='', updated_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,))
        else:
            c.execute('UPDATE jobs SET decision=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (payload.decision, job_id))
    return {'ok': True}


@app.post('/api/jobs/{job_id}/application-status')
def set_application_status(job_id: int, payload: ApplicationStatus):
    allowed = {'prefilled', 'needs_human', 'submitted', 'submitted_verified', 'withdrawn', 'error', ''}
    if payload.status not in allowed:
        raise HTTPException(400, 'invalid application status')
    with connect() as c:
        exists = c.execute('SELECT id FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not exists:
            raise HTTPException(404, 'job not found')
        tracker = 'submitted' if payload.status in {'submitted','submitted_verified'} else ('prepared' if payload.status in {'prefilled','needs_human'} else '')
        c.execute('UPDATE jobs SET application_status=?, tracker_stage=CASE WHEN ?<>'' THEN ? ELSE tracker_stage END, last_application_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?', (payload.status, tracker, tracker, job_id))
        c.execute('INSERT INTO applications(job_id,status,note) VALUES(?,?,?)', (job_id, payload.status or 'status_cleared', 'Manual dashboard status change'))
        if tracker:
            c.execute('INSERT INTO application_stage_events(job_id,stage,note) VALUES(?,?,?)', (job_id, tracker, 'Application status changed from dashboard'))
    return {'ok': True}


@app.get('/api/jobs/{job_id}/applications')
def application_history(job_id: int):
    with connect() as c:
        rows = c.execute('SELECT * FROM applications WHERE job_id=? ORDER BY id DESC LIMIT 100', (job_id,)).fetchall()
    return [dict(r) for r in rows]


@app.get('/api/jobs/{job_id}/audit')
def application_audit(job_id: int):
    with connect() as c:
        row = c.execute('SELECT fill_audit_path FROM jobs WHERE id=?', (job_id,)).fetchone()
    if not row or not row['fill_audit_path']:
        raise HTTPException(404, 'No fill audit for this job')
    path = Path(row['fill_audit_path']).resolve()
    audit_root = (ROOT / 'data' / 'application_audits').resolve()
    if audit_root not in path.parents or not path.exists():
        raise HTTPException(404, 'Audit file unavailable')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise HTTPException(500, f'Audit read error: {exc}')


@app.get('/api/jobs/{job_id}/agent-trace')
def agent_trace(job_id: int):
    with connect() as c:
        row = c.execute('SELECT agent_trace_path FROM jobs WHERE id=?', (job_id,)).fetchone()
    if not row or not row['agent_trace_path']:
        raise HTTPException(404, 'No agent trace for this job')
    path = Path(row['agent_trace_path']).resolve()
    trace_root = (ROOT / 'data' / 'agent_traces').resolve()
    if trace_root not in path.parents or not path.exists():
        raise HTTPException(404, 'Agent trace unavailable')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise HTTPException(500, f'Agent trace read error: {exc}')


@app.get('/api/learnings/stats')
def get_learning_stats():
    return learning_stats()


@app.get('/api/ats-adapters')
def ats_adapters():
    return adapter_catalog()


@app.post('/api/jobs/{job_id}/review')
def review(job_id: int):
    profile = runtime_profile()
    cfg = profile.get('chatgpt_web_reviewer', {})
    if not cfg.get('enabled', True):
        raise HTTPException(400, 'ChatGPT web reviewer is disabled')
    with connect() as c:
        row = c.execute('SELECT id FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'job not found')
        c.execute("UPDATE jobs SET review_verdict='QUEUED', review_summary='Waiting for ChatGPT web reviewer', updated_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,))
    launch_review(job_id)
    return {'ok': True, 'message': 'ChatGPT web review queued'}


@app.post('/api/review/batch')
def review_batch(mode: str = 'strong'):
    if mode not in {'strong', 'liked'}:
        raise HTTPException(400, 'mode must be strong or liked')
    launch_batch_review(mode)
    return {'ok': True, 'message': f'Batch review queued: {mode}'}


@app.post('/api/jobs/{job_id}/apply')
def apply(job_id: int):
    with connect() as c:
        row = c.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'job not found')
        job = dict(row)
    launch_apply(job_id)
    return {'ok': True, 'message': 'Browser worker launched', 'review_verdict': job.get('review_verdict', '')}



@app.get('/api/queue')
def get_queue():
    return queue_status()


@app.post('/api/queue')
def add_queue(payload: QueueRequest):
    return queue_enqueue(payload.job_ids, payload.priority)


@app.post('/api/queue/start')
def start_queue():
    return queue_start()


@app.delete('/api/queue/{job_id}')
def remove_queue(job_id: int):
    queue_remove(job_id)
    return {'ok': True}


@app.post('/api/queue/clear-finished')
def clear_queue_finished():
    queue_clear_finished()
    return {'ok': True}


TRACK_STAGES = {'saved','queued','prepared','submitted','screening','interview','offer','rejected','withdrawn'}


@app.get('/api/pipeline')
def pipeline():
    with connect() as c:
        rows = c.execute("""SELECT jobs.*,COALESCE((SELECT status FROM application_queue q WHERE q.job_id=jobs.id),'') AS queue_status
                            FROM jobs WHERE tracker_stage<>'' OR application_status<>'' OR user_action='liked'
                            ORDER BY COALESCE(last_application_at,updated_at) DESC""").fetchall()
    return [dict(r) for r in rows]


@app.put('/api/jobs/{job_id}/track')
def track(job_id: int, payload: TrackPatch):
    if payload.stage not in TRACK_STAGES:
        raise HTTPException(400, 'invalid tracker stage')
    with connect() as c:
        row = c.execute('SELECT id FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'job not found')
        c.execute('UPDATE jobs SET tracker_stage=?,tracker_note=?,next_followup_at=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                  (payload.stage, payload.note[:4000], payload.followup_at[:80], job_id))
        c.execute('INSERT INTO application_stage_events(job_id,stage,note,followup_at) VALUES(?,?,?,?)',
                  (job_id, payload.stage, payload.note[:4000], payload.followup_at[:80]))
    return {'ok': True}


@app.get('/api/jobs/{job_id}/stage-events')
def stage_events(job_id: int):
    with connect() as c:
        rows = c.execute('SELECT * FROM application_stage_events WHERE job_id=? ORDER BY id DESC LIMIT 200', (job_id,)).fetchall()
    return [dict(r) for r in rows]


@app.get('/api/analytics')
def analytics():
    with connect() as c:
        totals = dict(c.execute("""SELECT COUNT(*) total,
            COALESCE(SUM(CASE WHEN user_action='liked' THEN 1 ELSE 0 END),0) liked,
            COALESCE(SUM(CASE WHEN review_verdict='APPLY' THEN 1 ELSE 0 END),0) reviewer_apply,
            COALESCE(SUM(CASE WHEN application_status IN ('submitted','submitted_verified') THEN 1 ELSE 0 END),0) submitted
            FROM jobs""").fetchone())
        stages = [dict(r) for r in c.execute("SELECT tracker_stage stage,COUNT(*) n FROM jobs WHERE tracker_stage<>'' GROUP BY tracker_stage ORDER BY n DESC").fetchall()]
        sources = [dict(r) for r in c.execute("SELECT provider_key source,COUNT(*) n FROM jobs GROUP BY provider_key ORDER BY n DESC LIMIT 20").fetchall()]
        campaigns = [dict(r) for r in c.execute("SELECT search_profile_label profile,COUNT(*) n FROM jobs GROUP BY search_profile_label ORDER BY n DESC LIMIT 20").fetchall()]
        queue = [dict(r) for r in c.execute("SELECT status,COUNT(*) n FROM application_queue GROUP BY status").fetchall()]
    return {'totals': totals, 'stages': stages, 'sources': sources, 'campaigns': campaigns, 'queue': queue, 'scheduler': scheduler_status()}

@app.delete('/api/jobs')
def clear_jobs():
    with connect() as c:
        c.execute('DELETE FROM application_queue')
        c.execute('DELETE FROM application_stage_events')
        c.execute('DELETE FROM applications')
        c.execute('DELETE FROM jobs')
    return {'ok': True}
