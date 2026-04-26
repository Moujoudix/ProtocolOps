from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceType(StrEnum):
    exact_evidence = "exact_evidence"
    adjacent_evidence = "adjacent_evidence"
    generic_protocol_evidence = "generic_protocol_evidence"
    supplier_evidence = "supplier_evidence"
    assumption = "assumption"


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
    organism_or_system: str | None
    intervention: str | None
    comparator: str | None
    outcome: str | None
    effect_size: str | None
    mechanism: str | None
    key_terms: list[str]
    safety_notes: list[str]


class EvidenceSource(StrictModel):
    id: str
    source_name: str
    title: str
    url: str | None
    evidence_type: EvidenceType
    snippet: str
    authors: list[str]
    year: int | None
    doi: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    retrieved_at: datetime


class LiteratureQC(StrictModel):
    novelty_signal: NoveltySignal
    confidence: float = Field(ge=0.0, le=1.0)
    references: list[EvidenceSource] = Field(max_length=3)
    searched_sources: list[str]
    rationale: str
    evidence_gap_warnings: list[str]


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
    requires_procurement_check: bool
    evidence_source_ids: list[str] = Field(min_length=1)
    notes: str
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def enforce_procurement_check(self) -> "MaterialItem":
        if self.catalog_number is None or self.price is None:
            self.requires_procurement_check = True
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

