"""HTTP contracts and workflow vocabulary shared by the API surface.

Keeping request models and allowed state values outside ``main.py`` follows the
same controller/service separation used by mature FastAPI applications. The
database layer remains private to repositories and services.
"""

from typing import Literal

from pydantic import BaseModel, Field


DecisionValue = Literal[
    'liked', 'skipped', 'clear_user_action', 'keep', 'review', 'low',
    'reject', 'expired',
]
ApplicationStatusValue = Literal[
    'prefilled', 'needs_human', 'submitted', 'submitted_verified',
    'withdrawn', 'error', '',
]
TrackerStage = Literal[
    'saved', 'queued', 'prepared', 'submitted', 'screening', 'interview',
    'offer', 'rejected', 'withdrawn',
]

TRACK_STAGES = frozenset({
    'saved', 'queued', 'prepared', 'submitted', 'screening', 'interview',
    'offer', 'rejected', 'withdrawn',
})


class Decision(BaseModel):
    decision: DecisionValue


class ResumePatch(BaseModel):
    label: str | None = None
    tags: list[str] | None = None


class ApplicationStatus(BaseModel):
    status: ApplicationStatusValue


class HumanReview(BaseModel):
    status: Literal['approved', 'declined', 'pending']
    review_token: str = Field(min_length=64, max_length=64)


class ReviewExport(BaseModel):
    format: Literal['html', 'xlsx'] = 'html'
    language: Literal['zh', 'fr', 'en', 'de', 'es', 'pt'] = 'zh'
    scope: Literal['pending', 'visible'] = 'pending'
    job_ids: list[int] = Field(default_factory=list, max_length=1000)
    translate_text: bool = True


class QueueRequest(BaseModel):
    job_ids: list[int] = Field(min_length=1, max_length=200)
    priority: int = Field(default=100, ge=0, le=1000)


class TitleTranslationRequest(BaseModel):
    job_ids: list[int] = Field(min_length=1, max_length=12)
    language: Literal['zh', 'fr', 'en', 'de', 'es', 'pt']


class TrackPatch(BaseModel):
    stage: TrackerStage
    note: str = Field(default='', max_length=4000)
    followup_at: str = Field(default='', max_length=80)
    source: Literal['', 'email', 'recruiter_portal', 'phone', 'manual'] = ''
