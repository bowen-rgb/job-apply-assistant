"""Application outcomes, never discovery decisions or preparation failures."""
from datetime import datetime, timedelta, timezone


def snapshot(jobs, followups, events, now=None):
    now = now or datetime.now(timezone.utc)
    final = {'rejected', 'withdrawn', 'hired', 'offer_declined', 'no_response'}
    sent = lambda j: j.get('application_status') in {'submitted', 'submitted_verified'}
    groups = {
        'waiting': [j for j in jobs if sent(j) and j.get('tracker_stage') not in final | {'screening', 'interview', 'offer'}],
        'responses': [j for j in jobs if sent(j) and j.get('tracker_stage') in {'screening', 'interview', 'offer'}],
        'followups': [j for j in jobs if j['id'] in {r['job_id'] for r in followups}],
        'decide': [j for j in jobs if not sent(j) and j.get('application_status') != 'withdrawn'
                   and j.get('tracker_stage') not in final and j.get('user_action') != 'skipped'
                   and j.get('human_review_status') != 'declined' and j.get('review_verdict') != 'SKIP'
                   and (j.get('decision') in {'keep', 'review'} or j.get('user_action') == 'liked'
                        or j.get('review_verdict') in {'APPLY', 'HUMAN_REVIEW'})
                   and j.get('availability_status') != 'expired'],
        'rejected': [j for j in jobs if sent(j) and j.get('tracker_stage') == 'rejected'],
    }
    by_id = {j['id']: j for j in jobs}
    recent = []
    for event in events:
        stamp = event.get('occurred_at') or event.get('created_at')
        try:
            date = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        job = by_id.get(event.get('job_id'))
        if job and now-timedelta(days=7) <= date <= now:
            recent.append({'job_id': job['id'], 'company': job['company'], 'title': job['title'],
                           'at': date.isoformat(), 'kind': event.get('stage') or event.get('kind'),
                           'note': (event.get('note') or '')[:600]})
    return {'counts': {key: len(rows) for key, rows in groups.items()},
            'job_ids': {key: [j['id'] for j in rows] for key, rows in groups.items()},
            'recent': sorted(recent, key=lambda row: row['at'], reverse=True)[:20]}
