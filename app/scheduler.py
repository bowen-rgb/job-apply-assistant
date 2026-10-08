from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

from .profile_store import load_profile_raw, runtime_profile
from .scan_manager import start as start_scan, status as scan_status

_lock = threading.Lock()
_started = False
_state: dict[str, Any] = {'enabled': False, 'interval_minutes': 0, 'last_auto_scan_at': '', 'next_due_at': ''}


def status() -> dict[str, Any]:
    with _lock:
        return dict(_state)


def _loop():
    last_run = 0.0
    while True:
        try:
            from .workspaces import CURRENT, LOCK, active_id
            with LOCK:
                owner = active_id()
                token = CURRENT.set(owner)
                try: raw = load_profile_raw()
                finally: CURRENT.reset(token)
            interval = int(raw.get('automation', {}).get('auto_scan_interval_minutes') or 0)
        except Exception:
            interval = 0
        now = time.time()
        due = interval > 0 and (last_run == 0.0 or now - last_run >= interval * 60)
        with _lock:
            _state['enabled'] = interval > 0
            _state['interval_minutes'] = interval
            if interval > 0:
                _state['next_due_at'] = datetime.fromtimestamp((last_run or now) + interval * 60, tz=timezone.utc).isoformat()
            else:
                _state['next_due_at'] = ''
        if due and not scan_status().get('running'):
            try:
                with LOCK:
                    if owner != active_id(): continue
                    token = CURRENT.set(owner)
                    try: start_scan(runtime_profile(raw))
                    finally: CURRENT.reset(token)
                last_run = now
                with _lock:
                    _state['last_auto_scan_at'] = datetime.now(timezone.utc).isoformat()
                    _state['next_due_at'] = datetime.fromtimestamp(now + interval * 60, tz=timezone.utc).isoformat()
            except Exception:
                pass
        time.sleep(20)


def start_scheduler():
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, daemon=True, name='auto-scan-scheduler').start()
