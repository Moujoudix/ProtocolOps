from __future__ import annotations

from app.core.config import Settings
from app.models.schemas import DomainRoute, EvidencePack, EvidenceSource, EvidenceType, LiteratureQC, ParsedHypothesis, ProviderTraceEntry, TrustLevel, TrustTier, now_utc
from app.providers.base import SearchContext
from app.providers.protocols import TavilyClient
from app.providers.utils import stable_source_id
from app.seeds.hela import is_hela_trehalose_hypothesis, seeded_hela_sources
from app.seeds.standards import anaerobic_safety_source, arrive_source, bmbl_source, miqe_source, stard_source
from app.services.source_router import KNOWN_HELA_URLS, SUPPLIER_DOMAINS, SourceRouter


class EvidencePackService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.router = SourceRouter(settings)
        self.tavily = TavilyClient(settings)

    async def build(
        self,
        parsed: ParsedHypothesis,
        literature_qc: LiteratureQC,
        preset_id: str | None,
    ) -> EvidencePack:
        context = SearchContext(parsed_hypothesis=parsed, preset_id=preset_id, stage="evidence_pack")
        recipe = self.router.evidence_recipe(parsed.domain_route)
        provider_trace = list(literature_qc.provider_trace)
        searched_providers = dedupe_names(list(literature_qc.searched_sources))
        sources = list(literature_qc.literature_sources or literature_qc.references)
        checklists: list[EvidenceSource] = []
        used_seed_data = any(source.id.startswith("seed-") for source in sources)

        if self.settings.app_env != "test":
            if parsed.domain_route == DomainRoute.cell_biology:
                supplier_sources, supplier_trace, supplier_seeded = await self._build_hela_supplier_sources(context)
                sources.extend(supplier_sources)
                provider_trace.extend(supplier_trace)
                searched_providers.extend(trace.provider for trace in supplier_trace if trace.attempted)
                used_seed_data = used_seed_data or supplier_seeded
            elif parsed.domain_route == DomainRoute.diagnostics_biosensor:
                supplier_sources, supplier_trace = await self._search_supplier_materials(context, recipe.supplier_queries)
                sources.extend(supplier_sources)
                provider_trace.extend(supplier_trace)
                searched_providers.extend(trace.provider for trace in supplier_trace if trace.attempted)
            elif parsed.domain_route == DomainRoute.microbial_electrochemistry and recipe.supplier_queries:
                supplier_sources, supplier_trace = await self._search_supplier_materials(context, recipe.supplier_queries)
                sources.extend(supplier_sources)
                provider_trace.extend(supplier_trace)
                searched_providers.extend(trace.provider for trace in supplier_trace if trace.attempted)

            protocol_sources, protocol_trace = await self._collect_protocol_sources(context, recipe.protocol_queries)
            sources.extend(protocol_sources)
            provider_trace.extend(protocol_trace)
            searched_providers.extend(trace.provider for trace in protocol_trace if trace.attempted)

            community_sources, community_trace = await self._collect_openwetware_sources(context, recipe.openwetware_queries)
            sources.extend(community_sources)
            provider_trace.extend(community_trace)
            searched_providers.extend(trace.provider for trace in community_trace if trace.attempted)

            if recipe.allow_bio_protocol_discovery:
                bio_protocol_sources, bio_protocol_trace = await self._discover_bio_protocol_sources(context)
                sources.extend(bio_protocol_sources)
                provider_trace.extend(bio_protocol_trace)
                searched_providers.extend(trace.provider for trace in bio_protocol_trace if trace.attempted)

        if parsed.domain_route == DomainRoute.cell_biology and not any(source.source_name == "ATCC" for source in sources):
            seeded = seeded_hela_sources()
            sources.extend(source for source in seeded if source.id in {
                "seed-atcc-hela-culture",
                "seed-thermo-cryopreservation",
                "seed-promega-viability",
                "seed-sigma-trehalose",
                "seed-protocolsio-fallback",
                "seed-openwetware-fallback",
                "seed-assumption-expert-review",
            })
            used_seed_data = True

        standards = standards_for_route(parsed, recipe.standards)
        if standards:
            checklists.extend(standards)
            sources.extend(standards)
            provider_trace.extend(
                ProviderTraceEntry(
                    provider=standard.source_name,
                    attempted=True,
                    succeeded=True,
                    cached=False,
                    query="static checklist",
                    result_count=1,
                )
                for standard in standards
            )
            searched_providers.extend(standard.source_name for standard in standards)

        assumption = inferred_assumption_source(parsed)
        sources.append(assumption)

        sources = dedupe_sources(sources)
        provider_trace = dedupe_trace(provider_trace)
        warnings = list(literature_qc.gaps or literature_qc.evidence_gap_warnings)
        if not sources:
            warnings.append("Evidence pack is sparse because no protocol, supplier, or checklist sources were retrieved.")
        if parsed.domain_route != DomainRoute.cell_biology:
            warnings.append("Non-HeLa routes should keep conservative protocol confidence until more source-backed methods are retrieved.")

        return EvidencePack(
            domain_route=parsed.domain_route,
            sources=sources,
            searched_providers=dedupe_names(searched_providers),
            provider_trace=provider_trace,
            evidence_gap_warnings=dedupe_names(warnings),
            literature_synthesis=literature_qc.literature_synthesis,
            checklists=checklists,
            used_seed_data=used_seed_data,
            confidence_summary=confidence_summary(sources, literature_qc),
        )

    async def _build_hela_supplier_sources(
        self,
        context: SearchContext,
    ) -> tuple[list[EvidenceSource], list[ProviderTraceEntry], bool]:
        sources: list[EvidenceSource] = []
        trace: list[ProviderTraceEntry] = []
        used_seed_data = False
        url_targets = [
            ("ATCC CCL-2", KNOWN_HELA_URLS["atcc_ccl2"]),
            ("Thermo/Gibco freezing guidance", KNOWN_HELA_URLS["thermo_gibco_freezing"]),
            ("Promega CellTiter-Glo", KNOWN_HELA_URLS["promega_celltiter_glo"]),
        ]
        seeded_by_title = {source.title: source for source in seeded_hela_sources()}

        for label, url in url_targets:
            try:
                results = await self.tavily.extract([url], query=label, chunks_per_source=5)
                normalized = [self.tavily.normalize_extract_result(item, context, supplier_mode=True, title_hint=label) for item in results]
                sources.extend(normalized)
                trace.append(
                    ProviderTraceEntry(
                        provider="Tavily Extract",
                        attempted=True,
                        succeeded=True,
                        cached=False,
                        query=url,
                        result_count=len(normalized),
                    )
                )
            except Exception as exc:
                seeded = seeded_by_title.get("ATCC HeLa cell line product page (CCL-2)" if "ATCC" in label else "")
                if label.startswith("Thermo"):
                    seeded = seeded_by_title.get("Gibco cell-freezing protocol guidance")
                if label.startswith("Promega"):
                    seeded = seeded_by_title.get("Promega CellTiter-Glo viability assay guidance")
                if seeded is not None:
                    sources.append(seeded)
                    used_seed_data = True
                trace.append(
                    ProviderTraceEntry(
                        provider="Tavily Extract",
                        attempted=True,
                        succeeded=False,
                        cached=False,
                        query=url,
                        result_count=0,
                        error=str(exc),
                    )
                )

        try:
            results = await self.tavily.search(
                "Sigma trehalose product page",
                include_domains=["sigmaaldrich.com", "sigma-aldrich.com"],
                max_results=5,
            )
            trace.append(
                ProviderTraceEntry(
                    provider="Tavily Search",
                    attempted=True,
                    succeeded=True,
                    cached=False,
                    query="Sigma trehalose product page",
                    result_count=len(results),
                )
            )
            if results:
                extract_results = await self.tavily.extract([result["url"] for result in results[:2] if result.get("url")], query="trehalose product details", chunks_per_source=5)
                normalized = [self.tavily.normalize_extract_result(item, context, supplier_mode=True, title_hint="Sigma trehalose") for item in extract_results]
                sources.extend(normalized)
                trace.append(
                    ProviderTraceEntry(
                        provider="Tavily Extract",
                        attempted=True,
                        succeeded=True,
                        cached=False,
                        query="Sigma trehalose selected URLs",
                        result_count=len(normalized),
                    )
                )
        except Exception as exc:
            sigma_seed = next((source for source in seeded_hela_sources() if source.id == "seed-sigma-trehalose"), None)
            if sigma_seed is not None:
                sources.append(sigma_seed)
                used_seed_data = True
            trace.append(
                ProviderTraceEntry(
                    provider="Tavily Search",
                    attempted=True,
                    succeeded=False,
                    cached=False,
                    query="Sigma trehalose product page",
                    result_count=0,
                    error=str(exc),
                )
            )

        return sources, trace, used_seed_data

    async def _search_supplier_materials(
        self,
        context: SearchContext,
        queries: list[str],
    ) -> tuple[list[EvidenceSource], list[ProviderTraceEntry]]:
        sources: list[EvidenceSource] = []
        trace: list[ProviderTraceEntry] = []
        for query in queries:
            try:
                search_results = await self.tavily.search(query, include_domains=SUPPLIER_DOMAINS, max_results=5)
                trace.append(
                    ProviderTraceEntry(
                        provider="Tavily Search",
                        attempted=True,
                        succeeded=True,
                        cached=False,
                        query=query,
                        result_count=len(search_results),
                    )
                )
                urls = [result.get("url") for result in search_results if result.get("url")]
                if not urls:
                    continue
                extract_results = await self.tavily.extract(urls[:2], query=query, chunks_per_source=5)
                normalized = [self.tavily.normalize_extract_result(item, context, supplier_mode=True) for item in extract_results]
                sources.extend(normalized)
                trace.append(
                    ProviderTraceEntry(
                        provider="Tavily Extract",
                        attempted=True,
                        succeeded=True,
                        cached=False,
                        query=query,
                        result_count=len(normalized),
                    )
                )
            except Exception as exc:
                trace.append(
                    ProviderTraceEntry(
                        provider="Tavily Search",
                        attempted=True,
                        succeeded=False,
                        cached=False,
                        query=query,
                        result_count=0,
                        error=str(exc),
                    )
                )
        return sources, trace

    async def _collect_protocol_sources(
        self,
        context: SearchContext,
        query_pack: list[str],
    ) -> tuple[list[EvidenceSource], list[ProviderTraceEntry]]:
        sources: list[EvidenceSource] = []
        trace: list[ProviderTraceEntry] = []
        for query in query_pack:
            if len({source.id for source in sources}) >= 5:
                break
            try:
                result = await self.router.protocols.search(query, context)
                sources.extend(result.sources)
                trace.append(
                    ProviderTraceEntry(
                        provider="protocols.io",
                        attempted=True,
                        succeeded=True,
                        cached=False,
                        query=query,
                        result_count=len(result.sources),
                    )
                )
            except Exception as exc:
                trace.append(
                    ProviderTraceEntry(
                        provider="protocols.io",
                        attempted=True,
                        succeeded=False,
                        cached=False,
                        query=query,
                        result_count=0,
                        error=str(exc),
                    )
                )
        return dedupe_sources(sources)[:5], trace

    async def _collect_openwetware_sources(
        self,
        context: SearchContext,
        queries: list[str],
    ) -> tuple[list[EvidenceSource], list[ProviderTraceEntry]]:
        sources: list[EvidenceSource] = []
        trace: list[ProviderTraceEntry] = []
        for query in queries:
            try:
                result = await self.router.openwetware.search(query, context)
                sources.extend(result.sources)
                trace.append(
                    ProviderTraceEntry(
                        provider="OpenWetWare",
                        attempted=True,
                        succeeded=True,
                        cached=False,
                        query=query,
                        result_count=len(result.sources),
                    )
                )
            except Exception as exc:
                trace.append(
                    ProviderTraceEntry(
                        provider="OpenWetWare",
                        attempted=True,
                        succeeded=False,
                        cached=False,
                        query=query,
                        result_count=0,
                        error=str(exc),
                    )
                )
        return dedupe_sources(sources)[:5], trace

    async def _discover_bio_protocol_sources(
        self,
        context: SearchContext,
    ) -> tuple[list[EvidenceSource], list[ProviderTraceEntry]]:
        query = "bio-protocol CRP assay"
        try:
            search_results = await self.tavily.search(query, include_domains=["bio-protocol.org"], max_results=3)
            sources = [self.tavily.normalize_search_result(item, context, supplier_mode=False) for item in search_results]
            return (
                sources,
                [
                    ProviderTraceEntry(
                        provider="Tavily Search",
                        attempted=True,
                        succeeded=True,
                        cached=False,
                        query=query,
                        result_count=len(sources),
                    )
                ],
            )
        except Exception as exc:
            return (
                [],
                [
                    ProviderTraceEntry(
                        provider="Tavily Search",
                        attempted=True,
                        succeeded=False,
                        cached=False,
                        query=query,
                        result_count=0,
                        error=str(exc),
                    )
                ],
            )


def standards_for_route(parsed: ParsedHypothesis, standard_names: list[str]) -> list[EvidenceSource]:
    resolved: list[EvidenceSource] = []
    for name in standard_names:
        if name == "bmbl":
            resolved.append(bmbl_source())
        elif name == "stard":
            resolved.append(stard_source())
        elif name == "arrive":
            resolved.append(arrive_source())
        elif name == "miqe" and should_include_miqe(parsed):
            resolved.append(miqe_source())
        elif name == "anaerobic_safety":
            resolved.append(anaerobic_safety_source())
    return resolved


def should_include_miqe(parsed: ParsedHypothesis) -> bool:
    joined = " ".join(parsed.key_terms + parsed.literature_query_terms + parsed.protocol_query_terms).lower()
    return any(token in joined for token in ["qpcr", "rt-qpcr", "claudin", "occludin", "gene expression"])


def inferred_assumption_source(parsed: ParsedHypothesis) -> EvidenceSource:
    return EvidenceSource(
        id=stable_source_id("assumption", parsed.domain_route, parsed.original_text[:80]),
        source_name="MVP assumption",
        title=f"{parsed.domain} assumptions requiring expert review",
        url=None,
        evidence_type=EvidenceType.assumption,
        trust_tier=TrustTier.inferred,
        trust_level=TrustLevel.low,
        snippet="Inferred operational details remain expert-review-required unless source-backed evidence is retrieved.",
        authors=[],
        year=None,
        doi=None,
        confidence=0.33,
        retrieved_at=now_utc(),
    )


def dedupe_sources(sources: list[EvidenceSource]) -> list[EvidenceSource]:
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


def dedupe_trace(entries: list[ProviderTraceEntry]) -> list[ProviderTraceEntry]:
    seen: set[tuple[str, str, bool]] = set()
    deduped: list[ProviderTraceEntry] = []
    for entry in entries:
        key = (entry.provider, entry.query, entry.cached)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def confidence_summary(sources: list[EvidenceSource], literature_qc: LiteratureQC) -> float:
    if not sources:
        return literature_qc.confidence
    return min(0.95, sum(source.confidence for source in sources) / len(sources))
