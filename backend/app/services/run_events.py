from __future__ import annotations

from uuid import uuid4

from sqlmodel import Session, select

from app.models.db import RunEvent
from app.models.schemas import RunEventRecord


def record_run_event(
    session: Session,
    *,
    run_id: str,
    stage: str,
    status: str,
    message: str,
) -> RunEvent:
    event = RunEvent(
        id=str(uuid4()),
        run_id=run_id,
        stage=stage,
        status=status,
        message=message,
    )
    session.add(event)
    session.commit()
    return event


def list_run_events(session: Session, run_id: str) -> list[RunEventRecord]:
    events = session.exec(select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.created_at)).all()
    return [RunEventRecord.model_validate(event.model_dump()) for event in events]
