from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

from .browser import launch_apply
from .db import connect

_lock = threading.Lock()
_state: dict[str, Any] = {'running': False, 'current_job_id': None, 'started_at': '', 'message': ''}
_terminal = {'prefilled', 'needs_human', 'submitted', 'submitted_verified', 'error', 'withdrawn'}


def _set(**kwargs):
    with _lock:
        _state.update(kwargs)


def status() -> dict[str, Any]:
    with connect() as c:
        counts = {r['status']: r['n'] for r in c.execute('SELECT status,COUNT(*) n FROM application_queue GROUP BY status').fetchall()}
        rows = c.execute('''SELECT q.*,j.title,j.company,j.location,j.review_verdict,j.application_status,j.tracker_stage
                            FROM application_queue q JOIN jobs j ON j.id=q.job_id
                            ORDER BY CASE q.status WHEN 'running' THEN 0 WHEN 'queued' THEN 1 WHEN 'waiting_user' THEN 2 ELSE 3 END,
                                     q.priority ASC,q.id ASC LIMIT 200''').fetchall()
    with _lock:
        base = dict(_state)
    base['counts'] = counts
    base['items'] = [dict(r) for r in rows]
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
            if not c.execute('SELECT id FROM jobs WHERE id=?', (jid,)).fetchone():
                continue
            c.execute('''INSERT INTO application_queue(job_id,status,priority,updated_at)
                         VALUES(?, 'queued', ?, CURRENT_TIMESTAMP)
                         ON CONFLICT(job_id) DO UPDATE SET
                           status=CASE WHEN application_queue.status IN ('done','error','cancelled') THEN 'queued' ELSE application_queue.status END,
                           priority=excluded.priority, updated_at=CURRENT_TIMESTAMP''', (jid, priority))
            c.execute("UPDATE jobs SET tracker_stage=CASE WHEN tracker_stage='' THEN 'queued' ELSE tracker_stage END,updated_at=CURRENT_TIMESTAMP WHERE id=?", (jid,))
    return status()


def remove(job_id: int) -> None:
    with connect() as c:
        row = c.execute('SELECT status FROM application_queue WHERE job_id=?', (job_id,)).fetchone()
        if row and row['status'] == 'running':
            c.execute("UPDATE application_queue SET status='cancelled',finished_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE job_id=?", (job_id,))
        else:
            c.execute('DELETE FROM application_queue WHERE job_id=?', (job_id,))


def clear_finished() -> None:
    with connect() as c:
        c.execute("DELETE FROM application_queue WHERE status IN ('done','error','cancelled')")


def _wait_until_prepared(job_id: int, timeout: int = 240) -> str:
    end = time.time() + timeout
    last = ''
    while time.time() < end:
        with connect() as c:
            row = c.execute('SELECT application_status FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            return 'error'
        last = row['application_status'] or ''
        if last in _terminal:
            return last
        time.sleep(2.0)
    return last or 'timeout'


def _worker():
    _set(running=True, started_at=datetime.now(timezone.utc).isoformat(), message='Queue worker running')
    try:
        while True:
            with connect() as c:
                row = c.execute("SELECT * FROM application_queue WHERE status='queued' ORDER BY priority ASC,id ASC LIMIT 1").fetchone()
                if not row:
                    break
                jid = int(row['job_id'])
                c.execute("UPDATE application_queue SET status='running',attempts=attempts+1,started_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE job_id=?", (jid,))
            _set(current_job_id=jid, message=f'Preparing job {jid}')
            try:
                launch_apply(jid)
                result = _wait_until_prepared(jid)
                if result in {'prefilled', 'needs_human'}:
                    qstatus = 'waiting_user'
                elif result in {'submitted', 'submitted_verified', 'withdrawn'}:
                    qstatus = 'done'
                else:
                    qstatus = 'error'
                with connect() as c:
                    c.execute("UPDATE application_queue SET status=?,note=?,finished_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE job_id=?", (qstatus, result, jid))
            except Exception as exc:
                with connect() as c:
                    c.execute("UPDATE application_queue SET status='error',note=?,finished_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE job_id=?", (str(exc)[:500], jid))
            _set(current_job_id=None)
    finally:
        _set(running=False, current_job_id=None, message='Queue idle')


def start() -> dict[str, Any]:
    already = False
    with _lock:
        already = bool(_state['running'])
        if not already:
            _state['running'] = True
    if not already:
        threading.Thread(target=_worker, daemon=True, name='application-queue').start()
    return status()
