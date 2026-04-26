import {
  Activity,
  AlertTriangle,
  ChevronDown,
  FlaskConical,
  History,
  Loader2,
  Play,
  Search,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { LiteratureQcPanel } from "./components/LiteratureQcPanel";
import { PlanTabs } from "./components/PlanTabs";
import { StageRail } from "./components/StageRail";
import {
  fetchComparison,
  fetchPresets,
  fetchReadiness,
  fetchReviews,
  fetchRun,
  fetchRunEvents,
  fetchRuns,
  generatePlan,
  markPresentationAnchor,
  revisePlan,
  runLiteratureQc,
} from "./lib/api";
import type {
  EvidenceMode,
  LiteratureQcResponse,
  PlanResponse,
  Preset,
  ProviderReadiness,
  ReadinessResponse,
  RunComparisonResponse,
  RunEventRecord,
  RunListItem,
  RunMode,
  RunStateResponse,
  ReviewSessionRecord,
  ReviewState,
} from "./types/api";

type Stage = "input" | "qc" | "plan";
type BusyState = "bootstrap" | "opening" | "qc" | "plan" | "refreshing" | null;

export default function App() {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [hypothesis, setHypothesis] = useState("");
  const [qcResponse, setQcResponse] = useState<LiteratureQcResponse | null>(null);
  const [planResponse, setPlanResponse] = useState<PlanResponse | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [recentRuns, setRecentRuns] = useState<RunListItem[]>([]);
  const [runEvents, setRunEvents] = useState<RunEventRecord[]>([]);
  const [reviews, setReviews] = useState<ReviewSessionRecord[]>([]);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [reviewState, setReviewState] = useState<ReviewState>("generated");
  const [runMode, setRunMode] = useState<RunMode>("degraded_live");
  const [evidenceMode, setEvidenceMode] = useState<EvidenceMode>("seeded_demo");
  const [usedSeedData, setUsedSeedData] = useState(false);
  const [isPresentationAnchor, setIsPresentationAnchor] = useState(false);
  const [parentRunId, setParentRunId] = useState<string | null>(null);
  const [revisionNumber, setRevisionNumber] = useState(0);
  const [comparison, setComparison] = useState<RunComparisonResponse | null>(null);
  const [activeStage, setActiveStage] = useState<Stage>("input");
  const [loading, setLoading] = useState<BusyState>("bootstrap");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void bootstrap();
  }, []);

  const selectedPreset = useMemo(
    () => presets.find((preset) => preset.id === selectedPresetId) ?? null,
    [presets, selectedPresetId],
  );
  const artifactStage = activeStage !== "input";
  const hypothesisLocked = loading === "bootstrap" || loading === "opening";

  async function bootstrap() {
    setLoading("bootstrap");
    setError(null);
    const runIdFromUrl = new URLSearchParams(window.location.search).get("run");

    const [presetsResult, readinessResult, runsResult] = await Promise.allSettled([
      fetchPresets(),
      fetchReadiness(),
      fetchRuns(),
    ]);

    let presetItems: Preset[] = [];

    if (presetsResult.status === "fulfilled") {
      presetItems = presetsResult.value;
      setPresets(presetItems);
      const defaultPreset = presetItems.find((item) => item.optimized_demo) ?? presetItems[0] ?? null;
      if (defaultPreset) {
        setSelectedPresetId(defaultPreset.id);
        setHypothesis(defaultPreset.hypothesis);
      }
    } else {
      setError(presetsResult.reason instanceof Error ? presetsResult.reason.message : "Unable to load presets");
    }

    if (readinessResult.status === "fulfilled") {
      setReadiness(readinessResult.value);
    }

    if (runsResult.status === "fulfilled") {
      setRecentRuns(runsResult.value);
    }

    if (runIdFromUrl) {
      await openRun(runIdFromUrl, presetItems);
    } else {
      setLoading(null);
    }
  }

  async function refreshSidebarData() {
    const [readinessResult, runsResult] = await Promise.allSettled([fetchReadiness(), fetchRuns()]);
    if (readinessResult.status === "fulfilled") {
      setReadiness(readinessResult.value);
    }
    if (runsResult.status === "fulfilled") {
      setRecentRuns(runsResult.value);
    }
  }

  function hydrateRun(run: RunStateResponse, availablePresets: Preset[]) {
    setCurrentRunId(run.run_id);
    setReviewState(run.review_state);
    setRunMode(run.run_mode);
    setEvidenceMode(run.evidence_mode);
    setUsedSeedData(run.used_seed_data);
    setIsPresentationAnchor(run.is_presentation_anchor);
    setParentRunId(run.parent_run_id);
    setRevisionNumber(run.revision_number);
    setHypothesis(run.hypothesis);
    if (run.preset_id) {
      setSelectedPresetId(run.preset_id);
    } else if (run.parsed_hypothesis) {
      const matched = availablePresets.find((preset) => preset.domain === run.parsed_hypothesis?.domain);
      setSelectedPresetId(matched?.id ?? null);
    }
    if (run.parsed_hypothesis && run.literature_qc) {
      setQcResponse({
        run_id: run.run_id,
        parsed_hypothesis: run.parsed_hypothesis,
        literature_qc: run.literature_qc,
      });
      setActiveStage("qc");
    } else {
      setQcResponse(null);
      setActiveStage("input");
    }

    if (run.plan) {
      setPlanResponse({ run_id: run.run_id, plan: run.plan });
      setActiveStage("plan");
    } else {
      setPlanResponse(null);
    }
    window.history.replaceState(null, "", `?run=${run.run_id}`);
  }

  async function openRun(runId: string, availablePresets = presets) {
    setLoading("opening");
    setError(null);
    try {
      const [run, events, reviewSessions] = await Promise.all([fetchRun(runId), fetchRunEvents(runId), fetchReviews(runId)]);
      hydrateRun(run, availablePresets);
      setRunEvents(events);
      setReviews(reviewSessions);
      setComparison(await fetchComparison(runId).catch(() => null));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open run");
    } finally {
      setLoading(null);
      await refreshSidebarData();
    }
  }

  function resetToInput(nextHypothesis?: string) {
    setCurrentRunId(null);
    setQcResponse(null);
    setPlanResponse(null);
    setRunEvents([]);
    setReviews([]);
    setReviewState("generated");
    setRunMode("degraded_live");
    setEvidenceMode(readiness?.evidence_mode ?? "seeded_demo");
    setUsedSeedData(false);
    setIsPresentationAnchor(false);
    setParentRunId(null);
    setRevisionNumber(0);
    setComparison(null);
    setActiveStage("input");
    if (typeof nextHypothesis === "string") {
      setHypothesis(nextHypothesis);
    }
    window.history.replaceState(null, "", window.location.pathname);
  }

  function selectPreset(presetId: string) {
    const preset = presets.find((item) => item.id === presetId);
    setSelectedPresetId(presetId);
    resetToInput(preset?.hypothesis ?? hypothesis);
    setError(null);
  }

  async function handleRunQc() {
    setLoading("qc");
    setError(null);
    setPlanResponse(null);
    try {
      const response = await runLiteratureQc(hypothesis, selectedPresetId);
      setQcResponse(response);
      setCurrentRunId(response.run_id);
      setRunEvents(await fetchRunEvents(response.run_id).catch(() => []));
      setReviews([]);
      setReviewState("generated");
      setRunMode("degraded_live");
      setEvidenceMode(readiness?.evidence_mode ?? "seeded_demo");
      setUsedSeedData(false);
      setIsPresentationAnchor(false);
      setParentRunId(null);
      setRevisionNumber(0);
      setComparison(null);
      setActiveStage("qc");
      window.history.replaceState(null, "", `?run=${response.run_id}`);
      await refreshSidebarData();
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
      setCurrentRunId(response.run_id);
      setActiveStage("plan");
      const [events, reviewSessions, latestRun] = await Promise.all([
        fetchRunEvents(response.run_id).catch(() => []),
        fetchReviews(response.run_id).catch(() => []),
        fetchRun(response.run_id),
      ]);
      setRunEvents(events);
      setReviews(reviewSessions);
      setReviewState(latestRun.review_state);
      hydrateRun(latestRun, presets);
      setComparison(await fetchComparison(response.run_id).catch(() => null));
      await refreshSidebarData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to generate plan");
    } finally {
      setLoading(null);
    }
  }

  async function handleReviewSubmitted() {
    if (!currentRunId) {
      return;
    }
    setLoading("refreshing");
    try {
      const [latestRun, events, reviewSessions] = await Promise.all([
        fetchRun(currentRunId),
        fetchRunEvents(currentRunId),
        fetchReviews(currentRunId),
      ]);
      hydrateRun(latestRun, presets);
      setRunEvents(events);
      setReviews(reviewSessions);
      setReviewState(latestRun.review_state);
      setComparison(await fetchComparison(currentRunId).catch(() => null));
      await refreshSidebarData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to refresh run after review");
    } finally {
      setLoading(null);
    }
  }

  async function handleRevisePlan() {
    if (!currentRunId) {
      return;
    }
    setLoading("plan");
    setError(null);
    try {
      const revised = await revisePlan(currentRunId);
      await openRun(revised.run_id, presets);
      setActiveStage("plan");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to generate revised plan");
    } finally {
      setLoading(null);
    }
  }

  async function handleMarkPresentationAnchor() {
    if (!currentRunId) {
      return;
    }
    setLoading("refreshing");
    setError(null);
    try {
      const updated = await markPresentationAnchor(currentRunId);
      hydrateRun(updated, presets);
      setIsPresentationAnchor(true);
      await refreshSidebarData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to mark presentation anchor");
    } finally {
      setLoading(null);
    }
  }

  return (
    <main className="min-h-screen bg-[#f5f6f3] text-zinc-950">
      <header className="border-b border-zinc-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-950 text-white">
              <FlaskConical className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-normal">ProtocolOps AI</h1>
              <p className="text-sm text-zinc-500">Review-ready experiment planning workspace</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm text-zinc-600">
            {readiness && (
              <div className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1.5">
                <span className={`h-2 w-2 rounded-full ${readiness.live_ready ? "bg-emerald-500" : "bg-amber-500"}`} />
                <span className="font-medium text-zinc-800">
                  {readiness.live_ready ? "Live ready" : "Presentation fallback ready"}
                </span>
                <span className="text-zinc-400">·</span>
                <span>{humanizeEvidenceMode(readiness.evidence_mode)}</span>
              </div>
            )}
            {isPresentationAnchor && <span className="text-xs font-medium text-cyan-700">Presentation anchor</span>}
          </div>
        </div>
      </header>

      <div className={`mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:px-8 workspace-grid ${artifactStage ? "workspace-grid-compact" : ""}`}>
        <aside className={`space-y-4 ${artifactStage ? "hidden lg:block" : ""}`}>
          <StageRail active={activeStage} hasQc={Boolean(qcResponse)} hasPlan={Boolean(planResponse)} />
          {artifactStage ? (
            <ExperimentSetupDisclosure
              selectedPreset={selectedPreset}
              presets={presets}
              selectedPresetId={selectedPresetId}
              hypothesis={hypothesis}
              hypothesisLocked={hypothesisLocked}
              loading={loading}
              qcReady={Boolean(qcResponse)}
              onSelectPreset={selectPreset}
              onHypothesisChange={(next) => {
                setHypothesis(next);
                resetToInput(next);
              }}
              onRunQc={handleRunQc}
              onGeneratePlan={handleGeneratePlan}
            />
          ) : (
            <ExperimentSetupCard
              selectedPreset={selectedPreset}
              presets={presets}
              selectedPresetId={selectedPresetId}
              hypothesis={hypothesis}
              hypothesisLocked={hypothesisLocked}
              loading={loading}
              qcReady={Boolean(qcResponse)}
              onSelectPreset={selectPreset}
              onHypothesisChange={(next) => {
                setHypothesis(next);
                resetToInput(next);
              }}
              onRunQc={handleRunQc}
              onGeneratePlan={handleGeneratePlan}
            />
          )}

          <details className="rounded-lg border border-zinc-200 bg-white">
            <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-4">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-zinc-500" />
                <div>
                  <p className="text-sm font-semibold text-zinc-950">System status</p>
                  <p className="text-xs text-zinc-500">Readiness, evidence mode, and fallback availability</p>
                </div>
              </div>
              <ChevronDown className="h-4 w-4 text-zinc-400" />
            </summary>
            <div className="border-t border-zinc-200 px-5 py-4">
              <div className="space-y-3">
                {(readiness?.providers ?? []).map((provider) => (
                  <ProviderStatusCard key={provider.provider} provider={provider} />
                ))}
              </div>
              {readiness && (
                <div className="mt-4 grid gap-3 rounded-lg bg-zinc-50 p-4 text-sm text-zinc-700 sm:grid-cols-3">
                  <StatusRow label="Mode" value={humanizeEvidenceMode(readiness.evidence_mode)} />
                  <StatusRow label="Cached live" value={readiness.cached_live_available ? "Available" : "Not yet captured"} />
                  <StatusRow label="Seeded demo" value={readiness.seeded_demo_available ? "Available" : "Unavailable"} />
                </div>
              )}
            </div>
          </details>

          <details className="rounded-lg border border-zinc-200 bg-white">
            <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-4">
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-zinc-500" />
                <div>
                  <p className="text-sm font-semibold text-zinc-950">Recent runs</p>
                  <p className="text-xs text-zinc-500">Reopen prior plans and presentation anchors</p>
                </div>
              </div>
              <ChevronDown className="h-4 w-4 text-zinc-400" />
            </summary>
            <div className="border-t border-zinc-200 px-5 py-4">
              <div className="space-y-3">
                {recentRuns.length === 0 ? (
                  <p className="text-sm text-zinc-500">No stored runs yet.</p>
                ) : (
                  recentRuns.slice(0, 6).map((run) => (
                    <button
                      key={run.run_id}
                      type="button"
                      onClick={() => void openRun(run.run_id)}
                      className={`w-full rounded-lg border p-3 text-left transition hover:border-zinc-950 ${
                        currentRunId === run.run_id ? "border-emerald-300 bg-emerald-50/60" : "border-zinc-200 bg-white"
                      }`}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-zinc-950">{run.plan_title ?? run.domain ?? "Saved run"}</span>
                        <span className="text-xs text-zinc-500">{humanizeEvidenceMode(run.evidence_mode)}</span>
                        {run.is_presentation_anchor && <span className="text-xs font-medium text-cyan-700">Anchor</span>}
                      </div>
                      <p className="mt-2 line-clamp-2 text-sm leading-6 text-zinc-600">{run.hypothesis}</p>
                    </button>
                  ))
                )}
              </div>
            </div>
          </details>

          {error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
              <div className="flex gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            </div>
          )}
        </aside>

        <section className="min-w-0 space-y-5">
          {artifactStage && (
            <div className="space-y-3 lg:hidden">
              <StageRail active={activeStage} hasQc={Boolean(qcResponse)} hasPlan={Boolean(planResponse)} />
              <ExperimentSetupDisclosure
                selectedPreset={selectedPreset}
                presets={presets}
                selectedPresetId={selectedPresetId}
                hypothesis={hypothesis}
                hypothesisLocked={hypothesisLocked}
                loading={loading}
                qcReady={Boolean(qcResponse)}
                onSelectPreset={selectPreset}
                onHypothesisChange={(next) => {
                  setHypothesis(next);
                  resetToInput(next);
                }}
                onRunQc={handleRunQc}
                onGeneratePlan={handleGeneratePlan}
                mobile
              />
              {error && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
                  <div className="flex gap-2">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {loading && (
            <div className="rounded-lg border border-zinc-200 bg-white p-4">
              <div className="flex items-center gap-3">
                <Loader2 className="h-4 w-4 animate-spin text-emerald-700" />
                <div>
                  <p className="text-sm font-semibold text-zinc-950">{loadingLabel(loading)}</p>
                  <p className="text-sm text-zinc-500">{loadingDescription(loading)}</p>
                </div>
              </div>
            </div>
          )}

          {!qcResponse && !planResponse && (
            <div className="enter-up rounded-xl border border-zinc-200 bg-white px-6 py-7">
              <div className="max-w-4xl">
                <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Start here</p>
                <h2 className="mt-2 text-2xl font-semibold tracking-normal text-zinc-950">Ground the hypothesis before you plan the experiment.</h2>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600">
                  Run Literature QC first, review the novelty signal and references, then generate a review-ready plan with sourcing and operational caveats already attached.
                </p>
                <div className="mt-6 grid gap-4 border-t border-zinc-200 pt-5 md:grid-cols-3">
                  <ValueCallout label="Workflow" body="Literature QC unlocks planning." />
                  <ValueCallout label="Deliverable" body="Protocol, materials, budget, timeline, validation." />
                  <ValueCallout label="Trust posture" body="Uncertainty and procurement gaps stay visible." />
                </div>
              </div>
            </div>
          )}

          {qcResponse && activeStage !== "plan" && (
            <>
              <LiteratureQcPanel parsed={qcResponse.parsed_hypothesis} qc={qcResponse.literature_qc} />
              <div className="rounded-lg border border-zinc-200 bg-white p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-base font-semibold text-zinc-950">Literature QC complete</h3>
                    <p className="mt-1 text-sm text-zinc-600">
                      The novelty check and references are stored. The next step builds an evidence pack before drafting the plan.
                    </p>
                  </div>
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
              </div>
            </>
          )}

          {planResponse && (
            <PlanTabs
              plan={planResponse.plan}
              parsedHypothesis={qcResponse?.parsed_hypothesis ?? null}
              runId={currentRunId}
              reviewState={reviewState}
              runMode={runMode}
              evidenceMode={evidenceMode}
              usedSeedData={usedSeedData}
              isPresentationAnchor={isPresentationAnchor}
              parentRunId={parentRunId}
              revisionNumber={revisionNumber}
              comparison={comparison}
              reviews={reviews}
              runEvents={runEvents}
              onReviewSubmitted={handleReviewSubmitted}
              onRevise={handleRevisePlan}
              onMarkPresentationAnchor={handleMarkPresentationAnchor}
            />
          )}
        </section>
      </div>
    </main>
  );
}

function ExperimentSetupCard(props: ExperimentSetupProps) {
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5">
      <div>
        <h2 className="text-base font-semibold">Experiment setup</h2>
        <p className="mt-1 text-sm leading-6 text-zinc-500">Choose an example hypothesis or edit the scientific question directly.</p>
      </div>
      <SetupControls {...props} className="mt-5" />
    </section>
  );
}

function ExperimentSetupDisclosure({
  selectedPreset,
  hypothesis,
  mobile = false,
  ...props
}: ExperimentSetupProps & { mobile?: boolean }) {
  return (
    <details className="rounded-lg border border-zinc-200 bg-white" open={false}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4">
        <div>
          <p className="text-sm font-semibold text-zinc-950">Experiment setup</p>
          <p className="mt-1 line-clamp-1 text-xs leading-5 text-zinc-500">
            {selectedPreset?.label ?? "Custom hypothesis"} · {compactHypothesis(hypothesis, mobile ? 48 : 96)}
          </p>
        </div>
        <ChevronDown className="h-4 w-4 shrink-0 text-zinc-400" />
      </summary>
      <div className="border-t border-zinc-200 px-5 py-4">
        <SetupControls
          {...props}
          selectedPreset={selectedPreset}
          hypothesis={hypothesis}
          compact
        />
      </div>
    </details>
  );
}

interface ExperimentSetupProps {
  selectedPreset: Preset | null;
  presets: Preset[];
  selectedPresetId: string | null;
  hypothesis: string;
  hypothesisLocked: boolean;
  loading: BusyState;
  qcReady: boolean;
  onSelectPreset: (presetId: string) => void;
  onHypothesisChange: (value: string) => void;
  onRunQc: () => void;
  onGeneratePlan: () => void;
}

function SetupControls({
  presets,
  selectedPresetId,
  hypothesis,
  hypothesisLocked,
  loading,
  qcReady,
  onSelectPreset,
  onHypothesisChange,
  onRunQc,
  onGeneratePlan,
  className = "",
  compact = false,
}: ExperimentSetupProps & { className?: string; compact?: boolean }) {
  return (
    <div className={className}>
      <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500" htmlFor={compact ? "preset-compact" : "preset"}>
        Example hypotheses
      </label>
      <select
        id={compact ? "preset-compact" : "preset"}
        className="mt-2 min-h-11 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-emerald-200"
        value={selectedPresetId ?? ""}
        onChange={(event) => onSelectPreset(event.target.value)}
        disabled={hypothesisLocked}
      >
        {presets.map((preset) => (
          <option key={preset.id} value={preset.id}>
            {preset.label}
          </option>
        ))}
      </select>

      <label className="mt-5 block text-xs font-semibold uppercase tracking-wide text-zinc-500" htmlFor={compact ? "hypothesis-compact" : "hypothesis"}>
        Natural-language hypothesis
      </label>
      <textarea
        id={compact ? "hypothesis-compact" : "hypothesis"}
        className={`mt-2 w-full resize-y rounded-md border border-zinc-300 bg-white px-3 py-3 text-sm leading-6 outline-none transition focus:border-zinc-950 focus:ring-2 focus:ring-emerald-200 ${compact ? "min-h-32" : "min-h-56"}`}
        value={hypothesis}
        onChange={(event) => onHypothesisChange(event.target.value)}
      />

      <div className="mt-5 grid gap-3">
        <button
          type="button"
          onClick={onRunQc}
          disabled={loading !== null || hypothesis.trim().length < 20}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
        >
          {loading === "qc" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          Run Literature QC
        </button>
        <button
          type="button"
          onClick={onGeneratePlan}
          disabled={loading !== null || !qcReady}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-zinc-300 bg-white px-4 text-sm font-semibold text-zinc-950 transition hover:border-zinc-950 disabled:cursor-not-allowed disabled:text-zinc-400"
        >
          {loading === "plan" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          Generate Plan
        </button>
        {!qcReady && <p className="text-xs text-zinc-500">Run Literature QC to unlock planning.</p>}
      </div>
    </div>
  );
}

function compactHypothesis(hypothesis: string, limit: number) {
  const compacted = hypothesis.replace(/\s+/g, " ").trim();
  if (compacted.length <= limit) {
    return compacted;
  }
  return `${compacted.slice(0, limit - 1).trimEnd()}…`;
}

function ProviderStatusCard({ provider }: { provider: ProviderReadiness }) {
  const tone =
    provider.status === "ready" || provider.status === "public_mode"
      ? "bg-emerald-50/70"
      : provider.status === "degraded"
        ? "bg-amber-50"
        : "bg-rose-50";
  const textTone =
    provider.status === "ready" || provider.status === "public_mode"
      ? "text-emerald-900"
      : provider.status === "degraded"
        ? "text-amber-900"
        : "text-rose-900";

  return (
    <div className={`rounded-lg px-3 py-3 ${tone}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className={`text-sm font-semibold ${textTone}`}>{provider.provider}</span>
        <span className="text-xs font-medium text-zinc-600">{humanizeProviderStatus(provider.status)}</span>
      </div>
      <p className={`mt-1 text-sm leading-6 ${textTone}`}>{provider.detail}</p>
    </div>
  );
}

function ValueCallout({ label, body }: { label: string; body: string }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="text-sm leading-6 text-zinc-700">{body}</p>
    </div>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-1 font-medium text-zinc-900">{value}</p>
    </div>
  );
}

function humanizeProviderStatus(status: ProviderReadiness["status"]) {
  const labels: Record<ProviderReadiness["status"], string> = {
    ready: "Ready",
    missing_secret: "Missing secret",
    public_mode: "Public mode",
    unreachable: "Unreachable",
    degraded: "Degraded",
  };
  return labels[status];
}

function humanizeEvidenceMode(evidenceMode: EvidenceMode) {
  const labels: Record<EvidenceMode, string> = {
    strict_live: "strict live",
    cached_live: "cached live",
    seeded_demo: "seeded demo",
  };
  return labels[evidenceMode];
}

function loadingLabel(loading: Exclude<BusyState, null>) {
  const labels: Record<Exclude<BusyState, null>, string> = {
    bootstrap: "Loading presets, readiness, and recent runs",
    opening: "Opening saved run",
    qc: "Parsing hypothesis and running literature QC",
    plan: "Building evidence pack and generating the plan",
    refreshing: "Refreshing run state and review memory",
  };
  return labels[loading];
}

function loadingDescription(loading: Exclude<BusyState, null>) {
  const descriptions: Record<Exclude<BusyState, null>, string> = {
    bootstrap: "Cold-start checks keep the app honest about live-provider readiness.",
    opening: "Rehydrating stored QC, plan, review, and comparison artifacts.",
    qc: "The backend is grounding the hypothesis before any plan is allowed.",
    plan: "This includes evidence-pack construction, section scoring, and source-linked drafting.",
    refreshing: "Pulling the latest review state, timeline events, and any revised artifacts.",
  };
  return descriptions[loading];
}
