"""Native workflow endpoints; uses the existing profile, queue and SQLite store."""
from datetime import datetime, timezone, date
import json
from typing import Literal
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel, Field
from .db import connect
from .repositories.jobs import JobRepository
from .repositories import application_insights as records
from .application_intelligence import followup_status, interview_pack, keyword_coverage, score_evaluation
from .profile_store import load_profile_raw, save_profile_raw, list_resumes, resume_directory, select_resume_for_job

router = APIRouter(prefix='/api/insights')


class FollowupRules(BaseModel):
    after_days: int = Field(default=14, ge=1, le=90)
    max_followups: int = Field(default=1, ge=0, le=10)


class Dimension(BaseModel):
    id: str = Field(min_length=1, max_length=60, pattern=r'^[a-z][a-z0-9_]*$')
    label: str = Field(min_length=1, max_length=100)
    weight: float = Field(ge=0, le=1000, allow_inf_nan=False)
    guide: str = Field(default='', max_length=1000)


class InsightConfig(BaseModel):
    follow_up: FollowupRules = Field(default_factory=FollowupRules)
    dimensions: list[Dimension] = Field(default_factory=list, max_length=20)


class MailScan(BaseModel):
    days: int = Field(default=30, ge=1, le=90)


class MailConfirmation(BaseModel):
    message_ids: list[str] = Field(min_length=1, max_length=100)
    accept: bool


class Activity(BaseModel):
    kind: Literal['followup_sent', 'note'] = 'note'
    note: str = Field(min_length=1, max_length=4000)
    occurred_at: date = Field(default_factory=date.today)


class Coverage(BaseModel):
    keywords: list[str] = Field(default_factory=list, max_length=100)


def job_by_id(job_id):
    with connect() as conn:
        row = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'job not found')
    return dict(row)


@router.get('')
def overview():
    raw = load_profile_raw()
    cfg = InsightConfig.model_validate(raw.get('insights') or {}).model_dump()
    activities = records.activities()
    due = []
    jobs = JobRepository().list()
    with connect() as conn:
        stage_events = [dict(row) for row in conn.execute("SELECT * FROM application_stage_events")]
    events_by_job = {}
    for event in [*activities, *stage_events]:
        events_by_job.setdefault(event["job_id"], []).append(event)
    for job in jobs:
        events = events_by_job.get(job['id'], [])
        item = followup_status(job, events, cfg['follow_up'])
        if item and item.get('due'):
            due.append({**item, 'title': job['title'], 'company': job['company'], 'url': job['url']})
    from .application_overview import snapshot
    fields = ('id','company','title','display_title','tracker_stage','tracker_note','application_status','user_action','decision','review_verdict')
    return {'application_rows': [{key:j.get(key) for key in fields} for j in jobs], 'summary': snapshot(jobs, due, [*activities, *stage_events]), 'config': cfg, 'followups': sorted(due, key=lambda x: x['due_at']),
            'mail_proposals': records.proposals(), 'rejected': sum(j['tracker_stage']=='rejected' for j in jobs)}


def activities_for(job_id, saved=None):
    return [*JobRepository().stage_events(job_id),
            *(event for event in (records.activities(job_id) if saved is None else saved) if event['job_id']==job_id)]


@router.put('/config')
def configure(payload: InsightConfig):
    dimensions = [d.model_dump() for d in payload.dimensions]
    if dimensions:
        try:
            score_evaluation(dimensions, {d['id']: 0 for d in dimensions})
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    save_profile_raw({'insights': payload.model_dump()})
    return {'ok': True}


@router.post('/gmail-sync')
def sync_mail(payload: MailScan):
    from .mail_outcomes import sync
    try:
        return sync(payload.days)
    except Exception as exc:
        # OAuth/network errors may contain bearer tokens or credentials in URLs.
        raise HTTPException(400, 'Gmail unavailable. Check the connection in Profiles & accounts.') from exc


@router.post('/mail-confirm')
def confirm_mail(payload: MailConfirmation):
    try:
        records.confirm_proposals(payload.message_ids, payload.accept)
    except KeyError as exc:
        raise HTTPException(404, 'Message not found') from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {'ok': True}


@router.post('/jobs/{job_id}/activities')
def record_activity(job_id: int, payload: Activity):
    if payload.occurred_at > date.today():
        raise HTTPException(400, 'Only record contact that already happened')
    try:
        records.add_activity(job_id, payload.kind, payload.note, payload.occurred_at.isoformat())
    except KeyError as exc:
        raise HTTPException(404, 'job not found') from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {'ok': True}


@router.get('/jobs/{job_id}/dossier')
def dossier(job_id: int):
    from .cover_letter import resume_text
    from .resume_matcher import rank_resumes
    job, raw = job_by_id(job_id), load_profile_raw()
    text = job.get('body') or job.get('snippet') or ''
    ranked = rank_resumes({'role_title': job['title'], 'tasks': [text]}, list_resumes(),
                          lambda row: resume_text(resume_directory()/row['filename']))
    path, chosen = select_resume_for_job(job, raw)
    try:
        cv = resume_text(path)
    except ValueError:
        cv = ''
    evidence = ranked[0].get('evidence', []) if ranked else []
    return {'job': {key: job.get(key) for key in ('id', 'company', 'title', 'url', 'tracker_stage')},
            'resume': chosen, 'ranked_resumes': ranked, 'cv_readable': bool(cv),
            'interview': interview_pack(job, raw, evidence),
            'activities': activities_for(job_id),
            'followup': followup_status(job, activities_for(job_id), (raw.get('insights') or {}).get('follow_up'))}


@router.post('/jobs/{job_id}/coverage')
def coverage(job_id: int, payload: Coverage):
    from .cover_letter import resume_text
    job = job_by_id(job_id)
    path, resume = select_resume_for_job(job)
    try:
        cv = resume_text(path)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    # Only keywords actually in the posting can be measured against its CV.
    from .application_intelligence import has_term
    text = (job.get('title') or '')+' '+(job.get('body') or job.get('snippet') or '')
    valid = [kw[:100] for kw in payload.keywords if has_term(text, kw[:100])]
    return {**keyword_coverage(valid, cv), 'resume': resume,
            'ignored': [kw for kw in payload.keywords if kw[:100] not in valid]}


@router.post('/import')
async def import_ledger(file: UploadFile = File(...), write: bool = Form(False)):
    from .tracker_exchange import parse_upload, preview, import_rows
    content = await file.read(2_000_001)
    try:
        rows = parse_upload(file.filename or '', content)
        return import_rows(rows) if write else {'rows': preview(rows)}
    except Exception as exc:
        raise HTTPException(400, 'Cannot read this ledger. Use UTF-8 CSV/JSON/Markdown or a valid XLSX, up to 2 MB and 1000 rows.') from exc


@router.get('/export')
def export_ledger(format: Literal['json', 'csv', 'xlsx', 'md', 'html'] = 'xlsx'):
    from .tracker_exchange import export_rows
    content, media = export_rows(JobRepository().pipeline(), format)
    return Response(content, media_type=media, headers={'Content-Disposition': f'attachment; filename="applications.{format}"'})
