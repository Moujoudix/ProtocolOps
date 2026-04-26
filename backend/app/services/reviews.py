from __future__ import annotations

from uuid import uuid4

from sqlmodel import Session, select

from app.models.db import ReviewItem, ReviewSession, Run, utc_now
from app.models.schemas import (
    ReviewItemPayload,
    ReviewItemRecord,
    ReviewSessionRecord,
    ReviewSubmissionRequest,
    ReviewSubmissionResponse,
)


def create_review(
    session: Session,
    *,
    run: Run,
    submission: ReviewSubmissionRequest,
) -> ReviewSubmissionResponse:
    review = ReviewSession(
        id=str(uuid4()),
        run_id=run.id,
        reviewer_name=submission.reviewer_name,
        summary=submission.summary,
        review_state=submission.review_state,
        updated_at=utc_now(),
    )
    session.add(review)

    items = [build_review_item(review.id, item) for item in submission.items]
    for item in items:
        session.add(item)

    run.review_state = submission.review_state
    run.updated_at = utc_now()
    session.add(run)
    session.commit()

    return ReviewSubmissionResponse(
        review=ReviewSessionRecord(
            id=review.id,
            run_id=review.run_id,
            reviewer_name=review.reviewer_name,
            summary=review.summary,
            review_state=review.review_state,
            created_at=review.created_at,
            updated_at=review.updated_at,
            items=[to_review_item_record(item) for item in items],
        )
    )


def list_reviews(session: Session, run_id: str) -> list[ReviewSessionRecord]:
    sessions = session.exec(
        select(ReviewSession).where(ReviewSession.run_id == run_id).order_by(ReviewSession.created_at.desc())
    ).all()
    if not sessions:
        return []

    session_ids = [review.id for review in sessions]
    items = session.exec(select(ReviewItem).where(ReviewItem.review_session_id.in_(session_ids))).all()
    items_by_review: dict[str, list[ReviewItem]] = {review_id: [] for review_id in session_ids}
    for item in items:
        items_by_review.setdefault(item.review_session_id, []).append(item)

    records: list[ReviewSessionRecord] = []
    for review in sessions:
        records.append(
            ReviewSessionRecord(
                id=review.id,
                run_id=review.run_id,
                reviewer_name=review.reviewer_name,
                summary=review.summary,
                review_state=review.review_state,
                created_at=review.created_at,
                updated_at=review.updated_at,
                items=[to_review_item_record(item) for item in items_by_review.get(review.id, [])],
            )
        )
    return records


def build_review_item(review_session_id: str, item: ReviewItemPayload) -> ReviewItem:
    return ReviewItem(
        id=str(uuid4()),
        review_session_id=review_session_id,
        target_type=item.target_type,
        target_key=item.target_key,
        action=item.action,
        comment=item.comment,
        replacement_text=item.replacement_text,
        confidence_override=item.confidence_override,
    )


def to_review_item_record(item: ReviewItem) -> ReviewItemRecord:
    return ReviewItemRecord(
        id=item.id,
        target_type=item.target_type,
        target_key=item.target_key,
        action=item.action,
        comment=item.comment,
        replacement_text=item.replacement_text,
        confidence_override=item.confidence_override,
        created_at=item.created_at,
    )
