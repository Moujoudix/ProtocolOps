from __future__ import annotations

import json

from sqlmodel import Session

from app.core.config import Settings
from app.models.db import ConsensusCache, utc_now
from app.models.schemas import DomainRoute, EvidenceMode, EvidenceSource, EvidenceType, LiteratureQC, NoveltySignal, ProviderTraceEntry, TrustTier
from app.providers.base import ProviderSearchResult, SearchContext
from app.providers.utils import normalize_hypothesis_key
from app.seeds.hela import is_hela_trehalose_hypothesis, seeded_hela_literature_qc, seeded_hela_sources
from app.services.consensus_adapter import ConsensusMcpAdapter
from app.services.replay_cache import EvidenceReplayCacheService
from app.services.source_router import SourceRouter


class LiteratureQcService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.router = SourceRouter(settings)
        self.consensus = ConsensusMcpAdapter(settings)
        self.replay_cache = EvidenceReplayCacheService()

    async def run(self, context: SearchContext, session: Session | None = None) -> LiteratureQC:
        query = build_literature_query(context, self.router)

        if self.settings.app_env == "test":
            return build_test_qc(context, query, self.settings.consensus_mcp_enabled)

        if self.settings.effective_evidence_mode == EvidenceMode.cached_live:
            cached = self.replay_cache.load_literature_qc(session, context.parsed_hypothesis.original_text)
            if cached is None:
                raise RuntimeError("No cached live evidence is available for this hypothesis yet.")
            return cached

        if (
            self.settings.effective_evidence_mode == EvidenceMode.seeded_demo
            and is_hela_trehalose_hypothesis(context.parsed_hypothesis.original_text, context.preset_id)
        ):
            seeded = seeded_hela_literature_qc()
            seeded.provider_trace = [
                ProviderTraceEntry(
                    provider="HeLa demo seed",
                    attempted=True,
                    succeeded=True,
                    cached=False,
                    stage="literature_qc",
                    fallback_used=True,
                    query=query,
                    result_count=len(seeded.literature_sources),
                )
            ]
            seeded.searched_sources = dedupe_strings([*seeded.searched_sources, "HeLa demo seed"])
            return seeded

        provider_trace: list[ProviderTraceEntry] = []
        sources: list[EvidenceSource] = []
        searched_sources: list[str] = []
        literature_synthesis: str | None = None

        consensus_sources, consensus_synthesis, consensus_trace = await self._run_consensus(query, context, session)
        if consensus_trace is not None:
            provider_trace.append(consensus_trace)
            searched_sources.append(consensus_trace.provider)
            sources.extend(consensus_sources)
            if consensus_synthesis:
                literature_synthesis = consensus_synthesis

        for provider in self.router.literature_primary_providers():
            result, trace = await self._run_provider(provider.name, provider.search(query, context), query)
            provider_trace.append(trace)
            searched_sources.append(provider.name)
            sources.extend(result.sources)

        primary_sources = dedupe_sources(sources)
        if should_use_ncbi(context, primary_sources):
            result, trace = await self._run_provider(
                self.router.ncbi_provider().name,
                self.router.ncbi_provider().search(query, context),
                query,
            )
            provider_trace.append(trace)
            searched_sources.append(trace.provider)
            sources.extend(result.sources)

        if context.parsed_hypothesis.domain_route in {
            DomainRoute.diagnostics_biosensor,
            DomainRoute.microbial_electrochemistry,
        }:
            result, trace = await self._run_provider(
                self.router.arxiv_provider().name,
                self.router.arxiv_provider().search(query, context),
                query,
            )
            provider_trace.append(trace)
            searched_sources.append(trace.provider)
            sources.extend(result.sources)

        sources = dedupe_sources(sources)
        used_seed_data = False
        if not has_usable_results(sources) and is_hela_trehalose_hypothesis(
            context.parsed_hypothesis.original_text,
            context.preset_id,
        ):
            if self.settings.strict_live_mode:
                raise RuntimeError("Strict live mode forbids seeded HeLa literature fallback.")
            sources = dedupe_sources(sources + seeded_hela_sources())
            searched_sources.append("HeLa demo seed")
            used_seed_data = True

        top_refs = sorted(sources, key=lambda source: source.confidence, reverse=True)[:3]
        novelty_signal = classify_novelty(sources)
        confidence = confidence_for(novelty_signal, top_refs)
        gaps = build_gaps(context, sources, used_seed_data)
        rationale = build_rationale(novelty_signal, top_refs)

        return LiteratureQC(
            novelty_signal=novelty_signal,
            confidence=confidence,
            references=top_refs,
            literature_sources=sources,
            searched_sources=dedupe_strings(searched_sources),
            provider_trace=provider_trace,
            rationale=rationale,
            literature_synthesis=literature_synthesis or build_synthesis(top_refs),
            gaps=gaps,
            evidence_gap_warnings=list(gaps),
        )

    async def _run_consensus(
        self,
        query: str,
        context: SearchContext,
        session: Session | None,
    ) -> tuple[list[EvidenceSource], str | None, ProviderTraceEntry | None]:
        if not self.settings.consensus_mcp_enabled:
            return [], None, None

        normalized = normalize_hypothesis_key(context.parsed_hypothesis.original_text)
        if session is not None:
            cached = session.get(ConsensusCache, normalized)
            if cached is not None:
                payload = json.loads(cached.references_json)
                sources = [EvidenceSource.model_validate(item) for item in payload]
                return (
                    sources,
                    cached.literature_synthesis,
                    ProviderTraceEntry(
                        provider="Consensus",
                        attempted=True,
                    succeeded=True,
                    cached=True,
                    stage="literature_qc",
                    fallback_used=False,
                    query=query,
                    result_count=len(sources),
                ),
            )

        try:
            result = await self.consensus.search(query, context)
        except Exception as exc:  # pragma: no cover - exercised via tests with monkeypatch
            return (
                [],
                None,
                ProviderTraceEntry(
                    provider="Consensus",
                    attempted=True,
                    succeeded=False,
                    cached=False,
                    stage="literature_qc",
                    fallback_used=False,
                    query=query,
                    result_count=0,
                    error=str(exc),
                ),
            )

        if session is not None:
            session.merge(
                ConsensusCache(
                    normalized_hypothesis=normalized,
                    query=query,
                    references_json=json.dumps([source.model_dump(mode="json") for source in result.sources]),
                    literature_synthesis=result.literature_synthesis,
                    updated_at=utc_now(),
                )
            )
            session.commit()

        return (
            result.sources,
            result.literature_synthesis,
            ProviderTraceEntry(
                provider="Consensus",
                attempted=True,
                succeeded=True,
                cached=False,
                stage="literature_qc",
                fallback_used=False,
                query=query,
                result_count=len(result.sources),
            ),
        )

    async def _run_provider(
        self,
        provider_name: str,
        operation,
        query: str,
    ) -> tuple[ProviderSearchResult, ProviderTraceEntry]:
        try:
            result = await operation
            return (
                result,
                ProviderTraceEntry(
                    provider=provider_name,
                    attempted=True,
                    succeeded=True,
                    cached=False,
                    stage="literature_qc",
                    fallback_used=False,
                    query=query,
                    result_count=len(result.sources),
                ),
            )
        except Exception as exc:
            return (
                ProviderSearchResult(sources=[]),
                ProviderTraceEntry(
                    provider=provider_name,
                    attempted=True,
                    succeeded=False,
                    cached=False,
                    stage="literature_qc",
                    fallback_used=False,
                    query=query,
                    result_count=0,
                    error=str(exc),
                ),
            )


def build_literature_query(context: SearchContext, router: SourceRouter) -> str:
    parsed = context.parsed_hypothesis
    terms = [term for term in parsed.literature_query_terms if term]
    if terms:
        return " ".join(terms[:6])
    examples = router.literature_query_examples(parsed.domain_route)
    if examples:
        return examples[0]
    return parsed.original_text[:200]


def classify_novelty(references: list[EvidenceSource]) -> NoveltySignal:
    if any(source.evidence_type == EvidenceType.exact_match for source in references):
        return NoveltySignal.exact_match_found
    if any(source.evidence_type in {EvidenceType.close_match, EvidenceType.adjacent_method, EvidenceType.generic_method} for source in references):
        return NoveltySignal.similar_work_exists
    return NoveltySignal.not_found_in_searched_sources


def confidence_for(signal: NoveltySignal, references: list[EvidenceSource]) -> float:
    if not references:
        return 0.3
    avg = sum(source.confidence for source in references) / len(references)
    if signal == NoveltySignal.exact_match_found:
        return min(0.92, avg + 0.08)
    if signal == NoveltySignal.similar_work_exists:
        return min(0.78, avg + 0.03)
    return min(0.46, avg)


def build_rationale(signal: NoveltySignal, references: list[EvidenceSource]) -> str:
    if signal == NoveltySignal.exact_match_found:
        return "At least one searched source appears to match the system, intervention, comparator, and outcome or method requested."
    if signal == NoveltySignal.similar_work_exists:
        return "Searched sources returned related work or adjacent methods, but an exact match was not confirmed in the configured searched sources."
    return "No exact match was found in the configured searched sources."


def build_synthesis(references: list[EvidenceSource]) -> str | None:
    if not references:
        return None
    titles = ", ".join(source.title for source in references[:2])
    return f"Top supporting references for this QC pass include: {titles}."


def build_gaps(
    context: SearchContext,
    references: list[EvidenceSource],
    used_seed_data: bool,
) -> list[str]:
    gaps = [
        "Do not interpret this as an exhaustive novelty review; it only covers the configured searched sources.",
        "Use 'not found in searched sources' rather than claiming the work has never been done.",
    ]
    if not references:
        gaps.append("Provider results were empty or unavailable, so downstream plans should remain low confidence.")
    if used_seed_data:
        gaps.append("Seeded demo evidence was used because live literature providers did not return enough usable results.")
    if context.preset_id != "hela-trehalose":
        gaps.append("Non-HeLa routes should keep stronger expert-review flags unless additional source-backed evidence is retrieved.")
    return gaps


def build_test_qc(context: SearchContext, query: str, consensus_enabled: bool) -> LiteratureQC:
    provider_trace = []
    searched_sources = []
    if consensus_enabled:
        provider_trace.append(
            ProviderTraceEntry(
                provider="Consensus",
                attempted=True,
                succeeded=False,
                cached=False,
                stage="literature_qc",
                fallback_used=False,
                query=query,
                result_count=0,
                error="Consensus MCP bridge not configured in test mode",
            )
        )
        searched_sources.append("Consensus")

    searched_sources.extend(["Semantic Scholar", "Europe PMC"])
    if is_hela_trehalose_hypothesis(context.parsed_hypothesis.original_text, context.preset_id):
        sources = seeded_hela_sources()
        return LiteratureQC(
            novelty_signal=NoveltySignal.similar_work_exists,
            confidence=0.71,
            references=sources[:3],
            literature_sources=sources,
            searched_sources=searched_sources + ["HeLa demo seed"],
            provider_trace=provider_trace,
            rationale=(
                "Searched sources indicate adjacent cryoprotection evidence for trehalose and generic HeLa or mammalian "
                "cell cryopreservation evidence. An exact head-to-head result was not confirmed in the configured searched sources."
            ),
            literature_synthesis="Seeded HeLa evidence pack summarizes adjacent cryoprotection evidence and supplier-backed demo references.",
            gaps=[
                "Use 'not found in searched sources' rather than claiming the experiment has never been done.",
                "Exact trehalose concentration, freezing rate, thaw timing, and replicate count require expert review.",
            ],
            evidence_gap_warnings=[
                "Use 'not found in searched sources' rather than claiming the experiment has never been done.",
                "Exact trehalose concentration, freezing rate, thaw timing, and replicate count require expert review.",
            ],
        )

    return LiteratureQC(
        novelty_signal=NoveltySignal.not_found_in_searched_sources,
        confidence=0.3,
        references=[],
        literature_sources=[],
        searched_sources=searched_sources,
        provider_trace=provider_trace,
        rationale="No exact match was found in the configured searched sources.",
        literature_synthesis=None,
        gaps=[
            "Provider calls are disabled in test mode for deterministic fallback behavior.",
            "Downstream plans should remain conservative until live evidence is retrieved.",
        ],
        evidence_gap_warnings=[
            "Provider calls are disabled in test mode for deterministic fallback behavior.",
            "Downstream plans should remain conservative until live evidence is retrieved.",
        ],
    )


def should_use_ncbi(context: SearchContext, references: list[EvidenceSource]) -> bool:
    if context.parsed_hypothesis.domain_route not in {
        DomainRoute.cell_biology,
        DomainRoute.diagnostics_biosensor,
        DomainRoute.animal_gut_health,
    }:
        return False
    usable = [
        source
        for source in references
        if source.trust_tier == TrustTier.literature_database
        and source.evidence_type in {EvidenceType.exact_match, EvidenceType.close_match, EvidenceType.adjacent_method}
    ]
    if len(usable) < 2:
        return True
    if not any(source.evidence_type in {EvidenceType.exact_match, EvidenceType.close_match} for source in usable):
        return True
    average_confidence = sum(source.confidence for source in usable) / len(usable)
    return average_confidence < 0.55


def has_usable_results(references: list[EvidenceSource]) -> bool:
    return any(source.evidence_type in {EvidenceType.exact_match, EvidenceType.close_match, EvidenceType.adjacent_method} for source in references)


def dedupe_sources(sources: list[EvidenceSource]) -> list[EvidenceSource]:
    seen: set[str] = set()
    merged: list[EvidenceSource] = []
    for source in sources:
        if source.id in seen:
            continue
        seen.add(source.id)
        merged.append(source)
    return merged


def dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped
