"""Candidate-scoped material approvals and durable submission receipts.

Approvals describe immutable copies of the bytes passed to the form filler.
Receipts attest to a browser observation, not delivery to a recruiter's inbox.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .db import connect
from .workspaces import data_dir
from .profile_store import load_profile_raw, select_resume_for_job
from .human_review import review_token


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def private_path(path, directory):
    resolved = Path(path).resolve()
    if (data_dir() / directory).resolve() not in resolved.parents or not resolved.is_file():
        raise ValueError('Application file unavailable')
    return resolved


def context_token(job, raw):
    # Conservative: changes to saved answers, routing, candidate facts or options
    # require another review. Runtime/browser timestamps are not part of raw.
    return digest({'review': review_token(job), 'profile': raw,
                   'job': {k: job.get(k) for k in ('id', 'url', 'title', 'company', 'body', 'snippet',
                                                   'location', 'employment_type', 'search_profile_id')}})


def freeze_materials(job, raw, resume, letter=None, packet=None, inline_text=''):
    documents = []
    for role, source in (('resume', resume), ('letter', letter), ('packet', packet)):
        if not source:
            continue
        source = Path(source).resolve()
        content = source.read_bytes()
        checksum = hashlib.sha256(content).hexdigest()
        target = data_dir() / 'material_versions' / (checksum + source.suffix.lower())
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or file_hash(target) != checksum:
            temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
            temporary.write_bytes(content)
            temporary.replace(target)
        documents.append({'role': role, 'name': source.name, 'source': str(source),
                          'path': str(target.resolve()), 'sha256': checksum})
    snapshot = {'context': context_token(job, raw), 'documents': documents, 'inline_text': inline_text}
    snapshot['token'] = digest(snapshot)
    return snapshot


def validate_materials(job, raw, snapshot):
    if not isinstance(snapshot, dict) or snapshot.get('context') != context_token(job, raw):
        raise ValueError('Materials or candidate details changed. Prepare and review again.')
    unsigned = {k: v for k, v in snapshot.items() if k != 'token'}
    if snapshot.get('token') != digest(unsigned):
        raise ValueError('Material review unavailable. Prepare again.')
    resume, _ = select_resume_for_job(job, raw)
    docs = snapshot.get('documents', [])
    if not isinstance(docs, list) or not docs or any(not isinstance(d, dict) for d in docs):
        raise ValueError('Material review unavailable. Prepare again.')
    if not resume or not any(d['role'] == 'resume' and Path(d['source']) == resume.resolve() for d in docs):
        raise ValueError('Selected CV changed. Prepare and review again.')
    for document in docs:
        sealed = private_path(document['path'], 'material_versions')
        if file_hash(sealed) != document['sha256'] or file_hash(document['source']) != document['sha256']:
            raise ValueError('Application file changed. Prepare and review again.')
    if snapshot.get('inline_text'):
        from .cover_letter import letter_paths
        state = json.loads(letter_paths(job['id'])[0].read_text(encoding='utf-8'))
        if state.get('letter') != snapshot['inline_text']:
            raise ValueError('Cover letter changed. Prepare and review again.')


def get_job(job_id):
    with connect() as conn:
        row = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
    if not row:
        raise KeyError(job_id)
    return dict(row)


def prepared_snapshot(job):
    path = private_path(job.get('fill_audit_path') or '', 'application_audits')
    audit = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(audit, dict) or audit.get('job_id') != job['id']:
        raise ValueError('Material review unavailable. Prepare again.')
    if not isinstance(audit.get('materials'), dict):
        raise ValueError('Material review unavailable. Prepare again.')
    return audit['materials']


def is_approved(job, raw, snapshot):
    try:
        validate_materials(job, raw, snapshot)
    except (ValueError, OSError, KeyError, TypeError):
        return False
    with connect() as conn:
        return conn.execute('SELECT 1 FROM material_approvals WHERE job_id=? AND token=?',
                            (job['id'], snapshot['token'])).fetchone() is not None


def material_status(job_id):
    job = get_job(job_id)
    try:
        snapshot = prepared_snapshot(job)
    except (ValueError, OSError, KeyError, TypeError):
        return {'status': 'missing', 'documents': []}
    try:
        validate_materials(job, load_profile_raw(), snapshot)
    except (ValueError, OSError, KeyError, TypeError):
        return {'status': 'stale', 'documents': []}
    return {'status': 'approved' if is_approved(job, load_profile_raw(), snapshot) else 'pending',
            'token': snapshot['token'], 'inline_text': snapshot.get('inline_text', ''),
            'documents': [{'role': d['role'], 'name': d['name'], 'sha256': d['sha256'],
                           'url': f'/api/jobs/{job_id}/materials/{d["role"]}'} for d in snapshot['documents']]}


def approve_materials(job_id, token):
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise KeyError(job_id)
        job = dict(row)
        if job['application_status'] not in {'prefilled', 'needs_human'}:
            raise ValueError('Wait for preparation to finish before reviewing materials.')
        snapshot = prepared_snapshot(job)
        validate_materials(job, load_profile_raw(), snapshot)
        if snapshot['token'] != token:
            raise ValueError('Materials changed. Reload and review again.')
        conn.execute('INSERT OR IGNORE INTO material_approvals(job_id,token) VALUES(?,?)', (job_id, token))


def has_dispatch(job_id):
    with connect() as conn:
        return conn.execute('SELECT 1 FROM submission_attempts WHERE job_id=?', (job_id,)).fetchone() is not None


def begin_dispatch(job_id, snapshot):
    # Commit before clicking. A crash or timeout must never make retry look safe.
    job = get_job(job_id)
    if not is_approved(job, load_profile_raw(), snapshot):
        raise ValueError('Review the current application materials before sending.')
    attempt = uuid.uuid4().hex
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT application_status FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row or row['application_status'] in {'submitted', 'submitted_verified', 'withdrawn'}:
            raise ValueError('Application is already closed.')
        if conn.execute('SELECT 1 FROM submission_attempts WHERE job_id=?', (job_id,)).fetchone():
            raise ValueError('A send was already initiated. Check the recruiter site before any retry.')
        conn.execute('INSERT INTO submission_attempts(id,job_id,material_token) VALUES(?,?,?)',
                     (attempt, job_id, snapshot['token']))
    return attempt


def record_verified(job_id, attempt, result):
    text = result.get('confirmation_text', '')
    pattern = result.get('reason', '').removeprefix('confirmation_text:')
    if result.get('status') != 'verified' or not result.get('reason', '').startswith('confirmation_text:') or not re.search(pattern, text, re.I | re.S):
        raise ValueError('No observed submission confirmation')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM submission_attempts WHERE id=? AND job_id=?', (attempt, job_id)).fetchone()
        if not row or row['receipt_json']:
            raise ValueError('Submission attempt unavailable or already recorded')
        receipt = {'job_id': job_id, 'attempt_id': attempt, 'material_token': row['material_token'],
                   'observed_at': datetime.now(timezone.utc).isoformat(), 'url': result.get('confirmation_url', ''),
                   'confirmation_text': text, 'reason': result['reason']}
        target = data_dir() / 'submission_receipts' / f'{attempt}.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
        conn.execute('UPDATE submission_attempts SET receipt_json=?,receipt_path=?,receipt_hash=? WHERE id=?',
                     (json.dumps(receipt), str(target.resolve()), file_hash(target), attempt))
        # A user's later recruiter response or withdrawal must survive a late worker.
        changed = conn.execute("""UPDATE jobs SET application_status='submitted_verified',application_step='completed',
                   tracker_stage='submitted',last_application_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND application_status NOT IN ('submitted','submitted_verified','withdrawn')
                   AND tracker_stage NOT IN ('screening','interview','offer','rejected','withdrawn')""", (job_id,)).rowcount
        if changed:
            conn.execute("INSERT INTO applications(job_id,status,note) VALUES(?,'submitted_verified',?)", (job_id, result['reason']))
            conn.execute("INSERT INTO application_stage_events(job_id,stage,note) VALUES(?,'submitted',?)", (job_id, 'Browser confirmation with a saved receipt'))
            conn.execute("UPDATE application_queue SET status='done',note='submitted_verified',finished_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE job_id=?", (job_id,))


def verification_state(job_id, status):
    if status != 'submitted_verified':
        return 'self_reported' if status == 'submitted' else ''
    return 'verified' if submission_receipt(job_id) else 'unverified'


def submission_receipt(job_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM submission_attempts WHERE job_id=? AND receipt_hash<>'' ORDER BY created_at DESC LIMIT 1", (job_id,)).fetchone()
    if row:
        try:
            path = private_path(row['receipt_path'], 'submission_receipts')
            if file_hash(path) == row['receipt_hash'] and json.loads(path.read_text(encoding='utf-8')) == json.loads(row['receipt_json']):
                return json.loads(row['receipt_json'])
        except (OSError, ValueError, TypeError):
            pass
    return None
