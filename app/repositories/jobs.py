"""SQLite repository for job and application workflow data.

The repository owns SQL and transaction boundaries. API handlers should deal
with validated contracts and domain outcomes, rather than assembling SQL.
"""

from __future__ import annotations

from typing import Any

from ..contracts import TRACK_STAGES
from ..db import connect
from ..human_review import annotate, can_prepare, confirmation_status, review_token, REVIEWABLE


class JobRepository:
    """Queries and mutations for jobs, applications, queues and stage events."""

    _ORDER = (
        " ORDER BY CASE user_action WHEN 'liked' THEN 0 WHEN 'skipped' THEN 6 "
        "ELSE CASE decision WHEN 'keep' THEN 1 WHEN 'review' THEN 2 "
        "WHEN 'new' THEN 3 WHEN 'low' THEN 4 ELSE 5 END END, "
        "score DESC, discovered_at DESC"
    )

    @staticmethod
    def _row_dict(row: Any) -> dict[str, Any] | None:
        return dict(row) if row else None

    def exists(self, job_id: int) -> bool:
        with connect() as conn:
            return conn.execute('SELECT 1 FROM jobs WHERE id=?', (job_id,)).fetchone() is not None

    def titles(self, job_ids: list[int]) -> list[dict]:
        ids = list(dict.fromkeys(job_ids))
        placeholders = ','.join('?' for _ in ids)
        with connect() as conn:
            return [dict(row) for row in conn.execute(f'SELECT id,title FROM jobs WHERE id IN ({placeholders})', ids).fetchall()]

    def list(self, decision: str | None = None, source: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        args: list[object] = []
        if decision:
            clauses.append('jobs.decision=?')
            args.append(decision)
        if source:
            clauses.append('jobs.provider_key=?')
            args.append(source)
        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        query = (
            "SELECT jobs.*, COALESCE((SELECT status FROM application_queue q "
            "WHERE q.job_id=jobs.id),'') AS queue_status, "
            "COALESCE((SELECT note FROM applications a WHERE a.job_id=jobs.id "
            "AND a.status='apply_error' ORDER BY a.id DESC LIMIT 1),'') AS application_error, "
            "COALESCE((SELECT status FROM applications a WHERE a.job_id=jobs.id "
            "ORDER BY a.id DESC LIMIT 1),'') AS last_workflow_event FROM jobs"
            + where + self._ORDER
        )
        with connect() as conn:
            return [annotate(dict(row)) for row in conn.execute(query, tuple(args)).fetchall()]

    def stats(self) -> dict[str, Any]:
        query = """SELECT
            COALESCE(SUM(CASE WHEN user_action<>'skipped' THEN 1 ELSE 0 END),0) AS total,
            COALESCE(SUM(CASE WHEN decision='keep' AND user_action<>'skipped' THEN 1 ELSE 0 END),0) AS keep_n,
            COALESCE(SUM(CASE WHEN user_action='liked' THEN 1 ELSE 0 END),0) AS liked_n,
            COALESCE(SUM(CASE WHEN review_verdict='APPLY' AND user_action<>'skipped' THEN 1 ELSE 0 END),0) AS apply_n,
            COALESCE(SUM(CASE WHEN review_verdict='HUMAN_REVIEW' AND user_action<>'skipped' THEN 1 ELSE 0 END),0) AS human_n,
            COALESCE(SUM(CASE WHEN decision='expired' OR availability_status='expired' THEN 1 ELSE 0 END),0) AS expired_n,
            COALESCE(SUM(CASE WHEN application_status IN ('submitted','submitted_verified') THEN 1 ELSE 0 END),0) AS submitted_n
            FROM jobs"""
        with connect() as conn:
            result = dict(conn.execute(query).fetchone())
            result['human_n'] = sum(confirmation_status(dict(j)) == 'pending' and j['user_action'] != 'skipped'
                                    and j['application_status'] not in {'submitted', 'submitted_verified', 'withdrawn'}
                                    and j['tracker_stage'] not in {'rejected', 'withdrawn'}
                                    and j['decision'] != 'expired' and j['availability_status'] != 'expired'
                                    for j in conn.execute('SELECT * FROM jobs'))
            return result

    def review_verdict(self, job_id: int) -> str:
        with connect() as conn:
            row = conn.execute('SELECT review_verdict FROM jobs WHERE id=?', (job_id,)).fetchone()
        return str(row['review_verdict'] or '') if row else ''

    def mark_review_queued(self, job_id: int) -> None:
        with connect() as conn:
            if not self._exists_in(conn, job_id):
                raise KeyError(job_id)
            conn.execute("UPDATE jobs SET review_verdict='QUEUED', review_summary='Waiting for ChatGPT web reviewer', updated_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,))

    def analytics(self) -> dict[str, Any]:
        with connect() as conn:
            totals = dict(conn.execute("""SELECT COUNT(*) total,
                COALESCE(SUM(CASE WHEN user_action='liked' THEN 1 ELSE 0 END),0) liked,
                COALESCE(SUM(CASE WHEN review_verdict='APPLY' THEN 1 ELSE 0 END),0) reviewer_apply,
                COALESCE(SUM(CASE WHEN application_status IN ('submitted','submitted_verified') THEN 1 ELSE 0 END),0) submitted
                FROM jobs""").fetchone())
            stages = [dict(row) for row in conn.execute("SELECT tracker_stage stage,COUNT(*) n FROM jobs WHERE tracker_stage<>'' GROUP BY tracker_stage ORDER BY n DESC").fetchall()]
            sources = [dict(row) for row in conn.execute("SELECT provider_key source,COUNT(*) n FROM jobs GROUP BY provider_key ORDER BY n DESC LIMIT 20").fetchall()]
            campaigns = [dict(row) for row in conn.execute("SELECT search_profile_label profile,COUNT(*) n FROM jobs GROUP BY search_profile_label ORDER BY n DESC LIMIT 20").fetchall()]
            queue = [dict(row) for row in conn.execute("SELECT status,COUNT(*) n FROM application_queue GROUP BY status").fetchall()]
        return {'totals': totals, 'stages': stages, 'sources': sources, 'campaigns': campaigns, 'queue': queue}

    def set_decision(self, job_id: int, decision: str) -> None:
        with connect() as conn:
            if not self._exists_in(conn, job_id):
                raise KeyError(job_id)
            if decision in {'liked', 'skipped'}:
                conn.execute('UPDATE jobs SET user_action=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (decision, job_id))
            elif decision == 'clear_user_action':
                conn.execute("UPDATE jobs SET user_action='', updated_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,))
            else:
                conn.execute('UPDATE jobs SET decision=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (decision, job_id))

    def set_application_status(self, job_id: int, status: str) -> None:
        with connect() as conn:
            if not self._exists_in(conn, job_id):
                raise KeyError(job_id)
            previous = conn.execute('SELECT application_status FROM jobs WHERE id=?', (job_id,)).fetchone()['application_status']
            if status in {'submitted', 'submitted_verified'} and previous in {'submitted', 'submitted_verified'}:
                return  # Repeated confirmation must not erase an interview or rejection.
            tracker = 'submitted' if status in {'submitted', 'submitted_verified'} else ('prepared' if status in {'prefilled', 'needs_human'} else '')
            conn.execute(
                "UPDATE jobs SET application_status=?, "
                "tracker_stage=CASE WHEN ?<>'' THEN ? ELSE tracker_stage END, "
                "last_application_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, tracker, tracker, job_id),
            )
            conn.execute('INSERT INTO applications(job_id,status,note) VALUES(?,?,?)', (job_id, status or 'status_cleared', 'Manual dashboard status change'))
            if status in {'submitted', 'submitted_verified', 'withdrawn'}:
                conn.execute("UPDATE application_queue SET status='done',note=?,finished_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE job_id=? AND status<>'running'", (status, job_id))
            if tracker:
                conn.execute('INSERT INTO application_stage_events(job_id,stage,note) VALUES(?,?,?)', (job_id, tracker, 'Application status changed from dashboard'))

    def history(self, job_id: int) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute('SELECT * FROM applications WHERE job_id=? ORDER BY id DESC LIMIT 100', (job_id,)).fetchall()
        return [dict(row) for row in rows]

    def stage_events(self, job_id: int) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute('SELECT * FROM application_stage_events WHERE job_id=? ORDER BY id DESC LIMIT 200', (job_id,)).fetchall()
        return [dict(row) for row in rows]

    def pipeline(self) -> list[dict[str, Any]]:
        query = """SELECT jobs.*, COALESCE((SELECT status FROM application_queue q WHERE q.job_id=jobs.id),'') AS queue_status
                   FROM jobs
                     WHERE (user_action<>'skipped' OR application_status IN ('submitted','submitted_verified','withdrawn') OR tracker_stage IN ('rejected','screening','interview','offer')) AND (tracker_stage<>'' OR application_status<>'' OR user_action='liked')
                   ORDER BY COALESCE(last_application_at,updated_at) DESC"""
        with connect() as conn:
            return [dict(row) for row in conn.execute(query).fetchall()]

    def track(self, job_id: int, stage: str, note: str = '', followup_at: str = '', source: str = '') -> None:
        if stage not in TRACK_STAGES:
            raise ValueError('invalid tracker stage')
        with connect() as conn:
            if not self._exists_in(conn, job_id):
                raise KeyError(job_id)
            job = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            external = stage in {'screening', 'interview', 'offer', 'rejected'}
            if external:
                if job['application_status'] not in {'submitted', 'submitted_verified'}:
                    raise ValueError('Confirm submission before recording a recruiter response')
                if source not in {'email', 'recruiter_portal', 'phone', 'manual'} or not note.strip():
                    raise ValueError('A recruiter response requires its source and a confirmation note')
            if stage == 'withdrawn' and job['application_status'] not in {'submitted', 'submitted_verified', 'withdrawn'}:
                raise ValueError('Confirm submission before recording a withdrawal')
            if stage == 'queued':
                queue = conn.execute('SELECT status FROM application_queue WHERE job_id=?', (job_id,)).fetchone()
                if not queue or queue['status'] not in {'queued', 'running', 'waiting_user'}:
                    raise ValueError('Add the job to the preparation queue first')
            if stage == 'prepared' and job['application_status'] not in {'prefilled', 'needs_human'}:
                raise ValueError('Prepare the application before marking it prepared')
            if stage == 'submitted':
                conn.execute("UPDATE jobs SET application_status='submitted',last_application_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,))
                conn.execute("INSERT INTO applications(job_id,status,note) VALUES(?,'submitted',?)", (job_id, 'Manual confirmation from pipeline'))
            if stage == 'withdrawn':
                conn.execute("UPDATE jobs SET application_status='withdrawn' WHERE id=?", (job_id,))
            if stage in {'submitted', 'withdrawn', 'rejected'}:
                conn.execute("UPDATE application_queue SET status='done',note=?,updated_at=CURRENT_TIMESTAMP WHERE job_id=? AND status<>'running'", (stage, job_id))
            conn.execute('UPDATE jobs SET tracker_stage=?,tracker_note=?,tracker_source=?,next_followup_at=?,updated_at=CURRENT_TIMESTAMP WHERE id=?', (stage, note.strip()[:4000], source, followup_at[:80], job_id))
            conn.execute('INSERT INTO application_stage_events(job_id,stage,note,followup_at,source) VALUES(?,?,?,?,?)', (job_id, stage, note.strip()[:4000], followup_at[:80], source))

    def assert_preparable(self, job_id: int) -> None:
        with connect() as conn:
            job = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise KeyError(job_id)
        if not can_prepare(dict(job)):
            raise ValueError('Confirm the AI review yourself before preparing this application')
        if (job['user_action'] == 'skipped' or job['decision'] == 'expired'
                or job['availability_status'] == 'expired'
                or job['tracker_stage'] in {'rejected', 'withdrawn'}
                or job['application_status'] in {'submitted', 'submitted_verified', 'withdrawn', 'opening', 'preparing', 'preparing_letter'}):
            raise ValueError('Application cannot be prepared in its current state')

    def confirm_review(self, job_id: int, status: str, token: str) -> None:
        with connect() as conn:
            row = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            job = dict(row)
            if status not in {'approved', 'declined', 'pending'} or job['review_verdict'] not in REVIEWABLE:
                raise ValueError('Wait for a completed AI review before confirming')
            if token != review_token(job):
                raise ValueError('The review or listing changed. Reload and check the latest result')
            conn.execute('''UPDATE jobs SET human_review_status=?,human_review_fingerprint=?,
                            human_reviewed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?''',
                         (status, token, job_id))
            conn.execute('INSERT INTO human_review_events(job_id,status,review_token) VALUES(?,?,?)', (job_id, status, token))
            if status != 'approved':
                conn.execute("UPDATE application_queue SET status='cancelled',note='Human confirmation required',updated_at=CURRENT_TIMESTAMP WHERE job_id=? AND status='queued'", (job_id,))

    def human_review_history(self, job_id: int) -> list[dict]:
        with connect() as conn:
            return [dict(r) for r in conn.execute('SELECT * FROM human_review_events WHERE job_id=? ORDER BY id DESC', (job_id,))]

    def audit_path(self, job_id: int, column: str) -> str:
        if column not in {'fill_audit_path', 'agent_trace_path'}:
            raise ValueError('unsupported audit column')
        with connect() as conn:
            row = conn.execute(f'SELECT {column} FROM jobs WHERE id=?', (job_id,)).fetchone()
        return str(row[column] or '') if row else ''

    def clear(self) -> None:
        with connect() as conn:
            conn.execute('DELETE FROM human_review_events')
            conn.execute('DELETE FROM application_queue')
            conn.execute('DELETE FROM application_stage_events')
            conn.execute('DELETE FROM applications')
            conn.execute('DELETE FROM jobs')

    @staticmethod
    def _exists_in(conn: Any, job_id: int) -> bool:
        return conn.execute('SELECT 1 FROM jobs WHERE id=?', (job_id,)).fetchone() is not None
