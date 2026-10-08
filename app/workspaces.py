"""Candidate-owned data paths; pin each request, thread and worker to one owner."""
import contextvars
import json
import os
import re
import threading
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURRENT = contextvars.ContextVar('candidate_workspace', default=None)
LOCK = threading.RLock()


def validate(identifier):
    if identifier != 'default' and not re.fullmatch(r'[0-9a-f]{12}', identifier or ''):
        raise ValueError('Invalid candidate')
    return identifier


def active_id():
    try:
        return validate(json.loads((ROOT/'data'/'active_candidate.json').read_text(encoding='utf-8'))['id'])
    except FileNotFoundError:
        return 'default'


def candidate_id():
    return validate(os.environ.get('JAA_CANDIDATE_ID') or CURRENT.get() or active_id())


def data_dir(identifier=None):
    identifier = validate(identifier or candidate_id())
    return ROOT/'data' if identifier == 'default' else ROOT/'data'/'candidates'/identifier


def profile_path(identifier=None):
    identifier = validate(identifier or candidate_id())
    return ROOT/'profile.json' if identifier == 'default' else data_dir(identifier)/'profile.json'


def candidates():
    identifiers = ['default'] + sorted(p.name for p in (ROOT/'data'/'candidates').glob('*') if p.is_dir() and re.fullmatch(r'[0-9a-f]{12}',p.name))
    rows = []
    for identifier in identifiers:
        path = profile_path(identifier)
        raw = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        identity = raw.get('identity', {})
        name = raw.get('candidate_label') or ' '.join(filter(None,[identity.get('first_name'),identity.get('last_name')])) or 'Current profile'
        rows.append({'id':identifier,'name':name,'identity':identity,'roles':raw.get('preferences',{}).get('roles',[]),'active':identifier==active_id()})
    return rows


def create(name):
    from .profile_store import default_profile
    name = str(name).strip()
    if not name or len(name)>80:
        raise ValueError('Choose a name, up to 80 characters')
    identifier = uuid.uuid4().hex[:12]
    folder = data_dir(identifier)
    folder.mkdir(parents=True, exist_ok=False)
    profile = default_profile()
    profile['candidate_label'] = name
    profile_path(identifier).write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf-8')
    return identifier


def activate(identifier):
    validate(identifier)
    if identifier not in {row['id'] for row in candidates()}:
        raise KeyError(identifier)
    from .worker_runtime import any_running
    from .scan_manager import status as scan_status
    from .queue_manager import status as queue_status
    with LOCK:
        if any_running() or scan_status().get('running') or queue_status().get('running'):
            raise ValueError('Stop running tasks before switching candidate')
        token=CURRENT.set(identifier)
        try:
            from .db import init_db
            from .profile_store import ensure_profile
            init_db();ensure_profile()
            pointer = ROOT/'data'/'active_candidate.json'
            pointer.parent.mkdir(parents=True,exist_ok=True)
            tmp=pointer.with_suffix('.tmp')
            tmp.write_text(json.dumps({'id':identifier}),encoding='utf-8')
            tmp.replace(pointer)
            from . import scan_manager,queue_manager
            scan_manager._set(scan_id=None,found=0,fetched=0,inserted=0,updated=0,errors=0,source_diagnostics=[],current_source='',current_title='',current_campaign='',message='',started_at='',finished_at='')
            queue_manager._set(current_job_id=None,last_job_id=None,paused=False,message='',pause_reason='')
        finally:
            CURRENT.reset(token)
