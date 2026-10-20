"""Refresh a draft QR request using actual Chrome content; never submit an application."""
import json
import sys
from . import qr_application as qr
from .qr_context import page_context,discover_roles,readiness
from .qr_browser_reader import read_rendered
from .worker_runtime import check_cancelled


def run(identifier):
    row=qr.get_request(identifier)
    if row['state'] not in {'draft','analyzing'}:raise ValueError('qr_already_started')
    payload=json.loads(row['payload'])
    try:
        raw,_,final=read_rendered(payload['final_url'])
        context=page_context(raw,final)
        payload.pop('semantic_ranking',None)
        # Preserve an explicitly provided employer only if the page still lacks a name.
        if context['company'] or not payload.get('company'):
            for key in ('company','company_evidence','company_quote','company_source_url'):payload[key]=context[key]
        payload.update(kind=context['kind'],title=context['title'],role_title=context['role_title'],
                       tasks=context['tasks'],body=context['body'],final_url=final,read_mode='chrome_rendered',search_url=context['search_url'])
        payload['opportunities']=discover_roles(context,read_rendered) if context['kind']=='entry' else []
        check_cancelled()
        payload=qr.complete_context(payload)
        # A grounded semantic pass can resolve nonstandard prose and compare actual CVs.
        from .qr_semantics import enrich
        if payload['kind']!='entry':payload=enrich(payload)
        payload=qr.complete_context(payload)
        chosen,reason=qr.recommend(payload)
        payload.update(resume_id=chosen['id'] if chosen else '',resume_reason=reason)
        payload['inspection_error']=''
    except Exception as exc:
        payload['inspection_error']=str(exc)[:600]
    finally:
        payload=qr.complete_context(payload)
        chosen,reason=qr.recommend(payload)
        manual=next((r for r in qr.list_resumes() if r['id']==payload.get('user_resume_id')),None)
        payload.update(resume_id=manual['id'] if manual else chosen['id'] if chosen else '',resume_reason='qr_resume_manual' if manual else reason)
        with qr.connect() as c:
            c.execute("UPDATE qr_requests SET state='draft',payload=? WHERE id=? AND state IN ('analyzing','draft')",
                      (json.dumps(payload,ensure_ascii=False),identifier))


if __name__=='__main__':run(sys.argv[1])
