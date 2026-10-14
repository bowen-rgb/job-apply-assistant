"""Candidate-owned application to-dos, separate from submission evidence."""
import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import urlparse
from filelock import FileLock
from .workspaces import data_dir


def read():
    path=data_dir()/'pending_tasks.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []


def _change(operation):
    directory=data_dir();directory.mkdir(parents=True,exist_ok=True)
    with FileLock(str(directory/'pending_tasks.lock')):
        items=read();result=operation(items)
        path=directory/'pending_tasks.json';temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(path)
        return result


def add(rows):
    validated=[]
    for row in rows:
        title=str(row.get('title') or '').strip()
        kind=row.get('kind') or 'vacancy'
        url=str(row.get('url') or '')
        if not title or len(title)>500 or kind not in {'vacancy','contact','material'}:
            raise ValueError('Invalid task')
        parsed=urlparse(url)
        if url and (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password):
            raise ValueError('Use a public HTTPS URL')
        identifier=hashlib.sha256(f'{kind}:{url}:{title}'.encode('utf-8')).hexdigest()[:12]
        validated.append({'id':identifier,'title':title,'kind':kind,'url':url,
                          'note':str(row.get('note') or '')[:8000],
                          'source':str(row.get('source') or '')[:500],
                          'status':'pending','created_at':datetime.now(timezone.utc).isoformat()})
    def change(items):
        existing={item['id'] for item in items}
        for row in validated:
            if row['id'] not in existing:items.append(row);existing.add(row['id'])
        return len(items)
    return _change(change)


def set_status(identifier,status):
    if status not in {'pending','done'}:raise ValueError('Invalid task status')
    def change(items):
        item=next((item for item in items if item['id']==identifier),None)
        if item is None:raise KeyError(identifier)
        item.update(status=status,updated_at=datetime.now(timezone.utc).isoformat())
    _change(change)
