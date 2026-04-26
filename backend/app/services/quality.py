from __future__ import annotations

from app.models.schemas import (
    DomainRoute,
    EvidencePack,
    ExperimentPlan,
    LiteratureQC,
    ParsedHypothesis,
    PlanQualitySummary,
    ReviewMemoryReference,
    TrustTier,
)


def summarize_plan_quality(
    plan: ExperimentPlan,
    parsed: ParsedHypothesis,
    literature_qc: LiteratureQC,
    evidence_pack: EvidencePack,
    review_memory: list[ReviewMemoryReference],
) -> PlanQualitySummary:
    protocol_confidence = average([step.confidence for step in plan.protocol]) if plan.protocol else 0.0
    materials_confidence = average([item.confidence for item in plan.materials]) if plan.materials else 0.0
    budget_confidence = average([item.confidence for item in plan.budget.items]) if plan.budget.items else 0.0

    exact_or_close = count(
        source.evidence_type.value in {"exact_match", "close_match", "supplier_reference"}
        and source.trust_tier != TrustTier.inferred
        for source in plan.sources
    )
    community = count(source.trust_tier == TrustTier.community_protocol for source in plan.sources)
    inferred = count(source.trust_tier == TrustTier.inferred for source in plan.sources)

    total_sources = max(len(plan.sources), 1)
    evidence_completeness = min(
        1.0,
        (
            (exact_or_close / total_sources) * 0.65
            + ((community / total_sources) * 0.15)
            + max(0.0, 0.2 - ((inferred / total_sources) * 0.2))
        ),
    )

    review_flags = sum(
        1
        for flagged in [
            plan.overview.expert_review_required,
            plan.study_design.expert_review_required,
            plan.timeline.expert_review_required,
            plan.validation.expert_review_required,
            plan.risks.expert_review_required,
            plan.budget.expert_review_required,
            *(step.expert_review_required for step in plan.protocol),
        ]
        if flagged
    )
    total_reviewable = 6 + len(plan.protocol)
    review_burden = min(1.0, review_flags / max(total_reviewable, 1))

    domain_penalty = 0.0
    if parsed.domain_route == DomainRoute.animal_gut_health:
        domain_penalty = 0.05
    elif parsed.domain_route == DomainRoute.microbial_electrochemistry:
        domain_penalty = 0.04
    elif parsed.domain_route == DomainRoute.diagnostics_biosensor:
        domain_penalty = 0.03

    operational_readiness = clamp(
        (
            literature_qc.confidence * 0.2
            + protocol_confidence * 0.25
            + materials_confidence * 0.2
            + budget_confidence * 0.15
            + evidence_completeness * 0.15
            + min(0.1, len(review_memory) * 0.02)
            - (review_burden * 0.15)
            - domain_penalty
        )
    )

    return PlanQualitySummary(
        literature_confidence=literature_qc.confidence,
        protocol_confidence=protocol_confidence,
        materials_confidence=materials_confidence,
        budget_confidence=budget_confidence,
        evidence_completeness=clamp(evidence_completeness),
        operational_readiness=operational_readiness,
        review_burden=review_burden,
    )


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def count(values) -> int:
    return sum(1 for value in values if value)


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
