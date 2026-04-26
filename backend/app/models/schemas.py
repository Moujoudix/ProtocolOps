import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DomainRoute(StrEnum):
    cell_biology = "cell_biology"
    diagnostics_biosensor = "diagnostics_biosensor"
    animal_gut_health = "animal_gut_health"
    microbial_electrochemistry = "microbial_electrochemistry"


class EvidenceType(StrEnum):
    exact_match = "exact_match"
    close_match = "close_match"
    adjacent_method = "adjacent_method"
    generic_method = "generic_method"
    supplier_reference = "supplier_reference"
    safety_or_standard = "safety_or_standard"
    assumption = "assumption"


class TrustTier(StrEnum):
    literature_database = "literature_database"
    supplier_documentation = "supplier_documentation"
    community_protocol = "community_protocol"
    scientific_standard = "scientific_standard"
    inferred = "inferred"


class TrustLevel(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class ProcurementStatus(StrEnum):
    verified = "verified"
    requires_procurement_check = "requires_procurement_check"


class PriceStatus(StrEnum):
    visible_price = "visible_price"
    requires_procurement_check = "requires_procurement_check"
    contact_supplier = "contact_supplier"


class NoveltySignal(StrEnum):
    exact_match_found = "exact_match_found"
    similar_work_exists = "similar_work_exists"
    not_found_in_searched_sources = "not_found_in_searched_sources"


class ReviewState(StrEnum):
    generated = "generated"
    reviewed = "reviewed"
    revised = "revised"
    approved_for_proposal = "approved_for_proposal"


class ReviewAction(StrEnum):
    approve = "approve"
    reject = "reject"
    edit = "edit"
    replace = "replace"
    unrealistic = "unrealistic"
    missing_dependency = "missing_dependency"
    comment = "comment"


class ReviewTargetType(StrEnum):
    section = "section"
    protocol_step = "protocol_step"
    material = "material"
    budget_item = "budget_item"
    timeline = "timeline"
    validation = "validation"
    risk = "risk"


class ReadinessStatus(StrEnum):
    ready = "ready"
    missing_secret = "missing_secret"
    public_mode = "public_mode"
    unreachable = "unreachable"
    degraded = "degraded"


class RunMode(StrEnum):
    fully_live = "fully_live"
    degraded_live = "degraded_live"
    demo_fallback = "demo_fallback"


class EvidenceMode(StrEnum):
    strict_live = "strict_live"
    cached_live = "cached_live"
    seeded_demo = "seeded_demo"


class Preset(StrictModel):
    id: str
    label: str
    domain: str
    hypothesis: str
    optimized_demo: bool


class LiteratureQcRequest(StrictModel):
    hypothesis: str = Field(min_length=20)
    preset_id: str | None = None


class ParsedHypothesis(StrictModel):
    original_text: str
    domain: str
    domain_route: DomainRoute
    scientific_system: str | None
    model_or_organism: str | None
    intervention: str | None
    comparator: str | None
    outcome_metric: str | None
    success_threshold: str | None
    mechanism: str | None
    literature_query_terms: list[str]
    protocol_query_terms: list[str]
    supplier_material_query_terms: list[str]
    organism_or_system: str | None = None
    outcome: str | None = None
    effect_size: str | None = None
    key_terms: list[str] = Field(default_factory=list)
    safety_notes: list[str]

    @model_validator(mode="after")
    def derive_compatibility_fields(self) -> "ParsedHypothesis":
        if self.organism_or_system is None:
            self.organism_or_system = self.model_or_organism or self.scientific_system
        if self.outcome is None:
            self.outcome = self.outcome_metric
        if self.effect_size is None:
            self.effect_size = self.success_threshold
        if not self.key_terms:
            ordered_terms = [
                *(self.literature_query_terms or []),
                *(self.protocol_query_terms or []),
                *(self.supplier_material_query_terms or []),
            ]
            deduped: list[str] = []
            for term in ordered_terms:
                cleaned = term.strip()
                if cleaned and cleaned not in deduped:
                    deduped.append(cleaned)
            self.key_terms = deduped[:12]
        return self


class EvidenceSource(StrictModel):
    id: str
    source_name: str
    title: str
    url: str | None
    evidence_type: EvidenceType
    trust_tier: TrustTier
    trust_level: TrustLevel
    snippet: str
    authors: list[str]
    year: int | None
    doi: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    retrieved_at: datetime


class ProviderTraceEntry(StrictModel):
    provider: str
    attempted: bool
    succeeded: bool
    cached: bool = False
    stage: str = "literature_qc"
    fallback_used: bool = False
    query: str
    result_count: int = Field(ge=0)
    error: str | None = None


class LiteratureQC(StrictModel):
    novelty_signal: NoveltySignal
    confidence: float = Field(ge=0.0, le=1.0)
    references: list[EvidenceSource] = Field(max_length=3)
    literature_sources: list[EvidenceSource] = Field(default_factory=list)
    searched_sources: list[str]
    provider_trace: list[ProviderTraceEntry] = Field(default_factory=list)
    rationale: str
    literature_synthesis: str | None = None
    gaps: list[str] = Field(default_factory=list)
    evidence_gap_warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_gap_fields(self) -> "LiteratureQC":
        if not self.gaps and self.evidence_gap_warnings:
            self.gaps = list(self.evidence_gap_warnings)
        if not self.evidence_gap_warnings and self.gaps:
            self.evidence_gap_warnings = list(self.gaps)
        if not self.literature_sources:
            self.literature_sources = list(self.references)
        return self


class EvidencePack(StrictModel):
    domain_route: DomainRoute
    sources: list[EvidenceSource]
    searched_providers: list[str]
    provider_trace: list[ProviderTraceEntry] = Field(default_factory=list)
    evidence_gap_warnings: list[str]
    literature_synthesis: str | None = None
    checklists: list[EvidenceSource] = Field(default_factory=list)
    used_seed_data: bool
    confidence_summary: float = Field(ge=0.0, le=1.0)


class ProviderReadiness(StrictModel):
    provider: str
    status: ReadinessStatus
    detail: str
    configured: bool
    authenticated: bool = False


class ReadinessResponse(StrictModel):
    strict_live_mode: bool
    evidence_mode: EvidenceMode
    live_ready: bool
    cached_live_available: bool = False
    seeded_demo_available: bool = True
    providers: list[ProviderReadiness]


class ReviewMemoryReference(StrictModel):
    run_id: str
    review_session_id: str
    target_type: ReviewTargetType
    target_key: str
    action: ReviewAction
    note: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class PlanQualitySummary(StrictModel):
    literature_confidence: float = Field(ge=0.0, le=1.0)
    protocol_confidence: float = Field(ge=0.0, le=1.0)
    materials_confidence: float = Field(ge=0.0, le=1.0)
    budget_confidence: float = Field(ge=0.0, le=1.0)
    evidence_completeness: float = Field(ge=0.0, le=1.0)
    operational_readiness: float = Field(ge=0.0, le=1.0)
    review_burden: float = Field(ge=0.0, le=1.0)


class ExperimentPlanSection(StrictModel):
    title: str
    summary: str
    bullets: list[str]
    evidence_source_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    expert_review_required: bool


class MaterialItem(StrictModel):
    name: str
    role: str
    vendor: str | None
    catalog_number: str | None
    price: str | None
    currency: str | None
    procurement_status: ProcurementStatus = ProcurementStatus.verified
    price_status: PriceStatus = PriceStatus.visible_price
    requires_procurement_check: bool = False
    evidence_source_ids: list[str] = Field(min_length=1)
    notes: str
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def enforce_procurement_check(self) -> "MaterialItem":
        self.procurement_status = (
            ProcurementStatus.requires_procurement_check if self.catalog_number is None else ProcurementStatus.verified
        )
        if self.price is None:
            self.price_status = PriceStatus.contact_supplier if self.vendor else PriceStatus.requires_procurement_check
        else:
            self.price_status = PriceStatus.visible_price
        self.requires_procurement_check = (
            self.procurement_status == ProcurementStatus.requires_procurement_check
            or self.price_status != PriceStatus.visible_price
        )
        return self


class ProtocolStep(StrictModel):
    step_number: int = Field(ge=1)
    title: str
    purpose: str
    actions: list[str] = Field(min_length=1)
    critical_parameters: list[str]
    materials: list[str]
    evidence_source_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    expert_review_required: bool
    review_reason: str | None

    @model_validator(mode="after")
    def require_review_reason_when_flagged(self) -> "ProtocolStep":
        if self.expert_review_required and not self.review_reason:
            self.review_reason = "Protocol detail is inferred or adjacent-source-backed and requires expert review."
        return self


class BudgetSummary(StrictModel):
    title: str
    summary: str
    items: list[MaterialItem]
    evidence_source_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    expert_review_required: bool


class ExperimentPlan(StrictModel):
    plan_title: str
    status_label: str
    quality_summary: PlanQualitySummary | None = None
    memory_applied: list[ReviewMemoryReference] = Field(default_factory=list)
    overview: ExperimentPlanSection
    literature_qc: LiteratureQC
    study_design: ExperimentPlanSection
    protocol: list[ProtocolStep]
    materials: list[MaterialItem]
    budget: BudgetSummary
    timeline: ExperimentPlanSection
    validation: ExperimentPlanSection
    risks: ExperimentPlanSection
    sources: list[EvidenceSource]
    generated_at: datetime


class LiteratureQcResponse(StrictModel):
    run_id: str
    parsed_hypothesis: ParsedHypothesis
    literature_qc: LiteratureQC


class PlanResponse(StrictModel):
    run_id: str
    plan: ExperimentPlan


class ComparisonMetricRecord(StrictModel):
    label: str
    baseline: str
    current: str
    delta: float | None = None


class RunComparisonResponse(StrictModel):
    baseline_run_id: str
    current_run_id: str
    baseline_title: str
    current_title: str
    summary: list[str] = Field(default_factory=list)
    metrics: list[ComparisonMetricRecord] = Field(default_factory=list)
    protocol_changes: list[str] = Field(default_factory=list)
    material_changes: list[str] = Field(default_factory=list)
    budget_changes: list[str] = Field(default_factory=list)


class RunListItem(StrictModel):
    run_id: str
    hypothesis: str
    preset_id: str | None
    status: str
    review_state: ReviewState
    run_mode: RunMode
    evidence_mode: EvidenceMode
    created_at: datetime
    updated_at: datetime
    domain: str | None = None
    plan_title: str | None = None
    quality_summary: PlanQualitySummary | None = None
    used_seed_data: bool = False
    is_presentation_anchor: bool = False
    parent_run_id: str | None = None
    revision_number: int = 0


class RunStateResponse(StrictModel):
    run_id: str
    hypothesis: str
    preset_id: str | None
    status: str
    review_state: ReviewState = ReviewState.generated
    run_mode: RunMode = RunMode.degraded_live
    evidence_mode: EvidenceMode = EvidenceMode.seeded_demo
    used_seed_data: bool = False
    is_presentation_anchor: bool = False
    parent_run_id: str | None = None
    revision_number: int = 0
    parsed_hypothesis: ParsedHypothesis | None
    literature_qc: LiteratureQC | None
    plan: ExperimentPlan | None


class RunEventRecord(StrictModel):
    id: str
    run_id: str
    stage: str
    status: str
    message: str
    created_at: datetime


class ReviewItemPayload(StrictModel):
    target_type: ReviewTargetType
    target_key: str
    action: ReviewAction
    comment: str | None = None
    replacement_text: str | None = None
    confidence_override: float | None = Field(default=None, ge=0.0, le=1.0)


class ReviewSubmissionRequest(StrictModel):
    reviewer_name: str | None = None
    summary: str | None = None
    review_state: ReviewState = ReviewState.reviewed
    items: list[ReviewItemPayload] = Field(min_length=1)


class ReviewItemRecord(StrictModel):
    id: str
    target_type: ReviewTargetType
    target_key: str
    action: ReviewAction
    comment: str | None = None
    replacement_text: str | None = None
    confidence_override: float | None = None
    created_at: datetime


class ReviewSessionRecord(StrictModel):
    id: str
    run_id: str
    reviewer_name: str | None = None
    summary: str | None = None
    review_state: ReviewState
    created_at: datetime
    updated_at: datetime
    items: list[ReviewItemRecord] = Field(default_factory=list)


class ReviewSubmissionResponse(StrictModel):
    review: ReviewSessionRecord


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def model_from_json(model: type[BaseModel], raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        return model.model_validate_json(raw)
    except ValidationError:
        if model is not ParsedHypothesis:
            raise

    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return model.model_validate(payload)
    return model.model_validate(_coerce_legacy_parsed_hypothesis(payload))


def _coerce_legacy_parsed_hypothesis(payload: dict[str, Any]) -> dict[str, Any]:
    domain = payload.get("domain") or "Scientific hypothesis"
    scientific_system = payload.get("scientific_system")
    model_or_organism = payload.get("model_or_organism") or payload.get("organism_or_system")
    intervention = payload.get("intervention")
    comparator = payload.get("comparator")
    outcome_metric = payload.get("outcome_metric") or payload.get("outcome")
    success_threshold = payload.get("success_threshold") or payload.get("effect_size")
    mechanism = payload.get("mechanism")
    literature_query_terms = _coerce_list(payload.get("literature_query_terms"))
    protocol_query_terms = _coerce_list(payload.get("protocol_query_terms"))
    supplier_material_query_terms = _coerce_list(payload.get("supplier_material_query_terms"))
    key_terms = _coerce_list(payload.get("key_terms"))

    if not literature_query_terms and key_terms:
        literature_query_terms = key_terms[:6]

    derived_key_terms = _dedupe_terms(
        [
            *literature_query_terms,
            *protocol_query_terms,
            *supplier_material_query_terms,
            *key_terms,
        ]
    )

    return {
        **payload,
        "domain_route": payload.get("domain_route") or _infer_legacy_domain_route(payload),
        "scientific_system": scientific_system or domain,
        "model_or_organism": model_or_organism,
        "intervention": intervention,
        "comparator": comparator,
        "outcome_metric": outcome_metric,
        "success_threshold": success_threshold,
        "mechanism": mechanism,
        "literature_query_terms": literature_query_terms,
        "protocol_query_terms": protocol_query_terms,
        "supplier_material_query_terms": supplier_material_query_terms,
        "key_terms": derived_key_terms,
        "safety_notes": _coerce_list(payload.get("safety_notes")),
    }


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _dedupe_terms(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped[:12]


def _infer_legacy_domain_route(payload: dict[str, Any]) -> DomainRoute:
    hints = " ".join(
        str(value)
        for value in [
            payload.get("domain"),
            payload.get("original_text"),
            payload.get("scientific_system"),
            payload.get("organism_or_system"),
            payload.get("model_or_organism"),
            payload.get("intervention"),
            payload.get("outcome"),
            payload.get("mechanism"),
        ]
        if value
    ).lower()

    if any(token in hints for token in ["sporomusa", "bioelectrochemical", "electrosynthesis", "cathode", "co2", "acetate"]):
        return DomainRoute.microbial_electrochemistry
    if any(token in hints for token in ["crp", "biosensor", "diagnostic", "whole blood", "electrochemical"]):
        return DomainRoute.diagnostics_biosensor
    if any(token in hints for token in ["lactobacillus", "c57bl/6", "mouse", "mice", "fitc", "gut"]):
        return DomainRoute.animal_gut_health
    return DomainRoute.cell_biology
