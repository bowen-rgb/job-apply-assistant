from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKER = ROOT / 'app' / 'batch_review_worker.py'


def launch_batch_review(mode: str = 'strong'):
    creationflags = 0
    if sys.platform.startswith('win'):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([sys.executable, str(WORKER), mode], cwd=str(ROOT), creationflags=creationflags)
