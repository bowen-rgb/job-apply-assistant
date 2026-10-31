"""Agent-independent native CLI. Run python -m app.cli --help.

Reuses the application's records/services; no second tracker or agent framework.
"""
import argparse
import json
from pathlib import Path
import sys


def parser():
    p=argparse.ArgumentParser(description='Job Apply Assistant — native workflows')
    p.add_argument('--candidate',help='Existing candidate ID (default or 12 hex characters)')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('init','doctor','status','list','followups','agents'):
        sub.add_parser(name)
    ui=sub.add_parser('ui');ui.add_argument('--port',type=int,default=8765)
    scan=sub.add_parser('scan');scan.add_argument('--source',action='append',help='Limit to these source IDs')
    scan.add_argument('--preview',action='store_true',help='Show plan without network access')
    task=sub.add_parser('task');task.add_argument('kind');task.add_argument('--job',type=int);task.add_argument('--backend',default='chatgpt')
    task.add_argument('--params',type=Path,help='JSON parameters file');task.add_argument('--run',action='store_true',help='Run here and wait')
    view=sub.add_parser('task-status');view.add_argument('id',type=int)
    cancel=sub.add_parser('cancel');cancel.add_argument('id',type=int)
    accept=sub.add_parser('accept');accept.add_argument('kind',choices=['cv','facts','rank','plan']);accept.add_argument('id',type=int);accept.add_argument('--indexes',type=int,nargs='*',default=[])
    status=sub.add_parser('stage');status.add_argument('job',type=int);status.add_argument('stage');status.add_argument('--note',required=True);status.add_argument('--source',default='manual')
    note=sub.add_parser('note');note.add_argument('job',type=int);note.add_argument('text')
    add=sub.add_parser('add');add.add_argument('--company',required=True);add.add_argument('--title',required=True);add.add_argument('--url',default='');add.add_argument('--location',default='')
    imp=sub.add_parser('import');imp.add_argument('paths',nargs='+',type=Path);imp.add_argument('--write',action='store_true')
    exp=sub.add_parser('export');exp.add_argument('output',type=Path);exp.add_argument('--format',choices=['json','csv','xlsx','md','html'],default='json')
    evaluation=sub.add_parser('eval');evaluation.add_argument('action',choices=['prompt','score','run','pipeline']);evaluation.add_argument('jobs',type=int,nargs='+');evaluation.add_argument('--answer',type=Path);evaluation.add_argument('--backend',default='chatgpt')
    agent=sub.add_parser('agent');agent.add_argument('backend',choices=['chatgpt','compatible','anthropic','ollama','claude','codex','opencode']);agent.add_argument('--check',action='store_true')
    linkedin=sub.add_parser('linkedin');linkedin.add_argument('action',choices=['login','scan','triage']);linkedin.add_argument('--query',action='append');linkedin.add_argument('--location',default='Île-de-France, France');linkedin.add_argument('--only',choices=['jobs','posts','all'],default='all');linkedin.add_argument('--parent',type=int);linkedin.add_argument('--backend',default='chatgpt')
    lint=sub.add_parser('lint');lint.add_argument('file',type=Path);lint.add_argument('--rules',type=Path)
    words=sub.add_parser('keywords');words.add_argument('job',type=int);words.add_argument('terms',nargs='+')
    jd=sub.add_parser('jd');jd.add_argument('url')
    docx=sub.add_parser('docx');docx.add_argument('action',choices=['list','build']);docx.add_argument('file',type=Path);docx.add_argument('--changes',type=Path);docx.add_argument('--output',type=Path)
    template=sub.add_parser('template');template.add_argument('file',type=Path);template.add_argument('--label',default='')
    salary=sub.add_parser('salary');salary.add_argument('file',type=Path)
    archive=sub.add_parser('archive');archive.add_argument('job',type=int)
    reset=sub.add_parser('reset');reset.add_argument('scope',choices=['profile','documents','all']);reset.add_argument('--token');reset.add_argument('--confirm',choices=['RESET'])
    return p


def execute(args):
    from .repositories.jobs import JobRepository
    from . import capability_store as store
    from .profile_store import runtime_profile,load_profile_raw
    if args.command=='init':
        from .db import init_db
        from .profile_store import ensure_profile
        init_db();ensure_profile();store.init();return {'ok':True}
    if args.command in {'doctor','agents'}:
        import shutil
        from .model_backends import status
        from .extended_sources import status as sources
        return {'models':status(),'sources':sources(),'compilers':{key:bool(shutil.which(key)) for key in ('xelatex','pdflatex','typst','pdftotext')},'candidate':__import__('app.workspaces',fromlist=['candidate_id']).candidate_id()}
    if args.command=='ui':
        from urllib.request import urlopen
        import webbrowser
        url='http://127.0.0.1:'+str(args.port)
        existing=None
        try:
            with urlopen(url+'/api/runtime',timeout=3) as response:existing=json.load(response)
        except OSError:pass
        if existing is not None:
            from .workspaces import storage_root
            if not isinstance(existing,dict) or existing.get('application')!='job-apply-assistant' or not existing.get('workspace') or Path(existing['workspace']).resolve()!=storage_root():
                raise ValueError('This port belongs to another application or data folder. Use the existing application or choose a different port.')
            webbrowser.open(url);return {'url':url,'reused_backend':True}
        import uvicorn
        return uvicorn.run('app.main:app',host='127.0.0.1',port=args.port)
    if args.command=='list':return JobRepository().list()
    if args.command=='status':
        from .queue_manager import status
        from .scan_manager import status as scanning
        return {'queue':status(),'scan':scanning(),'tasks':store.tasks()}
    if args.command=='followups':
        from .application_intelligence import followup_status
        from .repositories.application_insights import activities
        return [{'job_id':row['id'],**result} for row in JobRepository().pipeline() if (result:=followup_status(row,[*JobRepository().stage_events(row['id']),*activities(row['id'])],(load_profile_raw().get('insights') or {}).get('follow_up'))) and result.get('due')]
    if args.command=='scan':
        profile=runtime_profile()
        if args.source:profile['enabled_sources']=args.source;profile['capability_source_filter']=args.source
        if args.preview:return {'roles':profile.get('preferred_roles',[]),'sources':profile.get('enabled_sources',[]),'network_started':False}
        from .scan_manager import start,status
        import time
        start(profile)
        while status().get('running'):time.sleep(.2)
        return status()
    if args.command=='task':
        from .capabilities_routes import submit_task,TaskRequest
        params=json.loads(args.params.read_text(encoding='utf-8')) if args.params else {}
        payload=TaskRequest(kind=args.kind,job_id=args.job,backend=args.backend,params=params)
        result=submit_task(payload,background=not args.run)
        if not args.run:return result
        from .capability_worker import run
        run(result['id']);return store.task(result['id'])
    if args.command=='agent':
        from .capabilities_routes import choose_model,ModelChoice,submit_task,TaskRequest
        choose_model(ModelChoice(backend=args.backend))
        return submit_task(TaskRequest(kind='model_check',backend=args.backend)) if args.check else {'backend':args.backend}
    if args.command=='eval':
        from .reviewer import build_review_packet,build_prompt,validate_review,apply_local_guardrails
        from .db import connect
        if args.action in {'run','pipeline'}:
            from .capabilities_routes import submit_task,TaskRequest
            return submit_task(TaskRequest(kind='rank',backend=args.backend,params={'job_ids':args.jobs}))
        with connect() as c:raw=c.execute('SELECT * FROM jobs WHERE id=?',(args.jobs[0],)).fetchone()
        if not raw:raise ValueError('Job not found')
        job=dict(raw);profile=runtime_profile()
        if args.action=='prompt':return {'prompt':build_prompt(build_review_packet(job,profile))}
        if not args.answer:raise ValueError('Specify --answer with the model JSON file')
        result=validate_review(json.loads(args.answer.read_text(encoding='utf-8')))
        if profile.get('scoring_dimensions'):
            from .application_intelligence import score_evaluation
            result['rubric']=score_evaluation(profile['scoring_dimensions'],result.get('ratings',{}))
            if result['rubric']['decision']!='apply' and result['verdict']=='APPLY':result['verdict']='HUMAN_REVIEW'
        return apply_local_guardrails(result,job,profile,None)
    if args.command=='linkedin':
        if args.action=='login':
            from .linkedin_discovery import login
            return login()
        from .capabilities_routes import submit_task,TaskRequest
        params={'queries':args.query or [],'location':args.location,'only':args.only} if args.action=='scan' else {'parent_task':args.parent}
        return submit_task(TaskRequest(kind='linkedin_scan' if args.action=='scan' else 'linkedin_triage',backend=args.backend,params=params))
    if args.command=='task-status':return store.task(args.id)
    if args.command=='cancel':
        from .capabilities_routes import cancel_task
        return cancel_task(args.id)
    if args.command=='accept':
        if args.kind=='cv':
            from .career_intelligence import adopt_cv
            return adopt_cv(args.id)
        if args.kind=='facts':
            from .career_intelligence import accept_facts
            return accept_facts(args.id,args.indexes)
        from .capability_actions import accept_plan,accept_rank
        return (accept_rank if args.kind=='rank' else accept_plan)(args.id,args.indexes)
    if args.command=='stage':JobRepository().track(args.job,args.stage,args.note,source=args.source);return {'ok':True}
    if args.command=='note':
        from .repositories.application_insights import add_activity
        from datetime import date
        return add_activity(args.job,'note',args.text,date.today().isoformat())
    if args.command in {'import','add'}:
        from .tracker_exchange import parse_upload,preview,import_rows
        if args.command=='add':return import_rows([{'company':args.company,'title':args.title,'url':args.url,'location':args.location}])
        paths=[]
        for path in args.paths:paths.extend(sorted(p for p in path.rglob('*') if p.suffix.lower() in {'.csv','.json','.xlsx','.tsv','.md','.db','.sqlite','.sqlite3'})) if path.is_dir() else paths.append(path)
        if len(paths)>50:raise ValueError('At most 50 files per import')
        rows=[]
        for path in paths:
            if path.stat().st_size>2_000_000:raise ValueError('Each ledger must be at most 2 MB')
            rows.extend(parse_upload(path.name,path.read_bytes()))
            if len(rows)>1000:raise ValueError('At most 1000 rows')
        return import_rows(rows) if args.write else preview(rows)
    if args.command=='export':
        from .tracker_exchange import export_rows
        content,_=export_rows(JobRepository().pipeline(),args.format);args.output.write_bytes(content);return {'output':str(args.output.resolve())}
    if args.command=='lint':
        from .writing_lint import lint
        return lint(args.file.read_text(encoding='utf-8'),json.loads(args.rules.read_text(encoding='utf-8')) if args.rules else {})
    if args.command=='keywords':
        from .insights_routes import coverage,Coverage
        return coverage(args.job,Coverage(keywords=args.terms))
    if args.command=='jd':
        from .pfe_discovery import read_public
        from .vendor.job_search.posting_guard import guard
        raw,_,url=read_public(args.url);text,integrity=guard(raw.decode('utf-8',errors='replace'),'html');return {'url':url,'text':text,'integrity':integrity}
    if args.command=='docx':
        from .document_templates import docx_paragraphs,build_docx
        if args.action=='list':return docx_paragraphs(args.file.read_bytes())
        if not args.changes or not args.output:raise ValueError('Specify --changes and --output')
        if args.file.resolve()==args.output.resolve():raise ValueError('Keep the original template; choose a new output path')
        args.output.write_bytes(build_docx(args.file.read_bytes(),json.loads(args.changes.read_text(encoding='utf-8'))));return {'output':str(args.output.resolve())}
    if args.command=='template':
        from .document_templates import register
        return register(args.file.name,args.file.read_bytes(),args.label)
    if args.command=='salary':
        from .salary_benchmarks import ingest
        return ingest(args.file.name,args.file.read_bytes())
    if args.command=='archive':
        from .application_archive import archive_job
        return archive_job(args.job)
    if args.command=='reset':
        from .application_archive import reset,reset_preview
        return reset(args.scope,args.token,args.confirm) if args.token and args.confirm else reset_preview(args.scope)


def main(argv=None):
    args=parser().parse_args(argv)
    if args.candidate:
        from .workspaces import CURRENT,validate,candidates
        validate(args.candidate)
        if args.candidate not in {row['id'] for row in candidates()}:raise ValueError('Unknown candidate')
        CURRENT.set(args.candidate)
    try:
        result=execute(args);print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
        return 1 if isinstance(result,dict) and result.get('state') in {'error','cancelled'} else 0
    except Exception as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
