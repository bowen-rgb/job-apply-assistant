"""Candidate-owned clarification records; no fabricated answers or form consent reuse."""
import json
from .db import connect
from . import workspaces
from .profile_store import load_profile_raw, save_profile_raw


def snapshot():
    items=[]
    with connect() as conn:
        rows=conn.execute("""SELECT id,title,company,url,review_json,review_summary FROM jobs
            WHERE review_verdict='HUMAN_REVIEW' AND decision='keep' AND user_action<>'skipped'
            AND application_status NOT IN ('submitted','submitted_verified','withdrawn')
            ORDER BY reviewed_at DESC,id DESC""")
        for row in rows:
            job=dict(row)
            try:review=json.loads(job.pop('review_json') or '{}')
            except (ValueError,TypeError):review={}
            if not isinstance(review,dict):review={}
            blockers=review.get('blockers') or []
            if not isinstance(blockers,list):blockers=[]
            questions=[b for b in blockers if isinstance(b,dict) and b.get('question')]
            if not questions:
                legacy=review.get('manual_questions',[])
                questions=[{'kind':'unknown','question':q,'reason':'','evidence':''}
                           for q in legacy if isinstance(q,str)] if isinstance(legacy,list) else []
            if review.get('rubric_error'):
                questions.append({'kind':'evaluation','question':review['rubric_error'],'reason':'','evidence':''})
            job.update(questions=questions,risks=review.get('risks',[]),reasons=review.get('reasons',[]),research_findings=review.get('research_findings',[]))
            items.append(job)
    return {'candidate_id':workspaces.candidate_id(),'items':items,
            'answers':load_profile_raw().get('background',{}).get('review_answers',[])}


def save_answer(payload):
    with workspaces.LOCK:
        if payload.get('candidate_id')!=workspaces.candidate_id():
            raise ValueError('Profile changed. Reopen the clarification window.')
        job_id=payload.get('job_id');question=payload.get('question');answer=payload.get('answer')
        if not isinstance(answer,str) or not answer.strip() or len(answer)>4000:
            raise ValueError('Enter an answer of 1–4000 characters.')
        job=next((j for j in snapshot()['items'] if j['id']==job_id),None)
        gap=next((q for q in job['questions'] if q['question']==question),None) if job else None
        if not gap:raise ValueError('This question changed. Reopen the clarification window.')
        if gap['kind']!='candidate':raise ValueError('Only personal facts can be entered here. Other questions are handled by automatic review.')
        reusable=payload.get('reusable') is True
        if reusable and gap['kind']!='candidate':
            raise ValueError('Posting details, form declarations and evaluation errors cannot be reused as personal facts.')
        profile=load_profile_raw();background=profile.setdefault('background',{})
        answers=background.setdefault('review_answers',[])
        answers[:]=[a for a in answers if not (a.get('question')==question and (a.get('job_id')==job_id or (reusable and a.get('reusable'))))]
        answers.append({'question':question,'answer':answer.strip(),'job_id':job_id,
                        'reusable':reusable,'source':'user_confirmed'})
        save_profile_raw(profile)
        return {'ok':True,'reusable':reusable}
