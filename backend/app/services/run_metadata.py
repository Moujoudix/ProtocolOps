from __future__ import annotations

from sqlmodel import Session, select

from app.models.db import PresentationAnchor, Run, RunRevision
from app.models.schemas import DomainRoute, EvidenceMode, EvidencePack, ExperimentPlan, LiteratureQC, RunMode, model_from_json


def resolve_run_mode(run: Run) -> RunMode:
    if run.used_seed_data:
        return RunMode.demo_fallback

    plan = model_from_json(ExperimentPlan, run.plan_json)
    literature_qc = model_from_json(LiteratureQC, run.literature_qc_json)
    provider_trace = (plan.literature_qc.provider_trace if plan else None) or (literature_qc.provider_trace if literature_qc else [])

    successful_providers = {entry.provider for entry in provider_trace if entry.succeeded}
    consensus_attempted = any(entry.provider == "Consensus" for entry in provider_trace)
    primary_literature_success = {"Semantic Scholar", "Europe PMC"} <= successful_providers

    if primary_literature_success and _route_specific_live_requirements_met(plan, successful_providers, consensus_attempted):
        return RunMode.fully_live
    return RunMode.degraded_live


def infer_evidence_mode(
    literature_qc: LiteratureQC | None,
    evidence_pack: EvidencePack | None = None,
) -> EvidenceMode:
    trace = []
    if evidence_pack is not None and evidence_pack.provider_trace:
        trace = evidence_pack.provider_trace
    elif literature_qc is not None:
        trace = literature_qc.provider_trace

    searched_labels: list[str] = []
    if literature_qc is not None:
        searched_labels.extend(literature_qc.searched_sources)
    if evidence_pack is not None:
        searched_labels.extend(evidence_pack.searched_providers)

    if "Cached live replay" in searched_labels or any(entry.cached and entry.fallback_used for entry in trace):
        return EvidenceMode.cached_live

    source_ids: list[str] = []
    if literature_qc is not None:
        source_ids.extend(source.id for source in literature_qc.literature_sources)
    if evidence_pack is not None:
        source_ids.extend(source.id for source in evidence_pack.sources)

    if any(source_id.startswith("seed-") for source_id in source_ids):
        return EvidenceMode.seeded_demo
    return EvidenceMode.strict_live


def _route_specific_live_requirements_met(
    plan: ExperimentPlan | None,
    successful_providers: set[str],
    consensus_attempted: bool,
) -> bool:
    if consensus_attempted and "Consensus" not in successful_providers:
        return False

    if plan is None:
        return False

    if plan.literature_qc.domain_route == DomainRoute.cell_biology:
        return any(source.trust_tier.value == "supplier_documentation" for source in plan.sources)

    return True


def get_parent_revision(session: Session, run_id: str) -> RunRevision | None:
    return session.exec(select(RunRevision).where(RunRevision.child_run_id == run_id)).first()


def get_child_revisions(session: Session, run_id: str) -> list[RunRevision]:
    return session.exec(
        select(RunRevision).where(RunRevision.parent_run_id == run_id).order_by(RunRevision.revision_number)
    ).all()


def next_revision_number(session: Session, run_id: str) -> int:
    current = get_parent_revision(session, run_id)
    if current is not None:
        return current.revision_number + 1

    existing = get_child_revisions(session, run_id)
    if not existing:
        return 1
    return max(item.revision_number for item in existing) + 1


def is_presentation_anchor(session: Session, run_id: str) -> bool:
    anchor = session.get(PresentationAnchor, "presentation")
    return bool(anchor and anchor.run_id == run_id)


def set_presentation_anchor(session: Session, run_id: str) -> None:
    session.merge(PresentationAnchor(label="presentation", run_id=run_id))
    session.commit()
