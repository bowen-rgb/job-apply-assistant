"""Start the local dashboard without a persistent Windows console."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = 'http://127.0.0.1:8765/api/health'


def ready():
    try:
        with urllib.request.urlopen(URL, timeout=3) as response:
            return json.load(response).get('profile_ok') is True
    except Exception:
        return False


def main():
    if ready():
        return 0
    logs = ROOT / 'data' / 'server-logs'
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output = logs / (stamp + '.log')
    # Keep the user's existing server and Chrome sessions intact.
    # Duplicate launches exit when the existing server answers its health check.
    with output.open('a', encoding='utf-8') as log:
        process = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host',
             '127.0.0.1', '--port', '8765', '--no-use-colors'],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            env={**os.environ, 'PYTHONUTF8': '1'},
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
        )
    (logs / 'latest.json').write_text(json.dumps(
        {'pid': process.pid, 'log': str(output)}, indent=2), encoding='utf-8')
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if ready():
            return 0
        if process.poll() is not None:
            print(f'Server could not start. See {output}')
            return 1
        time.sleep(.5)
    print(f'Server is taking longer to start. See {output}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
