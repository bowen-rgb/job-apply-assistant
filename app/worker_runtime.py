"""Managed UTF-8 workers with cooperative cancellation across processes."""
from __future__ import annotations
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_lock = threading.Lock()
_workers: dict[tuple[str, int], tuple[subprocess.Popen, Path]] = {}


class Cancelled(RuntimeError):
    pass


def check_cancelled() -> None:
    token = os.environ.get('JOB_WORKER_TOKEN')
    if token and Path(token).exists():
        raise Cancelled('Task cancelled by user')


def launch(module: str, job_id: int, *args: str):
    key = (module, job_id)
    with _lock:
        if module == 'app.apply_worker':
            for (name, other_id), (process, _) in _workers.items():
                if name == module and other_id != job_id and process.poll() is None:
                    raise ValueError('Une candidature est déjà en préparation. Attendez ou arrêtez-la depuis la file.')
        previous = _workers.get(key)
        if previous and previous[0].poll() is None:
            if previous[1].exists():
                raise ValueError('La tâche précédente s’arrête. Réessayez dans quelques secondes.')
            return previous[0]
        directory = ROOT / 'data' / 'workers'
        directory.mkdir(parents=True, exist_ok=True)
        token = directory / f'{module.rsplit(".", 1)[-1]}_{job_id}_{uuid.uuid4().hex}.cancel'
        env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8:backslashreplace', 'JOB_WORKER_TOKEN': str(token)}
        with (directory / f'{module.rsplit(".", 1)[-1]}_{job_id}.log').open('a', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, '-m', module, str(job_id), *args], cwd=str(ROOT), env=env,
                                       stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0)
        _workers[key] = (process, token)
        return process


def cancel(module: str, job_id: int) -> None:
    with _lock:
        entry = _workers.get((module, job_id))
        if entry and entry[0].poll() is None:
            entry[1].touch()


def cancel_all() -> None:
    with _lock:
        for process, token in _workers.values():
            if process.poll() is None:
                token.touch()
