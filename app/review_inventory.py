"""One disjoint snapshot of strong-match records, independent of a batch's scope."""
from .db import connect
from contextlib import nullcontext
import hashlib
import json


def snapshot(connection=None):
    groups={key:[] for key in ('pending','reviewing','needs_information','approved','queued','submitted','not_suitable','errors','inactive')}
    reviewed=[]
    with nullcontext(connection) if connection is not None else connect() as c:
        rows=c.execute("""SELECT j.*,q.status AS queue_state,
            EXISTS(SELECT 1 FROM applications a WHERE a.job_id=j.id AND a.status='chatgpt_review') AS has_review
            FROM jobs j LEFT JOIN application_queue q ON q.job_id=j.id ORDER BY j.id""")
        for job in rows:
            # A new attempt can temporarily set RUNNING/ERROR; prior completed reviews remain counted.
            if job['has_review'] or job['reviewed_at'] or job['review_verdict'] in {'APPLY','HUMAN_REVIEW','SKIP'}:
                reviewed.append(job['id'])
            if job['decision'] != 'keep':
                continue
            if job['application_status'] in {'submitted','submitted_verified'}:key='submitted'
            elif (job['user_action']=='skipped' or job['human_review_status']=='declined' or job['availability_status']=='expired'
                  or job['application_status']=='withdrawn' or job['queue_state']=='cancelled'
                  or job['tracker_stage'] in {'rejected','withdrawn','hired','offer_declined','no_response'}):key='inactive'
            elif job['queue_state'] or job['application_status'] in {'opening','preparing','preparing_letter'}:key='queued'
            elif job['review_verdict']=='SKIP':key='not_suitable'
            elif job['review_verdict'] in {'QUEUED','RUNNING'}:key='reviewing'
            elif job['review_verdict']=='HUMAN_REVIEW':key='needs_information'
            elif job['review_verdict']=='APPLY':key='approved'
            elif job['review_verdict']=='ERROR':key='errors'
            else:key='pending'
            groups[key].append(job['id'])
        queue_counts={row['status']:row['n'] for row in c.execute('SELECT status,COUNT(*) n FROM application_queue GROUP BY status')}
        queue_rows=[tuple(row) for row in c.execute('''SELECT q.job_id,q.status,q.attempts,q.note,q.updated_at,
            j.application_status,j.application_step,j.review_revision FROM application_queue q
            JOIN jobs j ON j.id=q.job_id ORDER BY q.job_id''')]
        queue_revision=hashlib.sha256(json.dumps(queue_rows,ensure_ascii=False).encode()).hexdigest()
    counts={key:len(ids) for key,ids in groups.items()}
    return {'total':sum(counts.values()),'counts':counts,'job_ids':groups,
            'cumulative':{'reviewed':len(reviewed),'reviewed_job_ids':reviewed,
                          'queued':counts['queued'],'submitted':counts['submitted'],
                          'not_suitable':counts['not_suitable'],'needs_information':counts['needs_information']},
            'queue_total':sum(queue_counts.values()),'queue_counts':queue_counts,'queue_revision':queue_revision}
