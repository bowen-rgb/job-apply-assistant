"""Start the local dashboard without a persistent Windows console."""
import json
import os
import subprocess
import sys
import time
import uuid
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = 'http://127.0.0.1:8765/api/runtime'


def ready():
    try:
        with urllib.request.urlopen(URL, timeout=3) as response:
            data = json.load(response)
            from .workspaces import storage_root
            return (data.get('application') == 'job-apply-assistant'
                    and Path(data.get('workspace', '')).resolve() == storage_root())
    except Exception:
        return False


def _start():
    if ready():
        return 0
    logs = ROOT / 'data' / 'server-logs'
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output = logs / (stamp + '.log')
    # Keep the user's existing server and Chrome sessions intact.
    # Duplicate launches exit when the existing server answers its health check.
    instance = uuid.uuid4().hex
    control = (logs/(instance+'.stop')).resolve()
    with output.open('a', encoding='utf-8') as log:
        process = subprocess.Popen(
            [str(Path(sys.executable).with_name('python.exe')) if Path(sys.executable).name.lower()=='pythonw.exe' else sys.executable, '-m', 'app.dashboard_host'],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            env={**os.environ, 'PYTHONUTF8': '1', 'JAA_DASHBOARD_INSTANCE':instance,'JAA_DASHBOARD_CONTROL':str(control)},
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
        )
    (logs / 'latest.json').write_text(json.dumps(
        {'pid': process.pid, 'log': str(output), 'instance':instance,'control':str(control)}, indent=2), encoding='utf-8')
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if ready():
            try:
                with urllib.request.urlopen(URL, timeout=2) as response:
                    live = json.load(response)
                if live.get('host_instance') == instance:
                    record = {'pid': live['pid'], 'log':str(output), 'instance':instance, 'control':str(control)}
                    (logs/'latest.json').write_text(json.dumps(record), encoding='utf-8')
            except OSError:
                pass
            return 0
        if process.poll() is not None:
            print(f'Server could not start. See {output}')
            return 1
        time.sleep(.5)
    print(f'Server is taking longer to start. See {output}')
    return 1


def main():
    from filelock import FileLock
    logs = ROOT/'data'/'server-logs'
    logs.mkdir(parents=True, exist_ok=True)
    with FileLock(str(logs/'launcher.lock'), timeout=90):
        return _start()


if __name__ == '__main__':
    raise SystemExit(main())
