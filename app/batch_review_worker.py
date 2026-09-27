from __future__ import annotations
import json
import sys
try:
    from .reviewer import review_via_chatgpt_web
    from .db import connect
except ImportError:
    from reviewer import review_via_chatgpt_web
    from db import connect


def main(mode: str = 'strong'):
    with connect() as c:
        if mode == 'liked':
            rows = c.execute("SELECT id FROM jobs WHERE user_action='liked' AND COALESCE(review_verdict,'') NOT IN ('APPLY','SKIP','HUMAN_REVIEW') ORDER BY score DESC").fetchall()
        else:
            rows = c.execute("SELECT id FROM jobs WHERE (user_action='liked' OR decision='keep') AND COALESCE(review_verdict,'') NOT IN ('APPLY','SKIP','HUMAN_REVIEW') ORDER BY CASE user_action WHEN 'liked' THEN 0 ELSE 1 END, score DESC").fetchall()
    results = []
    for row in rows:
        job_id = int(row['id'])
        try:
            r = review_via_chatgpt_web(job_id)
            results.append({'job_id': job_id, 'verdict': r['verdict']})
        except Exception as exc:
            msg = str(exc)
            with connect() as c:
                c.execute("UPDATE jobs SET review_verdict='ERROR', review_summary=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (msg[:1000], job_id))
            results.append({'job_id': job_id, 'error': msg})
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'strong')
