from __future__ import annotations

from app.core.config import Settings
from app.models.schemas import (
    BudgetSummary,
    DomainRoute,
    EvidencePack,
    EvidenceSource,
    EvidenceType,
    ExperimentPlan,
    ExperimentPlanSection,
    LiteratureQC,
    MaterialItem,
    ParsedHypothesis,
    PriceStatus,
    ProcurementStatus,
    ProtocolStep,
    ReviewMemoryReference,
    TrustLevel,
    TrustTier,
    now_utc,
)
from app.seeds.hela import is_hela_trehalose_hypothesis, seeded_hela_parsed, seeded_hela_plan_from_evidence_pack
from app.services.domain_routing import domain_label_for_route, resolve_domain_route


class OpenAIStructuredClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openai_api_key)

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._client

    async def parse_hypothesis(self, hypothesis: str, preset_id: str | None = None) -> ParsedHypothesis:
        if not self.enabled:
            if self.settings.strict_live_mode:
                raise RuntimeError("OpenAI is required in strict live mode.")
            if is_hela_trehalose_hypothesis(hypothesis, preset_id):
                return seeded_hela_parsed(hypothesis)
            return heuristic_parse_hypothesis(hypothesis, preset_id=preset_id)

        try:
            response = await self._get_client().responses.parse(
                model=self.settings.openai_parse_model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Extract a scientific hypothesis into structured fields for a scientific planning app. "
                            "Keep uncertain fields null. Set domain_route to one of: cell_biology, "
                            "diagnostics_biosensor, animal_gut_health, microbial_electrochemistry. "
                            "Return separate literature_query_terms, protocol_query_terms, and "
                            "supplier_material_query_terms. Do not call or mention outside providers. "
                            "JSON must match the schema."
                        ),
                    },
                    {"role": "user", "content": hypothesis},
                ],
                text_format=ParsedHypothesis,
            )
            return normalize_parsed_hypothesis(response.output_parsed, hypothesis, preset_id)
        except Exception:
            if self.settings.strict_live_mode:
                raise RuntimeError("OpenAI structured parsing failed in strict live mode.")
            return heuristic_parse_hypothesis(hypothesis, preset_id=preset_id)

    async def generate_plan(
        self,
        parsed: ParsedHypothesis,
        literature_qc: LiteratureQC,
        evidence_pack: EvidencePack,
        preset_id: str | None = None,
        review_memory: list[ReviewMemoryReference] | None = None,
    ) -> ExperimentPlan:
        if not self.enabled:
            if self.settings.strict_live_mode:
                raise RuntimeError("OpenAI plan generation is required in strict live mode.")
            if is_hela_trehalose_hypothesis(parsed.original_text, preset_id):
                return apply_review_memory_to_plan(
                    seeded_hela_plan_from_evidence_pack(parsed, literature_qc, evidence_pack),
                    review_memory or [],
                )
            return apply_review_memory_to_plan(
                generic_review_plan(parsed, literature_qc, evidence_pack),
                review_memory or [],
            )

        prompt = build_plan_prompt(parsed, literature_qc, evidence_pack, review_memory or [])
        try:
            response = await self._get_client().responses.parse(
                model=self.settings.openai_plan_model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You generate evidence-grounded review-ready experimental plans. Never invent catalog "
                            "numbers, exact prices, concentrations, timings, or validated protocol parameters. If "
                            "a value is not directly retrieved in the evidence pack, leave nullable fields null and "
                            "mark procurement, price, or expert review checks. Every protocol step must cite "
                            "evidence source IDs and include confidence."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                text_format=ExperimentPlan,
            )
            return apply_review_memory_to_plan(
                apply_plan_guardrails(response.output_parsed, parsed, literature_qc, evidence_pack),
                review_memory or [],
            )
        except Exception:
            try:
                response = await self._get_client().responses.parse(
                    model=self.settings.openai_fallback_model,
                    input=[
                        {"role": "system", "content": "Generate the requested JSON schema conservatively."},
                        {"role": "user", "content": prompt},
                    ],
                    text_format=ExperimentPlan,
                )
                return apply_review_memory_to_plan(
                    apply_plan_guardrails(response.output_parsed, parsed, literature_qc, evidence_pack),
                    review_memory or [],
                )
            except Exception:
                if self.settings.strict_live_mode:
                    raise RuntimeError("OpenAI plan generation failed in strict live mode.")
                if is_hela_trehalose_hypothesis(parsed.original_text, preset_id):
                    return apply_review_memory_to_plan(
                        seeded_hela_plan_from_evidence_pack(parsed, literature_qc, evidence_pack),
                        review_memory or [],
                    )
                return apply_review_memory_to_plan(
                    generic_review_plan(parsed, literature_qc, evidence_pack),
                    review_memory or [],
                )


def build_plan_prompt(
    parsed: ParsedHypothesis,
    literature_qc: LiteratureQC,
    evidence_pack: EvidencePack,
    review_memory: list[ReviewMemoryReference],
) -> str:
    evidence_json = [source.model_dump(mode="json") for source in evidence_pack.sources]
    memory_json = [memory.model_dump(mode="json") for memory in review_memory]
    return (
        "Create a review-ready experimental plan for this parsed hypothesis.\n\n"
        f"Parsed hypothesis:\n{parsed.model_dump_json(indent=2)}\n\n"
        f"Literature QC:\n{literature_qc.model_dump_json(indent=2)}\n\n"
        f"Evidence pack:\n{evidence_pack.model_dump_json(indent=2)}\n\n"
        f"Evidence sources:\n{evidence_json}\n\n"
        f"Prior reviewed corrections for similar runs:\n{memory_json}\n\n"
        "Required guardrails:\n"
        "- Use 'not found in searched sources'; do not say a hypothesis has never been done.\n"
        "- Distinguish exact_match, close_match, adjacent_method, generic_method, supplier_reference, safety_or_standard, and assumption evidence.\n"
        "- Treat trust_tier as provenance and trust_level as high, medium, or low.\n"
        "- Every protocol step needs evidence_source_ids, confidence, and expert_review_required.\n"
        "- Leave catalog_number, price, and currency null unless directly retrieved.\n"
        "- Use procurement_status and price_status conservatively.\n"
        "- Use 'review-ready experimental plan' or 'SOP draft for expert review'.\n"
        f"- Domain-specific implementation notes for {parsed.domain_route.value}: {domain_specific_generation_notes(parsed.domain_route)}\n"
        "- If prior reviewed corrections exist, prefer them over generic assumptions and mention them in the plan only when relevant.\n"
    )


def heuristic_parse_hypothesis(hypothesis: str, preset_id: str | None = None) -> ParsedHypothesis:
    domain_route = resolve_domain_route(hypothesis, preset_id)
    model_or_organism = _first_present(
        hypothesis,
        ["HeLa cells", "whole blood", "C57BL/6 mice", "Sporomusa ovata", "Lactobacillus rhamnosus GG"],
    )
    outcome_metric = _first_present(
        hypothesis,
        ["post-thaw viability", "C-reactive protein", "intestinal permeability", "acetate", "CO2 into acetate"],
    )
    return ParsedHypothesis(
        original_text=hypothesis,
        domain=domain_label_for_route(domain_route),
        domain_route=domain_route,
        scientific_system=_default_scientific_system(domain_route),
        model_or_organism=model_or_organism,
        intervention=_phrase_after(hypothesis, ["Replacing", "Supplementing", "Introducing", "functionalized with"]),
        comparator=_phrase_after(hypothesis, ["compared to", "matching", "outperforming"]),
        outcome_metric=outcome_metric,
        success_threshold=_first_present(hypothesis, ["15 percentage points", "0.5 mg/L", "30%", "150 mmol/L/day", "20%"]),
        mechanism=_phrase_after(hypothesis, ["due to"]),
        literature_query_terms=derive_query_terms(hypothesis, domain_route, "literature"),
        protocol_query_terms=derive_query_terms(hypothesis, domain_route, "protocol"),
        supplier_material_query_terms=derive_query_terms(hypothesis, domain_route, "supplier"),
        safety_notes=["Review all inferred wet-lab details with a qualified scientist before execution."],
    )


def derive_query_terms(text: str, domain_route: DomainRoute, stage: str) -> list[str]:
    important = [
        "HeLa",
        "trehalose",
        "DMSO",
        "cryopreservation",
        "CRP",
        "biosensor",
        "whole blood",
        "Lactobacillus rhamnosus GG",
        "C57BL/6",
        "FITC-dextran",
        "Sporomusa ovata",
        "bioelectrochemical",
        "CO2",
        "acetate",
    ]
    lowered = text.lower()
    terms = [term for term in important if term.lower() in lowered]
    if stage == "protocol":
        defaults = {
            DomainRoute.cell_biology: ["cell freezing", "cryopreservation", "post-thaw viability"],
            DomainRoute.diagnostics_biosensor: ["electrochemical biosensor", "CRP assay", "antibody functionalization"],
            DomainRoute.animal_gut_health: ["FITC-dextran assay", "gut permeability", "Lactobacillus culture"],
            DomainRoute.microbial_electrochemistry: ["microbial electrosynthesis", "anaerobic culture", "acetate quantification"],
        }
        terms.extend(defaults[domain_route])
    if stage == "supplier":
        defaults = {
            DomainRoute.cell_biology: ["ATCC CCL-2", "trehalose", "CellTiter-Glo"],
            DomainRoute.diagnostics_biosensor: ["anti-CRP antibody", "CRP ELISA kit"],
            DomainRoute.animal_gut_health: ["Lactobacillus rhamnosus GG"],
            DomainRoute.microbial_electrochemistry: ["reactor materials", "anaerobic supplies"],
        }
        terms.extend(defaults[domain_route])
    if terms:
        return dedupe_terms(terms)[:8]
    return [word.strip(".,;:()") for word in text.split()[:8] if len(word.strip(".,;:()")) > 3]


def _first_present(text: str, options: list[str]) -> str | None:
    lowered = text.lower()
    for option in options:
        if option.lower() in lowered:
            return option
    return None


def _phrase_after(text: str, markers: list[str]) -> str | None:
    lowered = text.lower()
    for marker in markers:
        idx = lowered.find(marker.lower())
        if idx >= 0:
            phrase = text[idx + len(marker) :].strip(" .,:;")
            return phrase[:160] if phrase else None
    return None


def normalize_parsed_hypothesis(
    parsed: ParsedHypothesis,
    hypothesis: str,
    preset_id: str | None,
) -> ParsedHypothesis:
    domain_route = resolve_domain_route(hypothesis, preset_id) if preset_id else parsed.domain_route
    domain = domain_label_for_route(domain_route) if preset_id else (parsed.domain or domain_label_for_route(domain_route))
    return parsed.model_copy(
        update={
            "domain_route": domain_route,
            "domain": domain,
            "scientific_system": parsed.scientific_system or _default_scientific_system(domain_route),
            "literature_query_terms": dedupe_terms(parsed.literature_query_terms),
            "protocol_query_terms": dedupe_terms(parsed.protocol_query_terms),
            "supplier_material_query_terms": dedupe_terms(parsed.supplier_material_query_terms),
        }
    )


def _default_scientific_system(domain_route: DomainRoute) -> str:
    labels = {
        DomainRoute.cell_biology: "mammalian cell cryopreservation",
        DomainRoute.diagnostics_biosensor: "diagnostic biosensor assay development",
        DomainRoute.animal_gut_health: "mouse gut permeability study",
        DomainRoute.microbial_electrochemistry: "microbial electrosynthesis system",
    }
    return labels[domain_route]


def dedupe_terms(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped


def domain_specific_generation_notes(domain_route: DomainRoute) -> str:
    notes = {
        DomainRoute.cell_biology: (
            "Prefer supplier-backed HeLa, cryopreservation, and viability assay evidence. "
            "Do not invent freeze rates, trehalose concentrations, or thaw timings."
        ),
        DomainRoute.diagnostics_biosensor: (
            "Prefer literature methods, assay comparators, and supplier antibody or ELISA evidence. "
            "Do not overstate device performance without source-backed validation."
        ),
        DomainRoute.animal_gut_health: (
            "Use ARRIVE and ethics-aware language. "
            "Do not invent dosing, housing, gavage, FITC-dextran dose, sample size, or euthanasia details."
        ),
        DomainRoute.microbial_electrochemistry: (
            "Require source backing for reactor design, cathode potential, anaerobic handling, CO2 delivery, and acetate benchmarks."
        ),
    }
    return notes[domain_route]


def apply_review_memory_to_plan(
    plan: ExperimentPlan,
    review_memory: list[ReviewMemoryReference],
) -> ExperimentPlan:
    if not review_memory:
        return plan

    updated = plan.model_copy(deep=True)
    for memory in review_memory:
        note = memory.note.strip()
        replacement = note if memory.action.value == "comment" else note

        if memory.target_type.value == "material":
            target = find_material(updated.materials, memory.target_key)
            if target is not None:
                target.notes = merge_note(target.notes, note)
                if memory.action.value in {"replace", "edit"}:
                    target.notes = merge_note(target.notes, f"Preferred reviewed adjustment: {note}")
                if memory.confidence is not None:
                    target.confidence = memory.confidence
                continue

        if memory.target_type.value == "budget_item":
            target = find_material(updated.budget.items, memory.target_key)
            if target is not None:
                target.notes = merge_note(target.notes, note)
                if memory.confidence is not None:
                    target.confidence = memory.confidence
                continue

        if memory.target_type.value == "protocol_step":
            target = find_protocol_step(updated.protocol, memory.target_key)
            if target is not None:
                target.actions.append(f"Scientist-reviewed adjustment: {note}")
                target.review_reason = merge_note(target.review_reason or "", note)
                target.expert_review_required = True
                if memory.confidence is not None:
                    target.confidence = memory.confidence
                continue

        target_section = find_section(updated, memory.target_type.value, memory.target_key)
        if target_section is not None:
            target_section.bullets.append(f"Scientist-reviewed adjustment: {replacement}")
            target_section.expert_review_required = True
            if memory.confidence is not None:
                target_section.confidence = memory.confidence
            continue

        updated.risks.bullets.append(f"Scientist review note for {memory.target_type.value} '{memory.target_key}': {note}")
        updated.risks.expert_review_required = True

    if review_memory:
        updated.status_label = "Scientist-reviewed revision for expert review"
    return updated


def find_material(items: list[MaterialItem], target_key: str) -> MaterialItem | None:
    target = target_key.strip().lower()
    for item in items:
        if target and (target == item.name.lower() or target in item.name.lower()):
            return item
    return None


def find_protocol_step(steps: list[ProtocolStep], target_key: str) -> ProtocolStep | None:
    target = target_key.strip().lower()
    for step in steps:
        if target == str(step.step_number) or target == step.title.lower() or target in step.title.lower():
            return step
    return None


def find_section(plan: ExperimentPlan, target_type: str, target_key: str) -> ExperimentPlanSection | None:
    section_map = {
        "section": {
            "overview": plan.overview,
            "study_design": plan.study_design,
            "timeline": plan.timeline,
            "validation": plan.validation,
            "risk": plan.risks,
            "risks": plan.risks,
        },
        "timeline": {"timeline": plan.timeline},
        "validation": {"validation": plan.validation},
        "risk": {"risk": plan.risks, "risks": plan.risks},
    }
    bucket = section_map.get(target_type, {})
    key = target_key.strip().lower()
    return bucket.get(key) or bucket.get(target_type)


def merge_note(existing: str, addition: str) -> str:
    existing_clean = existing.strip()
    addition_clean = addition.strip()
    if not existing_clean:
        return addition_clean
    if addition_clean in existing_clean:
        return existing_clean
    return f"{existing_clean} Scientist review: {addition_clean}"


def generic_review_plan(
    parsed: ParsedHypothesis,
    literature_qc: LiteratureQC,
    evidence_pack: EvidencePack,
) -> ExperimentPlan:
    sources = evidence_pack.sources or literature_qc.references
    if not sources:
        sources = [
            EvidenceSource(
                id="assumption-no-live-evidence",
                source_name="MVP assumption",
                title="No live provider evidence returned",
                url=None,
                evidence_type=EvidenceType.assumption,
                trust_tier=TrustTier.inferred,
                trust_level=TrustLevel.low,
                snippet="The plan is intentionally high-level because searched providers returned no usable evidence.",
                authors=[],
                year=None,
                doi=None,
                confidence=0.25,
                retrieved_at=now_utc(),
            )
        ]
    source_ids = [source.id for source in sources]
    assumption_id = source_ids[-1]

    materials = [
        MaterialItem(
            name="Domain-specific biological or assay model",
            role="Experimental system",
            vendor=None,
            catalog_number=None,
            price=None,
            currency=None,
            procurement_status=ProcurementStatus.requires_procurement_check,
            price_status=PriceStatus.requires_procurement_check,
            evidence_source_ids=[assumption_id],
            notes="Exact model sourcing must be checked by a scientist or procurement owner.",
            confidence=0.35,
        ),
        MaterialItem(
            name="Comparator or control materials",
            role="Control arm",
            vendor=None,
            catalog_number=None,
            price=None,
            currency=None,
            procurement_status=ProcurementStatus.requires_procurement_check,
            price_status=PriceStatus.requires_procurement_check,
            evidence_source_ids=[assumption_id],
            notes="Comparator materials are hypothesis-dependent and not finalized by this MVP.",
            confidence=0.32,
        ),
        MaterialItem(
            name="Endpoint measurement reagents or instrumentation",
            role="Outcome measurement",
            vendor=None,
            catalog_number=None,
            price=None,
            currency=None,
            procurement_status=ProcurementStatus.requires_procurement_check,
            price_status=PriceStatus.requires_procurement_check,
            evidence_source_ids=[assumption_id],
            notes="Assay choice, validation range, and procurement details require expert review.",
            confidence=0.32,
        ),
    ]

    return ExperimentPlan(
        plan_title=f"{parsed.domain.title()} Review-Ready Experimental Plan",
        status_label="SOP draft for expert review",
        overview=ExperimentPlanSection(
            title="Overview",
            summary="Best-effort review-ready plan generated from available evidence and explicit assumptions.",
            bullets=[
                f"Hypothesis: {parsed.original_text}",
                "Use this as a scoping document, not as a final executable wet-lab SOP.",
                "Low-confidence fields must be resolved through source review and scientist sign-off.",
            ],
            evidence_source_ids=[source_ids[0]],
            confidence=0.42,
            expert_review_required=True,
        ),
        literature_qc=literature_qc,
        study_design=ExperimentPlanSection(
            title="Study Design",
            summary="Define treatment, comparator, endpoint, and analysis criteria before execution.",
            bullets=[
                "Confirm the experimental system and inclusion criteria.",
                "Define comparator and treatment arms with source-backed parameters only.",
                "Predefine endpoint measurement, quality controls, and analysis thresholds.",
            ],
            evidence_source_ids=[source_ids[0]],
            confidence=0.4,
            expert_review_required=True,
        ),
        protocol=[
            ProtocolStep(
                step_number=1,
                title="Evidence review and design lock",
                purpose="Separate source-backed details from assumptions before laboratory planning.",
                actions=[
                    "Review Literature QC references, provider trace, and evidence gaps.",
                    "Map source-backed details to the proposed design.",
                    "Flag all inferred details for expert review.",
                ],
                critical_parameters=["evidence source IDs", "expert-review flags", "accepted comparator definition"],
                materials=[],
                evidence_source_ids=[source_ids[0]],
                confidence=0.45,
                expert_review_required=True,
                review_reason="Non-HeLa presets are best-effort paths with limited seeded evidence.",
            ),
            ProtocolStep(
                step_number=2,
                title="Prepare experimental and control arms",
                purpose="Create matched conditions for a hypothesis test.",
                actions=[
                    "Prepare treatment and comparator arms using only approved source-backed parameters.",
                    "Keep handling, timing, and measurement conditions consistent across arms.",
                    "Document any assumption or deviation before execution.",
                ],
                critical_parameters=["matched handling", "approved parameters", "deviation log"],
                materials=[item.name for item in materials[:2]],
                evidence_source_ids=[assumption_id],
                confidence=0.32,
                expert_review_required=True,
                review_reason="Specific wet-lab parameters were not retrieved with enough confidence.",
            ),
            ProtocolStep(
                step_number=3,
                title="Measure endpoint and classify result",
                purpose="Connect experimental output to the hypothesis claim.",
                actions=[
                    "Use a validated endpoint method selected during expert review.",
                    "Capture raw data, quality controls, and uncertainty.",
                    "Classify the result as supportive, inconclusive, or not supportive.",
                ],
                critical_parameters=["validated endpoint", "raw data retention", "predefined analysis threshold"],
                materials=[materials[2].name],
                evidence_source_ids=[assumption_id],
                confidence=0.33,
                expert_review_required=True,
                review_reason="Endpoint method and acceptance criteria require scientist approval.",
            ),
        ],
        materials=materials,
        budget=BudgetSummary(
            title="Budget",
            summary="Catalog numbers and exact prices were not retrieved; all items require procurement check.",
            items=materials,
            evidence_source_ids=[assumption_id],
            confidence=0.28,
            expert_review_required=True,
        ),
        timeline=ExperimentPlanSection(
            title="Timeline",
            summary="Schedule depends on approved protocol parameters and material availability.",
            bullets=["Evidence review", "Procurement check", "Pilot execution", "Endpoint analysis"],
            evidence_source_ids=[assumption_id],
            confidence=0.3,
            expert_review_required=True,
        ),
        validation=ExperimentPlanSection(
            title="Validation",
            summary="Validation should focus on controls, endpoint suitability, and traceability.",
            bullets=[
                "Confirm comparator and negative/positive controls.",
                "Validate endpoint range and quality criteria.",
                "Retain raw data and evidence links per section.",
            ],
            evidence_source_ids=[assumption_id],
            confidence=0.34,
            expert_review_required=True,
        ),
        risks=ExperimentPlanSection(
            title="Risks",
            summary="Main risks are weak evidence depth and inferred protocol details.",
            bullets=[
                "Provider searches may miss exact prior work.",
                "Protocol details are not validated unless source-backed.",
                "Procurement and price fields require manual checks.",
            ],
            evidence_source_ids=[assumption_id],
            confidence=0.38,
            expert_review_required=True,
        ),
        sources=sources,
        generated_at=now_utc(),
    )


def apply_plan_guardrails(
    plan: ExperimentPlan,
    parsed: ParsedHypothesis,
    literature_qc: LiteratureQC,
    evidence_pack: EvidencePack,
) -> ExperimentPlan:
    known_sources = evidence_pack.sources or literature_qc.references
    if not known_sources:
        known_sources = [
            EvidenceSource(
                id="assumption-no-live-evidence",
                source_name="MVP assumption",
                title="No live provider evidence returned",
                url=None,
                evidence_type=EvidenceType.assumption,
                trust_tier=TrustTier.inferred,
                trust_level=TrustLevel.low,
                snippet="The plan is intentionally conservative because the evidence pack was empty.",
                authors=[],
                year=None,
                doi=None,
                confidence=0.25,
                retrieved_at=now_utc(),
            )
        ]
    known_source_ids = {source.id for source in known_sources}
    fallback_id = next((source.id for source in known_sources if source.trust_tier == TrustTier.inferred), None)
    if fallback_id is None and known_sources:
        fallback_id = known_sources[-1].id

    def sanitize_ids(source_ids: list[str]) -> list[str]:
        valid = [source_id for source_id in source_ids if source_id in known_source_ids]
        if valid:
            return valid
        return [fallback_id] if fallback_id else source_ids

    plan.overview.evidence_source_ids = sanitize_ids(plan.overview.evidence_source_ids)
    plan.study_design.evidence_source_ids = sanitize_ids(plan.study_design.evidence_source_ids)
    plan.timeline.evidence_source_ids = sanitize_ids(plan.timeline.evidence_source_ids)
    plan.validation.evidence_source_ids = sanitize_ids(plan.validation.evidence_source_ids)
    plan.risks.evidence_source_ids = sanitize_ids(plan.risks.evidence_source_ids)

    has_protocol_support = has_retrieved_protocol_support(evidence_pack)
    normalized_protocol: list[ProtocolStep] = []
    for step in plan.protocol:
        step.evidence_source_ids = sanitize_ids(step.evidence_source_ids)
        if parsed.domain_route != DomainRoute.cell_biology and not has_protocol_support:
            step.confidence = min(step.confidence, 0.45)
            step.expert_review_required = True
            if not step.review_reason:
                step.review_reason = "Protocol evidence is limited for this preset and requires expert review."
        step = apply_domain_specific_protocol_guardrails(step, parsed, known_sources)
        normalized_protocol.append(ProtocolStep.model_validate(step.model_dump()))

    normalized_materials: list[MaterialItem] = []
    for material in plan.materials:
        material.evidence_source_ids = sanitize_ids(material.evidence_source_ids)
        normalized_materials.append(MaterialItem.model_validate(material.model_dump()))

    normalized_budget_items: list[MaterialItem] = []
    for item in plan.budget.items:
        item.evidence_source_ids = sanitize_ids(item.evidence_source_ids)
        normalized_budget_items.append(MaterialItem.model_validate(item.model_dump()))

    plan.protocol = normalized_protocol
    plan.materials = normalized_materials
    plan.budget.items = normalized_budget_items
    plan.budget.evidence_source_ids = sanitize_ids(plan.budget.evidence_source_ids)
    plan.literature_qc = literature_qc
    plan.sources = known_sources
    return ExperimentPlan.model_validate(plan.model_dump())


def has_retrieved_protocol_support(evidence_pack: EvidencePack) -> bool:
    for source in evidence_pack.sources:
        if source.trust_tier == TrustTier.inferred:
            continue
        if source.evidence_type in {
            EvidenceType.exact_match,
            EvidenceType.close_match,
            EvidenceType.adjacent_method,
            EvidenceType.generic_method,
        }:
            return True
    return False


def apply_domain_specific_protocol_guardrails(
    step: ProtocolStep,
    parsed: ParsedHypothesis,
    known_sources: list[EvidenceSource],
) -> ProtocolStep:
    supported_ids = {source.id for source in known_sources if source.trust_tier != TrustTier.inferred}
    has_supported_source = any(source_id in supported_ids for source_id in step.evidence_source_ids)
    joined_text = " ".join([step.title, step.purpose, *step.actions, *step.critical_parameters]).lower()

    if parsed.domain_route == DomainRoute.animal_gut_health and any(
        token in joined_text for token in ["dose", "housing", "gavage", "fitc-dextran", "sample size", "euthanasia"]
    ) and not has_supported_source:
        step.expert_review_required = True
        step.confidence = min(step.confidence, 0.4)
        step.review_reason = "Animal dosing, housing, gavage, FITC-dextran, sample-size, and euthanasia details must be source-backed."

    if parsed.domain_route == DomainRoute.microbial_electrochemistry and any(
        token in joined_text for token in ["cathode potential", "reactor", "co2", "anaerobic", "acetate", "benchmark"]
    ) and not has_supported_source:
        step.expert_review_required = True
        step.confidence = min(step.confidence, 0.4)
        step.review_reason = "Cathode potential, reactor design, CO2 delivery, anaerobic handling, acetate quantification, and benchmarks must be source-backed."

    return step
