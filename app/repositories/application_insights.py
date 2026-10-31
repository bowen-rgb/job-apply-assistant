"""Candidate-scoped application activities and reviewable mail evidence."""
from datetime import datetime, timezone
from ..db import connect
from ..application_intelligence import classify_response, has_term, parsed_date, new_message_text
from .jobs import JobRepository


def activities(job_id=None):
    with connect() as conn:
        where, args = (' WHERE job_id=?', (job_id,)) if job_id else ('', ())
        return [dict(row) for row in conn.execute('SELECT * FROM application_activities'+where+' ORDER BY occurred_at,id', args)]


def add_activity(job_id, kind, note, occurred_at):
    with connect() as conn:
        job = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise KeyError(job_id)
        if kind == 'followup_sent' and (job['application_status'] not in {'submitted', 'submitted_verified'}
                                       or job['tracker_stage'] in {'rejected', 'withdrawn', 'offer', 'hired', 'offer_declined'}):
            raise ValueError('Only an open submitted application can have a follow-up')
        conn.execute('INSERT INTO application_activities(job_id,kind,note,occurred_at) VALUES(?,?,?,?)',
                     (job_id, kind, note, occurred_at))


def proposals():
    with connect() as conn:
        return [dict(row) for row in conn.execute('''SELECT m.*,j.company,j.title FROM mail_outcomes m
             LEFT JOIN jobs j ON j.id=m.job_id WHERE m.state='pending' ORDER BY m.received_at DESC LIMIT 200''')]


def stage_allowed(current, signal):
    if current in {'rejected', 'withdrawn', 'hired', 'offer_declined'}:
        return False
    if current == 'offer' and signal != 'offer':
        return False
    if current == 'interview' and signal in {'ack', 'screening'}:
        return False
    return True


def stage_for(signal):
    return 'submitted' if signal == 'ack' else signal


def ingest_message(message, jobs):
    """Full body supplied by Gmail reader; previews never update the tracker."""
    text = message['text']
    result = classify_response(text)
    if result['signal'] in {'unknown', 'autoreply'}:
        return 'ignored'
    opening = new_message_text(text)[:4000]
    candidates = [j for j in jobs if j.get('company') and has_term(opening, j['company'])]
    if len(candidates) > 1:
        exact = [j for j in candidates if has_term(opening, j.get('title', ''))]
        if len(exact) == 1:
            candidates = exact
    job = candidates[0] if len(candidates) == 1 else None
    reason = ''
    if not job:
        reason = 'ambiguous_application' if candidates else 'unmatched_application'
    elif result['signal'] == 'conflict' or not stage_allowed(job['tracker_stage'], result['signal']):
        reason = 'conflicting_signal'
    elif (parsed_date(job.get('last_application_at')) and
          parsed_date(message['received_at']) < parsed_date(job['last_application_at'])):
        reason = 'conflicting_signal'
    elif result['signal'] != 'ack' and job['application_status'] not in {'submitted', 'submitted_verified'}:
        reason = 'unconfirmed_submission'
    with connect() as conn:
        inserted = conn.execute('''INSERT OR IGNORE INTO mail_outcomes
           (message_id,thread_id,job_id,signal,evidence,subject,sender,received_at,reason,expected_stage,expected_status)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
           (message['id'], message.get('thread_id', ''), job['id'] if job else None, result['signal'],
            result['evidence'], message.get('subject', '')[:400], message.get('sender', '')[:400],
            message['received_at'], reason, job['tracker_stage'] if job else '', job['application_status'] if job else '')).rowcount
    return 'proposed' if inserted else 'duplicate'


def confirm_proposals(ids, accept):
    """Atomic all-or-nothing approval; stale/conflicting proposals cannot overwrite history."""
    repo = JobRepository()
    with connect() as conn:
        for identifier in dict.fromkeys(ids):
            row = conn.execute('SELECT * FROM mail_outcomes WHERE message_id=?', (identifier,)).fetchone()
            if not row:
                raise KeyError(identifier)
            if row['state'] != 'pending':
                continue
            if not accept:
                conn.execute("UPDATE mail_outcomes SET state='dismissed' WHERE message_id=?", (identifier,))
                continue
            if row['reason'] or not row['job_id']:
                raise ValueError('Resolve ambiguous or conflicting evidence manually')
            job = conn.execute('SELECT * FROM jobs WHERE id=?', (row['job_id'],)).fetchone()
            if not job or job['tracker_stage'] != row['expected_stage'] or job['application_status'] != row['expected_status']:
                raise ValueError('Application changed since this proposal; review its history first')
            signal = row['signal']
            note = f"{row['received_at']} · {row['sender']} · {row['subject']} · {row['evidence']} · Gmail:{identifier}"
            # An acknowledgment may prove a manually sent, previously unrecorded application.
            if job['application_status'] not in {'submitted', 'submitted_verified'}:
                if signal != 'ack' or job['application_status'] == 'withdrawn':
                    raise ValueError('Confirm actual submission before recording this recruiter response')
                repo.track_in(conn, job['id'], 'submitted', note, source='email')
                conn.execute('UPDATE jobs SET last_application_at=? WHERE id=?', (row['received_at'], job['id']))
            if signal != 'ack':
                repo.track_in(conn, job['id'], stage_for(signal), note, source='email')
            conn.execute('''INSERT INTO application_activities(job_id,kind,note,source,occurred_at)
                            VALUES(?,?,?,'email',?)''', (job['id'], 'ack' if signal == 'ack' else 'response', note, row['received_at']))
            conn.execute("UPDATE mail_outcomes SET state='confirmed' WHERE message_id=?", (identifier,))
