from uuid import uuid4

from sqlmodel import Session

from app.core.database import create_db_and_tables, engine
from app.models.db import ReviewItem, ReviewSession, Run
from app.models.schemas import ParsedHypothesis, ReviewState
from app.services.openai_client import heuristic_parse_hypothesis
from app.services.review_memory import ReviewMemoryService


create_db_and_tables()


def test_review_memory_skips_stale_incompatible_runs():
    stale_run_id = f"stale-run-{uuid4()}"
    current_run_id = f"current-run-{uuid4()}"
    review_id = f"review-{uuid4()}"
    review_item_id = f"review-item-{uuid4()}"

    current_parsed = heuristic_parse_hypothesis(
        "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase post-thaw viability of HeLa cells.",
        preset_id="hela-trehalose",
    )

    with Session(engine) as session:
        for record_id, model in [
            (stale_run_id, Run),
            (current_run_id, Run),
        ]:
            existing = session.get(model, record_id)
            if existing is not None:
                session.delete(existing)
        existing_review = session.get(ReviewSession, review_id)
        if existing_review is not None:
            session.delete(existing_review)
        existing_item = session.get(ReviewItem, review_item_id)
        if existing_item is not None:
            session.delete(existing_item)
        session.commit()

        session.add(
            Run(
                id=stale_run_id,
                hypothesis="Legacy run",
                preset_id="hela-trehalose",
                parsed_hypothesis_json='{"original_text":"Legacy run","domain":"cell biology"}',
                review_state=ReviewState.generated,
            )
        )
        session.add(
            Run(
                id=current_run_id,
                hypothesis=current_parsed.original_text,
                preset_id="hela-trehalose",
                parsed_hypothesis_json=current_parsed.model_dump_json(),
                review_state=ReviewState.reviewed,
            )
        )
        session.add(
            ReviewSession(
                id=review_id,
                run_id=current_run_id,
                review_state=ReviewState.reviewed,
            )
        )
        session.add(
            ReviewItem(
                id=review_item_id,
                review_session_id=review_id,
                target_type="section",
                target_key="overview",
                action="comment",
                comment="Use a tighter scientist review note.",
            )
        )
        session.commit()

        memories = ReviewMemoryService().list_for_generation(
            session,
            parsed=current_parsed,
            preset_id="hela-trehalose",
        )

    assert memories
    assert all(memory.run_id == current_run_id for memory in memories)
