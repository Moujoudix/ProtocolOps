import csv
import io
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.models.db import Run, RunRevision, utc_now
from app.models.schemas import (
    ComparisonMetricRecord,
    ExperimentPlan,
    LiteratureQC,
    LiteratureQcRequest,
    LiteratureQcResponse,
    PlanQualitySummary,
    RunComparisonResponse,
    ParsedHypothesis,
    PlanResponse,
    Preset,
    ReadinessResponse,
    ReviewState,
    ReviewSessionRecord,
    ReviewSubmissionRequest,
    ReviewSubmissionResponse,
    RunEventRecord,
    RunListItem,
    RunStateResponse,
    model_from_json,
)
from app.providers.base import SearchContext
from app.seeds.presets import PRESETS
from app.services.literature_qc import LiteratureQcService
from app.services.openai_client import OpenAIStructuredClient
from app.services.plan_generation import PlanGenerationService
from app.services.comparison import compare_plans
from app.services.pdf_export import build_plan_pdf
from app.services.readiness import ReadinessService
from app.services.replay_cache import EvidenceReplayCacheService
from app.services.reviews import create_review, list_reviews
from app.services.run_metadata import (
    get_child_revisions,
    get_parent_revision,
    infer_evidence_mode,
    is_presentation_anchor,
    next_revision_number,
    resolve_run_mode,
    set_presentation_anchor,
)
from app.services.run_events import list_run_events, record_run_event


router = APIRouter()


@router.get("/presets", response_model=list[Preset])
def list_presets() -> list[Preset]:
    return PRESETS


@router.get("/readiness", response_model=ReadinessResponse)
async def get_readiness(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ReadinessResponse:
    return await ReadinessService(settings).build(session=session)


@router.get("/runs", response_model=list[RunListItem])
def list_runs(session: Session = Depends(get_session)) -> list[RunListItem]:
    runs = session.exec(select(Run).order_by(Run.updated_at.desc())).all()
    items: list[RunListItem] = []
    for run in runs:
        parsed = safe_model_from_json(ParsedHypothesis, run.parsed_hypothesis_json)
        plan = safe_model_from_json(ExperimentPlan, run.plan_json)
        quality_summary = safe_model_from_json(PlanQualitySummary, run.quality_summary_json)
        parent_revision = get_parent_revision(session, run.id)
        items.append(
            RunListItem(
                run_id=run.id,
                hypothesis=run.hypothesis,
                preset_id=run.preset_id,
                status=run.status,
                review_state=run.review_state,
                run_mode=resolve_run_mode(run),
                evidence_mode=run.evidence_mode,
                created_at=run.created_at,
                updated_at=run.updated_at,
                domain=parsed.domain if parsed else None,
                plan_title=plan.plan_title if plan else None,
                quality_summary=quality_summary,
                used_seed_data=run.used_seed_data,
                is_presentation_anchor=is_presentation_anchor(session, run.id),
                parent_run_id=parent_revision.parent_run_id if parent_revision else None,
                revision_number=parent_revision.revision_number if parent_revision else 0,
            )
        )
    return items


@router.post("/literature-qc", response_model=LiteratureQcResponse)
async def create_literature_qc(
    request: LiteratureQcRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> LiteratureQcResponse:
    parser = OpenAIStructuredClient(settings)
    parsed = await parser.parse_hypothesis(request.hypothesis, preset_id=request.preset_id)
    context = SearchContext(parsed_hypothesis=parsed, preset_id=request.preset_id, stage="literature_qc")
    literature_qc = await LiteratureQcService(settings).run(context, session=session)

    run_id = str(uuid4())
    run = Run(
        id=run_id,
        hypothesis=request.hypothesis,
        preset_id=request.preset_id,
        status="literature_qc_complete",
        evidence_mode=infer_evidence_mode(literature_qc),
        used_seed_data=any(source.id.startswith("seed-") for source in literature_qc.literature_sources),
        parsed_hypothesis_json=parsed.model_dump_json(),
        literature_qc_json=literature_qc.model_dump_json(),
        updated_at=utc_now(),
    )
    session.add(run)
    session.commit()
    record_run_event(
        session,
        run_id=run_id,
        stage="hypothesis_parse",
        status="completed",
        message="Hypothesis parsed into structured fields.",
    )
    record_run_event(
        session,
        run_id=run_id,
        stage="literature_qc",
        status="completed",
        message="Literature QC completed and references stored.",
    )

    return LiteratureQcResponse(run_id=run.id, parsed_hypothesis=parsed, literature_qc=literature_qc)


@router.post("/runs/{run_id}/plan", response_model=PlanResponse)
async def create_plan(
    run_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PlanResponse:
    run = get_run_or_404(session, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.parsed_hypothesis_json is None or run.literature_qc_json is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Literature QC must complete before plan generation",
        )

    parsed = model_from_json(ParsedHypothesis, run.parsed_hypothesis_json)
    literature_qc = model_from_json(LiteratureQC, run.literature_qc_json)
    record_run_event(
        session,
        run_id=run.id,
        stage="plan_generation",
        status="started",
        message="Building evidence pack and preparing plan generation.",
    )
    plan, evidence_pack, _ = await PlanGenerationService(settings).run_with_artifacts(
        parsed,
        literature_qc,
        run.preset_id,
        session=session,
    )

    run.status = "plan_complete"
    run.evidence_mode = infer_evidence_mode(literature_qc, evidence_pack)
    run.used_seed_data = evidence_pack.used_seed_data
    run.plan_json = plan.model_dump_json()
    run.quality_summary_json = plan.quality_summary.model_dump_json() if plan.quality_summary else None
    run.updated_at = utc_now()
    session.add(run)
    session.commit()
    session.refresh(run)
    if run.evidence_mode.value == "strict_live" and not evidence_pack.used_seed_data:
        EvidenceReplayCacheService().store(
            session,
            hypothesis=run.hypothesis,
            preset_id=run.preset_id,
            literature_qc=literature_qc,
            evidence_pack=evidence_pack,
            source_run_id=run.id,
        )
    record_run_event(
        session,
        run_id=run.id,
        stage="evidence_pack",
        status="completed",
        message=f"Evidence pack constructed from {len(evidence_pack.sources)} sources.",
    )
    record_run_event(
        session,
        run_id=run.id,
        stage="plan_generation",
        status="completed",
        message="Experiment plan generated and persisted.",
    )

    return PlanResponse(run_id=run.id, plan=plan)


@router.get("/runs/{run_id}", response_model=RunStateResponse)
def get_run(run_id: str, session: Session = Depends(get_session)) -> RunStateResponse:
    run = get_run_or_404(session, run_id)
    return build_run_state_response(session, run)


@router.get("/runs/{run_id}/events", response_model=list[RunEventRecord])
def get_run_events(run_id: str, session: Session = Depends(get_session)) -> list[RunEventRecord]:
    get_run_or_404(session, run_id)
    return list_run_events(session, run_id)


@router.get("/runs/{run_id}/reviews", response_model=list[ReviewSessionRecord])
def get_run_reviews(run_id: str, session: Session = Depends(get_session)) -> list[ReviewSessionRecord]:
    get_run_or_404(session, run_id)
    return list_reviews(session, run_id)


@router.post("/runs/{run_id}/reviews", response_model=ReviewSubmissionResponse)
def submit_run_review(
    run_id: str,
    request: ReviewSubmissionRequest,
    session: Session = Depends(get_session),
) -> ReviewSubmissionResponse:
    run = get_run_or_404(session, run_id)
    response = create_review(session, run=run, submission=request)
    record_run_event(
        session,
        run_id=run_id,
        stage="review",
        status="completed",
        message=f"Structured review submitted with {len(request.items)} items.",
    )
    return response


@router.post("/runs/{run_id}/revise", response_model=PlanResponse)
async def revise_run_plan(
    run_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PlanResponse:
    run = get_run_or_404(session, run_id)
    if run.parsed_hypothesis_json is None or run.literature_qc_json is None or run.plan_json is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A generated plan must exist before revision")
    if not list_reviews(session, run_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Submit at least one structured review before revising")

    parsed = model_from_json(ParsedHypothesis, run.parsed_hypothesis_json)
    literature_qc = model_from_json(LiteratureQC, run.literature_qc_json)
    revision_number = next_revision_number(session, run.id)
    child_run_id = str(uuid4())

    record_run_event(
        session,
        run_id=run.id,
        stage="plan_revision",
        status="started",
        message=f"Generating revision {revision_number} using prior scientist review memory.",
    )
    plan, evidence_pack, _ = await PlanGenerationService(settings).run_with_artifacts(
        parsed,
        literature_qc,
        run.preset_id,
        session=session,
    )

    child_run = Run(
        id=child_run_id,
        hypothesis=run.hypothesis,
        preset_id=run.preset_id,
        status="plan_revised",
        review_state=ReviewState.revised,
        evidence_mode=infer_evidence_mode(literature_qc, evidence_pack),
        used_seed_data=evidence_pack.used_seed_data,
        parsed_hypothesis_json=run.parsed_hypothesis_json,
        literature_qc_json=run.literature_qc_json,
        plan_json=plan.model_dump_json(),
        quality_summary_json=plan.quality_summary.model_dump_json() if plan.quality_summary else None,
        updated_at=utc_now(),
    )
    session.add(child_run)
    session.add(RunRevision(child_run_id=child_run_id, parent_run_id=run.id, revision_number=revision_number))
    session.commit()

    record_run_event(
        session,
        run_id=child_run_id,
        stage="plan_revision",
        status="completed",
        message=f"Revision {revision_number} generated from structured scientist review feedback.",
    )
    return PlanResponse(run_id=child_run_id, plan=plan)


@router.get("/runs/{run_id}/comparison", response_model=RunComparisonResponse)
def get_run_comparison(run_id: str, session: Session = Depends(get_session)) -> RunComparisonResponse:
    run = get_run_or_404(session, run_id)
    parent_revision = get_parent_revision(session, run_id)
    if parent_revision is not None:
        baseline_run = get_run_or_404(session, parent_revision.parent_run_id)
        current_run = run
    else:
        revisions = get_child_revisions(session, run_id)
        if not revisions:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No revised plan is available for comparison")
        latest_revision = revisions[-1]
        baseline_run = run
        current_run = get_run_or_404(session, latest_revision.child_run_id)

    baseline_plan = model_from_json(ExperimentPlan, baseline_run.plan_json)
    current_plan = model_from_json(ExperimentPlan, current_run.plan_json)
    if baseline_plan is None or current_plan is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Both baseline and revised plans must exist for comparison")

    return compare_plans(
        baseline_run_id=baseline_run.id,
        current_run_id=current_run.id,
        baseline=baseline_plan,
        current=current_plan,
    )


@router.post("/runs/{run_id}/presentation-anchor", response_model=RunStateResponse)
def mark_presentation_anchor(run_id: str, session: Session = Depends(get_session)) -> RunStateResponse:
    run = get_run_or_404(session, run_id)
    set_presentation_anchor(session, run_id)
    record_run_event(
        session,
        run_id=run_id,
        stage="presentation_anchor",
        status="completed",
        message="Run marked as the presentation anchor.",
    )
    return build_run_state_response(session, run)


@router.get("/runs/{run_id}/export/json")
def export_run_json(run_id: str, session: Session = Depends(get_session)) -> Response:
    payload = get_run(run_id, session=session).model_dump(mode="json")
    return Response(
        content=RunStateResponse.model_validate(payload).model_dump_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="run-{run_id}.json"'},
    )


@router.get("/runs/{run_id}/export/citations")
def export_run_citations(run_id: str, session: Session = Depends(get_session)) -> Response:
    run = get_run_or_404(session, run_id)
    plan = model_from_json(ExperimentPlan, run.plan_json)
    literature_qc = model_from_json(LiteratureQC, run.literature_qc_json)
    sources = plan.sources if plan else (literature_qc.literature_sources if literature_qc else [])
    lines = []
    for source in sources:
        authors = ", ".join(source.authors) if source.authors else "Unknown authors"
        year = source.year or "n.d."
        lines.append(f"- {authors} ({year}). {source.title}. {source.url or 'URL not available'}")
    content = "\n".join(lines) if lines else "No citations available."
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="run-{run_id}-citations.txt"'},
    )


@router.get("/runs/{run_id}/export/procurement")
def export_run_procurement(run_id: str, session: Session = Depends(get_session)) -> Response:
    run = get_run_or_404(session, run_id)
    plan = model_from_json(ExperimentPlan, run.plan_json)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Plan must exist before procurement export")

    rows = []
    for item in plan.materials:
        if item.requires_procurement_check:
            rows.append(item)
    for item in plan.budget.items:
        if item.requires_procurement_check and item.name not in {row.name for row in rows}:
            rows.append(item)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["name", "vendor", "catalog_number", "procurement_status", "price_status", "notes"])
    for item in rows:
        writer.writerow([
            item.name,
            item.vendor or "",
            item.catalog_number or "",
            item.procurement_status,
            item.price_status,
            item.notes,
        ])

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="run-{run_id}-procurement.csv"'},
    )


@router.get("/runs/{run_id}/export/pdf")
def export_run_pdf(run_id: str, session: Session = Depends(get_session)) -> Response:
    run = get_run_or_404(session, run_id)
    plan = model_from_json(ExperimentPlan, run.plan_json)
    parsed = model_from_json(ParsedHypothesis, run.parsed_hypothesis_json)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Plan must exist before PDF export")

    content = build_plan_pdf(plan, parsed)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="run-{run_id}.pdf"'},
    )


def get_run_or_404(session: Session, run_id: str) -> Run:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def build_run_state_response(session: Session, run: Run) -> RunStateResponse:
    parent_revision = get_parent_revision(session, run.id)
    return RunStateResponse(
        run_id=run.id,
        hypothesis=run.hypothesis,
        preset_id=run.preset_id,
        status=run.status,
        review_state=run.review_state,
        run_mode=resolve_run_mode(run),
        evidence_mode=run.evidence_mode,
        used_seed_data=run.used_seed_data,
        is_presentation_anchor=is_presentation_anchor(session, run.id),
        parent_run_id=parent_revision.parent_run_id if parent_revision else None,
        revision_number=parent_revision.revision_number if parent_revision else 0,
        parsed_hypothesis=model_from_json(ParsedHypothesis, run.parsed_hypothesis_json),
        literature_qc=model_from_json(LiteratureQC, run.literature_qc_json),
        plan=model_from_json(ExperimentPlan, run.plan_json),
    )


def safe_model_from_json(model: type, raw: str | None):
    try:
        return model_from_json(model, raw)
    except ValidationError:
        return None
