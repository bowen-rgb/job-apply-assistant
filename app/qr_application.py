"""Candidate-owned QR discovery and explicitly authorized single applications."""
from __future__ import annotations

import hashlib
import io
import json
import re
import uuid
import warnings
from datetime import datetime, date
from zoneinfo import ZoneInfo
from dataclasses import asdict
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from . import application_safety as safety
from .db import connect
from .profile_store import load_profile_raw, list_resumes, resume_directory, select_resume_for_job
from .pfe_discovery import read_public, validate_destination
from .qr_context import page_context, readiness, discover_roles

MAX_IMAGE = 8 * 1024 * 1024
MAX_PIXELS = 20_000_000


def init_tables():
    with connect() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS qr_requests(
          id TEXT PRIMARY KEY, job_id INTEGER, state TEXT NOT NULL DEFAULT 'draft',
          payload TEXT NOT NULL, context_token TEXT DEFAULT '', cv_hash TEXT DEFAULT '',
          resume_id TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')


def decode_image(content):
    from PIL import Image, ImageOps, UnidentifiedImageError
    import zxingcpp
    if not content or len(content) > MAX_IMAGE:
        raise ValueError('qr_image_size')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as original:
                if original.width * original.height > MAX_PIXELS:
                    raise ValueError('qr_image_pixels')
                if original.format not in {'PNG','JPEG','WEBP','BMP'}:
                    raise ValueError('qr_image_format')
                image = ImageOps.exif_transpose(original).convert('RGB')
                codes = zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('qr_image_format')
    values = list(dict.fromkeys(code.text.strip() for code in codes if code.text.strip()))
    if not values:
        raise ValueError('qr_no_code')
    return values


def get_request(identifier):
    init_tables()
    with connect() as c:
        row = c.execute('SELECT * FROM qr_requests WHERE id=?', (identifier,)).fetchone()
    if not row:
        raise KeyError(identifier)
    return dict(row)


def inspect_url(url):
    from .extractor import extract_job_document
    parsed = urlparse(url)
    if parsed.scheme in {'weixin','wechat'}:
        raise ValueError('qr_mobile_only')
    if parsed.scheme not in {'http','https'}:
        raise ValueError('qr_not_web_form')
    if parsed.hostname in {'weixin.qq.com','u.wechat.com','open.weixin.qq.com','qm.qq.com'}:
        raise ValueError('qr_mobile_only')
    validate_destination(url)
    try:
        content, ctype, final = read_public(url)
    except OSError as exc:
        return complete_context({'url':url,'final_url':url,'company':'','company_evidence':'',
               'sector':'unknown','sector_inferred':False,'sector_evidence':'','kind':'entry',
               'title':'','body':'','role_title':'','tasks':[],'opportunities':[],
               'location':'','employment_type':'','structured_json':'','start_date':'','end_date':'','valid_through':'',
               'inspection_error':str(exc)[:300]})
    if 'html' not in ctype.lower() and not content.lstrip().lower().startswith((b'<!doctype',b'<html')):
        raise ValueError('qr_not_web_form')
    soup = BeautifulSoup(content, 'lxml')
    text = soup.get_text(' ',strip=True)[:60000]
    if re.search(r'二维码已过期|二维码已失效|qr code (?:has )?expired|lien expiré',text,re.I):
        raise ValueError('qr_expired')
    document = asdict(extract_job_document(str(soup),final))
    try:
        if document.get('valid_through') and date.fromisoformat(document['valid_through'][:10]) < datetime.now(ZoneInfo('Europe/Paris')).date():
            raise ValueError('qr_expired')
    except ValueError as exc:
        if str(exc)=='qr_expired':raise
    context=page_context(str(soup),final)
    sectors = [('research','research|recherche|laboratoire|laboratory'),
               ('mechanical','mécanique|mechanical|aéronautique|aerospace|manufactur'),
               ('control','automatique|control systems|robotique|robotics'),
               ('digital','jumeau numérique|digital twin|software|logiciel|informatique')]
    sector, quote = 'unknown',''
    for key, pattern in sectors:
        match = re.search(pattern,text,re.I)
        if match:sector,quote=key,match.group();break
    return complete_context({'url':url,'final_url':final,'company':context['company'],'company_evidence':context['company_evidence'],
            'company_quote':context['company_quote'],'company_source_url':final,'page_title':context['page_title'],
            'sector':sector,'sector_evidence':quote,'sector_inferred':bool(quote),
            'kind':context['kind'],'role_title':context['role_title'],'tasks':context['tasks'],
            'opportunities':discover_roles(context,read_public) if context['kind']=='entry' else [],
            'search_url':context['search_url'],
            'title':context['title'][:500], 'body':context['body'][:45000],
            'location':document['location'], 'employment_type':document['employment_type'],
            'structured_json':document['structured_json'], 'start_date':document['start_date'],
            'end_date':document['end_date'], 'valid_through':document['valid_through'],'read_mode':'public_html'})


def complete_context(payload):
    from .resume_matcher import rank_resumes
    from .cover_letter import resume_text
    payload['readiness']=readiness(payload)
    rows=list_resumes()
    payload['resume_ranking']=payload.get('semantic_ranking') or rank_resumes(payload,rows,lambda row:resume_text(resume_directory()/row['filename']))
    payload['needs_enrichment']=not payload['readiness']['ready'] or not payload['resume_ranking'] or payload['resume_ranking'][0].get('source')=='tags_only'
    return payload


def recommend(payload):
    rows = list_resumes()
    if not rows:return None,'qr_no_resume'
    if payload['kind']=='vacancy':
        ranking=payload.get('resume_ranking') or []
        if ranking and ranking[0].get('source')!='tags_only' and (ranking[0].get('score',0)>0 or ranking[0].get('source')=='grounded_semantic'):
            return next((row for row in rows if row['id']==ranking[0]['resume_id']),None),'qr_resume_job'
        return None,'qr_resume_choose'
    # A company-only entrance can suggest a direction, but never claim a matched vacancy.
    themes={'control':'robotique commande robotics',
            'mechanical':'conception mécanique mechanical design',
            'digital':'jumeau numérique digital twin visualisation 3D'}
    if payload.get('sector') in themes:
        from .pfe import norm
        probe=norm(themes[payload['sector']])
        ranked=[(sum(len(tag) for tag in row.get('tags',[]) if norm(tag) in probe),row) for row in rows]
        ranked.sort(key=lambda item:item[0],reverse=True)
        if ranked[0][0]>0:return ranked[0][1],'qr_resume_sector'
    # Research alone is too broad to infer a specific technical role.
    from .pfe import norm
    general = next((row for row in rows if re.search(r'forum|general|综合',norm(row.get('original_name','')+' '+row.get('label','')))),None)
    if general:return general,'qr_resume_general'
    _, selected=select_resume_for_job({},load_profile_raw())
    return selected,'qr_resume_choose'


def create_request(url,source_name=""):
    payload = inspect_url(url)
    chosen, reason = recommend(payload)
    payload.update(resume_id=chosen['id'] if chosen else '',resume_reason=reason,source_name=str(source_name).replace('\\','/').rsplit('/',1)[-1][:180])
    identifier=uuid.uuid4().hex
    init_tables()
    with connect() as c:
        c.execute('INSERT INTO qr_requests(id,payload) VALUES(?,?)',(identifier,json.dumps(payload,ensure_ascii=False)))
    return request_status(identifier)


def request_status(identifier):
    row=get_request(identifier)
    payload=json.loads(row['payload'])
    result={'id':identifier,'state':row['state'],'preview':payload,
            'resumes':[{'id':r['id'],'label':r['label']} for r in list_resumes()], 'job_id':row['job_id'],
            'generate_letter':bool(payload.get('readiness',{}).get('letter_allowed')) and load_profile_raw().get('application',{}).get('generate_cover_letter',True)}
    if row['state']=='analyzing':
        from .worker_runtime import is_running
        result['inspection_running']=is_running('app.qr_inspect_worker',identifier)
    if row['job_id']:
        job=safety.get_job(row['job_id'])
        from .preparation_summary import preparation_summary
        summary=preparation_summary(job)
        result['progress']={'status':job.get('application_status'),'step':job.get('application_step'),
                            'summary':summary,'verification':safety.verification_state(job['id'],job.get('application_status'))}
        from .worker_runtime import is_running
        running=is_running('app.apply_worker',job['id'])
        result['progress']['worker_running']=running
        result['progress']['interrupted']=(not running and job.get('application_status') in {'','opening','preparing','preparing_letter'})
        with connect() as c:
            last=c.execute('SELECT status,note FROM applications WHERE job_id=? ORDER BY id DESC LIMIT 1',(job['id'],)).fetchone()
        result['progress']['detail']=dict(last) if last else {}
    return result


def start_request(identifier,resume_id,company):
    from . import browser_control
    from .worker_runtime import any_running, is_running
    from .workspaces import LOCK
    from .browser import launch_apply
    from .human_review import can_prepare
    with LOCK:
        row=get_request(identifier)
        if row['state']!='draft':
            if row['job_id'] and is_running('app.apply_worker',row['job_id']):return request_status(identifier)
            raise ValueError('qr_already_started')
        browser_control.require_connection()
        if any_running():raise ValueError('qr_busy')
        payload=json.loads(row['payload'])
        # Do not authorize a portal or a guessed role merely because a company was typed in.
        payload=complete_context(payload)
        if not payload['readiness']['ready'] and not (payload['kind']=='general' and payload.get('company_quote')):
            raise ValueError('qr_context_incomplete')
        company=str(company or payload['company']).strip()[:200]
        if not company:raise ValueError('qr_company_required')
        if payload['company']!=company:
            payload.update(company=company,company_evidence='candidate input',company_quote=company)
        payload['resume_id']=resume_id
        selected=next((r for r in list_resumes() if r['id']==resume_id),None)
        if not selected:raise ValueError('qr_no_resume')
        raw=load_profile_raw()
        # Final target has already been checked by the bounded redirect reader.
        validate_destination(payload['final_url'])
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            job=c.execute('SELECT * FROM jobs WHERE url=?',(payload['final_url'],)).fetchone()
            if job:
                job=dict(job)
                if (safety.has_dispatch(job['id']) or not can_prepare(job) or job.get('application_status') in {'submitted','submitted_verified','withdrawn','opening','preparing','preparing_letter'} or job.get('tracker_stage') in {'submitted','screening','interview','offer','rejected','withdrawn'}
                        or job.get('availability_status')=='expired' or job.get('decision')=='expired' or job.get('user_action')=='skipped'):
                    raise ValueError('qr_existing_application')
                c.execute('UPDATE jobs SET application_resume_id=?,application_context_json=?,company=?,title=?,body=? WHERE id=?',
                          (resume_id,json.dumps(payload,ensure_ascii=False),company,payload['title'],payload['body'],job['id']))
                job_id=job['id']
            else:
                title=payload['title'] if payload['kind']=='vacancy' else 'Candidature spontanée — '+company
                fields=dict(url=payload['final_url'],title=title,company=company,body=payload['body'],
                            location=payload['location'],employment_type=payload['employment_type'],
                            start_date=payload['start_date'],end_date=payload['end_date'],valid_through=payload['valid_through'],
                            source='QR',provider_key='qr',application_resume_id=resume_id,tracker_stage='saved')
                fields['application_context_json']=json.dumps(payload,ensure_ascii=False)
                keys=','.join(fields)
                job_id=c.execute(f'INSERT INTO jobs({keys}) VALUES({",".join("?" for _ in fields)})',list(fields.values())).lastrowid
            job=dict(c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone())
            if payload['company']!=company:payload['company_evidence']='candidate input'
            payload['company']=company
            payload['resume_id']=resume_id
            c.execute("UPDATE qr_requests SET job_id=?,state='authorized',payload=?,context_token=?,cv_hash=?,resume_id=? WHERE id=?",
                      (job_id,json.dumps(payload,ensure_ascii=False),safety.context_token(job,raw),
                       safety.file_hash(resume_directory()/selected['filename']),resume_id,identifier))
        try:
            launch_apply(job_id,qr_request_id=identifier)
        except Exception:
            with connect() as c:c.execute("UPDATE qr_requests SET state='draft' WHERE id=?",(identifier,))
            raise
        return request_status(identifier)


def validate_intent(identifier,job,raw):
    row=get_request(identifier)
    resume, selected=select_resume_for_job(job,raw)
    if (row['state']!='authorized' or row['job_id']!=job['id'] or not selected or selected['id']!=row['resume_id']
            or not resume or safety.file_hash(resume)!=row['cv_hash'] or safety.context_token(job,raw)!=row['context_token']):
        raise ValueError('qr_materials_changed')
    return row


def resume_request(identifier):
    from . import browser_control
    from .worker_runtime import any_running
    from .browser import launch_apply
    from .workspaces import LOCK
    with LOCK:
        row=get_request(identifier)
        if not row['job_id']:raise ValueError('qr_not_found')
        job=safety.get_job(row['job_id'])
        validate_intent(identifier,job,load_profile_raw())
        if safety.has_dispatch(job['id']) or job.get('application_status') in {'submitted','submitted_verified','withdrawn'}:
            raise ValueError('qr_already_started')
        if any_running():raise ValueError('qr_busy')
        browser_control.require_connection()
        launch_apply(job['id'],qr_request_id=identifier)
        return request_status(identifier)


def authorize_materials(identifier,job,raw,snapshot):
    validate_intent(identifier,job,raw)
    safety.validate_materials(job,raw,snapshot)
    from .application_target import requires_letter
    if requires_letter(job,raw):
        from .cover_letter import letter_paths,current_letter
        resume,_=select_resume_for_job(job,raw)
        state=json.loads(letter_paths(job['id'])[0].read_text(encoding='utf-8'))
        if not current_letter(state,job,raw,resume):raise ValueError('qr_letter_not_checked')
    with connect() as c:
        c.execute('INSERT OR IGNORE INTO material_approvals(job_id,token) VALUES(?,?)',(job['id'],snapshot['token']))
        c.execute("INSERT INTO applications(job_id,status,note) VALUES(?,'qr_material_authorized',?)",(job['id'],'Single-application click authorization; generated letter checked by current LM policy, not represented as human proofreading.'))


def analyze_request(identifier):
    from .worker_runtime import any_running,is_running,launch
    from .browser_control import require_connection
    from .workspaces import LOCK
    with LOCK:
        row=get_request(identifier)
        if row['state']=='analyzing' and is_running('app.qr_inspect_worker',identifier):return request_status(identifier)
        if row['state'] not in {'draft','analyzing'}:raise ValueError('qr_already_started')
        require_connection()
        if any_running():raise ValueError('qr_busy')
        with connect() as c:c.execute("UPDATE qr_requests SET state='analyzing' WHERE id=?",(identifier,))
        try:launch('app.qr_inspect_worker',identifier)
        except Exception:
            with connect() as c:c.execute("UPDATE qr_requests SET state='draft' WHERE id=?",(identifier,))
            raise
        return request_status(identifier)


def list_requests():
    init_tables()
    with connect() as c:
        rows=c.execute('SELECT id,state,payload,created_at FROM qr_requests ORDER BY created_at DESC,rowid DESC').fetchall()
    result=[]
    for row in rows:
        item={'id':row['id'],'state':row['state'],'preview':json.loads(row['payload']),'created_at':row['created_at']}
        if row['state']!='draft':
            live=request_status(row['id'])
            for key in ('progress','inspection_running','job_id'):
                if key in live:item[key]=live[key]
        result.append(item)
    return result


def remove_request(identifier):
    # Draft deletion removes discovery only. Application history is never deleted here.
    from .workspaces import LOCK
    from .worker_runtime import is_running,cancel
    with LOCK:
        row=get_request(identifier)
        if row['state'] not in {'draft','analyzing'}:raise ValueError('qr_already_started')
        if is_running('app.qr_inspect_worker',identifier):cancel('app.qr_inspect_worker',identifier)
        with connect() as c:c.execute('DELETE FROM qr_requests WHERE id=?',(identifier,))
    return {'removed':True}


def save_selection(identifier,resume_id,company,resume_explicit=True):
    from .workspaces import LOCK
    with LOCK:
        row=get_request(identifier)
        if row['state']!='draft':raise ValueError('qr_already_started')
        if not any(r['id']==resume_id for r in list_resumes()):raise ValueError('qr_no_resume')
        payload=json.loads(row['payload'])
        if company.strip()!=payload.get('company',''):
            payload.update(company=company.strip()[:200],company_quote=company.strip()[:200],company_evidence='candidate input')
        payload['resume_id']=resume_id
        if resume_explicit:payload.update(user_resume_id=resume_id,resume_reason='qr_resume_manual')
        payload=complete_context(payload)
        with connect() as c:c.execute('UPDATE qr_requests SET payload=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),identifier))
    return request_status(identifier)


def set_target(identifier,url):
    from .workspaces import LOCK
    with LOCK:
        row=get_request(identifier)
        if row['state']!='draft':raise ValueError('qr_already_started')
        old=json.loads(row['payload'])
        payload=inspect_url(url)
        chosen,reason=recommend(payload)
        manual=next((r for r in list_resumes() if r['id']==old.get('user_resume_id')),None)
        payload.update(source_name=old.get('source_name',''),original_qr_url=old.get('original_qr_url') or old['url'],
                       resume_id=manual['id'] if manual else chosen['id'] if chosen else '',
                       resume_reason='qr_resume_manual' if manual else reason)
        if manual:payload['user_resume_id']=manual['id']
        with connect() as c:c.execute("UPDATE qr_requests SET payload=? WHERE id=? AND state='draft'",(json.dumps(payload,ensure_ascii=False),identifier))
    return request_status(identifier)
