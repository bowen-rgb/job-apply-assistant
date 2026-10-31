"""Candidate-owned artifacts and native background jobs for advanced workflows."""
import json
from pathlib import Path
import re
from .db import connect
from .workspaces import data_dir


def init():
    with connect() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS capability_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,job_id INTEGER,
            state TEXT DEFAULT 'queued',request_json TEXT NOT NULL,result_json TEXT DEFAULT '{}',
            error TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP,finished_at TEXT DEFAULT '')''')
        c.execute('''CREATE TABLE IF NOT EXISTS capability_items (
            id TEXT PRIMARY KEY,kind TEXT NOT NULL,metadata_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')


def folder():
    path=data_dir()/'capabilities';path.mkdir(parents=True,exist_ok=True);return path


def safe_file(relative):
    root=folder().resolve();path=(root/relative).resolve()
    if not path.is_relative_to(root) or path==root or path.is_symlink():
        raise ValueError('Invalid artifact path')
    return path


def create_task(kind, job_id, payload):
    init()
    with connect() as c:
        return c.execute('INSERT INTO capability_tasks(kind,job_id,request_json) VALUES(?,?,?)',
                         (kind,job_id,json.dumps(payload,ensure_ascii=False))).lastrowid


def task(identifier):
    init()
    with connect() as c:row=c.execute('SELECT * FROM capability_tasks WHERE id=?',(identifier,)).fetchone()
    if not row:raise KeyError(identifier)
    item=dict(row)
    for key in ('request','result'):item[key]=json.loads(item.pop(key+'_json'))
    return item


def tasks():
    init()
    with connect() as c:ids=[r['id'] for r in c.execute('SELECT id FROM capability_tasks ORDER BY id DESC LIMIT 100')]
    return [task(identifier) for identifier in ids]


def update_task(identifier,state,*,result=None,error=''):
    with connect() as c:
        c.execute('''UPDATE capability_tasks SET state=?,result_json=?,error=?,
                     finished_at=CASE WHEN ? IN ('ready','error','cancelled') THEN CURRENT_TIMESTAMP ELSE '' END WHERE id=?''',
                  (state,json.dumps(result or {},ensure_ascii=False),error[:2000],state,identifier))


def save_item(identifier,kind,metadata):
    init()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',identifier):raise ValueError('Invalid record ID')
    metadata={key:value for key,value in metadata.items() if key!='id'}
    with connect() as c:c.execute('INSERT OR REPLACE INTO capability_items(id,kind,metadata_json) VALUES(?,?,?)',
                                  (identifier,kind,json.dumps(metadata,ensure_ascii=False)))


def items(kind):
    init()
    with connect() as c:return [dict(id=r['id'],**json.loads(r['metadata_json'])) for r in c.execute('SELECT * FROM capability_items WHERE kind=? ORDER BY created_at DESC',(kind,))]


def item(identifier,kind):
    return next((row for row in items(kind) if row['id']==identifier),None)
