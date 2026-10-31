"""One-way projection of the native tracker into an explicitly configured Notion database."""
import json
import re
import uuid
import time
from urllib.error import HTTPError
from urllib.request import Request,build_opener,HTTPRedirectHandler
from . import secret_store,capability_store as store
from .repositories.jobs import JobRepository

VERSION='2026-03-11'


def configure(payload):
    if payload.get('target_type','database') not in {'database','data_source'}:raise ValueError('Invalid Notion target type')
    target=str(payload.get('target_id','')).replace('-','').strip()
    if not re.fullmatch('[a-fA-F0-9]{32}',target):raise ValueError('Use the Notion database or data-source ID')
    def save(data):
        previous=data.get('notion',{})
        data['notion']={'target_id':target,'token':str(payload.get('token') or previous.get('token','')).strip(),
                        'target_type':payload.get('target_type','database')}
    secret_store.update(save)


def status():
    cfg=secret_store.read().get('notion',{})
    return {'configured':bool(cfg.get('token') and cfg.get('target_id')),'target_id':cfg.get('target_id',''),
            'target_type':cfg.get('target_type','database'),'version':VERSION}


def request(path,body=None,method='GET'):
    cfg=secret_store.read().get('notion',{})
    if not cfg.get('token'):raise ValueError('Configure Notion first')
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):raise ValueError('Notion redirect refused')
    req=Request('https://api.notion.com/v1/'+path,method=method,data=json.dumps(body).encode() if body is not None else None,
                headers={'Authorization':'Bearer '+cfg['token'],'Notion-Version':VERSION,'Content-Type':'application/json'})
    for attempt in range(3):
        try:
            with build_opener(NoRedirect()).open(req,timeout=30) as response:return json.loads(response.read(2_000_000))
        except HTTPError as exc:
            if exc.code!=429 or attempt==2:raise
            try:delay=min(10,max(1,float(exc.headers.get('Retry-After','1'))))
            except ValueError:delay=1
            time.sleep(delay)


def target(read=request):
    cfg=secret_store.read().get('notion',{})
    if not cfg.get('target_id'):raise ValueError('Configure Notion first')
    if cfg.get('target_type','database')=='database':
        database=read('databases/'+cfg['target_id'])
        sources=database.get('data_sources',[])
        if len(sources)!=1:raise ValueError('Choose the specific data-source ID from this multi-source database')
        identifier=sources[0]['id']
    else:identifier=cfg['target_id']
    data=read('data_sources/'+identifier)
    return identifier,data


def check(read=request):
    identifier,data=target(read)
    return {'ok':True,'data_source_id':identifier,'properties':data.get('properties',{}),'url':data.get('url','')}


def sync(read=request):
    from filelock import FileLock,Timeout
    try:
        with FileLock(str(store.folder()/'notion-sync.lock'),timeout=0):return _sync(read)
    except Timeout as exc:raise ValueError('A Notion sync is already running for this candidate') from exc


def _sync(read=request):
    identifier,data=target(read);properties=data.get('properties',{})
    title=next((name for name,prop in properties.items() if prop.get('type')=='title'),None)
    if not title:raise ValueError('Notion target has no title property')
    required={'JAA ID':{'rich_text':{}},'Company':{'rich_text':{}},'Stage':{'rich_text':{}},'Job URL':{'url':{}},'Last contact':{'rich_text':{}}}
    missing={name:config for name,config in required.items() if name not in properties}
    if missing:read('data_sources/'+identifier,{'properties':missing},'PATCH')
    for name,config in required.items():
        if name in properties and properties[name].get('type')!=next(iter(config)):raise ValueError('Notion property type mismatch: '+name)
    from .workspaces import candidate_id
    namespace=store.item('notion-namespace','sync_config')
    if not namespace:
        store.save_item('notion-namespace','sync_config',{'value':uuid.uuid4().hex})
        namespace=store.item('notion-namespace','sync_config')
    rows=JobRepository().pipeline();counts={'created':0,'updated':0}
    for row in rows:
        from .worker_runtime import check_cancelled,Cancelled
        try:check_cancelled()
        except Cancelled as exc:raise Cancelled('Stopped. Already written to Notion: '+json.dumps(counts)+'. These changes remain; a later sync reuses their stable IDs.') from exc
        key=namespace['value']+':'+candidate_id()+':'+str(row['id'])
        existing=read('data_sources/'+identifier+'/query',{'filter':{'property':'JAA ID','rich_text':{'equals':key}},'page_size':2},'POST').get('results',[])
        if len(existing)>1:raise ValueError('Duplicate Notion rows for '+key+'; resolve them before syncing')
        def rich(value):return {'rich_text':[{'text':{'content':str(value or '')[:1900]}}]}
        props={title:{'title':[{'text':{'content':str(row['title'] or '')[:1900]}}]},'JAA ID':rich(key),'Company':rich(row['company']),
               'Stage':rich(row['tracker_stage']),'Last contact':rich(row.get('last_application_at')),
               'Job URL':{'url':row['url'] if str(row['url'] or '').startswith('https://') else None}}
        if existing:read('pages/'+existing[0]['id'],{'properties':props},'PATCH');counts['updated']+=1
        else:read('pages',{'parent':{'type':'data_source_id','data_source_id':identifier},'properties':props},'POST');counts['created']+=1
    return counts
