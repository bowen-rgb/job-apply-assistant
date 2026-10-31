"""Run a bounded native career task using the existing owned-worker runtime."""
import json
from pathlib import Path
import sys
import uuid
from . import capability_store as store
from .worker_runtime import check_cancelled,Cancelled

TASK_KINDS={'tailor_cv','interview','upskill','research','profile_expand','search_plan','calibration','followup_draft',
            'rank','portal_analyze','template_test','pdf_check','archive','model_check','source_check','notion_check','notion_sync','mock_turn','linkedin_scan','linkedin_triage'}


def run(identifier):
    task=store.task(identifier)
    if task['state']!='queued':raise ValueError('Task already started')
    store.update_task(identifier,'running');args=task['request'];backend=args.get('backend','chatgpt');job_id=task['job_id']
    workspace=store.safe_file('tasks/'+str(identifier));workspace.mkdir(parents=True,exist_ok=True)
    try:
        from . import career_intelligence as career
        kind=task['kind'];check_cancelled()
        if kind=='tailor_cv':result=career.tailor_cv(job_id,backend,workspace,args.get('template_id',''))
        elif kind=='interview':result=career.prepare_interview(job_id,backend,workspace,args.get('stage','technical'))
        elif kind=='mock_turn':result=career.mock_turn(int(args['parent_task']),str(args.get('answer',''))[:20000],backend,workspace)
        elif kind=='upskill':result=career.upskill(job_id,backend,workspace)
        elif kind=='followup_draft':result=career.draft_followup(job_id,backend,workspace)
        elif kind=='research':
            from .db import connect
            with connect() as c:row=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if not row:raise ValueError('Job not found')
            result=career.company_research(dict(row))
        elif kind=='linkedin_scan':
            from .linkedin_discovery import scan
            result=scan(args.get('queries',[]),args.get('location','Île-de-France, France'),args.get('country','FR'),args.get('only','all'))
        elif kind=='linkedin_triage':
            from .linkedin_discovery import triage
            result=triage(int(args['parent_task']),backend,workspace)
        elif kind=='profile_expand':result=career.profile_expand(args.get('document_ids',[]),backend,workspace)
        elif kind in {'search_plan','calibration'}:
            from .profile_store import load_profile_raw
            payload={'profile':load_profile_raw()}
            if kind=='calibration':
                from .application_archive import calibration_context
                payload['outcomes']=calibration_context()
            result=career.model('Propose an evidence-based job-search plan or outcome calibration. Return {"roles":[],"queries":[],"transferable_skills":[],"lessons":[],"suggested_rules":[],"questions":[]}. Do not overwrite preferences, assume a rejection cause, or invent candidate facts. Unknown reasons stay unknown.',payload,backend,workspace,kind)
        elif kind=='rank':
            import hashlib
            from .capability_actions import job_fingerprint
            from .reviewer import build_review_packet,build_prompt,validate_review,apply_local_guardrails
            from .profile_store import runtime_profile
            from .application_intelligence import score_evaluation
            from .db import connect
            from .model_backends import ask
            rows=[];profile=runtime_profile()
            for job_id in args.get('job_ids',[])[:100]:
                check_cancelled()
                with connect() as c:raw=c.execute('SELECT * FROM jobs WHERE id=?',(int(job_id),)).fetchone()
                if not raw:continue
                job=dict(raw);review=validate_review(ask(build_prompt(build_review_packet(job,profile)),backend,workspace=workspace,purpose='final-review'))
                review=apply_local_guardrails(review,job,profile,None)
                if profile.get('scoring_dimensions'):
                    review['rubric']=score_evaluation(profile['scoring_dimensions'],review['ratings'])
                    if review['rubric']['decision']!='apply' and review['verdict']=='APPLY':review['verdict']='HUMAN_REVIEW'
                rows.append({'job_id':job_id,'company':job['company'],'title':job['title'],'review':review,'fingerprint':job_fingerprint(job)})
            rows.sort(key=lambda row:row['review'].get('rubric',{}).get('score',row['review'].get('confidence',0)),reverse=True)
            result={'ranked':rows,'persisted':False,'profile_fingerprint':hashlib.sha256(json.dumps(profile,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
        elif kind=='portal_analyze':
            from .portal_registry import analyze
            result=analyze(args['url'],backend,workspace)
        elif kind=='template_test':
            from .document_templates import compile_template,pdf_report
            path=compile_template(args['template_id'],workspace/'template-test.pdf',{'NAME':'Template test','CONTACT':'','BODY':'Template compilation test. This is not a candidate CV.'})
            result={'quality':pdf_report(path,max_pages=10),'artifact':str(path.relative_to(store.folder()))}
        elif kind=='pdf_check':
            from .document_templates import pdf_report
            document=store.item(args['document_id'],'document')
            if not document or not document['path'].lower().endswith('.pdf'):raise ValueError('Choose an imported PDF')
            result=pdf_report(store.safe_file(document['path']),max_pages=int(args.get('max_pages',2)))
        elif kind=='archive':
            from .application_archive import archive_job
            result=archive_job(job_id)
        elif kind=='model_check':
            from .model_backends import ask
            result=ask('Return exactly JSON {"ok":true}. Do not use tools or access files.',backend,workspace=workspace,purpose='model-check')
            if result.get('ok') is not True:raise ValueError('Model did not return the expected response')
        elif kind=='source_check':
            from .extended_sources import search
            rows=search(args['source'],args.get('query','internship'),args.get('location','France'),limit=5)
            result={'ok':True,'count':len(rows),'rows':rows}
        elif kind in {'notion_check','notion_sync'}:
            from . import notion_sync
            result=notion_sync.check() if kind=='notion_check' else notion_sync.sync()
        else:raise ValueError('Unknown task')
        check_cancelled()
        (workspace/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        store.update_task(identifier,'ready',result=result)
    except Cancelled as exc:store.update_task(identifier,'cancelled',error=str(exc) or 'Task cancelled')
    except Exception as exc:
        # Never leak provider credentials through request URLs or exception bodies.
        error=str(exc)
        from . import secret_store
        def redact(value):
            nonlocal error
            if isinstance(value,dict):
                for key,child in value.items():
                    if any(word in key.lower() for word in ('key','secret','token','password')) and isinstance(child,str) and len(child)>5:error=error.replace(child,'[redacted]')
                    elif isinstance(child,(dict,list)):redact(child)
            elif isinstance(value,list):
                for child in value:redact(child)
        try:redact(secret_store.read())
        except Exception:pass
        store.update_task(identifier,'error',error=error[:2000])


if __name__=='__main__':run(int(sys.argv[1]))
