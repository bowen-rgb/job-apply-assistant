"""Small browser-dashboard entry point. No Electron, installer or second runtime."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def workspace():
    saved = ROOT/'data'/'dashboard-workspace.json'
    old = Path(os.environ.get('APPDATA', ''))/'job-apply-assistant-desktop'/'workspace.json'
    for config in (saved, old):
        if config.is_file():
            value = Path(json.loads(config.read_text(encoding='utf-8'))['path']).resolve()
            return value
    return ROOT


def stop():
    logs = ROOT/'data'/'server-logs'
    record = logs/'latest.json'
    if not record.exists():
        return
    state = json.loads(record.read_text(encoding='utf-8'))
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/api/runtime', timeout=2) as response:
            live = json.load(response)
    except OSError:
        return
    if (live.get('application') != 'job-apply-assistant' or live.get('pid') != state.get('pid')
            or not live.get('dashboard_owned') or live.get('host_instance') != state.get('instance')):
        raise ValueError('已有后台不属于这次 Dashboard 启动，请先退出旧后台；不会按端口强行结束其他程序。')
    flag = Path(state['control']).resolve()
    if flag.parent != logs.resolve() or flag.name != state['instance']+'.stop':
        raise ValueError('后台控制记录不完整，请查看运行日志。')
    flag.touch()
    for _ in range(60):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8765/api/runtime', timeout=.5) as response:
                if json.load(response).get('host_instance') != state['instance']:
                    return
        except OSError:
            return
        time.sleep(.25)
    raise ValueError('后台仍在结束当前任务，请稍后再点停止。')


def main(action='start'):
    os.environ['JAA_WORKSPACE_HOME'] = str(workspace())
    if action == 'stop':
        from filelock import FileLock
        logs = ROOT/'data'/'server-logs'
        logs.mkdir(parents=True, exist_ok=True)
        with FileLock(str(logs/'launcher.lock'), timeout=90):
            stop()
        return
    if action != 'start':
        raise ValueError('Unknown dashboard action')
    from .server_launcher import main as start_server
    if start_server():
        raise ValueError('启动失败，请查看项目 data/server-logs 文件夹中的最新日志。')
    from .browser_control import chrome_executable
    browser = chrome_executable()
    if browser:
        subprocess.Popen([str(browser), 'http://127.0.0.1:8765'], creationflags=0x01000000 if os.name=='nt' else 0)
    else:
        import webbrowser
        webbrowser.open('http://127.0.0.1:8765')


if __name__ == '__main__':
    try:
        main(sys.argv[1] if len(sys.argv)>1 else 'start')
    except Exception as exc:
        if os.name == 'nt':
            ctypes.windll.user32.MessageBoxW(None, str(exc), 'Job Apply Dashboard', 0x10)
        else:
            print(str(exc), file=sys.stderr)
        raise SystemExit(1)
