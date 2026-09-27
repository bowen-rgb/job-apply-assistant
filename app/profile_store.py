from __future__ import annotations

import json
import re
import shutil
import uuid
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT / 'profile.json'
PROFILE_EXAMPLE = ROOT / 'profile.example.json'
DATA_DIR = ROOT / 'data'
RESUME_DIR = DATA_DIR / 'resumes'
RESUME_INDEX = RESUME_DIR / 'index.json'


def _deep_merge(base: dict, incoming: dict) -> dict:
    out = deepcopy(base)
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def default_profile() -> dict[str, Any]:
    return {
        'schema_version': 8,
        'identity': {
            'first_name': '',
            'last_name': '',
            'email': '',
            'phone': '',
            'address_line1': '',
            'city': '',
            'postal_code': '',
            'country': '',
            'linkedin': '',
            'portfolio': '',
        },
        'background': {
            'current_title': '',
            'current_company': '',
            'years_experience': '',
            'school': '',
            'degree': '',
            'field_of_study': '',
            'graduation_year': '',
        },
        'availability': {
            'start_date': '',
            'end_date': '',
            'text': '',
            'weekends': 'flexible',
            'night_shifts': 'flexible',
            'holiday_work': 'flexible',
            'hours_per_week_min': '',
            'hours_per_week_max': '',
        },
        'preferences': {
            'roles': [],
            'role_aliases': {},
            'locations': [],
            'contracts': [],
            'industries': [],
            'include_terms': [],
            'exclude_terms': [],
            'remote_modes': [],
            'max_commute_minutes': '',
            'min_salary': '',
            'salary_period': 'hour',
            'languages': [],
        },
        'application': {
            'active_resume_id': '',
            'cover_letter_path': '',
            'saved_answers': [],
            'custom_fields': [],
            'auto_resume_routing': False,
        },
        'review': {
            'rules': [
                'If an important fact is missing or ambiguous, request human review instead of guessing.',
                'Never answer sensitive/protected-personal questions automatically.',
                'Never make legally binding declarations on the candidate behalf.',
            ]
        },
        'automation': {
            'enabled_sources': [
                'france_travail', 'hellowork', 'indeed', 'wttj', 'cityone', 'plany',
                'staffme', 'adecco', 'manpower', 'randstad', 'synergie', 'meteojob',
                'crit', 'samsic', 'actual'
            ],
            'search_engines': ['bing', 'duckduckgo'],
            'search_queries_per_run': 18,
            'search_market': '',
            'custom_sources': [],
            'max_results_per_query': 10,
            'dynamic_fetch_fallback': True,
            'scan_delay_seconds': 0.25,
            'browser_mode': 'cdp',
            'chrome_cdp_endpoint': 'http://127.0.0.1:9222',
            'direct_source_discovery': True,
            'direct_sources': ['plany', 'cityone'],
            'direct_source_pages': 3,
            'auto_submit': False,
            'chatgpt_web_reviewer': {
                'enabled': True,
                'url': 'https://chatgpt.com/',
                'cdp_endpoint': 'http://127.0.0.1:9222',
                'timeout_seconds': 180,
                'keep_chat_tab_open': False,
            },
            'agent_fallback': {
                'enabled': True,
                'max_steps': 8,
                'min_action_confidence': 82,
                'allow_next_clicks': True,
                'run_for_agent_assisted_ats': True,
                'run_when_required_unanswered': True,
                'screenshot_each_step': False,
            },
            'company_boards': [],
            'jobspy_enabled': True,
            'jobspy_sites': ['indeed', 'google'],
            'jobspy_results_wanted': 20,
            'jobspy_hours_old': 168,
            'jobspy_country_indeed': '',
            'jobspy_timeout_seconds': 90,
            'jobspy_linkedin_fetch_description': False,
            'dedupe_scope': 'title_company_location',
            'search_profiles': [],
            'auto_scan_interval_minutes': 0,
        },
    }


def _legacy_to_v5(data: dict[str, Any]) -> dict[str, Any]:
    """Convert older profiles to the V8 user-editable schema."""
    p = default_profile()
    if not data:
        return p
    if int(data.get('schema_version') or 0) >= 5 and 'identity' in data:
        merged = _deep_merge(p, data)
        merged['schema_version'] = 8
        return merged

    p['identity'].update({
        'first_name': data.get('first_name', ''),
        'last_name': data.get('last_name', ''),
        'email': data.get('email', ''),
        'phone': data.get('phone', ''),
        'city': data.get('city', ''),
        'postal_code': data.get('postal_code', ''),
        'country': data.get('country', 'France'),
        'linkedin': data.get('linkedin', ''),
        'portfolio': data.get('portfolio', ''),
    })
    p['background'].update({
        'current_title': data.get('current_title', ''),
        'current_company': data.get('current_company', ''),
        'years_experience': data.get('years_experience', ''),
        'school': data.get('school', ''),
        'degree': data.get('degree', ''),
        'field_of_study': data.get('field_of_study', ''),
        'graduation_year': data.get('graduation_year', ''),
    })
    p['availability'].update({
        'end_date': data.get('max_end_date', ''),
        'text': data.get('availability_text', ''),
    })
    p['preferences'].update({
        'roles': data.get('preferred_roles', []),
        'role_aliases': data.get('role_aliases', {}),
        'locations': data.get('locations', []),
        'contracts': data.get('contracts', []),
        'exclude_terms': data.get('exclude_terms', []),
    })
    p['review']['rules'] = data.get('review_rules', p['review']['rules'])
    auto = p['automation']
    for key in (
        'enabled_sources', 'search_engines', 'search_queries_per_run', 'max_results_per_query',
        'dynamic_fetch_fallback', 'scan_delay_seconds', 'browser_mode', 'chrome_cdp_endpoint',
        'direct_source_discovery', 'direct_sources', 'direct_source_pages', 'auto_submit',
        'chatgpt_web_reviewer', 'agent_fallback', 'company_boards', 'search_market', 'custom_sources',
        'jobspy_enabled', 'jobspy_sites', 'jobspy_results_wanted', 'jobspy_hours_old',
        'jobspy_country_indeed', 'jobspy_timeout_seconds', 'jobspy_linkedin_fetch_description',
        'dedupe_scope', 'search_profiles', 'auto_scan_interval_minutes'
    ):
        if key in data:
            auto[key] = data[key]

    # Preserve an old resume as a synthetic external path until the user uploads it to the library.
    old_resume = data.get('resume_path')
    if old_resume:
        p['application']['legacy_resume_path'] = old_resume
    return p


def ensure_profile() -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    if PROFILE_PATH.exists():
        raw = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
    elif PROFILE_EXAMPLE.exists():
        raw = json.loads(PROFILE_EXAMPLE.read_text(encoding='utf-8'))
    else:
        raw = default_profile()
    p = _legacy_to_v5(raw)
    if p != raw:
        PROFILE_PATH.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding='utf-8')
    return p


def load_profile_raw() -> dict[str, Any]:
    return ensure_profile()


def save_profile_raw(data: dict[str, Any]) -> dict[str, Any]:
    current = ensure_profile()
    merged = _deep_merge(current, data or {})
    merged['schema_version'] = 8
    PROFILE_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')
    return merged


def _resume_index() -> list[dict[str, Any]]:
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    if not RESUME_INDEX.exists():
        return []
    try:
        rows = json.loads(RESUME_INDEX.read_text(encoding='utf-8'))
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def _write_resume_index(rows: list[dict[str, Any]]) -> None:
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    RESUME_INDEX.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')


def list_resumes() -> list[dict[str, Any]]:
    p = ensure_profile()
    active = p.get('application', {}).get('active_resume_id', '')
    rows = []
    for row in _resume_index():
        path = RESUME_DIR / row.get('filename', '')
        if not path.exists():
            continue
        x = dict(row)
        x['active'] = row.get('id') == active
        x['size'] = path.stat().st_size
        rows.append(x)
    return rows


def _safe_name(name: str) -> str:
    stem = re.sub(r'[^A-Za-z0-9._-]+', '_', Path(name or 'resume.pdf').name).strip('._')
    return stem or 'resume.pdf'


def add_resume(src_path: Path, original_name: str, label: str = '') -> dict[str, Any]:
    suffix = Path(original_name).suffix.lower()
    if suffix not in {'.pdf', '.doc', '.docx'}:
        raise ValueError('Only PDF, DOC and DOCX resumes are accepted')
    resume_id = uuid.uuid4().hex[:12]
    safe = _safe_name(original_name)
    filename = f'{resume_id}_{safe}'
    dst = RESUME_DIR / filename
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_path, dst)
    row = {
        'id': resume_id,
        'label': (label or Path(original_name).stem or 'CV').strip()[:100],
        'original_name': Path(original_name).name,
        'filename': filename,
        'uploaded_at': datetime.now(timezone.utc).isoformat(),
        'tags': [],
    }
    rows = _resume_index()
    rows.append(row)
    _write_resume_index(rows)
    p = ensure_profile()
    if not p.get('application', {}).get('active_resume_id'):
        p['application']['active_resume_id'] = resume_id
        save_profile_raw(p)
    return row


def activate_resume(resume_id: str) -> dict[str, Any]:
    if resume_id not in {x.get('id') for x in _resume_index()}:
        raise KeyError(resume_id)
    p = ensure_profile()
    p['application']['active_resume_id'] = resume_id
    save_profile_raw(p)
    return p


def delete_resume(resume_id: str) -> None:
    rows = _resume_index()
    target = next((x for x in rows if x.get('id') == resume_id), None)
    if not target:
        raise KeyError(resume_id)
    path = RESUME_DIR / target.get('filename', '')
    if path.exists():
        path.unlink()
    rows = [x for x in rows if x.get('id') != resume_id]
    _write_resume_index(rows)
    p = ensure_profile()
    if p.get('application', {}).get('active_resume_id') == resume_id:
        p['application']['active_resume_id'] = rows[0].get('id', '') if rows else ''
        save_profile_raw(p)


def active_resume_path(raw: dict[str, Any] | None = None) -> Path | None:
    p = raw or ensure_profile()
    rid = p.get('application', {}).get('active_resume_id', '')
    for row in _resume_index():
        if row.get('id') == rid:
            path = RESUME_DIR / row.get('filename', '')
            return path if path.exists() else None
    legacy = p.get('application', {}).get('legacy_resume_path', '')
    if legacy:
        path = Path(legacy)
        if not path.is_absolute():
            path = ROOT / path
        if path.exists():
            return path
    # Backward-friendly fallback for users dropping cv.pdf into root.
    fallback = ROOT / 'cv.pdf'
    return fallback if fallback.exists() else None



def replace_profile_raw(data: dict[str, Any]) -> dict[str, Any]:
    """Replace the profile with a normalized V8 document (used by dashboard import)."""
    if not isinstance(data, dict):
        raise ValueError('Profile must be a JSON object')
    normalized = _legacy_to_v5(data)
    normalized['schema_version'] = 8
    PROFILE_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding='utf-8')
    return normalized


def update_resume_metadata(resume_id: str, label: str | None = None, tags: list[str] | None = None) -> dict[str, Any]:
    rows = _resume_index()
    target = next((x for x in rows if x.get('id') == resume_id), None)
    if not target:
        raise KeyError(resume_id)
    if label is not None:
        target['label'] = str(label).strip()[:100] or target.get('label', 'CV')
    if tags is not None:
        clean = []
        seen = set()
        for tag in tags:
            t = str(tag).strip()[:80]
            if t and t.lower() not in seen:
                clean.append(t)
                seen.add(t.lower())
        target['tags'] = clean[:30]
    _write_resume_index(rows)
    return dict(target)


def select_resume_for_job(job: dict[str, Any], raw: dict[str, Any] | None = None) -> tuple[Path | None, dict[str, Any] | None]:
    """Choose a tagged resume when auto routing is enabled, else use the active resume.

    Routing is intentionally deterministic: tags must literally occur in title/body/contract/location.
    If nothing matches, the active resume is used.
    """
    p = raw or ensure_profile()
    rows = list_resumes()
    active_id = p.get('application', {}).get('active_resume_id', '')
    active = next((x for x in rows if x.get('id') == active_id), None)

    # A search campaign can explicitly bind one CV. This takes precedence over
    # automatic tag routing and makes multi-market workflows deterministic.
    search_profile_id = str(job.get('search_profile_id') or '').strip()
    if search_profile_id and search_profile_id != 'default':
        for campaign in p.get('automation', {}).get('search_profiles', []) or []:
            if str(campaign.get('id') or campaign.get('slug') or '') == search_profile_id:
                rid = str(campaign.get('resume_id') or '').strip()
                chosen = next((x for x in rows if x.get('id') == rid), None)
                if chosen:
                    path = RESUME_DIR / chosen.get('filename', '')
                    return (path if path.exists() else None), chosen
                break

    if not p.get('application', {}).get('auto_resume_routing', False):
        path = active_resume_path(p)
        return path, active

    def _norm_text(v: Any) -> str:
        x = unicodedata.normalize('NFD', str(v or ''))
        return ''.join(ch for ch in x if unicodedata.category(ch) != 'Mn').lower()

    hay = _norm_text(' '.join(str(job.get(k, '')) for k in ('title','body','snippet','employment_type','location')))
    best = None
    best_score = 0
    for row in rows:
        score = 0
        for tag in row.get('tags', []) or []:
            t = _norm_text(str(tag).strip())
            if t and t in hay:
                score += max(1, min(8, len(t.split())))
        if score > best_score:
            best_score = score
            best = row
    chosen = best if best_score > 0 else active
    if chosen:
        path = RESUME_DIR / chosen.get('filename', '')
        return (path if path.exists() else None), chosen
    return active_resume_path(p), None

def runtime_profile(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    """Flatten V8 settings to the keys used by discovery/reviewer/form engines.

    Keeping this adapter lets the automation engine stay modular while the dashboard/profile
    schema can evolve without hard-coding a particular candidate.
    """
    p = raw or ensure_profile()
    ident = p.get('identity', {})
    background = p.get('background', {})
    avail = p.get('availability', {})
    prefs = p.get('preferences', {})
    app = p.get('application', {})
    review = p.get('review', {})
    auto = p.get('automation', {})
    resume = active_resume_path(p)

    out = {
        'first_name': ident.get('first_name', ''),
        'last_name': ident.get('last_name', ''),
        'email': ident.get('email', ''),
        'phone': ident.get('phone', ''),
        'address_line1': ident.get('address_line1', ''),
        'city': ident.get('city', ''),
        'postal_code': ident.get('postal_code', ''),
        'country': ident.get('country', ''),
        'linkedin': ident.get('linkedin', ''),
        'portfolio': ident.get('portfolio', ''),
        'current_title': background.get('current_title', ''),
        'current_company': background.get('current_company', ''),
        'years_experience': background.get('years_experience', ''),
        'school': background.get('school', ''),
        'degree': background.get('degree', ''),
        'field_of_study': background.get('field_of_study', ''),
        'graduation_year': background.get('graduation_year', ''),
        'availability_text': avail.get('text', ''),
        'availability_start_date': avail.get('start_date', ''),
        'max_end_date': avail.get('end_date', ''),
        'availability': avail,
        'locations': prefs.get('locations', []),
        'contracts': prefs.get('contracts', []),
        'preferred_roles': prefs.get('roles', []),
        'role_aliases': prefs.get('role_aliases', {}),
        'industries': prefs.get('industries', []),
        'include_terms': prefs.get('include_terms', []),
        'exclude_terms': prefs.get('exclude_terms', []),
        'remote_modes': prefs.get('remote_modes', []),
        'max_commute_minutes': prefs.get('max_commute_minutes', ''),
        'min_salary': prefs.get('min_salary', ''),
        'salary_period': prefs.get('salary_period', 'hour'),
        'languages': prefs.get('languages', []),
        'review_rules': review.get('rules', []),
        'saved_answers': app.get('saved_answers', []),
        'custom_fields': app.get('custom_fields', []),
        'resume_path': str(resume) if resume else '',
        'active_resume_id': app.get('active_resume_id', ''),
        'auto_resume_routing': bool(app.get('auto_resume_routing', False)),
    }
    out.update(auto)
    return out
