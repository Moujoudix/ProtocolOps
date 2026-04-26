import pytest

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
from app.seeds.hela import seeded_hela_literature_qc, seeded_hela_parsed
from app.services.domain_routing import resolve_domain_route
from app.services.evidence_pack import EvidencePackService
from app.services.openai_client import OpenAIStructuredClient, heuristic_parse_hypothesis
from app.core.config import Settings


@pytest.mark.asyncio
async def test_hela_evidence_pack_contains_seeded_supplier_and_community_sources():
    settings = Settings(
        app_env="test",
        openai_api_key="",
        semantic_scholar_api_key="",
        protocols_io_token="",
        tavily_api_key="",
    )
    parsed = seeded_hela_parsed(
        "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase post-thaw "
        "viability of HeLa cells by at least 15 percentage points compared to the standard DMSO protocol."
    )
    literature_qc = seeded_hela_literature_qc()

    evidence_pack = await EvidencePackService(settings).build(parsed, literature_qc, preset_id="hela-trehalose")

    source_titles = {source.title for source in evidence_pack.sources}
    source_ids = {source.id for source in evidence_pack.sources}
    assert evidence_pack.domain_route == DomainRoute.cell_biology
    assert evidence_pack.used_seed_data is True
    assert "ATCC HeLa cell line product page (CCL-2)" in source_titles
    assert "Gibco cell-freezing protocol guidance" in source_titles
    assert "Promega CellTiter-Glo viability assay guidance" in source_titles
    assert "Trehalose supplier context" in source_titles
    assert "seed-protocolsio-fallback" in source_ids
    assert "seed-openwetware-fallback" in source_ids


@pytest.mark.asyncio
async def test_non_hela_fallback_plan_keeps_protocol_confidence_low_without_protocol_evidence():
    settings = Settings(openai_api_key="")
    parsed = heuristic_parse_hypothesis(
        "A paper-based electrochemical biosensor functionalized with anti-CRP antibodies will detect "
        "C-reactive protein in whole blood at concentrations below 0.5 mg/L within 10 minutes.",
        preset_id="crp-biosensor",
    )
    literature_qc = LiteratureQC(
        novelty_signal=NoveltySignal.not_found_in_searched_sources,
        confidence=0.28,
        references=[],
        literature_sources=[],
        searched_sources=["Semantic Scholar", "Europe PMC"],
        provider_trace=[],
        rationale="No matching references were found in the searched sources used by this MVP run.",
        literature_synthesis=None,
        gaps=["Limited evidence for this preset."],
        evidence_gap_warnings=["Limited evidence for this preset."],
    )
    evidence_pack = EvidencePack(
        domain_route=parsed.domain_route,
        sources=[
            EvidenceSource(
                id="assumption-no-protocol-evidence",
                source_name="MVP assumption",
                title="No retrieved protocol evidence",
                url=None,
                evidence_type=EvidenceType.assumption,
                trust_tier=TrustTier.inferred,
                trust_level=TrustLevel.low,
                snippet="No source-backed protocol evidence was retrieved for this preset.",
                authors=[],
                year=None,
                doi=None,
                confidence=0.2,
                retrieved_at=now_utc(),
            )
        ],
        searched_providers=["Semantic Scholar", "Europe PMC"],
        provider_trace=[],
        evidence_gap_warnings=["No protocol evidence retrieved."],
        literature_synthesis=None,
        checklists=[],
        used_seed_data=False,
        confidence_summary=0.2,
    )

    plan = await OpenAIStructuredClient(settings).generate_plan(parsed, literature_qc, evidence_pack, preset_id="crp-biosensor")

    assert resolve_domain_route(parsed.original_text, "crp-biosensor") == DomainRoute.diagnostics_biosensor
    assert all(step.confidence <= 0.45 for step in plan.protocol)
    assert all(step.expert_review_required for step in plan.protocol)


@pytest.mark.asyncio
async def test_strict_live_hela_accepts_live_atcc_supplier_source(monkeypatch):
    settings = Settings(
        app_env="development",
        openai_api_key="",
        strict_live_mode=True,
        evidence_mode="strict_live",
    )
    parsed = seeded_hela_parsed(
        "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase post-thaw "
        "viability of HeLa cells by at least 15 percentage points compared to the standard DMSO protocol."
    )
    literature_qc = seeded_hela_literature_qc().model_copy(
        update={
            "references": [],
            "literature_sources": [],
            "searched_sources": ["Consensus", "Semantic Scholar", "Europe PMC"],
            "provider_trace": [],
        }
    )
    service = EvidencePackService(settings)

    live_atcc = EvidenceSource(
        id="live-atcc-ccl2",
        source_name="www.atcc.org",
        title="ATCC HeLa cell line product page (CCL-2)",
        url="https://www.atcc.org/products/ccl-2",
        evidence_type=EvidenceType.supplier_reference,
        trust_tier=TrustTier.supplier_documentation,
        trust_level=TrustLevel.high,
        snippet="Live extracted ATCC supplier documentation for HeLa CCL-2.",
        authors=[],
        year=None,
        doi=None,
        confidence=0.8,
        retrieved_at=now_utc(),
    )

    async def fake_supplier_sources(context):
        return [live_atcc], [], False

    async def empty_sources(context, queries):
        return [], []

    monkeypatch.setattr(service, "_build_hela_supplier_sources", fake_supplier_sources)
    monkeypatch.setattr(service, "_collect_protocol_sources", empty_sources)
    monkeypatch.setattr(service, "_collect_openwetware_sources", empty_sources)

    evidence_pack = await service.build(parsed, literature_qc, preset_id="hela-trehalose")

    assert evidence_pack.used_seed_data is False
    assert any(source.url == "https://www.atcc.org/products/ccl-2" for source in evidence_pack.sources)


@pytest.mark.asyncio
async def test_strict_live_hela_rejects_any_seeded_supplier_fallback(monkeypatch):
    settings = Settings(
        app_env="development",
        openai_api_key="",
        strict_live_mode=True,
        evidence_mode="strict_live",
    )
    parsed = seeded_hela_parsed(
        "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium will increase post-thaw "
        "viability of HeLa cells by at least 15 percentage points compared to the standard DMSO protocol."
    )
    literature_qc = seeded_hela_literature_qc().model_copy(
        update={
            "references": [],
            "literature_sources": [],
            "searched_sources": ["Consensus", "Semantic Scholar", "Europe PMC"],
            "provider_trace": [],
        }
    )
    service = EvidencePackService(settings)

    live_atcc = EvidenceSource(
        id="live-atcc-ccl2",
        source_name="www.atcc.org",
        title="ATCC HeLa cell line product page (CCL-2)",
        url="https://www.atcc.org/products/ccl-2",
        evidence_type=EvidenceType.supplier_reference,
        trust_tier=TrustTier.supplier_documentation,
        trust_level=TrustLevel.high,
        snippet="Live extracted ATCC supplier documentation for HeLa CCL-2.",
        authors=[],
        year=None,
        doi=None,
        confidence=0.8,
        retrieved_at=now_utc(),
    )
    seeded_sigma = EvidenceSource(
        id="seed-sigma-trehalose",
        source_name="Sigma-Aldrich",
        title="Trehalose supplier context",
        url="https://www.sigmaaldrich.com/US/en/search/trehalose",
        evidence_type=EvidenceType.supplier_reference,
        trust_tier=TrustTier.supplier_documentation,
        trust_level=TrustLevel.medium,
        snippet="Seeded supplier fallback.",
        authors=[],
        year=None,
        doi=None,
        confidence=0.66,
        retrieved_at=now_utc(),
    )

    async def seeded_supplier_sources(context):
        return [live_atcc, seeded_sigma], [], True

    async def empty_sources(context, queries):
        return [], []

    monkeypatch.setattr(service, "_build_hela_supplier_sources", seeded_supplier_sources)
    monkeypatch.setattr(service, "_collect_protocol_sources", empty_sources)
    monkeypatch.setattr(service, "_collect_openwetware_sources", empty_sources)

    with pytest.raises(RuntimeError, match="Strict live mode forbids seeded evidence-pack sources"):
        await service.build(parsed, literature_qc, preset_id="hela-trehalose")
