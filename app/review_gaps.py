"""Candidate-owned clarification records; no fabricated answers or form consent reuse."""
import json
from contextlib import nullcontext
from .db import connect
from . import workspaces
from .profile_store import load_profile_raw, save_profile_raw


def action_sets(items, answers):
    """Distinct actions, counted by jobs; mixed gaps may belong to two actions."""
    groups = {key: [] for key in ('personal_input', 'public_research', 'rereview')}
    for job in items:
        if job['processing']:
            continue
        questions = [q for q in job['questions'] if q.get('blocking') is not False]
        def answered(question):
            return any(isinstance(a, dict) and str(a.get('answer', '')).strip()
                       and a.get('question') == question
                       and (a.get('job_id') == job['id'] or a.get('reusable') is True)
                       for a in answers)
        personal = [q for q in questions if q.get('kind') == 'candidate']
        unanswered = [q for q in personal if not answered(q['question'])]
        if unanswered:
            groups['personal_input'].append(job['id'])
        if any(q.get('kind') == 'posting' for q in questions):
            groups['public_research'].append(job['id'])
        if not unanswered and (any(answered(q['question']) for q in personal)
                               or any(q.get('kind') in {'evaluation', 'unknown'} for q in questions)
                               or not questions):
            groups['rereview'].append(job['id'])
    return {key: {'job_ids': sorted(set(ids)), 'count': len(set(ids))} for key, ids in groups.items()}


def snapshot(connection=None):
    items=[]
    with nullcontext(connection) if connection is not None else connect() as conn:
        rows=conn.execute("""SELECT id,title,company,url,review_json,review_summary,review_verdict,review_revision,reviewed_at FROM jobs
            WHERE review_verdict IN ('HUMAN_REVIEW','QUEUED','RUNNING','ERROR') AND decision='keep' AND user_action<>'skipped'
            AND application_status NOT IN ('submitted','submitted_verified','withdrawn','opening','preparing','preparing_letter')
            AND human_review_status<>'declined' AND availability_status<>'expired'
            AND tracker_stage NOT IN ('rejected','withdrawn','hired','offer_declined','no_response')
            AND NOT EXISTS (SELECT 1 FROM application_queue q WHERE q.job_id=jobs.id)
            ORDER BY reviewed_at DESC,id DESC""")
        for row in rows:
            job=dict(row)
            try:review=json.loads(job.pop('review_json') or '{}')
            except (ValueError,TypeError):review={}
            if not isinstance(review,dict):review={}
            if job['review_verdict']!='HUMAN_REVIEW' and review.get('verdict')!='HUMAN_REVIEW':continue
            job['processing']=job['review_verdict'] in {'QUEUED','RUNNING'}
            job['legacy']=not bool(review.get('preparation_readiness'))
            if job['processing']:
                job['review_summary']=review.get('summary','')
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
    answers = load_profile_raw().get('background',{}).get('review_answers',[])
    return {'candidate_id':workspaces.candidate_id(),'items':items, 'answers':answers,
            'actions':action_sets(items, answers)}


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
        if job['processing']:raise ValueError('This posting is being reviewed. Wait for its updated questions.')
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
