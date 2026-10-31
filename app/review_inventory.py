"""One disjoint snapshot of strong-match records, independent of a batch's scope."""
from .db import connect


def snapshot():
    groups={key:[] for key in ('pending','reviewing','needs_information','approved','queued','submitted','not_suitable','errors','inactive')}
    with connect() as c:
        rows=c.execute("SELECT j.*,q.status AS queue_state FROM jobs j LEFT JOIN application_queue q ON q.job_id=j.id WHERE j.decision='keep' ORDER BY j.id")
        for job in rows:
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
    counts={key:len(ids) for key,ids in groups.items()}
    return {'total':sum(counts.values()),'counts':counts,'job_ids':groups}
