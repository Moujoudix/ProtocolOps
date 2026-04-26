import asyncio

from app.core.config import Settings
from app.models.schemas import EvidenceSource, ExperimentPlan, LiteratureQC, ParsedHypothesis
from app.providers.base import SearchContext
from app.providers.protocols import OpenWetWareProvider, ProtocolsIoProvider, TavilyProvider
from app.services.openai_client import OpenAIStructuredClient
from app.seeds.hela import is_hela_trehalose_hypothesis


SUPPLIER_DOMAINS = [
    "atcc.org",
    "thermofisher.com",
    "promega.com",
    "sigmaaldrich.com",
    "sigma-aldrich.com",
]


class PlanGenerationService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.openai = OpenAIStructuredClient(settings)
        self.providers = [
            ProtocolsIoProvider(settings),
            OpenWetWareProvider(settings),
            TavilyProvider(settings),
            TavilyProvider(settings, include_domains=SUPPLIER_DOMAINS, source_name="Supplier search"),
        ]

    async def run(
        self,
        parsed: ParsedHypothesis,
        literature_qc: LiteratureQC,
        preset_id: str | None,
    ) -> ExperimentPlan:
        if should_use_seed_only(self.settings, parsed, preset_id):
            return await self.openai.generate_plan(parsed, literature_qc, [], preset_id=preset_id)

        if self.settings.app_env == "test" and is_hela_trehalose_hypothesis(parsed.original_text, preset_id):
            return await self.openai.generate_plan(parsed, literature_qc, [], preset_id=preset_id)

        context = SearchContext(parsed_hypothesis=parsed, preset_id=preset_id, stage="plan")
        query = build_protocol_query(parsed)
        provider_results = await asyncio.gather(
            *(provider.search(query, context) for provider in self.providers),
            return_exceptions=True,
        )
        sources: list[EvidenceSource] = []
        for result in provider_results:
            if isinstance(result, Exception):
                continue
            sources.extend(result)

        evidence = merge_by_id(literature_qc.references + sources)
        return await self.openai.generate_plan(parsed, literature_qc, evidence, preset_id=preset_id)


def build_protocol_query(parsed: ParsedHypothesis) -> str:
    terms = parsed.key_terms[:6]
    if parsed.organism_or_system:
        terms.insert(0, parsed.organism_or_system)
    terms.extend(["protocol", "materials", "assay"])
    deduped: list[str] = []
    for term in terms:
        if term and term not in deduped:
            deduped.append(term)
    return " ".join(deduped)


def merge_by_id(sources: list[EvidenceSource]) -> list[EvidenceSource]:
    seen: set[str] = set()
    merged: list[EvidenceSource] = []
    for source in sources:
        if source.id in seen:
            continue
        seen.add(source.id)
        merged.append(source)
    return merged


def should_use_seed_only(settings: Settings, parsed: ParsedHypothesis, preset_id: str | None) -> bool:
    is_seeded_demo = is_hela_trehalose_hypothesis(parsed.original_text, preset_id)
    has_live_provider_keys = bool(settings.protocols_io_token or settings.tavily_api_key)
    return is_seeded_demo and not has_live_provider_keys
