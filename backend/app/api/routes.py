from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.models.db import Run, utc_now
from app.models.schemas import (
    ExperimentPlan,
    LiteratureQC,
    LiteratureQcRequest,
    LiteratureQcResponse,
    ParsedHypothesis,
    PlanResponse,
    Preset,
    RunStateResponse,
    model_from_json,
)
from app.providers.base import SearchContext
from app.seeds.presets import PRESETS
from app.services.literature_qc import LiteratureQcService
from app.services.openai_client import OpenAIStructuredClient
from app.services.plan_generation import PlanGenerationService


router = APIRouter()


@router.get("/presets", response_model=list[Preset])
def list_presets() -> list[Preset]:
    return PRESETS


@router.post("/literature-qc", response_model=LiteratureQcResponse)
async def create_literature_qc(
    request: LiteratureQcRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> LiteratureQcResponse:
    parser = OpenAIStructuredClient(settings)
    parsed = await parser.parse_hypothesis(request.hypothesis, preset_id=request.preset_id)
    context = SearchContext(parsed_hypothesis=parsed, preset_id=request.preset_id, stage="literature_qc")
    literature_qc = await LiteratureQcService(settings).run(context)

    run = Run(
        id=str(uuid4()),
        hypothesis=request.hypothesis,
        preset_id=request.preset_id,
        status="literature_qc_complete",
        parsed_hypothesis_json=parsed.model_dump_json(),
        literature_qc_json=literature_qc.model_dump_json(),
        updated_at=utc_now(),
    )
    session.add(run)
    session.commit()

    return LiteratureQcResponse(run_id=run.id, parsed_hypothesis=parsed, literature_qc=literature_qc)


@router.post("/runs/{run_id}/plan", response_model=PlanResponse)
async def create_plan(
    run_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PlanResponse:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.parsed_hypothesis_json is None or run.literature_qc_json is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Literature QC must complete before plan generation",
        )

    parsed = model_from_json(ParsedHypothesis, run.parsed_hypothesis_json)
    literature_qc = model_from_json(LiteratureQC, run.literature_qc_json)
    plan = await PlanGenerationService(settings).run(parsed, literature_qc, run.preset_id)

    run.status = "plan_complete"
    run.plan_json = plan.model_dump_json()
    run.updated_at = utc_now()
    session.add(run)
    session.commit()
    session.refresh(run)

    return PlanResponse(run_id=run.id, plan=plan)


@router.get("/runs/{run_id}", response_model=RunStateResponse)
def get_run(run_id: str, session: Session = Depends(get_session)) -> RunStateResponse:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    return RunStateResponse(
        run_id=run.id,
        hypothesis=run.hypothesis,
        preset_id=run.preset_id,
        status=run.status,
        parsed_hypothesis=model_from_json(ParsedHypothesis, run.parsed_hypothesis_json),
        literature_qc=model_from_json(LiteratureQC, run.literature_qc_json),
        plan=model_from_json(ExperimentPlan, run.plan_json),
    )
