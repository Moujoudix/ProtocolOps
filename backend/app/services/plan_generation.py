from sqlmodel import Session

from app.core.config import Settings
from app.models.schemas import EvidencePack, ExperimentPlan, LiteratureQC, ParsedHypothesis, ReviewMemoryReference
from app.services.evidence_pack import EvidencePackService
from app.services.openai_client import OpenAIStructuredClient
from app.services.quality import summarize_plan_quality
from app.services.review_memory import ReviewMemoryService


class PlanGenerationService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.openai = OpenAIStructuredClient(settings)
        self.evidence_packs = EvidencePackService(settings)
        self.review_memory = ReviewMemoryService()

    async def build_evidence_pack(
        self,
        parsed: ParsedHypothesis,
        literature_qc: LiteratureQC,
        preset_id: str | None,
        *,
        session: Session | None = None,
    ) -> EvidencePack:
        return await self.evidence_packs.build(parsed, literature_qc, preset_id, session=session)

    async def run(
        self,
        parsed: ParsedHypothesis,
        literature_qc: LiteratureQC,
        preset_id: str | None,
        session: Session | None = None,
    ) -> ExperimentPlan:
        plan, _, _ = await self.run_with_artifacts(parsed, literature_qc, preset_id, session=session)
        return plan

    async def run_with_artifacts(
        self,
        parsed: ParsedHypothesis,
        literature_qc: LiteratureQC,
        preset_id: str | None,
        *,
        session: Session | None = None,
    ) -> tuple[ExperimentPlan, EvidencePack, list[ReviewMemoryReference]]:
        evidence_pack = await self.build_evidence_pack(parsed, literature_qc, preset_id, session=session)
        review_memory = self.review_memory.list_for_generation(session, parsed, preset_id)
        plan = await self.openai.generate_plan(
            parsed,
            literature_qc,
            evidence_pack,
            preset_id=preset_id,
            review_memory=review_memory,
        )
        plan.quality_summary = summarize_plan_quality(plan, parsed, literature_qc, evidence_pack, review_memory)
        plan.memory_applied = review_memory
        return plan, evidence_pack, review_memory
