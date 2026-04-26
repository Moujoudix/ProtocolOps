from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Run(SQLModel, table=True):
    id: str = Field(primary_key=True)
    hypothesis: str
    preset_id: str | None = None
    status: str = "created"
    parsed_hypothesis_json: str | None = None
    literature_qc_json: str | None = None
    plan_json: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

