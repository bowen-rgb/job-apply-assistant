"""Platform-owned Chrome bootstrap and queue preflight. Never switch browsers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import threading
import time
from urllib.parse import urlparse
from urllib.request import urlopen

from .profile_store import ROOT, runtime_profile

_launch_lock = threading.Lock()


def local_endpoint(profile):
    endpoint = str(profile.get('chrome_cdp_endpoint') or 'http://127.0.0.1:9222').rstrip('/')
    parsed = urlparse(endpoint)
    if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('Configurez une connexion Chrome locale, par exemple http://127.0.0.1:9222.')
    if not parsed.port:
        raise ValueError('La connexion Chrome locale doit préciser son port.')
    return endpoint


def chrome_executable():
    for variable in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        base = os.environ.get(variable)
        if base:
            path = Path(base) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe'
            if path.is_file():
                return path
    return None


def status(profile=None):
    profile = profile if profile is not None else runtime_profile()
    result = dict(ready=False, state='disconnected', browser='', engine='platform_chrome',
                  installed=chrome_executable() is not None, message='Ouvrez Chrome depuis la plateforme, puis vérifiez la connexion. Aucun remplacement par Edge.')
    if profile.get('browser_mode', 'cdp') != 'cdp':
        return dict(result, state='configuration', message='Choisissez Chrome dédié (CDP) dans le profil pour utiliser la file pilotée par la plateforme.')
    try:
        endpoint = local_endpoint(profile)
    except ValueError as exc:
        return dict(result, state='configuration', message=str(exc))
    try:
        with urlopen(endpoint + '/json/version', timeout=1.5) as response:
            version = json.load(response)
    except Exception:
        return result
    product = str(version.get('Browser') or '')
    user_agent = str(version.get('User-Agent') or '')
    if not product.startswith('Chrome/') or any(marker in (product + ' ' + user_agent) for marker in ('Edg/', 'Edge/', 'HeadlessChrome/')):
        return dict(result, state='wrong_browser', browser=product, message='La connexion configurée ne correspond pas au Chrome dédié. La file reste arrêtée ; aucun remplacement par Edge.')
    websocket = urlparse(str(version.get('webSocketDebuggerUrl') or ''))
    if websocket.scheme != 'ws' or websocket.hostname not in {'localhost', '127.0.0.1', '::1'}:
        return dict(result, state='configuration', browser=product, message='La connexion de contrôle Chrome locale est indisponible.')
    return dict(result, ready=True, state='ready', browser=product, message='Chrome dédié connecté. Ouvrir Chrome ne lance aucune candidature. Vérifiez votre connexion à ChatGPT.')


def require_connection(profile=None):
    result = status(profile)
    if not result['ready']:
        raise ValueError(result['message'])
    return result


def start(profile=None):
    """Explicit UI action only. Does not launch a queue, fill a form or send."""
    profile = profile if profile is not None else runtime_profile()
    with _launch_lock:
        current = status(profile)
        if current['ready']:
            return current
        if current['state'] in {'wrong_browser', 'configuration'}:
            raise ValueError(current['message'])
        executable = chrome_executable()
        if executable is None:
            raise ValueError('Google Chrome introuvable. Installez Chrome ; la plateforme ne bascule pas vers Edge.')
        endpoint = local_endpoint(profile)
        directory = ROOT / 'data' / 'chrome-profile'
        directory.mkdir(parents=True, exist_ok=True)
        arguments = [str(executable), '--remote-debugging-address=127.0.0.1',
                     f'--remote-debugging-port={urlparse(endpoint).port}',
                     f'--user-data-dir={directory}', '--new-window', 'https://chatgpt.com/']
        subprocess.Popen(arguments, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        for _ in range(20):
            result = status(profile)
            if result['ready']:
                return result
            if result['state'] in {'wrong_browser', 'configuration'}:
                raise ValueError(result['message'])
            time.sleep(0.2)
        raise ValueError('Chrome ne répond pas encore. Vérifiez la fenêtre Chrome ou lancez start_chrome_debug.bat, puis vérifiez la connexion. La file reste arrêtée.')
