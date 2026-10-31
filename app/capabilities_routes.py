"""Native endpoints for the complete upstream capability inventory."""
import hashlib
import json
from pathlib import Path
from typing import Literal
import uuid
from fastapi import APIRouter,HTTPException,UploadFile,File,Form
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field
from . import capability_store as store
from .worker_runtime import launch,cancel

router=APIRouter(prefix='/api/capabilities')


def invoke(function,*args,**kwargs):
    try:return function(*args,**kwargs)
    except HTTPException:raise
    except KeyError as exc:raise HTTPException(404,'Record not found') from exc
    except (ValueError,OSError) as exc:raise HTTPException(400,str(exc)[:2000]) from exc


class TaskRequest(BaseModel):
    kind:str=Field(max_length=40)
    job_id:int|None=Field(default=None,ge=1)
    backend:Literal['chatgpt','compatible','anthropic','ollama','claude','codex','opencode']='chatgpt'
    params:dict=Field(default_factory=dict)


class Selection(BaseModel):
    indexes:list[int]=Field(default_factory=list,max_length=300)


class SourceConfig(BaseModel):
    enabled:bool|None=None
    api_key:str=''
    app_id:str=''
    app_key:str=''
    affid:str=''
    client_id:str=''
    client_secret:str=''
    country:str=''
    location:str=''
    base_url:str=''
    query:str=''


class ModelConfig(BaseModel):
    base_url:str=Field(default='',max_length=2000)
    model:str=Field(default='',max_length=200)
    api_key:str=Field(default='',max_length=2000)


class ModelChoice(BaseModel):
    backend:Literal['chatgpt','compatible','anthropic','ollama','claude','codex','opencode']


@router.get('')
def overview():
    from . import model_backends,extended_sources,notion_sync,followup_mail
    from .profile_store import load_profile_raw
    from .portal_registry import entries
    summaries=[{key:row[key] for key in ('id','kind','job_id','state','error','created_at','finished_at')} for row in store.tasks()]
    docs=[{key:row.get(key) for key in ('id','name','sha256','path')} for row in store.items('document')]
    return {'models':model_backends.status(),'sources':extended_sources.status(),'notion':notion_sync.status(),
            'gmail_compose':followup_mail.status(),'tasks':summaries,'documents':docs,'templates':store.items('template'),
            'behavioral':load_profile_raw().get('career',{}).get('behavioral_profile',{}),
            'portals':entries(),'salary':[{'id':row['id'],'name':row['name'],'kind':row['kind']} for row in store.items('salary')],
            'selected_backend':load_profile_raw().get('automation',{}).get('chatgpt_web_reviewer',{}).get('backend','chatgpt')}


def submit_task(payload:TaskRequest,background=True):
    from .capability_worker import TASK_KINDS
    if payload.kind not in TASK_KINDS:raise HTTPException(422,'Unknown task kind')
    requires_job={'tailor_cv','interview','upskill','research','followup_draft','archive'}
    if payload.kind in requires_job and not payload.job_id:raise HTTPException(422,'Choose a job')
    allowed={'template_id','stage','document_ids','job_ids','url','document_id','max_pages','source','query','location','parent_task','answer','acknowledged','target_id','queries','country','only'}
    if any(key not in allowed for key in payload.params):raise HTTPException(422,'Unsupported task parameter')
    if len(json.dumps(payload.params,ensure_ascii=False))>100000:raise HTTPException(422,'Task parameters too large')
    if payload.kind=='notion_sync':
        from .notion_sync import status
        if payload.params.get('acknowledged') is not True or payload.params.get('target_id')!=status().get('target_id'):
            raise HTTPException(400,'Confirm the exact Notion target before writing')
    identifier=store.create_task(payload.kind,payload.job_id,{'backend':payload.backend,**payload.params})
    try:
        if background:launch('app.capability_worker',identifier)
    except ValueError as exc:
        store.update_task(identifier,'error',error=str(exc));raise HTTPException(409,str(exc)) from exc
    return {'id':identifier,'state':'queued'}


@router.post('/tasks')
def create_task(payload:TaskRequest):return submit_task(payload)


@router.get('/tasks/{identifier}')
def task(identifier:int):return invoke(store.task,identifier)


@router.post('/tasks/{identifier}/cancel')
def cancel_task(identifier:int):
    row=invoke(store.task,identifier)
    if row['state'] in {'queued','running'}:
        cancel('app.capability_worker',identifier)
        from .worker_runtime import is_running
        if not is_running('app.capability_worker',identifier):store.update_task(identifier,'cancelled',error='Task stopped or previous process interrupted')
    return {'ok':True}


@router.post('/tasks/{identifier}/adopt-cv')
def adopt_cv(identifier:int):
    from .career_intelligence import adopt_cv
    return invoke(adopt_cv,identifier)


@router.post('/tasks/{identifier}/accept-facts')
def accept_facts(identifier:int,payload:Selection):
    from .career_intelligence import accept_facts
    return invoke(accept_facts,identifier,payload.indexes)


@router.post('/tasks/{identifier}/accept-rank')
def accept_rank(identifier:int,payload:Selection):
    from .capability_actions import accept_rank
    return invoke(accept_rank,identifier,payload.indexes)


@router.post('/tasks/{identifier}/accept-plan')
def accept_plan(identifier:int,payload:Selection):
    from .capability_actions import accept_plan
    return invoke(accept_plan,identifier,payload.indexes)


class Writing(BaseModel):
    text:str=Field(max_length=100000)
    rules:dict=Field(default_factory=dict)


@router.post('/lint')
def lint(payload:Writing):
    from .writing_lint import lint
    return invoke(lint,payload.text,payload.rules)


@router.post('/tasks/{identifier}/accept-discovery')
def accept_discovery(identifier:int,payload:Selection):
    from .linkedin_discovery import accept
    return invoke(accept,identifier,payload.indexes)


@router.post('/linkedin/login')
def linkedin_login():
    from .linkedin_discovery import login
    return invoke(login)


class Behavioral(BaseModel):
    energizers:str=Field(default='',max_length=4000)
    drainers:str=Field(default='',max_length=4000)
    work_style:str=Field(default='',max_length=4000)
    motivation:str=Field(default='',max_length=4000)
    assessment:str=Field(default='',max_length=4000)


@router.put('/behavioral')
def behavioral(payload:Behavioral):
    from .profile_store import load_profile_raw,save_profile_raw
    career=load_profile_raw().get('career',{});career['behavioral_profile']=payload.model_dump()
    save_profile_raw({'career':career});return {'ok':True}


@router.put('/models/{backend}')
def configure_model(backend:str,payload:ModelConfig):
    from .model_backends import configure
    invoke(configure,backend,payload.model_dump());return {'ok':True}


@router.put('/model-choice')
def choose_model(payload:ModelChoice):
    from .profile_store import save_profile_raw
    save_profile_raw({'automation':{'model_backend':payload.backend,'chatgpt_web_reviewer':{'backend':payload.backend}}})
    return {'ok':True}


@router.put('/sources/{source}')
def configure_source(source:str,payload:SourceConfig):
    from .extended_sources import configure
    invoke(configure,source,payload.model_dump(exclude_none=True));return {'ok':True}


@router.post('/documents')
async def import_documents(files:list[UploadFile]=File(...)):
    if len(files)>50:raise HTTPException(400,'Import at most 50 files at a time')
    result=[];total=0
    for file in files:
        content=await file.read(8_000_001)
        total+=len(content)
        if total>20_000_000:raise HTTPException(400,'Import at most 20 MB per batch')
        if len(content)>8_000_000:raise HTTPException(400,'Each document must be at most 8 MB')
        name=Path(file.filename or 'document').name;extension=Path(name).suffix.lower()
        if extension not in {'.pdf','.docx','.txt','.md','.json','.csv','.tsv','.xlsx'}:raise HTTPException(400,'Unsupported candidate document format')
        identifier=hashlib.sha256(content).hexdigest()[:24];path=store.safe_file('documents/'+identifier+extension);path.parent.mkdir(exist_ok=True);path.write_bytes(content)
        try:
            if extension in {'.pdf','.docx'}:
                from .cover_letter import resume_text
                text=resume_text(path)
            elif extension=='.xlsx':
                from .tracker_exchange import read_xlsx
                text=json.dumps(read_xlsx(content),ensure_ascii=False)
            else:text=content.decode('utf-8-sig')
        except Exception as exc:raise HTTPException(400,'Cannot extract text from '+name) from exc
        record={'name':name,'text':text[:100000],'path':str(path.relative_to(store.folder())),'sha256':hashlib.sha256(content).hexdigest()}
        store.save_item(identifier,'document',record);result.append({'id':identifier,'name':name,'characters':len(record['text'])})
    return {'items':result}


@router.post('/templates')
async def import_template(file:UploadFile=File(...),label:str=Form('')):
    from .document_templates import register
    return invoke(register,file.filename or '',await file.read(8_000_001),label)


class DocxChanges(BaseModel):
    changes:dict=Field(default_factory=dict)


@router.get('/templates/{identifier}/paragraphs')
def template_paragraphs(identifier:str):
    from .document_templates import docx_paragraphs
    row=store.item(identifier,'template')
    if not row or row['engine']!='docx':raise HTTPException(400,'Choose a DOCX template')
    return {'paragraphs':invoke(docx_paragraphs,store.safe_file(row['path']).read_bytes())}


@router.post('/templates/{identifier}/build-docx')
def build_docx(identifier:str,payload:DocxChanges):
    from .document_templates import build_docx
    row=store.item(identifier,'template')
    if not row or row['engine']!='docx':raise HTTPException(400,'Choose a DOCX template')
    if len(json.dumps(payload.changes))>100000:raise HTTPException(400,'Replacement content too large')
    content=invoke(build_docx,store.safe_file(row['path']).read_bytes(),payload.changes)
    path=store.safe_file('documents/built-'+uuid.uuid4().hex+'.docx');path.parent.mkdir(exist_ok=True);path.write_bytes(content)
    return {'artifact':str(path.relative_to(store.folder())),'template_sha256':row['sha256']}


@router.get('/download')
def download(path:str):
    file=invoke(store.safe_file,path)
    if not file.is_file():raise HTTPException(404,'File not found')
    return FileResponse(file,filename=file.name)


@router.post('/salary')
async def import_salary(file:UploadFile=File(...)):
    from .salary_benchmarks import ingest
    return invoke(ingest,file.filename or '',await file.read(2_000_001))


@router.get('/salary/{identifier}')
def salary(identifier:str,company:str='',role:str='',city:str='',currency:str='',period:str='',basis:str=''):
    from .salary_benchmarks import lookup
    return invoke(lookup,identifier,company,role,city,currency,period,basis)


class NotionConfig(BaseModel):
    target_id:str=Field(max_length=40)
    target_type:Literal['database','data_source']='data_source'
    token:str=Field(default='',max_length=2000)


@router.put('/notion')
def configure_notion(payload:NotionConfig):
    from .notion_sync import configure
    invoke(configure,payload.model_dump());return {'ok':True}


class PortalConfig(BaseModel):
    config:dict


@router.post('/portals')
def register_portal(payload:PortalConfig):
    from .portal_registry import register
    return invoke(register,payload.config)


class PortalProbe(BaseModel):
    query:str=Field(default='internship',max_length=200)


@router.post('/portals/{identifier}/probe')
def probe_portal(identifier:str,payload:PortalProbe):
    from .portal_registry import probe
    return invoke(probe,identifier,payload.query)


class Enabled(BaseModel):enabled:bool


@router.put('/portals/{identifier}')
def enable_portal(identifier:str,payload:Enabled):
    from .portal_registry import enable
    invoke(enable,identifier,payload.enabled);return {'ok':True}


@router.put('/gmail-compose')
def configure_compose(payload:Enabled):
    from .followup_mail import configure_compose
    configure_compose(payload.enabled);return {'ok':True,'reconnect_required':payload.enabled}


class MailPreview(BaseModel):
    task_id:int
    to:str=Field(max_length=320)
    subject:str=Field(max_length=400)
    body:str=Field(max_length=20000)
    message_id:str=Field(default='',max_length=200)


@router.get('/jobs/{job_id}/threads')
def mail_threads(job_id:int):
    from .db import connect
    from email.utils import parseaddr
    with connect() as c:
        rows=[dict(row) for row in c.execute("SELECT message_id,subject,sender,received_at FROM mail_outcomes WHERE job_id=? AND state<>'dismissed' ORDER BY received_at DESC LIMIT 50",(job_id,))]
    return {'items':[{**row,'recipient':parseaddr(row['sender'])[1]} for row in rows]}


@router.post('/mail-preview')
def mail_preview(payload:MailPreview):
    from .followup_mail import preview
    return invoke(preview,payload.task_id,payload.to,payload.subject,payload.body,payload.message_id)


class MailAction(BaseModel):
    token:str=Field(pattern=r'^[0-9a-f]{64}$')
    acknowledged:Literal[True]


@router.post('/mail-draft')
def mail_draft(payload:MailAction):
    from .followup_mail import create_draft
    return invoke(create_draft,payload.token)


@router.post('/mail-send')
def mail_send(payload:MailAction):
    from .followup_mail import send
    return invoke(send,payload.token,payload.acknowledged)


@router.post('/import-ledgers')
async def import_ledgers(files:list[UploadFile]=File(...),write:bool=Form(False)):
    from .tracker_exchange import parse_upload,preview,import_rows
    if len(files)>50:raise HTTPException(400,'Import at most 50 ledgers at a time')
    rows=[]
    for file in files:
        batch=invoke(parse_upload,file.filename or '',await file.read(2_000_001));rows.extend(batch)
        if len(rows)>1000:raise HTTPException(400,'Import at most 1000 total rows')
    return invoke(import_rows,rows) if write else {'rows':invoke(preview,rows)}


@router.get('/reset-preview')
def reset_preview(scope:Literal['profile','documents','all']='profile'):
    from .application_archive import reset_preview
    return invoke(reset_preview,scope)


class Reset(BaseModel):
    scope:Literal['profile','documents','all']
    token:str=Field(pattern=r'^[0-9a-f]{64}$')
    confirmation:Literal['RESET']


@router.post('/reset')
def reset(payload:Reset):
    from .application_archive import reset
    return invoke(reset,payload.scope,payload.token,payload.confirmation)
