from app.models.schemas import (
    DomainRoute,
    EvidenceMode,
    EvidencePack,
    LiteratureQC,
    NoveltySignal,
    ProviderTraceEntry,
)
from app.services.run_metadata import infer_evidence_mode


def _literature_qc(*, searched_sources, provider_trace):
    return LiteratureQC(
        novelty_signal=NoveltySignal.similar_work_exists,
        confidence=0.6,
        references=[],
        literature_sources=[],
        searched_sources=searched_sources,
        provider_trace=provider_trace,
        rationale="Test fixture",
        literature_synthesis=None,
        gaps=[],
        evidence_gap_warnings=[],
    )


def _evidence_pack(*, searched_providers, provider_trace):
    return EvidencePack(
        domain_route=DomainRoute.cell_biology,
        sources=[],
        searched_providers=searched_providers,
        provider_trace=provider_trace,
        evidence_gap_warnings=[],
        literature_synthesis=None,
        checklists=[],
        used_seed_data=False,
        confidence_summary=0.5,
    )


def test_infer_evidence_mode_keeps_consensus_cache_as_strict_live():
    literature_qc = _literature_qc(
        searched_sources=["Consensus", "Semantic Scholar", "Europe PMC"],
        provider_trace=[
            ProviderTraceEntry(
                provider="Consensus",
                attempted=True,
                succeeded=True,
                cached=True,
                stage="literature_qc",
                fallback_used=False,
                query="hela trehalose",
                result_count=1,
            )
        ],
    )

    assert infer_evidence_mode(literature_qc) == EvidenceMode.strict_live


def test_infer_evidence_mode_marks_cached_live_replay():
    literature_qc = _literature_qc(
        searched_sources=["Consensus", "Europe PMC", "Cached live replay"],
        provider_trace=[
            ProviderTraceEntry(
                provider="Consensus",
                attempted=True,
                succeeded=True,
                cached=True,
                stage="literature_qc",
                fallback_used=True,
                query="hela trehalose",
                result_count=1,
            )
        ],
    )
    evidence_pack = _evidence_pack(
        searched_providers=["Tavily Extract", "Cached live replay"],
        provider_trace=literature_qc.provider_trace,
    )

    assert infer_evidence_mode(literature_qc, evidence_pack) == EvidenceMode.cached_live
