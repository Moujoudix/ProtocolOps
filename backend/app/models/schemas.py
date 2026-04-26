from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class RunStateResponse(StrictModel):
    run_id: str
    hypothesis: str
    preset_id: str | None
    status: str
    parsed_hypothesis: ParsedHypothesis | None
    literature_qc: LiteratureQC | None
    plan: ExperimentPlan | None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def model_from_json(model: type[BaseModel], raw: str | None) -> Any:
    if raw is None:
        return None
    return model.model_validate_json(raw)
