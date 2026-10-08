"""Small, read-only handoff summary from a locally stored preparation audit."""
from .workspaces import data_dir
import json
from pathlib import Path
from urllib.parse import urlparse

from .profile_store import ROOT
_ORIGINAL_ROOT = ROOT


def preparation_summary(job: dict) -> dict:
    summary = {'audit_available': False, 'form_url': job.get('url', ''),
               'documents': {}, 'required_unanswered': None, 'missing_fields': []}
    try:
        path = Path(job.get('fill_audit_path') or '').resolve()
        if ((ROOT / 'data' if ROOT != _ORIGINAL_ROOT else data_dir()) / 'application_audits').resolve() not in path.parents:
            return summary
        audit = json.loads(path.read_text(encoding='utf-8'))
        documents = audit.get('documents', {})
        labels = audit.get('required_unanswered_labels', [])
        count = audit.get('required_unanswered_count')
        summary.update(audit_available=True, documents={
            'resume_attached': bool(documents.get('resume_attached')),
            'letter_attached': bool(documents.get('letter_attached') or documents.get('letter_text_filled')),
            'letter_generated': bool(documents.get('letter_generated')),
        }, required_unanswered=count if isinstance(count, int) and count >= 0 else None,
            missing_fields=[label for label in labels if isinstance(label, str)] if isinstance(labels, list) else [])
        url = audit.get('page_url_after_prepare') or job.get('url', '')
        if urlparse(url).scheme in {'http', 'https'}:
            summary['form_url'] = url
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return summary
