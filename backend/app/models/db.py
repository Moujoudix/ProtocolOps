from datetime import datetime, timezone

from sqlmodel import Field, SQLModel

from app.models.schemas import ReviewState


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Run(SQLModel, table=True):
    id: str = Field(primary_key=True)
    hypothesis: str
    preset_id: str | None = None
    status: str = "created"
    review_state: ReviewState = ReviewState.generated
    used_seed_data: bool = False
    parsed_hypothesis_json: str | None = None
    literature_qc_json: str | None = None
    plan_json: str | None = None
    quality_summary_json: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ConsensusCache(SQLModel, table=True):
    normalized_hypothesis: str = Field(primary_key=True)
    query: str
    references_json: str
    literature_synthesis: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RunEvent(SQLModel, table=True):
    id: str = Field(primary_key=True)
    run_id: str = Field(index=True)
    stage: str
    status: str
    message: str
    created_at: datetime = Field(default_factory=utc_now)


class ReviewSession(SQLModel, table=True):
    id: str = Field(primary_key=True)
    run_id: str = Field(index=True)
    reviewer_name: str | None = None
    summary: str | None = None
    review_state: ReviewState = ReviewState.reviewed
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ReviewItem(SQLModel, table=True):
    id: str = Field(primary_key=True)
    review_session_id: str = Field(index=True)
    target_type: str
    target_key: str
    action: str
    comment: str | None = None
    replacement_text: str | None = None
    confidence_override: float | None = None
    created_at: datetime = Field(default_factory=utc_now)


class RunRevision(SQLModel, table=True):
    child_run_id: str = Field(primary_key=True)
    parent_run_id: str = Field(index=True)
    revision_number: int = 1
    created_at: datetime = Field(default_factory=utc_now)


class PresentationAnchor(SQLModel, table=True):
    label: str = Field(primary_key=True)
    run_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now)
