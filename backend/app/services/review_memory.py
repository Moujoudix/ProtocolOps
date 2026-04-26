from __future__ import annotations

from sqlmodel import Session, select

from app.models.db import ReviewItem, ReviewSession, Run
from app.models.schemas import ParsedHypothesis, ReviewAction, ReviewMemoryReference, ReviewState, ReviewTargetType
from app.models.schemas import model_from_json


class ReviewMemoryService:
    def list_for_generation(
        self,
        session: Session | None,
        parsed: ParsedHypothesis,
        preset_id: str | None,
    ) -> list[ReviewMemoryReference]:
        if session is None:
            return []

        candidate_runs = session.exec(select(Run)).all()
        ranked_candidates: list[tuple[float, Run, ParsedHypothesis | None]] = []
        for run in candidate_runs:
            run_parsed = model_from_json(ParsedHypothesis, run.parsed_hypothesis_json)
            score = run_similarity_score(run, run_parsed, parsed, preset_id)
            if score <= 0:
                continue
            ranked_candidates.append((score, run, run_parsed))

        ranked_candidates.sort(key=lambda item: item[0], reverse=True)
        candidate_runs = [item[1] for item in ranked_candidates[:24]]
        run_ids = [run.id for run in candidate_runs]
        if not run_ids:
            return []

        reviews = session.exec(
            select(ReviewSession).where(
                ReviewSession.run_id.in_(run_ids),
                ReviewSession.review_state.in_([ReviewState.reviewed, ReviewState.revised, ReviewState.approved_for_proposal]),
            )
        ).all()
        review_ids = [review.id for review in reviews]
        if not review_ids:
            return []

        review_by_id = {review.id: review for review in reviews}
        items = session.exec(select(ReviewItem).where(ReviewItem.review_session_id.in_(review_ids))).all()

        review_score = {
            review.id: review_session_score(review)
            for review in reviews
        }
        memories: list[tuple[float, ReviewMemoryReference]] = []
        for item in items:
            note = item.comment or item.replacement_text
            if not note:
                continue
            score = review_score[item.review_session_id] + item_score(item)
            if score < 0.45:
                continue
            memories.append(
                (
                    score,
                    ReviewMemoryReference(
                        run_id=review_by_id[item.review_session_id].run_id,
                        review_session_id=item.review_session_id,
                        target_type=ReviewTargetType(item.target_type),
                        target_key=item.target_key,
                        action=ReviewAction(item.action),
                        note=note,
                        confidence=item.confidence_override,
                    ),
                )
            )

        unique: list[ReviewMemoryReference] = []
        seen: set[tuple[str, str, str]] = set()
        for _, memory in sorted(memories, key=lambda item: item[0], reverse=True):
            key = (memory.run_id, memory.target_type, memory.target_key)
            if key in seen:
                continue
            seen.add(key)
            unique.append(memory)
        return unique[:12]


def run_similarity_score(
    run: Run,
    run_parsed: ParsedHypothesis | None,
    parsed: ParsedHypothesis,
    preset_id: str | None,
) -> float:
    score = 0.0
    if preset_id and run.preset_id == preset_id:
        score += 0.7
    if run_parsed and run_parsed.domain_route == parsed.domain_route:
        score += 0.55

    run_terms = set(normalize_terms(run_parsed.key_terms if run_parsed else []))
    current_terms = set(normalize_terms(parsed.key_terms))
    overlap = len(run_terms & current_terms)
    score += min(0.45, overlap * 0.08)

    if run.review_state == ReviewState.approved_for_proposal:
        score += 0.18
    elif run.review_state == ReviewState.revised:
        score += 0.12
    elif run.review_state == ReviewState.reviewed:
        score += 0.08

    return round(score, 4)


def review_session_score(review: ReviewSession) -> float:
    score = 0.3
    if review.review_state == ReviewState.approved_for_proposal:
        score += 0.3
    elif review.review_state == ReviewState.revised:
        score += 0.22
    elif review.review_state == ReviewState.reviewed:
        score += 0.16
    return score


def item_score(item: ReviewItem) -> float:
    score = 0.08
    if item.action in {ReviewAction.replace.value, ReviewAction.edit.value, ReviewAction.approve.value}:
        score += 0.18
    elif item.action in {ReviewAction.unrealistic.value, ReviewAction.missing_dependency.value}:
        score += 0.14
    elif item.action in {ReviewAction.reject.value, ReviewAction.comment.value}:
        score += 0.06

    if item.confidence_override is not None:
        score += max(0.0, min(0.2, item.confidence_override * 0.2))
    return score


def normalize_terms(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        token = value.strip().lower()
        if token:
            normalized.append(token)
    return normalized
