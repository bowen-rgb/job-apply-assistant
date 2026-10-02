from __future__ import annotations
import json
import sys
from pathlib import Path
try:
    from .reviewer import review_via_chatgpt_web
    from .db import connect
except ImportError:
    from reviewer import review_via_chatgpt_web
    from db import connect


def main(job_id: int, snapshot_path: str | None = None):
    snapshot = None
    if snapshot_path:
        p = Path(snapshot_path)
        if p.exists():
            snapshot = json.loads(p.read_text(encoding='utf-8'))
    try:
        result = review_via_chatgpt_web(job_id, form_snapshot=snapshot)
    except Exception as exc:
        msg = str(exc)
        with connect() as c:
            c.execute("UPDATE jobs SET review_verdict='ERROR', review_summary=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (msg[:1000], job_id))
            c.execute('INSERT INTO applications(job_id,status,note) VALUES(?,?,?)', (job_id, 'chatgpt_review_error', msg[:2000]))
        print('Reviewer error:', msg, file=sys.stderr)
        raise
    # Logging must never overwrite a successful review as an error.
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    job_id = int(sys.argv[1])
    snapshot_path = sys.argv[2] if len(sys.argv) > 2 else None
    main(job_id, snapshot_path)
