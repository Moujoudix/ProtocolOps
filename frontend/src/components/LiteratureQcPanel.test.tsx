import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LiteratureQcPanel } from "./LiteratureQcPanel";

const parsed = {
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
  supplier_material_query_terms: ["ATCC CCL-2", "CellTiter-Glo"],
  key_terms: ["HeLa", "trehalose"],
  safety_notes: [],
};

const qc = {
  novelty_signal: "similar_work_exists" as const,
  confidence: 0.7,
  references: [
    {
      id: "source-1",
      source_name: "Semantic Scholar",
      title: "Trehalose cryopreservation reference",
      url: "https://example.com/source-1",
      evidence_type: "close_match" as const,
      trust_tier: "literature_database" as const,
      trust_level: "high" as const,
      snippet: "A related cryopreservation study.",
      authors: [],
      year: 2024,
      doi: null,
      confidence: 0.7,
      retrieved_at: "2026-04-26T00:00:00Z",
    },
  ],
  literature_sources: [],
  searched_sources: ["Consensus", "Semantic Scholar", "Europe PMC"],
  provider_trace: [
    {
      provider: "Consensus",
      attempted: true,
      succeeded: false,
      cached: false,
      query: "trehalose HeLa cryopreservation viability DMSO",
      result_count: 0,
      error: "Consensus MCP bridge not configured",
    },
  ],
  rationale: "Similar work exists.",
  literature_synthesis: "Top references indicate related trehalose cryopreservation evidence.",
  gaps: ["Exact protocol still needs expert review."],
  evidence_gap_warnings: ["Exact protocol still needs expert review."],
};

describe("LiteratureQcPanel", () => {
  it("renders provider trace, parsed query terms, and gaps", () => {
    render(<LiteratureQcPanel parsed={parsed} qc={qc} />);

    expect(screen.getByText("Provider Trace")).toBeInTheDocument();
    expect(screen.getAllByText("Consensus").length).toBeGreaterThan(0);
    expect(screen.getAllByText("trehalose HeLa cryopreservation viability DMSO").length).toBeGreaterThan(0);
    expect(screen.getByText("Literature query terms")).toBeInTheDocument();
    expect(screen.getByText("ATCC CCL-2")).toBeInTheDocument();
    expect(screen.getByText("Exact protocol still needs expert review.")).toBeInTheDocument();
  });
});
