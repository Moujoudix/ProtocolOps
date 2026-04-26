from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.models.schemas import EvidencePack, EvidenceSource, LiteratureQC, ParsedHypothesis
from app.providers.base import SearchContext
from app.seeds.hela import is_hela_trehalose_hypothesis, seeded_hela_sources
from app.services.source_router import SourceRouter


class EvidencePackService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.router = SourceRouter(settings)

    async def build(
        self,
        parsed: ParsedHypothesis,
        literature_qc: LiteratureQC,
        preset_id: str | None,
    ) -> EvidencePack:
        context = SearchContext(parsed_hypothesis=parsed, preset_id=preset_id, stage="evidence_pack")
        providers = self.router.evidence_pack_providers(parsed.domain_route)
        query = build_protocol_query(parsed)
        live_sources: list[EvidenceSource] = []
        if self.settings.app_env != "test":
            provider_results = await asyncio.gather(
                *(provider.search(query, context) for provider in providers),
                return_exceptions=True,
            )
            for result in provider_results:
                if isinstance(result, Exception):
                    continue
                live_sources.extend(result)

        seeded_sources = seeded_hela_sources() if is_hela_trehalose_hypothesis(parsed.original_text, preset_id) else []
        sources = merge_by_id(literature_qc.references + seeded_sources + live_sources)
        searched_providers = dedupe_names(literature_qc.searched_sources + [provider.name for provider in providers])
        warnings = list(literature_qc.evidence_gap_warnings)
        if not live_sources and not seeded_sources and not literature_qc.references:
            warnings.append("Evidence pack is sparse because no additional sources were retrieved for this preset.")

        return EvidencePack(
            domain_route=parsed.domain_route,
            sources=sources,
            searched_providers=searched_providers,
            evidence_gap_warnings=warnings,
            used_seed_data=bool(seeded_sources),
            confidence_summary=confidence_summary(sources, literature_qc),
        )


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


def dedupe_names(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def confidence_summary(sources: list[EvidenceSource], literature_qc: LiteratureQC) -> float:
    if not sources:
        return literature_qc.confidence
    return min(0.95, sum(source.confidence for source in sources) / len(sources))
