"""Job-specific letters through the existing authenticated ChatGPT session."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree
from datetime import datetime, timezone

from .chatgpt_bridge import ask_chatgpt_json
from .profile_store import ROOT
from .worker_runtime import check_cancelled, Cancelled
from . import letter_policy
from .letter_layout import correspondence, render_pdf
from filelock import FileLock, Timeout
import time
import uuid

LETTER_DIR = ROOT / 'data' / 'cover_letters'


from .workspaces import data_dir

def owned_directory():
    return LETTER_DIR if LETTER_DIR != ROOT / 'data' / 'cover_letters' else data_dir() / 'cover_letters'

def generation_error(exc: Exception) -> str:
    message = str(exc)
    if 'connect_over_cdp' in message or 'ECONNREFUSED' in message:
        return 'ChatGPT n’est pas connecté. Lancez start.bat puis connectez-vous à ChatGPT dans le navigateur dédié.'
    if 'prompt box not found' in message:
        return 'Connectez-vous à ChatGPT dans le navigateur dédié, puis relancez la génération.'
    if 'No ChatGPT response' in message:
        return 'ChatGPT n’a pas répondu à temps. Vérifiez sa connexion puis réessayez.'
    if 'Target page, context or browser has been closed' in message:
        return 'Le navigateur a été fermé pendant la génération. Rouvrez-le puis réessayez.'
    return message[:500]


def resume_text(path: Path | None) -> str:
    if not path or not path.is_file():
        raise ValueError('Aucun CV sélectionné. Ajoutez ou activez un CV dans le profil.')
    if path.suffix.lower() == '.pdf':
        from pypdf import PdfReader
        text = '\n'.join(page.extract_text() or '' for page in PdfReader(path).pages)
    elif path.suffix.lower() == '.docx':
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read('word/document.xml'))
        text = '\n'.join(node.text or '' for node in root.iter() if node.tag.endswith('}t'))
    else:
        raise ValueError('Convertissez le CV DOC en PDF ou DOCX pour générer une lettre.')
    if not text.strip():
        raise ValueError('Le CV ne contient pas de texte lisible. Utilisez un PDF avec texte ou un DOCX.')
    return text[:18000]


def letter_paths(job_id: int) -> tuple[Path, Path]:
    return owned_directory() / f'job_{job_id}.json', owned_directory() / f'job_{job_id}.pdf'


def save_letter_state(job_id: int, state: dict) -> None:
    metadata, _ = letter_paths(job_id)
    metadata.parent.mkdir(parents=True, exist_ok=True)
    temporary = metadata.with_name(metadata.name + '.' + uuid.uuid4().hex + '.tmp')
    state = {**state, 'updated_at': datetime.now(timezone.utc).isoformat()}
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(metadata)


def generation_payload(job, raw, resume_path):
    payload = {
        'policy_version': letter_policy.VERSION,
        'job': {key: job.get(key, '') for key in ('title', 'company', 'location', 'url', 'body', 'snippet', 'employment_type', 'start_date', 'end_date', 'search_profile_id')},
        'candidate': {key: raw.get(key, {}) for key in ('identity', 'background', 'availability', 'pfe')},
        'cv': resume_text(resume_path),
        'cv_sha256': hashlib.sha256(resume_path.read_bytes()).hexdigest() if resume_path else '',
        'correspondence_date': correspondence(job, raw, '')['date'],
    }
    return payload


def payload_fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def current_letter(state, job, raw, resume_path):
    if state.get('policy_version') != letter_policy.VERSION or state.get('quality', {}).get('passed') is not True:
        return False
    try:
        return state.get('fingerprint') == payload_fingerprint(generation_payload(job, raw, resume_path))
    except (ValueError, OSError):
        return False


def generate_letter(context, job: dict, raw: dict, resume_path: Path | None, cfg: dict) -> dict:
    owned_directory().mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(owned_directory() / f'job_{job["id"]}.lock'))
    deadline = time.monotonic() + 600
    while True:
        check_cancelled()
        try:
            lock.acquire(timeout=0.5)
            break
        except Timeout:
            if time.monotonic() >= deadline:
                raise RuntimeError('Une génération est déjà en cours. Réessayez plus tard.')
    try:
        return _generate_letter(context, job, raw, resume_path, cfg)
    finally:
        lock.release()


def _generate_letter(context, job: dict, raw: dict, resume_path: Path | None, cfg: dict) -> dict:
    metadata, pdf = letter_paths(int(job['id']))
    try:
        payload = generation_payload(job, raw, resume_path)
        fingerprint = payload_fingerprint(payload)
        if metadata.exists() and pdf.exists():
            cached = json.loads(metadata.read_text(encoding='utf-8'))
            if (cached.get('fingerprint') == fingerprint and cached.get('status') == 'ready'
                    and cached.get('policy_version') == letter_policy.VERSION
                    and cached.get('quality', {}).get('passed') is True):
                return cached
        if not cfg.get('enabled', True):
            raise ValueError('Activez ChatGPT Web dans le profil pour générer la lettre.')
        save_letter_state(job['id'], {'status': 'generating'})
        feedback = None
        for attempt in range(2):
            check_cancelled()
            result = ask_chatgpt_json(context, letter_policy.draft_prompt(payload, feedback), cfg, purpose='cover-letter')
            check_cancelled()
            body = result.get('letter')
            body = body.strip().replace('\r\n', '\n') if isinstance(body, str) else body
            issues = letter_policy.local_issues(body)
            concerns = result.get('concerns', [])
            if not isinstance(concerns, list) or concerns:
                issues.append('Faits contradictoires ou informations à confirmer : ' + str(concerns)[:600])
            audit = {}
            if not issues:
                audit = ask_chatgpt_json(context, letter_policy.audit_prompt(payload, body), cfg, purpose='cover-letter-review')
                check_cancelled()
                issues.extend(letter_policy.audit_issues(audit, payload))
            if not issues:
                break
            feedback = {'previous_letter': body, 'issues': issues}
        if issues:
            raise ValueError('Lettre à corriger avant utilisation : ' + ' ; '.join(issues))
        document = correspondence(job, raw, body)
        letter = document['inline']
        temporary_pdf = pdf.with_name(f'{pdf.stem}.{uuid.uuid4().hex}.tmp.pdf')
        try:
            render_pdf(temporary_pdf, document)
            temporary_pdf.replace(pdf)
        finally:
            temporary_pdf.unlink(missing_ok=True)
        state = {'status': 'ready', 'letter': letter, 'body': body, 'fingerprint': fingerprint,
                 'policy_version': letter_policy.VERSION,
                 'quality': {'passed': True, 'checks': audit['checks'], 'evidence': audit['evidence'],
                             'page_count': 1, 'attempts': attempt + 1, 'human_review_required': True}}
        save_letter_state(job['id'], state)
        return state
    except Cancelled:
        save_letter_state(job['id'], {'status': 'cancelled'})
        raise
    except Exception as exc:
        save_letter_state(job['id'], {'status': 'error', 'error': generation_error(exc)})
        raise
