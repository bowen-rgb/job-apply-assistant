"""Immutable application packets, append-only lessons, and previewed local resets."""
import hashlib
import io
import json
from pathlib import Path
import uuid
import zipfile
from . import capability_store as store
from .repositories.jobs import JobRepository
from .repositories.application_insights import activities
from .profile_store import load_profile_raw,select_resume_for_job,list_resumes
from .db import connect


def archive_job(job_id):
    with connect() as c:row=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
    if not row:raise KeyError(job_id)
    job=dict(row);path,resume=select_resume_for_job(job)
    identifier='archive-'+uuid.uuid4().hex[:16];target=store.safe_file('archives/'+identifier+'.zip');target.parent.mkdir(exist_ok=True)
    snapshot={'job':job,'stage_events':JobRepository().stage_events(job_id),'activities':activities(job_id),'resume':resume}
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr('application.json',json.dumps(snapshot,ensure_ascii=False,indent=2))
        if path and path.is_file():output.write(path,'resume'+path.suffix.lower())
        from .cover_letter import letter_paths
        meta,pdf=letter_paths(job_id)
        if meta.is_file():output.write(meta,'letter-state.json')
        if pdf.is_file():output.write(pdf,'letter.pdf')
    result={'job_id':job_id,'artifact':str(target.relative_to(store.folder())),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    store.save_item(identifier,'archive',result);return result


def calibration_context():
    jobs=[job for job in JobRepository().pipeline() if job.get('tracker_stage') in {'rejected','withdrawn','offer','hired','offer_declined','no_response'}]
    return [{'company':j['company'],'title':j['title'],'stage':j['tracker_stage'],'note':j['tracker_note'],
             'review':j.get('review_json',''),'events':JobRepository().stage_events(j['id'])} for j in jobs]


def reset_preview(scope):
    if scope not in {'profile','documents','all'}:raise ValueError('Unknown reset scope')
    with connect() as c:jobs=c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
    state={'scope':scope,'profile':load_profile_raw(),'resumes':list_resumes(),'documents':store.items('document'),
           'templates':store.items('template'),'jobs':jobs}
    token=hashlib.sha256(json.dumps(state,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'scope':scope,'token':token,'jobs':jobs if scope=='all' else 0,
            'resumes':len(state['resumes']) if scope in {'documents','all'} else 0,
            'documents':len(state['documents']) if scope in {'documents','all'} else 0,
            'templates':len(state['templates']) if scope in {'documents','all'} else 0,
            'profile_will_reset':scope in {'profile','all'},'accounts_preserved':True,
            'tool_history_preserved':True,'archives_preserved':True}


def reset(scope,token,confirmation):
    if confirmation!='RESET' or reset_preview(scope)['token']!=token:raise ValueError('Review the current reset preview and type RESET')
    from .worker_runtime import any_running
    from .queue_manager import status as queue_status
    from .scan_manager import status as scan_status
    if any_running() or queue_status().get('running') or scan_status().get('running'):raise ValueError('Stop active tasks before resetting data')
    backup=store.safe_file('archives/reset-'+uuid.uuid4().hex+'.zip');backup.parent.mkdir(exist_ok=True)
    from .profile_store import resume_directory
    snapshot={'profile':load_profile_raw(),'jobs':JobRepository().list(),'resumes':list_resumes(),
              'documents':store.items('document'),'templates':store.items('template')}
    with zipfile.ZipFile(backup,'w',compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr('snapshot.json',json.dumps(snapshot,ensure_ascii=False))
        for row in snapshot['resumes']:
            path=(resume_directory()/row['filename']).resolve()
            if not path.is_relative_to(resume_directory().resolve()):raise ValueError('Invalid resume copy')
            if path.is_file():output.write(path,'resumes/'+path.name)
        for kind in ('documents','templates'):
            for row in snapshot[kind]:
                path=store.safe_file(row['path'])
                if kind=='templates':
                    from .document_templates import template_root
                    root=template_root(row);paths=list(root.rglob('*'))
                    if any(not p.resolve().is_relative_to(root) for p in paths):raise ValueError('Template contains a path outside its registered copy')
                else:paths=[path]
                for source in paths:
                    source=store.safe_file(str(source.relative_to(store.folder())))
                    if source.is_file():output.write(source,str(source.relative_to(store.folder())))
        # Include every table and binary SQLite value as a restorable SQL dump.
        with connect() as c:output.writestr('database.sql','\n'.join(c.iterdump()))
    with zipfile.ZipFile(backup) as verify:
        if verify.testzip():raise ValueError('Reset backup could not be verified')
    # Remove only generated/imported copies, never original uploads in Downloads/Desktop.
    if scope in {'documents','all'}:
        from .profile_store import delete_resume
        for row in list_resumes():delete_resume(row['id'])
        for row in store.items('document'):
            path=store.safe_file(row['path'])
            if path.is_file():path.unlink()
        from .document_templates import template_root
        for row in store.items('template'):
            root=template_root(row)
            for path in sorted(root.rglob('*'),key=lambda p:len(p.parts),reverse=True):
                if not path.resolve().is_relative_to(root):raise ValueError('Invalid template copy')
                if path.is_file():path.unlink()
                elif path.is_dir():path.rmdir()
            root.rmdir()
        with connect() as c:c.execute("DELETE FROM capability_items WHERE kind IN ('document','template')")
    if scope=='all':JobRepository().clear()
    if scope in {'profile','all'}:
        from .profile_store import replace_profile_raw,default_profile
        replace_profile_raw(default_profile())
    return {'ok':True,'backup':str(backup.relative_to(store.folder()))}
