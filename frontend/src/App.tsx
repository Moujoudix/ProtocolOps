import { AlertTriangle, FlaskConical, Loader2, Play, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { LiteratureQcPanel } from "./components/LiteratureQcPanel";
import { PlanTabs } from "./components/PlanTabs";
import { StageRail } from "./components/StageRail";
import { fetchPresets, generatePlan, runLiteratureQc } from "./lib/api";
import type { LiteratureQcResponse, PlanResponse, Preset } from "./types/api";

type Stage = "input" | "qc" | "plan";

export default function App() {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [hypothesis, setHypothesis] = useState("");
  const [qcResponse, setQcResponse] = useState<LiteratureQcResponse | null>(null);
  const [planResponse, setPlanResponse] = useState<PlanResponse | null>(null);
  const [activeStage, setActiveStage] = useState<Stage>("input");
  const [loading, setLoading] = useState<"presets" | "qc" | "plan" | null>("presets");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPresets()
      .then((items) => {
        setPresets(items);
        const defaultPreset = items.find((item) => item.optimized_demo) ?? items[0];
        if (defaultPreset) {
          setSelectedPresetId(defaultPreset.id);
          setHypothesis(defaultPreset.hypothesis);
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(null));
  }, []);

  const selectedPreset = useMemo(
    () => presets.find((preset) => preset.id === selectedPresetId) ?? null,
    [presets, selectedPresetId],
  );

  function selectPreset(presetId: string) {
    const preset = presets.find((item) => item.id === presetId);
    setSelectedPresetId(presetId);
    if (preset) {
      setHypothesis(preset.hypothesis);
    }
    setQcResponse(null);
    setPlanResponse(null);
    setActiveStage("input");
    setError(null);
  }

  async function handleRunQc() {
    setLoading("qc");
    setError(null);
    setPlanResponse(null);
    try {
      const response = await runLiteratureQc(hypothesis, selectedPresetId);
      setQcResponse(response);
      setActiveStage("qc");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run Literature QC");
    } finally {
      setLoading(null);
    }
  }

  async function handleGeneratePlan() {
    if (!qcResponse) {
      return;
    }
    setLoading("plan");
    setError(null);
    try {
      const response = await generatePlan(qcResponse.run_id);
      setPlanResponse(response);
      setActiveStage("plan");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to generate plan");
    } finally {
      setLoading(null);
    }
  }

  return (
    <main className="min-h-screen text-zinc-950">
      <header className="border-b border-zinc-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-zinc-950 text-white">
              <FlaskConical className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-normal">AI Scientist</h1>
              <p className="text-sm text-zinc-500">Hypothesis to review-ready experiment plan</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
            <span className="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1">Backend-only secrets</span>
            <span className="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1">Evidence-gated planning</span>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:px-8 workspace-grid">
        <aside className="space-y-5">
          <StageRail active={activeStage} hasQc={Boolean(qcResponse)} hasPlan={Boolean(planResponse)} />

          <section className="rounded-md border border-zinc-200 bg-white p-5 shadow-crisp">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">Hypothesis</h2>
                <p className="mt-1 text-sm leading-6 text-zinc-500">Select a preset or edit the input directly.</p>
              </div>
              {selectedPreset?.optimized_demo && (
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800">
                  demo path
                </span>
              )}
            </div>

            <label className="mt-5 block text-xs font-semibold uppercase tracking-wide text-zinc-500" htmlFor="preset">
              Preset
            </label>
            <select
              id="preset"
              className="mt-2 min-h-11 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-emerald-200"
              value={selectedPresetId ?? ""}
              onChange={(event) => selectPreset(event.target.value)}
              disabled={loading === "presets"}
            >
              {presets.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.label}
                </option>
              ))}
            </select>

            <label className="mt-5 block text-xs font-semibold uppercase tracking-wide text-zinc-500" htmlFor="hypothesis">
              Natural-language hypothesis
            </label>
            <textarea
              id="hypothesis"
              className="mt-2 min-h-56 w-full resize-y rounded-md border border-zinc-300 bg-white px-3 py-3 text-sm leading-6 outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-emerald-200"
              value={hypothesis}
              onChange={(event) => {
                setHypothesis(event.target.value);
                setQcResponse(null);
                setPlanResponse(null);
                setActiveStage("input");
              }}
            />

            <div className="mt-5 grid gap-3">
              <button
                type="button"
                onClick={handleRunQc}
                disabled={loading !== null || hypothesis.trim().length < 20}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
              >
                {loading === "qc" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                Run Literature QC
              </button>
              <button
                type="button"
                onClick={handleGeneratePlan}
                disabled={loading !== null || !qcResponse}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-zinc-300 bg-white px-4 text-sm font-semibold text-zinc-950 transition hover:border-zinc-950 disabled:cursor-not-allowed disabled:text-zinc-400"
              >
                {loading === "plan" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Generate Plan
              </button>
            </div>
          </section>

          {error && (
            <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
              <div className="flex gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            </div>
          )}
        </aside>

        <section className="min-w-0 space-y-5">
          {!qcResponse && !planResponse && (
            <div className="enter-up rounded-md border border-zinc-200 bg-white p-6 shadow-crisp">
              <div className="max-w-3xl">
                <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Stage 1</p>
                <h2 className="mt-2 text-2xl font-semibold tracking-normal text-zinc-950">Start with Literature QC</h2>
                <p className="mt-3 text-sm leading-6 text-zinc-600">
                  The plan generator stays locked until the backend parses the hypothesis and returns novelty, confidence,
                  references, searched sources, and evidence gaps.
                </p>
              </div>
            </div>
          )}

          {qcResponse && activeStage !== "plan" && (
            <>
              <LiteratureQcPanel parsed={qcResponse.parsed_hypothesis} qc={qcResponse.literature_qc} />
              <div className="rounded-md border border-zinc-200 bg-white p-5 shadow-crisp">
                <button
                  type="button"
                  onClick={handleGeneratePlan}
                  disabled={loading !== null}
                  className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
                >
                  {loading === "plan" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  Generate review-ready plan
                </button>
              </div>
            </>
          )}

          {planResponse && <PlanTabs plan={planResponse.plan} parsedHypothesis={qcResponse?.parsed_hypothesis ?? null} />}
        </section>
      </div>
    </main>
  );
}
