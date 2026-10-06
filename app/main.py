from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
import urllib.request
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .db import init_db
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
from .contracts import (
    ApplicationStatus,
    HumanReview,
    ReviewExport,
    Decision,
    QueueRequest,
    ResumePatch,
    TrackPatch,
    TitleTranslationRequest,
)
from .repositories import JobRepository
from .services import ApplicationService
from .cover_letter import letter_paths, save_letter_state
from .job_translation import translate_jobs, local_title
from .worker_runtime import launch as launch_worker, cancel as cancel_worker
from .queue_manager import stop as queue_stop
from .queue_manager import retry as queue_retry
from .matching_service import rescore_jobs
from .review_exports import create_export, read_state as export_state, download as export_download, cancel_export

STATIC = ROOT / 'static'

app = FastAPI(title='Job Apply Assistant V8.4')
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


job_repository = JobRepository()
application_service = ApplicationService(job_repository)


@app.on_event('startup')
def startup():
    init_db()
    load_profile_raw()
    rescore_jobs(runtime_profile())
    start_scheduler()


@app.on_event('shutdown')
def shutdown():
    from .worker_runtime import cancel_all
    queue_stop()
    cancel_all()


@app.get('/')
def index():
    return FileResponse(STATIC / 'index.html')


@app.post('/api/jobs/translate-titles')
def translate_job_titles(payload: TitleTranslationRequest):
    return {'language': payload.language, 'translations': translate_jobs(job_repository.titles(payload.job_ids), payload.language)}


@app.post('/api/review-exports')
def start_review_export(payload: ReviewExport):
    rows=job_repository.list()
    if payload.scope=='pending':
        rows=[j for j in rows if j['human_review_status']=='pending' and j['user_action']!='skipped'
              and j['application_status'] not in {'submitted','submitted_verified','withdrawn'}
              and j['tracker_stage'] not in {'rejected','withdrawn'}
              and j['decision']!='expired' and j['availability_status']!='expired']
    else:
        if not payload.job_ids:raise HTTPException(400,'Aucun poste à exporter dans cette sélection.')
        by_id={j['id']:j for j in rows}
        if any(id not in by_id for id in payload.job_ids):raise HTTPException(409,'La sélection a changé. Rechargez la liste avant d’exporter.')
        rows=[by_id[id] for id in dict.fromkeys(payload.job_ids)]
    try:return create_export(rows,payload.language,payload.format,payload.translate_text)
    except ValueError as exc:raise HTTPException(400,str(exc))


@app.get('/api/review-exports/{export_id}')
def review_export_status(export_id: str):
    try:return export_state(export_id)
    except KeyError:raise HTTPException(404,'Export introuvable.')


@app.post('/api/review-exports/{export_id}/cancel')
def stop_review_export(export_id: str):
    try:return cancel_export(export_id)
    except KeyError:raise HTTPException(404,'Export introuvable.')


@app.get('/api/review-exports/{export_id}/download')
def download_review_export(export_id: str):
    try:path,state=export_download(export_id)
    except KeyError:raise HTTPException(404,'Export introuvable.')
    except ValueError as exc:raise HTTPException(409,str(exc))
    media='text/html; charset=utf-8' if state['format']=='html' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return FileResponse(path,media_type=media,filename=f'job-review-{state["created_at"][:10]}-{state["language"]}.{state["format"]}')


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
def jobs(decision: str | None = None, source: str | None = None, language: str = 'fr'):
    if language not in {'fr','zh','en','de','es','pt'}:
        raise HTTPException(400, 'Unsupported language')
    rows = job_repository.list(decision, source)
    if language != 'fr':
        for row in rows:
            translated = local_title(row.get('title') or '', language)
            if translated:
                row['display_title'] = translated
    return rows


@app.get('/api/stats')
def stats():
    return job_repository.stats()


@app.post('/api/search')
def search():
    state = start_scan(runtime_profile())
    return state


@app.get('/api/search/status')
def search_status():
    return scan_status()


@app.post('/api/jobs/{job_id}/decision')
def set_decision(job_id: int, payload: Decision):
    try:
        job_repository.set_decision(job_id, payload.decision)
        if payload.decision == 'skipped':
            queue_remove(job_id)
    except KeyError:
        raise HTTPException(404, 'job not found')
    return {'ok': True}


@app.post('/api/jobs/rescore')
def rescore_existing_jobs():
    if scan_status().get('running'):
        raise HTTPException(409, 'Wait for the current scan to finish before recalculating matches')
    return rescore_jobs(runtime_profile())


@app.post('/api/jobs/{job_id}/application-status')
def set_application_status(job_id: int, payload: ApplicationStatus):
    try:
        job_repository.set_application_status(job_id, payload.status)
    except KeyError:
        raise HTTPException(404, 'job not found')
    return {'ok': True}


@app.post('/api/jobs/{job_id}/human-review')
def confirm_human_review(job_id: int, payload: HumanReview):
    try:
        job_repository.confirm_review(job_id, payload.status, payload.review_token)
    except KeyError:
        raise HTTPException(404, 'job not found')
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {'ok': True}


@app.get('/api/jobs/{job_id}/human-review-events')
def human_review_events(job_id: int):
    return job_repository.human_review_history(job_id)


@app.get('/api/jobs/{job_id}/applications')
def application_history(job_id: int):
    return job_repository.history(job_id)


@app.get('/api/jobs/{job_id}/letter')
def letter_status(job_id: int):
    if not job_repository.exists(job_id):
        raise HTTPException(404, 'job not found')
    metadata, _ = letter_paths(job_id)
    state = json.loads(metadata.read_text(encoding='utf-8')) if metadata.exists() else {'status': 'missing'}
    if state.get('status') == 'generating':
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(state['updated_at'])).total_seconds()
        except (KeyError, ValueError):
            age = 601
        if age > 600:
            return {'status': 'error', 'error': 'La génération a été interrompue. Réessayez.'}
    return state


@app.post('/api/jobs/{job_id}/letter')
def create_letter(job_id: int):
    state = letter_status(job_id)
    if state.get('status') == 'generating':
        return {'ok': True, 'status': 'generating'}
    raw = load_profile_raw()
    if not active_resume_path(raw):
        raise HTTPException(400, 'Ajoutez ou activez un CV dans le profil.')
    if not runtime_profile(raw).get('chatgpt_web_reviewer', {}).get('enabled', True):
        raise HTTPException(400, 'Activez ChatGPT Web dans le profil.')
    save_letter_state(job_id, {'status': 'generating'})
    try:
        launch_worker('app.cover_letter_worker', job_id)
    except Exception as exc:
        save_letter_state(job_id, {'status': 'error', 'error': str(exc)})
        raise HTTPException(500, 'Impossible de démarrer la génération.')
    return {'ok': True, 'status': 'generating'}


@app.get('/api/jobs/{job_id}/letter/pdf')
def download_letter(job_id: int):
    state = letter_status(job_id)
    _, pdf = letter_paths(job_id)
    if state.get('status') != 'ready' or not pdf.is_file():
        raise HTTPException(404, 'Lettre indisponible')
    return FileResponse(pdf, media_type='application/pdf', filename=f'lettre_motivation_{job_id}.pdf')


@app.post('/api/jobs/{job_id}/stop')
def stop_application(job_id: int):
    if not job_repository.exists(job_id):
        raise HTTPException(404, 'job not found')
    cancel_worker('app.apply_worker', job_id)
    cancel_worker('app.cover_letter_worker', job_id)
    queue_remove(job_id)
    return {'ok': True}


@app.get('/api/jobs/{job_id}/audit')
def application_audit(job_id: int):
    raw_path = job_repository.audit_path(job_id, 'fill_audit_path')
    if not raw_path:
        raise HTTPException(404, 'No fill audit for this job')
    path = Path(raw_path).resolve()
    audit_root = (ROOT / 'data' / 'application_audits').resolve()
    if audit_root not in path.parents or not path.exists():
        raise HTTPException(404, 'Audit file unavailable')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise HTTPException(500, f'Audit read error: {exc}')


@app.get('/api/jobs/{job_id}/agent-trace')
def agent_trace(job_id: int):
    raw_path = job_repository.audit_path(job_id, 'agent_trace_path')
    if not raw_path:
        raise HTTPException(404, 'No agent trace for this job')
    path = Path(raw_path).resolve()
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
    try:
        return application_service.queue_review(job_id, bool(cfg.get('enabled', True)))
    except KeyError:
        raise HTTPException(404, 'job not found')
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post('/api/review/batch')
def review_batch(mode: str = 'strong'):
    try:
        return application_service.queue_batch_review(mode)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post('/api/jobs/{job_id}/apply')
def apply(job_id: int, privacy_confirmed: bool = False):
    try:
        result = application_service.prefill(job_id, privacy_confirmed=privacy_confirmed)
    except KeyError:
        raise HTTPException(404, 'job not found')
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return result



@app.get('/api/queue')
def get_queue():
    return queue_status()


@app.post('/api/queue')
def add_queue(payload: QueueRequest):
    return queue_enqueue(payload.job_ids, payload.priority)


@app.post('/api/queue/start')
def start_queue(mode: Literal['one', 'batch'] = 'one'):
    return queue_start(mode)


@app.post('/api/queue/{job_id}/retry')
def retry_queue(job_id: int):
    try:
        return queue_retry(job_id)
    except KeyError:
        raise HTTPException(404, 'Queue item not found')
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.delete('/api/queue/{job_id}')
def remove_queue(job_id: int):
    queue_remove(job_id)
    return {'ok': True}


@app.post('/api/queue/stop')
def stop_queue():
    return queue_stop()


@app.post('/api/queue/clear-finished')
def clear_queue_finished():
    queue_clear_finished()
    return {'ok': True}


@app.get('/api/pipeline')
def pipeline():
    return job_repository.pipeline()


@app.put('/api/jobs/{job_id}/track')
def track(job_id: int, payload: TrackPatch):
    try:
        job_repository.track(job_id, payload.stage, payload.note, payload.followup_at, payload.source)
    except KeyError:
        raise HTTPException(404, 'job not found')
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {'ok': True}


@app.get('/api/jobs/{job_id}/stage-events')
def stage_events(job_id: int):
    return job_repository.stage_events(job_id)


@app.get('/api/analytics')
def analytics():
    data = job_repository.analytics()
    data['scheduler'] = scheduler_status()
    return data

@app.delete('/api/jobs')
def clear_jobs():
    job_repository.clear()
    return {'ok': True}
