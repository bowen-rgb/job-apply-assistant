"""Application workflow orchestration.

External browser and reviewer workers are intentionally called from this
service, keeping HTTP handlers thin and making the safety boundary testable.
"""

from __future__ import annotations

from typing import Any

from ..browser import launch_apply
from ..batch_review_launcher import launch_batch_review
from ..review_launcher import launch_review
from ..repositories import JobRepository


class ApplicationService:
    def __init__(self, jobs: JobRepository | None = None):
        self.jobs = jobs or JobRepository()

    def queue_review(self, job_id: int, enabled: bool = True) -> dict[str, Any]:
        if not enabled:
            raise ValueError('ChatGPT web reviewer is disabled')
        if not self.jobs.exists(job_id):
            raise KeyError(job_id)
        self.jobs.mark_review_queued(job_id)
        launch_review(job_id)
        return {'ok': True, 'message': 'ChatGPT web review queued'}

    def queue_batch_review(self, mode: str) -> dict[str, Any]:
        if mode not in {'strong', 'liked'}:
            raise ValueError('mode must be strong or liked')
        launch_batch_review(mode)
        return {'ok': True, 'message': f'Batch review queued: {mode}'}

    def prefill(self, job_id: int) -> dict[str, Any]:
        if not self.jobs.exists(job_id):
            raise KeyError(job_id)
        review_verdict = self.jobs.review_verdict(job_id)
        launch_apply(job_id)
        return {'ok': True, 'message': 'Browser worker launched', 'review_verdict': review_verdict}
