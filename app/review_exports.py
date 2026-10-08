"""Private export snapshots and background-worker state, never live approvals."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from filelock import FileLock

from .profile_store import ROOT
from .review_report import report_row
from .worker_runtime import launch, cancel

EXPORT_ROOT=ROOT/'data'/'review_exports'


from .workspaces import data_dir

def owned_directory():
    return EXPORT_ROOT if EXPORT_ROOT != ROOT / 'data' / 'review_exports' else data_dir() / 'review_exports'

def directory(export_id):
    if not re.fullmatch(r'[0-9a-f]{32}',export_id):raise KeyError(export_id)
    return owned_directory()/export_id


def read_state(export_id):
    path=directory(export_id)/'state.json'
    if not path.is_file():raise KeyError(export_id)
    state=json.loads(path.read_text(encoding='utf-8'))
    if state['status'] in {'queued','running'}:
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(state['updated_at'])).total_seconds()
        if age>3600:
            update_state(export_id,status='error',message='Export interrompu. Relancez l’export.')
            state=json.loads(path.read_text(encoding='utf-8'))
    return state


def update_state(export_id,**values):
    folder=directory(export_id)
    with FileLock(str(folder/'state.lock')):
        path=folder/'state.json'
        state=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if state.get('status')=='cancelled':return False
        state.update(values,updated_at=datetime.now(timezone.utc).isoformat())
        temporary=folder/f'{uuid4().hex}.tmp'
        temporary.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
        temporary.replace(path)
    return True


def create_export(jobs,language,format,translate_text=True):
    if not jobs:raise ValueError('Aucun poste à exporter dans cette sélection.')
    if len(jobs)>1000:raise ValueError('Limitez la sélection à 1000 postes.')
    export_id=uuid4().hex
    folder=directory(export_id)
    folder.mkdir(parents=True)
    metadata={'id':export_id,'language':language,'format':format,'translate_text':translate_text,
              'created_at':datetime.now(timezone.utc).isoformat()}
    (folder/'snapshot.json').write_text(json.dumps({'metadata':metadata,'rows':[report_row(j) for j in jobs]},ensure_ascii=False),encoding='utf-8')
    update_state(export_id,**metadata,status='queued',completed=0,total=len(jobs),message='Préparation de l’export…')
    try:launch('app.review_export_worker',export_id)
    except Exception:
        update_state(export_id,status='error',message='Impossible de démarrer l’export. Réessayez.')
        raise ValueError('Impossible de démarrer l’export. Réessayez.')
    return read_state(export_id)


def cancel_export(export_id):
    state=read_state(export_id)
    if state['status'] not in {'queued','running'}:return state
    update_state(export_id,status='cancelled',message='Export annulé.')
    cancel('app.review_export_worker',export_id)
    return read_state(export_id)


def download(export_id):
    state=read_state(export_id)
    if state['status']!='ready':raise ValueError('L’export n’est pas encore prêt.')
    path=directory(export_id)/f'report.{state["format"]}'
    if not path.is_file():raise KeyError(export_id)
    return path,state
