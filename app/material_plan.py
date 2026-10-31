"""Read-only material intent, separate from actual generation and upload evidence."""
from .profile_store import select_resume_for_job
from .application_target import requires_letter


def material_plan(job,raw):
    path,meta=select_resume_for_job(job,raw)
    meta=meta or {}
    return {'status':'planned','resume_id':meta.get('id',''),'resume_label':meta.get('label',''),
            'resume_available':bool(path and path.is_file()),'selection_reason':meta.get('selection_reason',''),
            'matched_tags':meta.get('matched_tags',[]),
            'letter_mode':'targeted' if requires_letter(job,raw) else 'cv_only'}
