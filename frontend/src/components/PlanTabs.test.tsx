import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PlanTabs } from "./PlanTabs";

const parsedHypothesis = {
  original_text: "HeLa cells with trehalose versus DMSO.",
  domain: "cell biology",
  domain_route: "cell_biology" as const,
  scientific_system: "mammalian cell cryopreservation",
  model_or_organism: "HeLa cells",
  organism_or_system: "HeLa cells",
  intervention: "trehalose",
  comparator: "DMSO",
  outcome_metric: "post-thaw viability",
  success_threshold: "15 percentage points",
  outcome: "post-thaw viability",
  effect_size: "15 percentage points",
  mechanism: "membrane stabilization",
  literature_query_terms: ["trehalose HeLa cryopreservation viability DMSO"],
  protocol_query_terms: ["cell freezing", "cell thawing"],
  supplier_material_query_terms: ["ATCC CCL-2", "trehalose product page"],
  key_terms: ["HeLa", "trehalose"],
  safety_notes: [],
};

const plan = {
  plan_title: "Trehalose vs DMSO HeLa Cryopreservation Review-Ready Experimental Plan",
  status_label: "SOP draft for expert review",
  quality_summary: {
    literature_confidence: 0.66,
    protocol_confidence: 0.4,
    materials_confidence: 0.72,
    budget_confidence: 0.55,
    evidence_completeness: 0.64,
    operational_readiness: 0.58,
    review_burden: 0.72,
  },
  memory_applied: [
    {
      run_id: "run-previous",
      review_session_id: "review-1",
      target_type: "protocol_step" as const,
      target_key: "protocol.1",
      action: "comment" as const,
      note: "Reduce confidence when protocol detail is only community-backed.",
      confidence: 0.76,
    },
  ],
  overview: {
    title: "Overview",
    summary: "Overview summary",
    bullets: ["Primary endpoint", "Secondary note"],
    evidence_source_ids: ["source-backed", "adjacent", "community", "inferred"],
    confidence: 0.72,
    expert_review_required: true,
  },
  literature_qc: {
    novelty_signal: "similar_work_exists" as const,
    confidence: 0.66,
    references: [
      {
        id: "adjacent",
        source_name: "Semantic Scholar",
        title: "Adjacent trehalose evidence",
        url: "https://example.com/adjacent",
        evidence_type: "adjacent_method" as const,
        trust_tier: "literature_database" as const,
        trust_level: "medium" as const,
        snippet: "Adjacent evidence snippet",
        authors: [],
        year: 2024,
        doi: null,
        confidence: 0.66,
        retrieved_at: "2026-04-26T00:00:00Z",
      },
    ],
    literature_sources: [],
    searched_sources: ["Semantic Scholar", "Europe PMC"],
    provider_trace: [
      {
        provider: "Consensus",
        attempted: true,
        succeeded: false,
        cached: false,
        query: "trehalose HeLa cryopreservation viability DMSO",
        result_count: 0,
        error: "Consensus bridge unavailable",
      },
    ],
    rationale: "Similar work exists.",
    literature_synthesis: "Top references indicate adjacent trehalose cryopreservation evidence.",
    gaps: ["Exact protocol still needs expert review."],
    evidence_gap_warnings: ["Exact protocol still needs expert review."],
  },
  study_design: {
    title: "Study Design",
    summary: "Study design summary",
    bullets: ["Matched starting populations"],
    evidence_source_ids: ["source-backed"],
    confidence: 0.6,
    expert_review_required: true,
  },
  protocol: [
    {
      step_number: 1,
      title: "Prepare samples",
      purpose: "Step purpose",
      actions: ["Do the thing"],
      critical_parameters: ["Parameter A"],
      materials: ["ATCC HeLa cell stock"],
      evidence_source_ids: ["community", "inferred"],
      confidence: 0.4,
      expert_review_required: true,
      review_reason: "Protocol detail requires expert review.",
    },
  ],
  materials: [
    {
      name: "ATCC HeLa cell stock",
      role: "Cell model",
      vendor: "ATCC",
      catalog_number: "CCL-2",
      price: null,
      currency: null,
      procurement_status: "verified" as const,
      price_status: "contact_supplier" as const,
      requires_procurement_check: true,
      evidence_source_ids: ["source-backed"],
      notes: "Validated source-backed catalog number.",
      confidence: 0.8,
    },
    {
      name: "Trehalose",
      role: "Candidate cryoprotectant",
      vendor: "Sigma-Aldrich",
      catalog_number: null,
      price: null,
      currency: null,
      procurement_status: "requires_procurement_check" as const,
      price_status: "contact_supplier" as const,
      requires_procurement_check: true,
      evidence_source_ids: ["source-backed"],
      notes: "Catalog number not validated.",
      confidence: 0.63,
    },
  ],
  budget: {
    title: "Budget",
    summary: "Budget summary",
    items: [
      {
        name: "Trehalose",
        role: "Candidate cryoprotectant",
        vendor: "Sigma-Aldrich",
        catalog_number: null,
        price: null,
        currency: null,
        procurement_status: "requires_procurement_check" as const,
        price_status: "contact_supplier" as const,
        requires_procurement_check: true,
        evidence_source_ids: ["source-backed"],
        notes: "Contact supplier.",
        confidence: 0.63,
      },
    ],
    evidence_source_ids: ["source-backed"],
    confidence: 0.55,
    expert_review_required: true,
  },
  timeline: {
    title: "Timeline",
    summary: "Timeline summary",
    bullets: ["Review", "Run"],
    evidence_source_ids: ["community"],
    confidence: 0.5,
    expert_review_required: true,
  },
  validation: {
    title: "Validation",
    summary: "Validation summary",
    bullets: ["Use controls"],
    evidence_source_ids: ["source-backed"],
    confidence: 0.6,
    expert_review_required: true,
  },
  risks: {
    title: "Risks",
    summary: "Risk summary",
    bullets: ["May fail"],
    evidence_source_ids: ["inferred"],
    confidence: 0.5,
    expert_review_required: true,
  },
  sources: [
    {
      id: "source-backed",
      source_name: "ATCC",
      title: "ATCC HeLa cell line product page (CCL-2)",
      url: "https://example.com/atcc",
      evidence_type: "supplier_reference" as const,
      trust_tier: "supplier_documentation" as const,
      trust_level: "high" as const,
      snippet: "Supplier documentation",
      authors: [],
      year: null,
      doi: null,
      confidence: 0.8,
      retrieved_at: "2026-04-26T00:00:00Z",
    },
    {
      id: "adjacent",
      source_name: "Semantic Scholar",
      title: "Adjacent trehalose evidence",
      url: "https://example.com/adjacent",
      evidence_type: "adjacent_method" as const,
      trust_tier: "literature_database" as const,
      trust_level: "medium" as const,
      snippet: "Adjacent evidence snippet",
      authors: [],
      year: 2024,
      doi: null,
      confidence: 0.66,
      retrieved_at: "2026-04-26T00:00:00Z",
    },
    {
      id: "community",
      source_name: "protocols.io fallback",
      title: "Community cryopreservation protocol scaffold",
      url: "https://example.com/protocols",
      evidence_type: "generic_method" as const,
      trust_tier: "community_protocol" as const,
      trust_level: "low" as const,
      snippet: "Community scaffold",
      authors: [],
      year: null,
      doi: null,
      confidence: 0.51,
      retrieved_at: "2026-04-26T00:00:00Z",
    },
    {
      id: "inferred",
      source_name: "MVP assumption",
      title: "Experimental design assumptions requiring scientist review",
      url: null,
      evidence_type: "assumption" as const,
      trust_tier: "inferred" as const,
      trust_level: "low" as const,
      snippet: "Expert review required",
      authors: [],
      year: null,
      doi: null,
      confidence: 0.45,
      retrieved_at: "2026-04-26T00:00:00Z",
    },
  ],
  generated_at: "2026-04-26T00:00:00Z",
};

describe("PlanTabs", () => {
  it("shows source and procurement labels", async () => {
    render(<PlanTabs plan={plan} parsedHypothesis={parsedHypothesis} />);

    await userEvent.click(screen.getByRole("button", { name: "Materials" }));

    expect(screen.getAllByText("Requires procurement check").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Contact supplier").length).toBeGreaterThan(0);
  });

  it("renders the Sources tab with trust tier, evidence class, and usage", async () => {
    render(<PlanTabs plan={plan} parsedHypothesis={parsedHypothesis} />);

    await userEvent.click(screen.getByRole("button", { name: "Sources" }));

    expect(screen.getAllByText("Source-backed").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Adjacent evidence").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Community source").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Inferred / expert review required").length).toBeGreaterThan(0);
    expect(screen.getAllByText("High trust").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Supplier documentation").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ATCC").length).toBeGreaterThan(0);
    expect(screen.getByText(/ATCC HeLa cell stock/)).toBeInTheDocument();
    expect(screen.getAllByText(/Protocol step 1/).length).toBeGreaterThan(0);
  });

  it("renders review memory and run timeline when provided", () => {
    render(
      <PlanTabs
        plan={plan}
        parsedHypothesis={parsedHypothesis}
        runId="run-1"
        reviewState="reviewed"
        runEvents={[
          {
            id: "evt-1",
            run_id: "run-1",
            stage: "plan_generation",
            status: "completed",
            message: "Experiment plan generated and persisted.",
            created_at: "2026-04-26T00:00:00Z",
          },
        ]}
      />,
    );

    expect(screen.getByText(/prior reviewed signals applied/i)).toBeInTheDocument();
    expect(screen.getByText("Run timeline")).toBeInTheDocument();
  });
});
