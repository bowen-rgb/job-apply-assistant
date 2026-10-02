from __future__ import annotations

import sys
from playwright.sync_api import sync_playwright
from .apply_worker import _open_browser
from .cover_letter import generate_letter
from .db import connect
from .profile_store import load_profile_raw, runtime_profile, select_resume_for_job


def main(job_id: int):
    raw = load_profile_raw()
    profile = runtime_profile(raw)
    with connect() as connection:
        row = connection.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
    if not row:
        raise ValueError('job not found')
    job = dict(row)
    resume, _ = select_resume_for_job(job, raw)
    with sync_playwright() as playwright:
        _, context, mode = _open_browser(playwright, profile)
        try:
            generate_letter(context, job, raw, resume, profile.get('chatgpt_web_reviewer', {}))
        finally:
            if mode != 'cdp':
                context.close()


if __name__ == '__main__':
    job_id = int(sys.argv[1])
    try:
        main(job_id)
    except Exception as exc:
        from .cover_letter import save_letter_state, generation_error
        save_letter_state(job_id, {'status': 'error', 'error': generation_error(exc)})
        raise
