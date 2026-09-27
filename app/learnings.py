from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .db import connect


def normalize_label(label: str) -> str:
    return re.sub(r'\s+', ' ', (label or '').strip().lower())[:500]


def record_field_result(*, ats: str, label: str, field_type: str, value_ref: str, strategy: str,
                        success: bool, option_text: str = '', note: str = '') -> None:
    key = normalize_label(label)
    if not key:
        return
    now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        row = c.execute(
            'SELECT id, success_count, failure_count FROM field_learnings WHERE ats=? AND label_norm=? AND field_type=? AND value_ref=?',
            (ats or 'generic', key, field_type or '', value_ref or ''),
        ).fetchone()
        if row:
            c.execute(
                '''UPDATE field_learnings SET strategy=?, resolved_option=?, success_count=?, failure_count=?, note=?, last_seen=? WHERE id=?''',
                (strategy[:100], option_text[:300], int(row['success_count']) + (1 if success else 0),
                 int(row['failure_count']) + (0 if success else 1), note[:1000], now, row['id']),
            )
        else:
            c.execute(
                '''INSERT INTO field_learnings(ats,label_norm,field_type,value_ref,strategy,resolved_option,success_count,failure_count,note,last_seen)
                   VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (ats or 'generic', key, field_type or '', value_ref or '', strategy[:100], option_text[:300],
                 1 if success else 0, 0 if success else 1, note[:1000], now),
            )


def learned_option(ats: str, label: str, value_ref: str) -> str:
    key = normalize_label(label)
    with connect() as c:
        row = c.execute(
            '''SELECT resolved_option, success_count, failure_count FROM field_learnings
               WHERE ats=? AND label_norm=? AND value_ref=? AND resolved_option<>''
               ORDER BY success_count DESC, failure_count ASC, last_seen DESC LIMIT 1''',
            (ats or 'generic', key, value_ref or ''),
        ).fetchone()
    if row and int(row['success_count']) >= max(1, int(row['failure_count'])):
        return row['resolved_option'] or ''
    return ''


def stats() -> dict[str, Any]:
    with connect() as c:
        total = c.execute('SELECT COUNT(*) AS n FROM field_learnings').fetchone()['n']
        successful = c.execute('SELECT COALESCE(SUM(success_count),0) AS n FROM field_learnings').fetchone()['n']
        failed = c.execute('SELECT COALESCE(SUM(failure_count),0) AS n FROM field_learnings').fetchone()['n']
    return {'rules': total, 'successes': successful, 'failures': failed}
