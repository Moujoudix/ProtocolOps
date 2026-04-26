from app.models.schemas import EvidenceSource, EvidenceType, TrustLevel, TrustTier, now_utc


def bmbl_source() -> EvidenceSource:
    return _standard_source(
        source_id="standard-bmbl",
        source_name="BMBL",
        title="BMBL biosafety checklist for human cell lines and BSL-2 handling",
        url="https://www.cdc.gov/labs/BMBL.html",
        snippet="Use BMBL safeguards to review HeLa BSL-2 handling, HPV context, storage, and laboratory biosafety controls.",
    )


def arrive_source() -> EvidenceSource:
    return _standard_source(
        source_id="standard-arrive",
        source_name="ARRIVE",
        title="ARRIVE checklist for in vivo animal experiments",
        url="https://arriveguidelines.org",
        snippet="Use ARRIVE to flag ethics approval, housing, randomization, blinding, humane endpoints, and sample-size assumptions.",
    )


def miqe_source() -> EvidenceSource:
    return _standard_source(
        source_id="standard-miqe",
        source_name="MIQE",
        title="MIQE checklist for qPCR and RT-qPCR reporting",
        url="https://www.gene-quantification.de/miqe.html",
        snippet="Use MIQE when qPCR or RT-qPCR validation appears in the plan to enforce primer, normalization, and reporting controls.",
    )


def stard_source() -> EvidenceSource:
    return _standard_source(
        source_id="standard-stard",
        source_name="STARD",
        title="STARD checklist for diagnostic accuracy studies",
        url="https://www.equator-network.org/reporting-guidelines/stard/",
        snippet="Use STARD to flag comparator choice, sensitivity/specificity framing, sample handling, and diagnostic validation risks.",
    )


def anaerobic_safety_source() -> EvidenceSource:
    return _standard_source(
        source_id="standard-anaerobic-safety",
        source_name="Anaerobic handling checklist",
        title="Anaerobic handling and bioelectrochemical safety checklist",
        url=None,
        snippet="Use this checklist to review anaerobic handling, gas delivery, reactor containment, and measurement safety assumptions.",
    )


def _standard_source(
    source_id: str,
    source_name: str,
    title: str,
    url: str | None,
    snippet: str,
) -> EvidenceSource:
    return EvidenceSource(
        id=source_id,
        source_name=source_name,
        title=title,
        url=url,
        evidence_type=EvidenceType.safety_or_standard,
        trust_tier=TrustTier.scientific_standard,
        trust_level=TrustLevel.high,
        snippet=snippet,
        authors=[],
        year=None,
        doi=None,
        confidence=0.84,
        retrieved_at=now_utc(),
    )
