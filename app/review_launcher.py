from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKER = ROOT / 'app' / 'review_worker.py'


def launch_review(job_id: int, snapshot_path: str | None = None):
    creationflags = 0
    if sys.platform.startswith('win'):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    cmd = [sys.executable, str(WORKER), str(job_id)]
    if snapshot_path:
        cmd.append(str(snapshot_path))
    subprocess.Popen(cmd, cwd=str(ROOT), creationflags=creationflags)
