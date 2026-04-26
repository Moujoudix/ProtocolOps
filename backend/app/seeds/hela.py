from app.models.schemas import (
    BudgetSummary,
    EvidenceSource,
    EvidenceType,
    ExperimentPlan,
    ExperimentPlanSection,
    LiteratureQC,
    MaterialItem,
    NoveltySignal,
    ParsedHypothesis,
    ProtocolStep,
    now_utc,
)


def is_hela_trehalose_hypothesis(text: str, preset_id: str | None = None) -> bool:
    lowered = text.lower()
    return preset_id == "hela-trehalose" or (
        "hela" in lowered and "trehalose" in lowered and ("dmso" in lowered or "cryoprotect" in lowered)
    )


def seeded_hela_sources() -> list[EvidenceSource]:
    retrieved_at = now_utc()
    return [
        EvidenceSource(
            id="seed-lit-trehalose-cryoprotection",
            source_name="Seeded literature evidence",
            title="Trehalose as an adjacent cryoprotection and membrane-stabilization evidence source",
            url=None,
            evidence_type=EvidenceType.adjacent_evidence,
            snippet=(
                "Adjacent literature supports trehalose as a cryoprotection-relevant disaccharide and "
                "membrane stabilizer, but this seed does not establish an exact HeLa head-to-head result."
            ),
            authors=[],
            year=None,
            doi=None,
            confidence=0.72,
            retrieved_at=retrieved_at,
        ),
        EvidenceSource(
            id="seed-atcc-hela-culture",
            source_name="ATCC",
            title="ATCC HeLa cell information page",
            url="https://www.atcc.org/products/ccl-2",
            evidence_type=EvidenceType.supplier_evidence,
            snippet=(
                "Supplier context for the HeLa cell model. Catalog and ordering fields are not copied into "
                "the plan unless directly retrieved by a live provider."
            ),
            authors=[],
            year=None,
            doi=None,
            confidence=0.74,
            retrieved_at=retrieved_at,
        ),
        EvidenceSource(
            id="seed-thermo-cryopreservation",
            source_name="Thermo Fisher Scientific",
            title="Cell culture cryopreservation guidance",
            url="https://www.thermofisher.com/us/en/home/references/gibco-cell-culture-basics/cell-culture-protocols/freezing-cells.html",
            evidence_type=EvidenceType.generic_protocol_evidence,
            snippet=(
                "Generic mammalian cell freezing guidance supports using an established controlled freezing "
                "and thawing workflow as the comparator protocol backbone."
            ),
            authors=[],
            year=None,
            doi=None,
            confidence=0.78,
            retrieved_at=retrieved_at,
        ),
        EvidenceSource(
            id="seed-promega-viability",
            source_name="Promega",
            title="Cell viability assay overview",
            url="https://www.promega.com/resources/guides/cell-biology/cell-viability-assays/",
            evidence_type=EvidenceType.supplier_evidence,
            snippet=(
                "Supplier evidence for common cell viability assay options that can quantify post-thaw "
                "viability as an endpoint."
            ),
            authors=[],
            year=None,
            doi=None,
            confidence=0.73,
            retrieved_at=retrieved_at,
        ),
        EvidenceSource(
            id="seed-sigma-trehalose",
            source_name="Sigma-Aldrich",
            title="Trehalose supplier context",
            url="https://www.sigmaaldrich.com/US/en/search/trehalose",
            evidence_type=EvidenceType.supplier_evidence,
            snippet=(
                "Supplier context indicates trehalose is commercially available; exact catalog numbers and "
                "prices must be checked live before procurement."
            ),
            authors=[],
            year=None,
            doi=None,
            confidence=0.66,
            retrieved_at=retrieved_at,
        ),
        EvidenceSource(
            id="seed-assumption-expert-review",
            source_name="MVP assumption",
            title="Experimental design assumptions requiring scientist review",
            url=None,
            evidence_type=EvidenceType.assumption,
            snippet=(
                "Treatment concentrations, freeze/thaw parameters, replicate count, and acceptance criteria "
                "must be approved by a qualified scientist before lab execution."
            ),
            authors=[],
            year=None,
            doi=None,
            confidence=0.45,
            retrieved_at=retrieved_at,
        ),
    ]


def seeded_hela_parsed(hypothesis: str) -> ParsedHypothesis:
    return ParsedHypothesis(
        original_text=hypothesis,
        domain="cell biology / cryopreservation",
        organism_or_system="HeLa cells",
        intervention="trehalose-containing freezing medium",
        comparator="standard DMSO cryopreservation protocol",
        outcome="post-thaw viability increase of at least 15 percentage points",
        effect_size=">= 15 percentage points",
        mechanism="membrane stabilization at low temperatures",
        key_terms=["HeLa", "trehalose", "cryopreservation", "DMSO", "post-thaw viability"],
        safety_notes=[
            "Use authenticated, contamination-tested cell stocks and institutional biosafety practices.",
            "Treat all wet-lab details as expert-review-required before execution.",
        ],
    )


def seeded_hela_literature_qc() -> LiteratureQC:
    sources = seeded_hela_sources()
    return LiteratureQC(
        novelty_signal=NoveltySignal.similar_work_exists,
        confidence=0.71,
        references=sources[:3],
        searched_sources=["Semantic Scholar", "Europe PMC", "HeLa demo seed"],
        rationale=(
            "Searched sources indicate adjacent cryoprotection evidence for trehalose and generic HeLa or "
            "mammalian cell cryopreservation evidence. An exact HeLa trehalose-vs-standard-DMSO head-to-head "
            "claim was not confirmed in the searched sources."
        ),
        evidence_gap_warnings=[
            "Use 'not found in searched sources' rather than claiming the experiment has never been done.",
            "Exact trehalose concentration, freezing rate, thaw timing, and replicate count require expert review.",
        ],
    )


def seeded_hela_plan(parsed: ParsedHypothesis, literature_qc: LiteratureQC, live_sources: list[EvidenceSource]) -> ExperimentPlan:
    sources = merge_sources(seeded_hela_sources() + live_sources + literature_qc.references)
    source_ids = [source.id for source in sources]
    protocol_source_ids = [
        "seed-thermo-cryopreservation",
        "seed-lit-trehalose-cryoprotection",
        "seed-assumption-expert-review",
    ]
    supplier_source_ids = ["seed-atcc-hela-culture", "seed-promega-viability", "seed-sigma-trehalose"]

    materials = [
        MaterialItem(
            name="Authenticated HeLa cell stock",
            role="Experimental cell model",
            vendor="ATCC or existing authenticated lab source",
            catalog_number=None,
            price=None,
            currency=None,
            requires_procurement_check=True,
            evidence_source_ids=["seed-atcc-hela-culture"],
            notes="Confirm source, passage range, mycoplasma status, and cell-line authentication before use.",
            confidence=0.72,
        ),
        MaterialItem(
            name="Standard DMSO cryopreservation medium",
            role="Comparator arm",
            vendor=None,
            catalog_number=None,
            price=None,
            currency=None,
            requires_procurement_check=True,
            evidence_source_ids=["seed-thermo-cryopreservation"],
            notes="Use the lab's approved standard DMSO-containing freezing workflow as comparator.",
            confidence=0.7,
        ),
        MaterialItem(
            name="Trehalose",
            role="Candidate cryoprotectant",
            vendor="Sigma-Aldrich or equivalent qualified supplier",
            catalog_number=None,
            price=None,
            currency=None,
            requires_procurement_check=True,
            evidence_source_ids=["seed-sigma-trehalose", "seed-lit-trehalose-cryoprotection"],
            notes="Catalog number, grade, sterility, endotoxin status, and price require procurement check.",
            confidence=0.63,
        ),
        MaterialItem(
            name="Cell viability assay reagent or validated counting method",
            role="Post-thaw viability endpoint",
            vendor="Promega or validated lab method",
            catalog_number=None,
            price=None,
            currency=None,
            requires_procurement_check=True,
            evidence_source_ids=["seed-promega-viability"],
            notes="Select the endpoint method before execution and document linear range and acceptance criteria.",
            confidence=0.7,
        ),
        MaterialItem(
            name="Cryovials and controlled freezing workflow supplies",
            role="Freezing and storage workflow",
            vendor=None,
            catalog_number=None,
            price=None,
            currency=None,
            requires_procurement_check=True,
            evidence_source_ids=["seed-thermo-cryopreservation"],
            notes="Use validated lab equipment and storage conditions; do not infer exact equipment specs from this MVP.",
            confidence=0.68,
        ),
    ]

    return ExperimentPlan(
        plan_title="Trehalose vs DMSO HeLa Cryopreservation Review-Ready Experimental Plan",
        status_label="SOP draft for expert review",
        overview=ExperimentPlanSection(
            title="Overview",
            summary=(
                "Compare a trehalose-containing freezing strategy against the lab's standard DMSO workflow "
                "for HeLa post-thaw viability, using evidence-backed checkpoints and explicit review flags."
            ),
            bullets=[
                "Primary endpoint: post-thaw viability difference versus standard DMSO comparator.",
                "Decision threshold: investigate whether the trehalose arm improves viability by at least 15 percentage points.",
                "This is a review-ready experimental plan, not a final executable wet-lab SOP.",
            ],
            evidence_source_ids=source_ids[:3],
            confidence=0.72,
            expert_review_required=True,
        ),
        literature_qc=literature_qc,
        study_design=ExperimentPlanSection(
            title="Study Design",
            summary="Parallel-arm cryopreservation comparison with predefined endpoint measurement and evidence-gap tracking.",
            bullets=[
                "Use HeLa cells from the same authenticated starting stock across comparator and trehalose arms.",
                "Keep cell handling, freeze timing, thaw timing, and viability measurement consistent across arms.",
                "Predefine replicate strategy, exclusion criteria, and statistical analysis before execution.",
                "Record any deviation from the lab's standard DMSO workflow as a confounder.",
            ],
            evidence_source_ids=["seed-atcc-hela-culture", "seed-thermo-cryopreservation", "seed-assumption-expert-review"],
            confidence=0.66,
            expert_review_required=True,
        ),
        protocol=[
            ProtocolStep(
                step_number=1,
                title="Confirm evidence package and lab SOP boundaries",
                purpose="Prevent unsupported procedural details from being treated as validated instructions.",
                actions=[
                    "Review the Literature QC result and source list with a qualified scientist.",
                    "Map the comparator arm to the lab's approved DMSO cryopreservation SOP.",
                    "List all inferred trehalose-arm details that require approval before execution.",
                ],
                critical_parameters=["Approved comparator SOP", "reviewed evidence gaps", "documented acceptance criteria"],
                materials=[],
                evidence_source_ids=["seed-assumption-expert-review", "seed-thermo-cryopreservation"],
                confidence=0.74,
                expert_review_required=True,
                review_reason="The MVP evidence package does not validate exact wet-lab parameters.",
            ),
            ProtocolStep(
                step_number=2,
                title="Prepare matched HeLa cultures",
                purpose="Reduce biological and handling variability before cryopreservation.",
                actions=[
                    "Use authenticated, contamination-tested HeLa cultures from a consistent passage window.",
                    "Prepare matched cell populations for comparator and trehalose arms.",
                    "Document confluence, passage, viability baseline, and operator notes before freezing.",
                ],
                critical_parameters=["Cell authentication", "mycoplasma status", "matched starting viability"],
                materials=["Authenticated HeLa cell stock"],
                evidence_source_ids=["seed-atcc-hela-culture", "seed-assumption-expert-review"],
                confidence=0.65,
                expert_review_required=True,
                review_reason="Exact culture readiness criteria must follow the local cell-culture SOP.",
            ),
            ProtocolStep(
                step_number=3,
                title="Define cryoprotectant arms",
                purpose="Create a controlled comparison between standard DMSO and trehalose-containing conditions.",
                actions=[
                    "Assign one arm to the approved standard DMSO freezing medium.",
                    "Assign the intervention arm to a scientist-approved trehalose-containing formulation.",
                    "Do not treat trehalose concentration, osmolarity adjustment, or vehicle choice as validated unless sourced and approved.",
                ],
                critical_parameters=["DMSO comparator definition", "trehalose formulation approval", "osmolarity review"],
                materials=["Standard DMSO cryopreservation medium", "Trehalose"],
                evidence_source_ids=protocol_source_ids,
                confidence=0.58,
                expert_review_required=True,
                review_reason="Trehalose formulation details are adjacent-source-backed and require scientist approval.",
            ),
            ProtocolStep(
                step_number=4,
                title="Freeze and store matched samples",
                purpose="Apply consistent cryopreservation handling across arms.",
                actions=[
                    "Use the validated lab freezing workflow for all arms.",
                    "Keep container, fill volume, cooling approach, storage destination, and timing consistent where approved.",
                    "Capture deviations and freezer/storage metadata for traceability.",
                ],
                critical_parameters=["validated freezing workflow", "matched handling", "storage metadata"],
                materials=["Cryovials and controlled freezing workflow supplies"],
                evidence_source_ids=["seed-thermo-cryopreservation", "seed-assumption-expert-review"],
                confidence=0.64,
                expert_review_required=True,
                review_reason="Exact cooling parameters must come from the lab SOP or live retrieved protocol evidence.",
            ),
            ProtocolStep(
                step_number=5,
                title="Thaw and recover samples",
                purpose="Measure post-thaw performance without introducing arm-specific handling bias.",
                actions=[
                    "Thaw comparator and trehalose-arm samples using the same approved recovery workflow.",
                    "Apply the same wash, dilution, recovery medium, and timing rules across arms when approved.",
                    "Record immediate post-thaw observations and any sample loss.",
                ],
                critical_parameters=["matched thaw workflow", "consistent recovery window", "deviation capture"],
                materials=["Authenticated HeLa cell stock", "Standard DMSO cryopreservation medium", "Trehalose"],
                evidence_source_ids=["seed-thermo-cryopreservation", "seed-assumption-expert-review"],
                confidence=0.62,
                expert_review_required=True,
                review_reason="Thaw timing and recovery handling are procedural details requiring SOP confirmation.",
            ),
            ProtocolStep(
                step_number=6,
                title="Measure post-thaw viability",
                purpose="Quantify whether trehalose improves the primary endpoint versus comparator.",
                actions=[
                    "Use a validated cell viability assay or counting method selected before execution.",
                    "Measure comparator and trehalose samples under the same timing and assay conditions.",
                    "Preserve raw counts, assay output, normalization method, and quality-control notes.",
                ],
                critical_parameters=["validated assay method", "same measurement timing", "raw data retention"],
                materials=["Cell viability assay reagent or validated counting method"],
                evidence_source_ids=["seed-promega-viability", "seed-assumption-expert-review"],
                confidence=0.69,
                expert_review_required=True,
                review_reason="Assay selection and acceptance criteria require expert review.",
            ),
            ProtocolStep(
                step_number=7,
                title="Analyze result against threshold",
                purpose="Connect the measured endpoint back to the hypothesis claim.",
                actions=[
                    "Calculate post-thaw viability difference between trehalose and DMSO arms.",
                    "Compare the observed difference with the predefined 15 percentage-point threshold.",
                    "Classify the result as supportive, inconclusive, or not supportive with confidence and caveats.",
                ],
                critical_parameters=["predefined analysis method", "15 percentage-point threshold", "documented caveats"],
                materials=[],
                evidence_source_ids=["seed-lit-trehalose-cryoprotection", "seed-assumption-expert-review"],
                confidence=0.66,
                expert_review_required=True,
                review_reason="Statistical power and acceptance criteria must be defined before execution.",
            ),
        ],
        materials=materials,
        budget=BudgetSummary(
            title="Budget",
            summary="Exact prices are not included because supplier pricing was not retrieved in this MVP path.",
            items=materials,
            evidence_source_ids=supplier_source_ids,
            confidence=0.55,
            expert_review_required=True,
        ),
        timeline=ExperimentPlanSection(
            title="Timeline",
            summary="Plan execution should be scheduled around cell expansion, freeze/storage interval, thaw, and assay readout.",
            bullets=[
                "Stage 1: expert review, procurement check, and SOP alignment.",
                "Stage 2: cell preparation and matched freezing workflow.",
                "Stage 3: thaw, recovery, viability measurement, and analysis.",
                "Exact durations depend on approved local protocols and are not inferred here.",
            ],
            evidence_source_ids=["seed-thermo-cryopreservation", "seed-assumption-expert-review"],
            confidence=0.57,
            expert_review_required=True,
        ),
        validation=ExperimentPlanSection(
            title="Validation",
            summary="Use controls and traceability checks to decide whether the evidence supports the hypothesis.",
            bullets=[
                "Comparator control: standard DMSO cryopreservation arm.",
                "Quality checks: baseline viability, contamination status, matched handling, and raw assay traceability.",
                "Endpoint validation: viability assay suitability and linear range must be confirmed before use.",
            ],
            evidence_source_ids=["seed-promega-viability", "seed-thermo-cryopreservation", "seed-assumption-expert-review"],
            confidence=0.65,
            expert_review_required=True,
        ),
        risks=ExperimentPlanSection(
            title="Risks",
            summary="The main risk is overinterpreting adjacent evidence as a validated HeLa trehalose protocol.",
            bullets=[
                "Trehalose formulation details are not exact evidence and require expert review.",
                "Uncontrolled freeze/thaw handling differences could dominate the viability result.",
                "Supplier catalog numbers and prices require procurement verification.",
                "Cell-line status, passage, and contamination can confound the outcome.",
            ],
            evidence_source_ids=["seed-lit-trehalose-cryoprotection", "seed-atcc-hela-culture", "seed-assumption-expert-review"],
            confidence=0.68,
            expert_review_required=True,
        ),
        sources=sources,
        generated_at=now_utc(),
    )


def merge_sources(sources: list[EvidenceSource]) -> list[EvidenceSource]:
    seen: set[str] = set()
    merged: list[EvidenceSource] = []
    for source in sources:
        if source.id in seen:
            continue
        seen.add(source.id)
        merged.append(source)
    return merged

