from app.core.config import Settings
from app.models.schemas import EvidencePack, ExperimentPlan, LiteratureQC, ParsedHypothesis
from app.services.evidence_pack import EvidencePackService
from app.services.openai_client import OpenAIStructuredClient


class PlanGenerationService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.openai = OpenAIStructuredClient(settings)
        self.evidence_packs = EvidencePackService(settings)

    async def build_evidence_pack(
        self,
        parsed: ParsedHypothesis,
        literature_qc: LiteratureQC,
        preset_id: str | None,
    ) -> EvidencePack:
        return await self.evidence_packs.build(parsed, literature_qc, preset_id)

    async def run(
        self,
        parsed: ParsedHypothesis,
        literature_qc: LiteratureQC,
        preset_id: str | None,
    ) -> ExperimentPlan:
        evidence_pack = await self.build_evidence_pack(parsed, literature_qc, preset_id)
        return await self.openai.generate_plan(parsed, literature_qc, evidence_pack, preset_id=preset_id)
