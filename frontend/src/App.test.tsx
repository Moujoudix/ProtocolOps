import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const presets = [
  {
    id: "crp-biosensor",
    label: "Diagnostics / CRP biosensor",
    domain: "diagnostics",
    hypothesis: "A paper-based electrochemical biosensor will detect C-reactive protein in whole blood.",
    optimized_demo: false,
  },
  {
    id: "lgg-mouse-gut",
    label: "Gut health / Lactobacillus mouse study",
    domain: "gut health",
    hypothesis: "Supplementing C57BL/6 mice with Lactobacillus rhamnosus GG will reduce permeability.",
    optimized_demo: false,
  },
  {
    id: "sporomusa-co2",
    label: "Climate / Sporomusa ovata CO2 fixation",
    domain: "climate",
    hypothesis: "Introducing Sporomusa ovata into a bioelectrochemical system will fix CO2 into acetate.",
    optimized_demo: false,
  },
  {
    id: "hela-trehalose",
    label: "Main demo / HeLa cryopreservation",
    domain: "cell biology",
    hypothesis: "Replacing sucrose with trehalose as a cryoprotectant will increase post-thaw viability of HeLa cells.",
    optimized_demo: true,
  },
];

afterEach(() => {
  vi.restoreAllMocks();
});

const readiness = {
  strict_live_mode: false,
  live_ready: false,
  providers: [
    {
      provider: "OpenAI",
      status: "missing_secret" as const,
      detail: "Structured parsing and plan generation",
      configured: false,
      authenticated: false,
    },
  ],
};

const recentRuns: Array<{
  run_id: string;
  hypothesis: string;
  preset_id: string | null;
  status: string;
  review_state: "generated";
  created_at: string;
  updated_at: string;
  domain: string | null;
  plan_title: string | null;
  quality_summary: null;
  used_seed_data: boolean;
}> = [];

describe("App", () => {
  it("loads all four presets and gates plan generation before Literature QC", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.endsWith("/api/presets")) {
          return Promise.resolve({ ok: true, json: async () => presets });
        }
        if (url.endsWith("/api/readiness")) {
          return Promise.resolve({ ok: true, json: async () => readiness });
        }
        if (url.endsWith("/api/runs")) {
          return Promise.resolve({ ok: true, json: async () => recentRuns });
        }
        return Promise.reject(new Error(`Unexpected URL ${url}`));
      }),
    );

    render(<App />);

    expect(await screen.findByText("Main demo / HeLa cryopreservation")).toBeInTheDocument();
    expect(screen.getByText("Diagnostics / CRP biosensor")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate plan/i })).toBeDisabled();
    expect(screen.getByText("Provider readiness")).toBeInTheDocument();
  });

  it("runs Literature QC and enables plan generation", async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.endsWith("/api/presets")) {
        return Promise.resolve({ ok: true, json: async () => presets });
      }
      if (url.endsWith("/api/readiness")) {
        return Promise.resolve({ ok: true, json: async () => readiness });
      }
      if (url.endsWith("/api/runs")) {
        return Promise.resolve({ ok: true, json: async () => recentRuns });
      }
      if (url.endsWith("/api/literature-qc")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            run_id: "run-1",
            parsed_hypothesis: {
              original_text: presets[3].hypothesis,
              domain: "cell biology",
              domain_route: "cell_biology",
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
            },
            literature_qc: {
              novelty_signal: "similar_work_exists",
              confidence: 0.7,
              references: [],
              literature_sources: [],
              searched_sources: ["Semantic Scholar", "Europe PMC"],
              provider_trace: [],
              rationale: "Similar work exists.",
              literature_synthesis: null,
              gaps: ["Use not found in searched sources language."],
              evidence_gap_warnings: ["Use not found in searched sources language."],
            },
          }),
        });
      }
      if (url.endsWith("/api/runs/run-1/events")) {
        return Promise.resolve({
          ok: true,
          json: async () => [
            {
              id: "event-1",
              run_id: "run-1",
              stage: "literature_qc",
              status: "completed",
              message: "Literature QC completed and references stored.",
              created_at: "2026-04-26T00:00:00Z",
            },
          ],
        });
      }
      return Promise.reject(new Error(`Unexpected URL ${url}`));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await screen.findByText("Main demo / HeLa cryopreservation");

    await userEvent.click(screen.getByRole("button", { name: /run literature qc/i }));

    expect(await screen.findByText("Similar work exists")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: /generate review-ready plan/i })).toBeEnabled());
  });
});
