"""SQLite repository for job and application workflow data.

The repository owns SQL and transaction boundaries. API handlers should deal
with validated contracts and domain outcomes, rather than assembling SQL.
"""

from __future__ import annotations

from typing import Any

from ..contracts import TRACK_STAGES
from ..db import connect


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
            "WHERE q.job_id=jobs.id),'') AS queue_status FROM jobs"
            + where + self._ORDER
        )
        with connect() as conn:
            return [dict(row) for row in conn.execute(query, tuple(args)).fetchall()]

    def stats(self) -> dict[str, Any]:
        query = """SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN decision='keep' THEN 1 ELSE 0 END),0) AS keep_n,
            COALESCE(SUM(CASE WHEN user_action='liked' THEN 1 ELSE 0 END),0) AS liked_n,
            COALESCE(SUM(CASE WHEN review_verdict='APPLY' THEN 1 ELSE 0 END),0) AS apply_n,
            COALESCE(SUM(CASE WHEN review_verdict='HUMAN_REVIEW' THEN 1 ELSE 0 END),0) AS human_n,
            COALESCE(SUM(CASE WHEN decision='expired' OR availability_status='expired' THEN 1 ELSE 0 END),0) AS expired_n,
            COALESCE(SUM(CASE WHEN application_status IN ('submitted','submitted_verified') THEN 1 ELSE 0 END),0) AS submitted_n
            FROM jobs"""
        with connect() as conn:
            return dict(conn.execute(query).fetchone())

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
            tracker = 'submitted' if status in {'submitted', 'submitted_verified'} else ('prepared' if status in {'prefilled', 'needs_human'} else '')
            conn.execute(
                "UPDATE jobs SET application_status=?, "
                "tracker_stage=CASE WHEN ?<>'' THEN ? ELSE tracker_stage END, "
                "last_application_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, tracker, tracker, job_id),
            )
            conn.execute('INSERT INTO applications(job_id,status,note) VALUES(?,?,?)', (job_id, status or 'status_cleared', 'Manual dashboard status change'))
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
                   WHERE tracker_stage<>'' OR application_status<>'' OR user_action='liked'
                   ORDER BY COALESCE(last_application_at,updated_at) DESC"""
        with connect() as conn:
            return [dict(row) for row in conn.execute(query).fetchall()]

    def track(self, job_id: int, stage: str, note: str = '', followup_at: str = '') -> None:
        if stage not in TRACK_STAGES:
            raise ValueError('invalid tracker stage')
        with connect() as conn:
            if not self._exists_in(conn, job_id):
                raise KeyError(job_id)
            conn.execute('UPDATE jobs SET tracker_stage=?,tracker_note=?,next_followup_at=?,updated_at=CURRENT_TIMESTAMP WHERE id=?', (stage, note[:4000], followup_at[:80], job_id))
            conn.execute('INSERT INTO application_stage_events(job_id,stage,note,followup_at) VALUES(?,?,?,?)', (job_id, stage, note[:4000], followup_at[:80]))

    def audit_path(self, job_id: int, column: str) -> str:
        if column not in {'fill_audit_path', 'agent_trace_path'}:
            raise ValueError('unsupported audit column')
        with connect() as conn:
            row = conn.execute(f'SELECT {column} FROM jobs WHERE id=?', (job_id,)).fetchone()
        return str(row[column] or '') if row else ''

    def clear(self) -> None:
        with connect() as conn:
            conn.execute('DELETE FROM application_queue')
            conn.execute('DELETE FROM application_stage_events')
            conn.execute('DELETE FROM applications')
            conn.execute('DELETE FROM jobs')

    @staticmethod
    def _exists_in(conn: Any, job_id: int) -> bool:
        return conn.execute('SELECT 1 FROM jobs WHERE id=?', (job_id,)).fetchone() is not None
