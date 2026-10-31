"""Bounded AI review inside an explicitly requested preparation queue."""
import json

from .db import connect
from .human_review import automatic_token, confirmation_status, automatic_ready
from .profile_store import load_profile_raw
from .reviewer import review_via_chatgpt_web

NOTE = 'Automatic AI review pending'
CONTENT = ('title', 'company', 'location', 'body', 'employment_type', 'start_date', 'end_date', 'valid_through')


class ReviewNeedsInput(ValueError):
    """This item needs candidate input; unrelated queue items can continue."""


def prepare(job_id, stopped=lambda: False):
    profile = load_profile_raw()
    if profile.get('automation', {}).get('chatgpt_web_reviewer', {}).get('enabled') is False:
        raise ValueError('Enable the ChatGPT reviewer before starting automatic review')
    with connect() as conn:
        job = dict(conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())
    if job['application_status'] in {'submitted','submitted_verified','withdrawn'} or job['user_action']=='skipped' or job['tracker_stage'] in {'rejected','withdrawn','hired','offer_declined','no_response'} or job['decision']=='expired' or job['availability_status']=='expired':
        with connect() as conn:
            conn.execute("UPDATE application_queue SET status='cancelled',note='Application is no longer eligible' WHERE job_id=? AND status='queued'", (job_id,))
        return False
    if job.get('human_review_status') == 'declined':
        raise ValueError('This application was declined by the user')
    if automatic_ready(job):
        with connect() as conn:
            conn.execute("UPDATE application_queue SET note='' WHERE job_id=? AND status='queued'",(job_id,))
        return True
    content = [job.get(key) for key in CONTENT]
    for attempt in range(2):
        if stopped():
            return False
        result = review_via_chatgpt_web(job_id)
        if result['verdict'] != 'HUMAN_REVIEW':
            break
    with connect() as conn:
        row = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        queue = conn.execute('SELECT status FROM application_queue WHERE job_id=?', (job_id,)).fetchone()
        if stopped() or not row or not queue or queue['status'] != 'queued':
            return False
        current = dict(row)
        if content != [current.get(key) for key in CONTENT] or profile != load_profile_raw():
            raise ValueError('The posting or profile changed during AI review; review again')
        if current.get('human_review_status') == 'declined':
            raise ValueError('This application was declined by the user')
        if result['verdict'] == 'SKIP':
            conn.execute("UPDATE application_queue SET status='cancelled',note=?,updated_at=CURRENT_TIMESTAMP WHERE job_id=?",
                         (result.get('summary') or 'AI review: do not prepare', job_id))
            return False
        if result['verdict'] != 'APPLY' or current['review_verdict'] != 'APPLY':
            raise ReviewNeedsInput(result.get('summary') or 'AI review still needs missing information or your decision')
        conn.execute('UPDATE jobs SET automatic_review_token=? WHERE id=?', (automatic_token(current), job_id))
        conn.execute("UPDATE application_queue SET note='',updated_at=CURRENT_TIMESTAMP WHERE job_id=?", (job_id,))
    return True
