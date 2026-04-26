import pytest
from sqlmodel import Session

from app.core.config import Settings
from app.core.database import create_db_and_tables, engine
from app.models.db import ConsensusCache
from app.models.schemas import (
    DomainRoute,
    EvidencePack,
    EvidenceSource,
    EvidenceType,
    LiteratureQC,
    NoveltySignal,
    TrustLevel,
    TrustTier,
    now_utc,
)
from app.providers.base import ProviderSearchResult, SearchContext
from app.providers.protocols import OpenWetWareProvider
from app.providers.utils import normalize_hypothesis_key
from app.services.consensus_adapter import ConsensusMcpAdapter
from app.services.evidence_pack import EvidencePackService
from app.services.literature_qc import LiteratureQcService
from app.services.openai_client import OpenAIStructuredClient, heuristic_parse_hypothesis


create_db_and_tables()


def make_source(source_id: str, *, evidence_type: EvidenceType, trust_tier: TrustTier = TrustTier.literature_database) -> EvidenceSource:
    return EvidenceSource(
        id=source_id,
        source_name="Mock source",
        title=source_id,
        url="https://example.com/source",
        evidence_type=evidence_type,
        trust_tier=trust_tier,
        trust_level=TrustLevel.medium if trust_tier != TrustTier.inferred else TrustLevel.low,
        snippet="Mock snippet",
        authors=[],
        year=2024,
        doi=None,
        confidence=0.6,
        retrieved_at=now_utc(),
    )


@pytest.mark.asyncio
async def test_stage_1_parse_does_not_call_literature_providers(monkeypatch):
    parser = OpenAIStructuredClient(Settings(openai_api_key=""))
    called = {"semantic": False}

    async def should_not_run(*args, **kwargs):
        called["semantic"] = True
        return ProviderSearchResult(sources=[])

    monkeypatch.setattr("app.providers.literature.SemanticScholarProvider.search", should_not_run)

    parsed = await parser.parse_hypothesis(
        "A paper-based electrochemical biosensor functionalized with anti-CRP antibodies will detect C-reactive protein in whole blood at concentrations below 0.5 mg/L within 10 minutes.",
        preset_id="crp-biosensor",
    )

    assert parsed.domain_route == DomainRoute.diagnostics_biosensor
    assert called["semantic"] is False


@pytest.mark.asyncio
async def test_consensus_is_attempted_first_and_failure_does_not_stop_primary_sources(monkeypatch):
    settings = Settings(app_env="development", consensus_mcp_enabled=True, evidence_mode="strict_live")
    service = LiteratureQcService(settings)
    parsed = heuristic_parse_hypothesis(
        "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard DMSO protocol.",
        preset_id="hela-trehalose",
    )
    context = SearchContext(parsed_hypothesis=parsed, preset_id="hela-trehalose", stage="literature_qc")
    call_order: list[str] = []

    async def failing_consensus(query, ctx):
        call_order.append("Consensus")
        raise RuntimeError("bridge unavailable")

    async def semantic(query, ctx):
        call_order.append("Semantic Scholar")
        return ProviderSearchResult(sources=[make_source("semantic", evidence_type=EvidenceType.close_match)])

    async def europe(query, ctx):
        call_order.append("Europe PMC")
        return ProviderSearchResult(sources=[make_source("europe", evidence_type=EvidenceType.close_match)])

    monkeypatch.setattr(service.consensus, "search", failing_consensus)
    monkeypatch.setattr(service.router.semantic_scholar, "search", semantic)
    monkeypatch.setattr(service.router.europe_pmc, "search", europe)

    qc = await service.run(context)

    assert call_order[:3] == ["Consensus", "Semantic Scholar", "Europe PMC"]
    assert qc.provider_trace[0].provider == "Consensus"
    assert qc.provider_trace[0].succeeded is False
    assert qc.provider_trace[1].provider == "Semantic Scholar"
    assert qc.provider_trace[2].provider == "Europe PMC"


@pytest.mark.asyncio
async def test_consensus_cache_suppresses_duplicate_live_calls(monkeypatch):
    settings = Settings(app_env="development", consensus_mcp_enabled=True, evidence_mode="strict_live")
    service = LiteratureQcService(settings)
    parsed = heuristic_parse_hypothesis(
        "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase post-thaw viability of HeLa cells by at least 15 percentage points compared to the standard DMSO protocol.",
        preset_id="hela-trehalose",
    )
    context = SearchContext(parsed_hypothesis=parsed, preset_id="hela-trehalose", stage="literature_qc")
    normalized = normalize_hypothesis_key(parsed.original_text)
    call_count = {"consensus": 0}

    async def consensus(query, ctx):
        call_count["consensus"] += 1
        return ProviderSearchResult(
            sources=[make_source("consensus-ref", evidence_type=EvidenceType.close_match)],
            literature_synthesis="Consensus synthesis",
        )

    async def no_results(query, ctx):
        return ProviderSearchResult(sources=[])

    monkeypatch.setattr(service.consensus, "search", consensus)
    monkeypatch.setattr(service.router.semantic_scholar, "search", no_results)
    monkeypatch.setattr(service.router.europe_pmc, "search", no_results)

    with Session(engine) as session:
        cached = session.get(ConsensusCache, normalized)
        if cached is not None:
            session.delete(cached)
            session.commit()
        await service.run(context, session=session)
        qc = await service.run(context, session=session)

    assert call_count["consensus"] == 1
    assert qc.provider_trace[0].cached is True


@pytest.mark.asyncio
async def test_consensus_adapter_fails_fast_when_bridge_is_unauthenticated(monkeypatch):
    settings = Settings(
        app_env="development",
        consensus_mcp_enabled=True,
        consensus_mcp_bridge_url="http://127.0.0.1:8765/search",
    )
    adapter = ConsensusMcpAdapter(settings)
    parsed = heuristic_parse_hypothesis("HeLa cryopreservation with trehalose versus DMSO.", preset_id="hela-trehalose")
    context = SearchContext(parsed_hypothesis=parsed, preset_id="hela-trehalose", stage="literature_qc")
    calls = {"get": 0, "post": 0}

    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"authenticated": False, "detail": "Consensus OAuth not detected yet"}

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            calls["get"] += 1
            return MockResponse()

        async def post(self, url, json):
            calls["post"] += 1
            return MockResponse()

    monkeypatch.setattr("app.services.consensus_adapter.httpx.AsyncClient", MockClient)

    with pytest.raises(RuntimeError, match="Consensus OAuth not detected yet"):
        await adapter.search("trehalose HeLa cryopreservation viability DMSO", context)

    assert calls == {"get": 1, "post": 0}


@pytest.mark.asyncio
async def test_ncbi_only_used_for_biomedical_fallback_and_arxiv_only_on_relevant_routes(monkeypatch):
    settings = Settings(app_env="development", consensus_mcp_enabled=False, evidence_mode="strict_live")
    service = LiteratureQcService(settings)
    counts = {"ncbi": 0, "arxiv": 0}

    async def weak_primary(query, ctx):
        return ProviderSearchResult(sources=[])

    async def ncbi(query, ctx):
        counts["ncbi"] += 1
        return ProviderSearchResult(sources=[make_source("ncbi", evidence_type=EvidenceType.close_match)])

    async def arxiv(query, ctx):
        counts["arxiv"] += 1
        return ProviderSearchResult(sources=[make_source("arxiv", evidence_type=EvidenceType.adjacent_method)])

    monkeypatch.setattr(service.router.semantic_scholar, "search", weak_primary)
    monkeypatch.setattr(service.router.europe_pmc, "search", weak_primary)
    monkeypatch.setattr(service.router.ncbi, "search", ncbi)
    monkeypatch.setattr(service.router.arxiv, "search", arxiv)

    hela_context = SearchContext(
        parsed_hypothesis=heuristic_parse_hypothesis("HeLa cryopreservation with trehalose versus DMSO.", preset_id="hela-trehalose"),
        preset_id="hela-trehalose",
        stage="literature_qc",
    )
    sporomusa_context = SearchContext(
        parsed_hypothesis=heuristic_parse_hypothesis("Sporomusa ovata in a bioelectrochemical system will fix CO2 into acetate.", preset_id="sporomusa-co2"),
        preset_id="sporomusa-co2",
        stage="literature_qc",
    )

    await service.run(hela_context)
    await service.run(sporomusa_context)

    assert counts["ncbi"] == 1
    assert counts["arxiv"] == 1


@pytest.mark.asyncio
async def test_non_hela_evidence_pack_does_not_use_hela_seeded_evidence():
    settings = Settings(app_env="test", openai_api_key="")
    parsed = heuristic_parse_hypothesis(
        "A paper-based electrochemical biosensor functionalized with anti-CRP antibodies will detect C-reactive protein in whole blood at concentrations below 0.5 mg/L within 10 minutes.",
        preset_id="crp-biosensor",
    )
    literature_qc = LiteratureQC(
        novelty_signal=NoveltySignal.not_found_in_searched_sources,
        confidence=0.3,
        references=[],
        literature_sources=[],
        searched_sources=["Semantic Scholar", "Europe PMC"],
        provider_trace=[],
        rationale="No exact match was found in the configured searched sources.",
        literature_synthesis=None,
        gaps=["Limited evidence for this preset."],
        evidence_gap_warnings=["Limited evidence for this preset."],
    )

    evidence_pack = await EvidencePackService(settings).build(parsed, literature_qc, preset_id="crp-biosensor")

    assert all(not source.id.startswith("seed-") for source in evidence_pack.sources)


@pytest.mark.asyncio
async def test_tavily_search_is_not_used_for_known_urls(monkeypatch):
    settings = Settings(app_env="development", openai_api_key="", evidence_mode="strict_live")
    parsed = heuristic_parse_hypothesis("HeLa cryopreservation with trehalose versus DMSO.", preset_id="hela-trehalose")
    literature_qc = LiteratureQC(
        novelty_signal=NoveltySignal.similar_work_exists,
        confidence=0.65,
        references=[],
        literature_sources=[],
        searched_sources=["Semantic Scholar", "Europe PMC"],
        provider_trace=[],
        rationale="Similar work exists.",
        literature_synthesis=None,
        gaps=[],
        evidence_gap_warnings=[],
    )
    service = EvidencePackService(settings)
    calls = {"search": [], "extract": []}

    async def fake_search(query, **kwargs):
        calls["search"].append(query)
        return [{"url": "https://www.sigmaaldrich.com/US/en/product/mock", "title": "Sigma trehalose"}]

    async def fake_extract(urls, **kwargs):
        calls["extract"].extend(urls)
        return [{"url": url, "title": "Extracted", "markdown": "content"} for url in urls]

    async def empty_protocol(query, context):
        return ProviderSearchResult(sources=[])

    monkeypatch.setattr(service.tavily, "search", fake_search)
    monkeypatch.setattr(service.tavily, "extract", fake_extract)
    monkeypatch.setattr(service.router.protocols, "search", empty_protocol)
    monkeypatch.setattr(service.router.openwetware, "search", empty_protocol)

    await service.build(parsed, literature_qc, preset_id="hela-trehalose")

    assert calls["search"] == ["Sigma trehalose product page"]
    assert "https://www.atcc.org/products/ccl-2" in calls["extract"]
    assert any("thermofisher.com" in url for url in calls["extract"])
    assert any("promega.com" in url for url in calls["extract"])


@pytest.mark.asyncio
async def test_openwetware_uses_mediawiki_api(monkeypatch):
    provider = OpenWetWareProvider(Settings())
    captured = {"url": None}

    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"query": {"search": []}}

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None):
            captured["url"] = url
            return MockResponse()

    monkeypatch.setattr("app.providers.protocols.httpx.AsyncClient", MockClient)

    context = SearchContext(
        parsed_hypothesis=heuristic_parse_hypothesis("HeLa cryopreservation with trehalose versus DMSO.", preset_id="hela-trehalose"),
        preset_id="hela-trehalose",
        stage="evidence_pack",
    )
    await provider.search("Marek Freeze-down Thaw", context)

    assert captured["url"] == "https://openwetware.org/mediawiki/api.php"


@pytest.mark.asyncio
async def test_non_hela_guardrails_keep_sensitive_details_low_confidence():
    settings = Settings(openai_api_key="")
    parsed = heuristic_parse_hypothesis(
        "Supplementing C57BL/6 mice with Lactobacillus rhamnosus GG for 4 weeks will reduce intestinal permeability by at least 30% compared to controls.",
        preset_id="lgg-mouse-gut",
    )
    literature_qc = LiteratureQC(
        novelty_signal=NoveltySignal.not_found_in_searched_sources,
        confidence=0.2,
        references=[],
        literature_sources=[],
        searched_sources=["Consensus", "Europe PMC", "Semantic Scholar"],
        provider_trace=[],
        rationale="No exact match was found in the configured searched sources.",
        literature_synthesis=None,
        gaps=["Low evidence."],
        evidence_gap_warnings=["Low evidence."],
    )
    evidence_pack = EvidencePack(
        domain_route=parsed.domain_route,
        sources=[
            make_source("assumption-only", evidence_type=EvidenceType.assumption, trust_tier=TrustTier.inferred)
        ],
        searched_providers=["Consensus", "Europe PMC", "Semantic Scholar"],
        provider_trace=[],
        evidence_gap_warnings=["No protocol evidence."],
        literature_synthesis=None,
        checklists=[],
        used_seed_data=False,
        confidence_summary=0.2,
    )

    plan = await OpenAIStructuredClient(settings).generate_plan(parsed, literature_qc, evidence_pack, preset_id="lgg-mouse-gut")

    assert all(step.expert_review_required for step in plan.protocol)
    assert all(step.confidence <= 0.45 for step in plan.protocol)
