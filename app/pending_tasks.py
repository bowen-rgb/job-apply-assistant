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


def with_queue():
    from .db import connect
    items=read()
    if not (data_dir()/'jobs.db').exists():return items
    with connect() as connection:
        if not connection.execute("SELECT name FROM sqlite_master WHERE name='jobs'").fetchone():return items
        for item in items:
            if item['kind']!='vacancy' or not item['url']:continue
            row=connection.execute('''SELECT j.id,j.application_status,q.status AS queue_status
                FROM jobs j LEFT JOIN application_queue q ON q.job_id=j.id WHERE j.url=?''',(item['url'],)).fetchone()
            if row:item.update(job_id=row['id'],queue_status=row['queue_status'] or '',application_status=row['application_status'])
    return items


def queue_task(identifier):
    """Import one vacancy and enqueue it; never launch a worker or claim sent."""
    from .db import connect,init_db
    from .queue_manager import enqueue
    from .repositories import JobRepository
    def change(items):
        item=next((item for item in items if item['id']==identifier),None)
        if item is None:raise KeyError(identifier)
        if item['kind']!='vacancy' or item['status']!='pending':
            raise ValueError('Only pending job applications can enter the application queue')
        parsed=urlparse(item['url'])
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('This task needs a valid HTTPS job link')
        init_db()
        with connect() as connection:
            row=connection.execute('SELECT * FROM jobs WHERE url=?',(item['url'],)).fetchone()
            if row is None:
                company='CEA' if parsed.hostname.endswith('.cea.fr') else parsed.hostname
                connection.execute('''INSERT INTO jobs(url,canonical_url,title,company,source,provider_key,
                     body,snippet,decision,tracker_note,source_variants_json)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                     (item['url'],item['url'],item['title'],company,'Personal to-do','pending_tasks',
                      item['note'],item['note'][:500],'review',item['note'],
                      json.dumps([{'source':item['source'],'url':item['url'],'provider_key':'pending_tasks'}])))
                row=connection.execute('SELECT * FROM jobs WHERE url=?',(item['url'],)).fetchone()
            job_id=row['id']
            if row['application_status'] in {'submitted','submitted_verified','withdrawn'} or row['tracker_stage'] in {'submitted','screening','interview','offer','rejected','withdrawn','hired','offer_declined','no_response'}:
                raise ValueError('This application is already sent or closed. Check its history instead of sending again.')
            previous=connection.execute('SELECT status FROM application_queue WHERE job_id=?',(job_id,)).fetchone()
        if previous:
            item['job_id']=job_id
            return {'job_id':job_id,'queue_status':previous['status'],'already_queued':True}
        JobRepository().assert_preparable(job_id)
        enqueue([job_id])
        with connect() as connection:
            queued=connection.execute('SELECT status FROM application_queue WHERE job_id=?',(job_id,)).fetchone()
        if not queued:raise ValueError('This job could not enter the queue. Confirm its review and eligibility first.')
        item['job_id']=job_id
        return {'job_id':job_id,'queue_status':queued['status'],'already_queued':False}
    return _change(change)
