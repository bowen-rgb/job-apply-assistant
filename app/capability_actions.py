"""Explicit adoption of model proposals; no automatic preference/state changes."""
import hashlib
import json
import uuid
from . import capability_store as store
from .db import connect
from .profile_store import load_profile_raw,save_profile_raw,runtime_profile


def job_fingerprint(job):
    return hashlib.sha256(json.dumps({k:job.get(k) for k in ('title','company','body','url','location')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def accept_rank(identifier,indexes):
    task=store.task(identifier)
    if task['kind']!='rank' or task['state']!='ready':raise ValueError('No ranking ready')
    rows=task['result'].get('ranked',[])
    if not indexes or any(not 0<=i<len(rows) for i in indexes):raise ValueError('Choose valid ranked records')
    profile_hash=hashlib.sha256(json.dumps(runtime_profile(),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if task['result'].get('profile_fingerprint')!=profile_hash:raise ValueError('Profile changed; rank again')
    with connect() as c:
        for i in sorted(set(indexes)):
            row=rows[i];raw=c.execute('SELECT * FROM jobs WHERE id=?',(row['job_id'],)).fetchone()
            if not raw or job_fingerprint(dict(raw))!=row.get('fingerprint'):raise ValueError('Posting changed; rank again')
            review=row['review']
            c.execute('UPDATE jobs SET review_verdict=?,review_confidence=?,review_summary=?,review_json=?,review_revision=?,reviewed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                      (review['verdict'],review['confidence'],review['summary'],json.dumps(review,ensure_ascii=False),uuid.uuid4().hex,row['job_id']))
    return {'updated':len(set(indexes)),'human_confirmation_still_required':True}


def accept_plan(identifier,indexes):
    task=store.task(identifier)
    if task['kind'] not in {'search_plan','calibration'} or task['state']!='ready':raise ValueError('No proposal ready')
    result=task['result'];field='roles' if task['kind']=='search_plan' else 'lessons'
    roles=result.get('roles',[])
    values=roles+result.get('queries',[]) if field=='roles' else result.get('lessons',[])
    if any(not 0<=i<len(values) for i in indexes):raise ValueError('Invalid selection')
    chosen=[values[i] for i in sorted(set(indexes))];raw=load_profile_raw()
    if field=='roles':
        existing=raw.setdefault('preferences',{}).setdefault('roles',[])
        queries=raw.setdefault('automation',{}).setdefault('additional_search_queries',[])
        for index in sorted(set(indexes)):
            value=values[index]
            if not isinstance(value,str) or len(value)>200:raise ValueError('Invalid role proposal')
            target=existing if index<len(roles) else queries
            if value not in target:target.append(value)
        save_profile_raw({'preferences':raw['preferences'],'automation':raw['automation']})
    else:
        lessons=raw.setdefault('career',{}).setdefault('outcome_lessons',[])
        for value in chosen:
            record={'task_id':identifier,'lesson':value}
            if record not in lessons:lessons.append(record)
        save_profile_raw({'career':raw['career']})
    return {'accepted':len(chosen),'field':field}
