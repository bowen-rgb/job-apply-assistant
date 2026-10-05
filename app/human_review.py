"""Version-bound human decisions, separate from the AI's recommendation.

Like GitHub's stale-review dismissal, confirmation belongs to the reviewed
content, not indefinitely to an item ID.
https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
"""
import hashlib
import json

REVIEWABLE = {'APPLY', 'HUMAN_REVIEW'}


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
    result['human_review_token'] = review_token(job)
    return result


def can_prepare(job: dict) -> bool:
    if job.get('review_verdict') in {'QUEUED', 'RUNNING'}:
        return False
    return job.get('review_verdict') not in REVIEWABLE or confirmation_status(job) == 'approved'
