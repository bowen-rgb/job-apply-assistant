"""Version-bound human decisions, separate from the AI's recommendation.

Like GitHub's stale-review dismissal, confirmation belongs to the reviewed
content, not indefinitely to an item ID.
https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
"""
import hashlib
import json

REVIEWABLE = {'APPLY', 'HUMAN_REVIEW'}
AUTOMATIC_REVIEW_POLICY_VERSION = '2026-10-31-compact-v1'


def review_token(job: dict) -> str:
    fields = ('review_revision', 'reviewed_at', 'review_verdict', 'review_summary',
              'review_json', 'title', 'company', 'location', 'body',
              'employment_type', 'start_date', 'end_date', 'valid_through')
    return hashlib.sha256(json.dumps([job.get(k) or '' for k in fields],
                                   ensure_ascii=False).encode('utf-8')).hexdigest()


def confirmation_status(job: dict) -> str:
    if job.get('review_verdict') not in REVIEWABLE:
        return 'not_required'
    if job.get('human_review_fingerprint') != review_token(job):
        return 'pending'
    return job.get('human_review_status') or 'pending'


def annotate(job: dict) -> dict:
    result = dict(job)
    result['human_review_status'] = confirmation_status(job)
    result['automatic_review_ready'] = automatic_ready(job)
    result['human_review_token'] = review_token(job)
    return result


def automatic_token(job: dict) -> str:
    from .profile_store import load_profile_raw
    return hashlib.sha256((AUTOMATIC_REVIEW_POLICY_VERSION+review_token(job)+json.dumps(load_profile_raw(), sort_keys=True, ensure_ascii=False)).encode()).hexdigest()


def automatic_ready(job: dict) -> bool:
    return bool(job.get('review_verdict') == 'APPLY' and job.get('automatic_review_token') and job.get('automatic_review_token') == automatic_token(job)
            and confirmation_status(job) != 'declined')


def can_prepare(job: dict) -> bool:
    if job.get('review_verdict') in {'QUEUED', 'RUNNING'}:
        return False
    return automatic_ready(job) or job.get('review_verdict') not in REVIEWABLE or confirmation_status(job) == 'approved'
