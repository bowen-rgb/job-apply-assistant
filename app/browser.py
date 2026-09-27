from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def launch_apply(job_id: int):
    # Use module execution so package-relative ATS adapters remain import-safe.
    creationflags = 0
    if sys.platform.startswith('win'):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [sys.executable, '-m', 'app.apply_worker', str(job_id)],
        cwd=str(ROOT),
        creationflags=creationflags,
    )
