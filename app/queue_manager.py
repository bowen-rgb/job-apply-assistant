from __future__ import annotations

import threading
import time
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from .browser import launch_apply
from .db import connect
from .worker_runtime import cancel

_lock = threading.Lock()
_stop = threading.Event()
_state: dict[str, Any] = {'paused': False, 'running': False, 'current_job_id': None, 'started_at': '', 'message': ''}
_terminal = {'prefilled', 'needs_human', 'submitted', 'submitted_verified', 'error', 'withdrawn'}


def _set(**kwargs):
    with _lock:
        _state.update(kwargs)


def status() -> dict[str, Any]:
    with connect() as c:
        counts = {r['status']: r['n'] for r in c.execute('SELECT status,COUNT(*) n FROM application_queue GROUP BY status').fetchall()}
        rows = c.execute('''SELECT q.*,j.title,j.company,j.location,j.review_verdict,j.application_status,j.tracker_stage,
                            COALESCE((SELECT note FROM applications a WHERE a.job_id=q.job_id AND a.status='apply_error' ORDER BY a.id DESC LIMIT 1),'') AS failure_reason
                            FROM application_queue q JOIN jobs j ON j.id=q.job_id
                            ORDER BY CASE q.status WHEN 'running' THEN 0 WHEN 'queued' THEN 1 WHEN 'waiting_user' THEN 2 ELSE 3 END,
                                     q.priority ASC,q.id ASC LIMIT 200''').fetchall()
    with _lock:
        base = dict(_state)
    base['counts'] = counts
    base['items'] = [dict(r) for r in rows]
    for item in base['items']:
        if item['status'] == 'error' and item['note'] in {'error', 'timeout', ''}:
            item['note'] = item['failure_reason'] or item['note']
    return base


def enqueue(job_ids: list[int], priority: int = 100) -> dict[str, Any]:
    ids = []
    for x in job_ids[:100]:
        try:
            n = int(x)
        except Exception:
            continue
        if n > 0 and n not in ids:
            ids.append(n)
    with connect() as c:
        for jid in ids:
            if not c.execute("SELECT id FROM jobs WHERE id=? AND user_action != 'skipped'", (jid,)).fetchone():
                continue
            c.execute('''INSERT INTO application_queue(job_id,status,priority,updated_at)
                         VALUES(?, 'queued', ?, CURRENT_TIMESTAMP)
                         ON CONFLICT(job_id) DO UPDATE SET
                           status=CASE WHEN application_queue.status IN ('done','error','cancelled') THEN 'queued' ELSE application_queue.status END,
                           priority=excluded.priority, updated_at=CURRENT_TIMESTAMP''', (jid, priority))
            c.execute("UPDATE jobs SET tracker_stage=CASE WHEN tracker_stage='' THEN 'queued' ELSE tracker_stage END,updated_at=CURRENT_TIMESTAMP WHERE id=?", (jid,))
    return status()


def remove(job_id: int) -> None:
    cancel('app.apply_worker', job_id)
    with connect() as c:
        row = c.execute('SELECT status FROM application_queue WHERE job_id=?', (job_id,)).fetchone()
        if row and row['status'] == 'running':
            c.execute("UPDATE application_queue SET status='cancelled',finished_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE job_id=?", (job_id,))
        else:
            c.execute('DELETE FROM application_queue WHERE job_id=?', (job_id,))
        c.execute("UPDATE jobs SET tracker_stage='saved' WHERE id=? AND tracker_stage='queued'", (job_id,))


def clear_finished() -> None:
    with connect() as c:
        c.execute("DELETE FROM application_queue WHERE status IN ('done','error','cancelled')")


def _wait_until_prepared(job_id: int, timeout: int = 240, process=None) -> str:
    end = time.time() + timeout
    last = ''
    while time.time() < end:
        with connect() as c:
            queue = c.execute('SELECT status FROM application_queue WHERE job_id=?', (job_id,)).fetchone()
            if not queue or queue['status'] == 'cancelled':
                return 'cancelled'
            row = c.execute('SELECT application_status FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            return 'error'
        last = row['application_status'] or ''
        if last in _terminal:
            return last
        if process is not None and process.poll() is not None:
            return 'error'
        time.sleep(0.5)
    return last or 'timeout'


def _worker():
    _set(running=True, started_at=datetime.now(timezone.utc).isoformat(), message='Queue worker running')
    try:
        while not _stop.is_set():
            with connect() as c:
                row = c.execute("SELECT * FROM application_queue WHERE status='queued' ORDER BY priority ASC,id ASC LIMIT 1").fetchone()
                if not row:
                    break
                jid = int(row['job_id'])
                c.execute("UPDATE application_queue SET status='running',attempts=attempts+1,started_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE job_id=?", (jid,))
            _set(current_job_id=jid, message=f'Preparing job {jid}')
            if _stop.is_set():
                remove(jid)
                break
            try:
                with connect() as c:
                    existing = c.execute('SELECT application_status,fill_audit_path FROM jobs WHERE id=?', (jid,)).fetchone()
                result = existing['application_status'] if existing else 'error'
                prepared = False
                if existing and result in {'prefilled', 'needs_human'}:
                    try:
                        audit = json.loads(Path(existing['fill_audit_path']).read_text(encoding='utf-8'))
                        documents = audit.get('documents', {})
                        prepared = bool(documents.get('resume_attached') and documents.get('letter_generated'))
                    except (OSError, ValueError, TypeError):
                        pass
                if not prepared and result not in {'submitted', 'submitted_verified', 'withdrawn'}:
                    # Clear stale terminal state before launch so polling cannot
                    # mistake a previous attempt for completion of this one.
                    with connect() as c:
                        c.execute("UPDATE jobs SET application_status='opening',updated_at=CURRENT_TIMESTAMP WHERE id=?", (jid,))
                    process = launch_apply(jid)
                    result = _wait_until_prepared(jid, timeout=600, process=process)
                    if result not in _terminal:
                        cancel('app.apply_worker', jid)
                if result in {'prefilled', 'needs_human'}:
                    qstatus = 'waiting_user'
                elif result in {'submitted', 'submitted_verified', 'withdrawn'}:
                    qstatus = 'done'
                elif result == 'cancelled':
                    qstatus = 'cancelled'
                else:
                    qstatus = 'error'
                with connect() as c:
                    note = result
                    if qstatus == 'error':
                        error = c.execute("SELECT note FROM applications WHERE job_id=? AND status IN ('apply_error','cover_letter_error') ORDER BY id DESC LIMIT 1", (jid,)).fetchone()
                        note = error['note'] if error else result
                    c.execute("UPDATE application_queue SET status=?,note=?,finished_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE job_id=? AND status='running'", (qstatus, note, jid))
            except Exception as exc:
                with connect() as c:
                    c.execute("UPDATE application_queue SET status='error',note=?,finished_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE job_id=? AND status='running'", (str(exc)[:500], jid))
            _set(current_job_id=None, paused=True)
            # Prepare one application per explicit start, then hand control back.
            break
    finally:
        _set(running=False, current_job_id=None)


def start() -> dict[str, Any]:
    already = False
    with _lock:
        already = bool(_state['running'])
        if not already:
            _state.update(running=True, paused=False, message='')
            _stop.clear()
    if not already:
        with connect() as c:
            c.execute("UPDATE application_queue SET status='error',note='Interrupted: retry explicitly',updated_at=CURRENT_TIMESTAMP WHERE status='running'")
        threading.Thread(target=_worker, daemon=True, name='application-queue').start()
    return status()


def stop() -> dict[str, Any]:
    # Prevent another claim before cancelling the current managed task.
    _stop.set()
    with _lock:
        current = _state['current_job_id']
        _state.update(paused=True, message='Stopped by user')
    if current:
        remove(current)
    return status()
