import { AlertTriangle, Download, ExternalLink, GitCompare, History, Link2, RotateCcw, ShieldCheck, Star } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { exportCitationsUrl, exportJsonUrl, exportPdfUrl, exportProcurementUrl, submitReview } from "../lib/api";
import type {
  BudgetSummary,
  ComparisonMetricRecord,
  EvidenceSource,
  ExperimentPlan,
  ExperimentPlanSection,
  MaterialItem,
  ParsedHypothesis,
  ProtocolStep,
  RunComparisonResponse,
  RunMode,
  ReviewSessionRecord,
  ReviewState,
  ReviewSubmissionRequest,
  RunEventRecord,
} from "../types/api";
import { Badge, ConfidenceBadge } from "./Badge";
import { LiteratureQcPanel } from "./LiteratureQcPanel";

interface PlanTabsProps {
  plan: ExperimentPlan;
  parsedHypothesis: ParsedHypothesis | null;
  runId?: string | null;
  reviewState?: ReviewState;
  runMode?: RunMode;
  usedSeedData?: boolean;
  isPresentationAnchor?: boolean;
  parentRunId?: string | null;
  revisionNumber?: number;
  comparison?: RunComparisonResponse | null;
  reviews?: ReviewSessionRecord[];
  runEvents?: RunEventRecord[];
  onReviewSubmitted?: () => void | Promise<void>;
  onRevise?: () => void | Promise<void>;
  onMarkPresentationAnchor?: () => void | Promise<void>;
}

const EMPTY_REVIEWS: ReviewSessionRecord[] = [];
const EMPTY_EVENTS: RunEventRecord[] = [];

const tabLabels = [
  "Overview",
  "Literature QC",
  "Study Design",
  "Protocol",
  "Materials",
  "Budget",
  "Timeline",
  "Validation",
  "Risks",
  "Sources",
  "Comparison",
  "Review",
] as const;

type Tab = (typeof tabLabels)[number];

export function PlanTabs({
  plan,
  parsedHypothesis,
  runId = null,
  reviewState = "generated",
  runMode = "degraded_live",
  usedSeedData = false,
  isPresentationAnchor = false,
  parentRunId = null,
  revisionNumber = 0,
  comparison = null,
  reviews = EMPTY_REVIEWS,
  runEvents = EMPTY_EVENTS,
  onReviewSubmitted,
  onRevise,
  onMarkPresentationAnchor,
}: PlanTabsProps) {
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [providerFilter, setProviderFilter] = useState("all");
  const [trustFilter, setTrustFilter] = useState("all");
  const [classFilter, setClassFilter] = useState("all");
  const [localReviewState, setLocalReviewState] = useState<ReviewState>(reviewState);
  const [localReviews, setLocalReviews] = useState<ReviewSessionRecord[]>(reviews);
  const [reviewerName, setReviewerName] = useState("");
  const [reviewSummary, setReviewSummary] = useState("");
  const [reviewTargetType, setReviewTargetType] = useState<ReviewSubmissionRequest["items"][number]["target_type"]>("section");
  const [reviewTargetKey, setReviewTargetKey] = useState("overview");
  const [reviewAction, setReviewAction] = useState<ReviewSubmissionRequest["items"][number]["action"]>("comment");
  const [reviewComment, setReviewComment] = useState("");
  const [reviewReplacement, setReviewReplacement] = useState("");
  const [reviewConfidenceOverride, setReviewConfidenceOverride] = useState("");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [revisionSubmitting, setRevisionSubmitting] = useState(false);
  const [anchorSubmitting, setAnchorSubmitting] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [linkCopied, setLinkCopied] = useState(false);

  useEffect(() => setLocalReviews(reviews), [reviews]);
  useEffect(() => setLocalReviewState(reviewState), [reviewState]);

  const sourceById = useMemo(() => new Map(plan.sources.map((source) => [source.id, source])), [plan.sources]);
  const sourceUsage = useMemo(() => buildSourceUsage(plan), [plan]);

  const providerOptions = useMemo(
    () => ["all", ...Array.from(new Set(plan.sources.map((source) => source.source_name)))],
    [plan.sources],
  );
  const filteredSources = useMemo(
    () =>
      plan.sources.filter((source) => {
        if (selectedSourceId && source.id !== selectedSourceId) {
          return false;
        }
        if (providerFilter !== "all" && source.source_name !== providerFilter) {
          return false;
        }
        if (trustFilter !== "all" && source.trust_level !== trustFilter) {
          return false;
        }
        if (classFilter !== "all" && source.evidence_type !== classFilter) {
          return false;
        }
        return true;
      }),
    [classFilter, plan.sources, providerFilter, selectedSourceId, trustFilter],
  );

  async function handleShareLink() {
    if (!runId) {
      return;
    }
    const shareUrl = `${window.location.origin}${window.location.pathname}?run=${runId}`;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setLinkCopied(true);
      window.history.replaceState(null, "", `?run=${runId}`);
      window.setTimeout(() => setLinkCopied(false), 1800);
    } catch {
      setReviewError("Unable to copy run link from this browser session.");
    }
  }

  async function handleSubmitReview() {
    if (!runId || reviewComment.trim().length < 8) {
      setReviewError("Add a short evidence-grounded review note before submitting.");
      return;
    }
    setReviewSubmitting(true);
    setReviewError(null);
    try {
      const confidenceValue =
        reviewConfidenceOverride.trim().length === 0 ? null : Number.parseFloat(reviewConfidenceOverride);
      const payload: ReviewSubmissionRequest = {
        reviewer_name: reviewerName.trim() || null,
        summary: reviewSummary.trim() || null,
        review_state: reviewAction === "approve" ? "approved_for_proposal" : "reviewed",
        items: [
          {
            target_type: reviewTargetType,
            target_key: reviewTargetKey.trim() || "overview",
            action: reviewAction,
            comment: reviewComment.trim(),
            replacement_text: reviewReplacement.trim() || null,
            confidence_override: Number.isFinite(confidenceValue ?? NaN) ? confidenceValue : null,
          },
        ],
      };
      const response = await submitReview(runId, payload);
      setLocalReviewState(response.review.review_state);
      setLocalReviews((current) => [response.review, ...current]);
      setReviewSummary("");
      setReviewComment("");
      setReviewReplacement("");
      setReviewConfidenceOverride("");
      if (onReviewSubmitted) {
        await onReviewSubmitted();
      }
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Unable to submit review");
    } finally {
      setReviewSubmitting(false);
    }
  }

  async function handleRevise() {
    if (!onRevise) {
      return;
    }
    setRevisionSubmitting(true);
    setReviewError(null);
    try {
      await onRevise();
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Unable to revise plan");
    } finally {
      setRevisionSubmitting(false);
    }
  }

  async function handleMarkAnchor() {
    if (!onMarkPresentationAnchor) {
      return;
    }
    setAnchorSubmitting(true);
    setReviewError(null);
    try {
      await onMarkPresentationAnchor();
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Unable to mark presentation anchor");
    } finally {
      setAnchorSubmitting(false);
    }
  }

  function jumpToSource(sourceId: string) {
    setSelectedSourceId(sourceId);
    setActiveTab("Sources");
  }

  return (
    <section className="enter-up rounded-md border border-zinc-200 bg-white shadow-crisp">
      <div className="border-b border-zinc-200 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">{plan.status_label}</p>
            <h2 className="mt-1 text-2xl font-semibold tracking-normal text-zinc-950">{plan.plan_title}</h2>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Badge tone="amber">{humanizeReviewState(localReviewState)}</Badge>
              <Badge tone={runModeTone(runMode)}>{humanizeRunMode(runMode)}</Badge>
              {usedSeedData && <Badge tone="amber">Seeded evidence used</Badge>}
              {isPresentationAnchor && <Badge tone="blue">Presentation anchor</Badge>}
              {revisionNumber > 0 && <Badge>Revision {revisionNumber}</Badge>}
              {plan.memory_applied.length > 0 && <Badge tone="blue">{plan.memory_applied.length} prior reviewed signals applied</Badge>}
              {plan.quality_summary && <ConfidenceBadge value={plan.quality_summary.operational_readiness} />}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {runId && (
              <>
                <ActionLink href={exportJsonUrl(runId)} label="JSON" />
                <ActionLink href={exportPdfUrl(runId)} label="PDF" />
                <ActionLink href={exportCitationsUrl(runId)} label="Citations" />
                <ActionLink href={exportProcurementUrl(runId)} label="Procurement" />
                <button
                  type="button"
                  onClick={handleShareLink}
                  className="inline-flex min-h-10 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium text-zinc-800 hover:border-zinc-950"
                >
                  <Link2 className="h-4 w-4" />
                  {linkCopied ? "Link copied" : "Share run"}
                </button>
                <button
                  type="button"
                  onClick={() => void handleMarkAnchor()}
                  disabled={!runId || anchorSubmitting}
                  className="inline-flex min-h-10 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium text-zinc-800 hover:border-zinc-950 disabled:cursor-not-allowed disabled:text-zinc-400"
                >
                  <Star className="h-4 w-4" />
                  {isPresentationAnchor ? "Presentation anchor" : anchorSubmitting ? "Saving anchor..." : "Set anchor"}
                </button>
              </>
            )}
            <Badge tone="amber">Expert review required</Badge>
          </div>
        </div>

        {plan.quality_summary && (
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <MetricCard label="Operational readiness" value={plan.quality_summary.operational_readiness} />
            <MetricCard label="Literature confidence" value={plan.quality_summary.literature_confidence} />
            <MetricCard label="Protocol confidence" value={plan.quality_summary.protocol_confidence} />
            <MetricCard label="Materials confidence" value={plan.quality_summary.materials_confidence} />
            <MetricCard label="Budget confidence" value={plan.quality_summary.budget_confidence} />
            <MetricCard label="Evidence completeness" value={plan.quality_summary.evidence_completeness} />
          </div>
        )}

        {(plan.memory_applied.length > 0 || runEvents.length > 0) && (
          <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
            {plan.memory_applied.length > 0 && (
              <div className="rounded-md border border-cyan-200 bg-cyan-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-cyan-800">Review memory</p>
                <div className="mt-3 space-y-2">
                  {plan.memory_applied.slice(0, 3).map((item) => (
                    <div key={`${item.review_session_id}-${item.target_key}`} className="rounded-md border border-cyan-200 bg-white p-3 text-sm text-zinc-800">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone="blue">{item.target_type}</Badge>
                        <Badge tone="amber">{item.action}</Badge>
                        <Badge>{item.target_key}</Badge>
                      </div>
                      <p className="mt-2 leading-6">{item.note}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {runEvents.length > 0 && (
              <div className="rounded-md border border-zinc-200 bg-zinc-50 p-4">
                <div className="flex items-center gap-2">
                  <History className="h-4 w-4 text-zinc-600" />
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-600">Run timeline</p>
                </div>
                <div className="mt-3 space-y-2">
                  {runEvents.slice(0, 4).map((event) => (
                    <div key={event.id} className="rounded-md border border-zinc-200 bg-white p-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge>{event.stage}</Badge>
                        <Badge tone={event.status === "completed" ? "green" : "amber"}>{event.status}</Badge>
                      </div>
                      <p className="mt-2 leading-6 text-zinc-700">{event.message}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex gap-2 overflow-x-auto border-b border-zinc-200 px-3 py-2">
        {tabLabels.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`min-h-10 shrink-0 rounded-md px-3 text-sm font-medium transition ${
              activeTab === tab ? "bg-zinc-950 text-white" : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="p-5">
        {activeTab === "Overview" && (
          <SectionView section={plan.overview} sourceById={sourceById} onSelectSource={jumpToSource} />
        )}
        {activeTab === "Literature QC" && (
          <LiteratureQcPanel parsed={parsedHypothesis ?? fallbackParsedHypothesis(plan)} qc={plan.literature_qc} />
        )}
        {activeTab === "Study Design" && (
          <SectionView section={plan.study_design} sourceById={sourceById} onSelectSource={jumpToSource} />
        )}
        {activeTab === "Protocol" && (
          <ProtocolView steps={plan.protocol} sourceById={sourceById} onSelectSource={jumpToSource} />
        )}
        {activeTab === "Materials" && (
          <MaterialsView materials={plan.materials} sourceById={sourceById} onSelectSource={jumpToSource} />
        )}
        {activeTab === "Budget" && (
          <BudgetView budget={plan.budget} sourceById={sourceById} onSelectSource={jumpToSource} />
        )}
        {activeTab === "Timeline" && (
          <SectionView section={plan.timeline} sourceById={sourceById} onSelectSource={jumpToSource} />
        )}
        {activeTab === "Validation" && (
          <SectionView section={plan.validation} sourceById={sourceById} onSelectSource={jumpToSource} />
        )}
        {activeTab === "Risks" && (
          <SectionView section={plan.risks} sourceById={sourceById} warning onSelectSource={jumpToSource} />
        )}
        {activeTab === "Sources" && (
          <SourcesView
            sources={filteredSources}
            sourceUsage={sourceUsage}
            selectedSourceId={selectedSourceId}
            providerFilter={providerFilter}
            trustFilter={trustFilter}
            classFilter={classFilter}
            providerOptions={providerOptions}
            onProviderFilter={setProviderFilter}
            onTrustFilter={setTrustFilter}
            onClassFilter={setClassFilter}
            onClearSelected={() => setSelectedSourceId(null)}
          />
        )}
        {activeTab === "Comparison" && (
          <ComparisonView
            comparison={comparison}
            runMode={runMode}
            parentRunId={parentRunId}
            revisionNumber={revisionNumber}
          />
        )}
        {activeTab === "Review" && (
          <ReviewView
            runId={runId}
            reviewState={localReviewState}
            runMode={runMode}
            revisionNumber={revisionNumber}
            reviews={localReviews}
            reviewerName={reviewerName}
            reviewSummary={reviewSummary}
            reviewTargetType={reviewTargetType}
            reviewTargetKey={reviewTargetKey}
            reviewAction={reviewAction}
            reviewComment={reviewComment}
            reviewReplacement={reviewReplacement}
            reviewConfidenceOverride={reviewConfidenceOverride}
            submitting={reviewSubmitting}
            error={reviewError}
            onReviewerName={setReviewerName}
            onReviewSummary={setReviewSummary}
            onTargetType={setReviewTargetType}
            onTargetKey={setReviewTargetKey}
            onAction={setReviewAction}
            onComment={setReviewComment}
            onReplacement={setReviewReplacement}
            onConfidenceOverride={setReviewConfidenceOverride}
            onSubmit={handleSubmitReview}
            onRevise={handleRevise}
            revising={revisionSubmitting}
          />
        )}
      </div>
    </section>
  );
}

function fallbackParsedHypothesis(plan: ExperimentPlan): ParsedHypothesis {
  return {
    original_text: plan.overview.bullets[0] ?? plan.plan_title,
    domain: plan.plan_title,
    domain_route: "cell_biology",
    scientific_system: null,
    model_or_organism: null,
    organism_or_system: null,
    intervention: null,
    comparator: null,
    outcome_metric: null,
    success_threshold: null,
    outcome: null,
    effect_size: null,
    mechanism: null,
    literature_query_terms: [],
    protocol_query_terms: [],
    supplier_material_query_terms: [],
    key_terms: [],
    safety_notes: [],
  };
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
      <div className="mt-2 flex items-center gap-2">
        <ConfidenceBadge value={value} />
      </div>
    </div>
  );
}

function ActionLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      className="inline-flex min-h-10 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium text-zinc-800 hover:border-zinc-950"
    >
      <Download className="h-4 w-4" />
      {label}
    </a>
  );
}

function SectionView({
  section,
  sourceById,
  warning = false,
  onSelectSource,
}: {
  section: ExperimentPlanSection;
  sourceById: Map<string, EvidenceSource>;
  warning?: boolean;
  onSelectSource: (sourceId: string) => void;
}) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <ConfidenceBadge value={section.confidence} />
        {section.expert_review_required && <Badge tone={warning ? "red" : "amber"}>Expert review</Badge>}
      </div>
      <div>
        <h3 className="text-lg font-semibold text-zinc-950">{section.title}</h3>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-700">{section.summary}</p>
      </div>
      <ul className="space-y-3">
        {section.bullets.map((bullet) => (
          <li key={bullet} className="flex gap-3 text-sm leading-6 text-zinc-800">
            <ShieldCheck className="mt-1 h-4 w-4 shrink-0 text-emerald-700" />
            <span>{bullet}</span>
          </li>
        ))}
      </ul>
      <SourceChips ids={section.evidence_source_ids} sourceById={sourceById} onSelectSource={onSelectSource} />
    </div>
  );
}

function ProtocolView({
  steps,
  sourceById,
  onSelectSource,
}: {
  steps: ProtocolStep[];
  sourceById: Map<string, EvidenceSource>;
  onSelectSource: (sourceId: string) => void;
}) {
  return (
    <div className="space-y-5">
      {steps.map((step) => (
        <article key={step.step_number} className="rounded-md border border-zinc-200 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-base font-semibold text-zinc-950">
              {step.step_number}. {step.title}
            </h3>
            <div className="flex flex-wrap gap-2">
              <ConfidenceBadge value={step.confidence} />
              {step.expert_review_required && <Badge tone="amber">Expert review</Badge>}
            </div>
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-700">{step.purpose}</p>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Actions</p>
              <ul className="mt-2 space-y-2 text-sm leading-6 text-zinc-800">
                {step.actions.map((action) => (
                  <li key={action}>- {action}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Critical Parameters</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {step.critical_parameters.map((parameter) => (
                  <Badge key={parameter}>{parameter}</Badge>
                ))}
              </div>
              {step.materials.length > 0 && (
                <>
                  <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-zinc-500">Materials</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {step.materials.map((material) => (
                      <Badge key={material} tone="blue">
                        {material}
                      </Badge>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
          {step.review_reason && (
            <div className="mt-4 flex gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{step.review_reason}</span>
            </div>
          )}
          <div className="mt-4">
            <SourceChips ids={step.evidence_source_ids} sourceById={sourceById} onSelectSource={onSelectSource} />
          </div>
        </article>
      ))}
    </div>
  );
}

function MaterialsView({
  materials,
  sourceById,
  onSelectSource,
}: {
  materials: MaterialItem[];
  sourceById: Map<string, EvidenceSource>;
  onSelectSource: (sourceId: string) => void;
}) {
  return (
    <div className="overflow-hidden rounded-md border border-zinc-200">
      <div className="grid grid-cols-[1.2fr_1fr_0.9fr_0.8fr] gap-3 bg-zinc-100 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 max-lg:hidden">
        <span>Material</span>
        <span>Vendor</span>
        <span>Catalog</span>
        <span>Procurement</span>
      </div>
      {materials.map((item) => (
        <div key={`${item.name}-${item.role}`} className="grid gap-3 border-t border-zinc-200 px-4 py-4 text-sm lg:grid-cols-[1.2fr_1fr_0.9fr_0.8fr]">
          <div>
            <p className="font-semibold text-zinc-950">{item.name}</p>
            <p className="mt-1 leading-6 text-zinc-600">{item.role}</p>
            <p className="mt-1 leading-6 text-zinc-500">{item.notes}</p>
            <div className="mt-2 lg:hidden">
              <SourceChips ids={item.evidence_source_ids} sourceById={sourceById} onSelectSource={onSelectSource} />
            </div>
          </div>
          <span className="break-words text-zinc-700">{item.vendor ?? "Not retrieved"}</span>
          <span className="break-words text-zinc-700">{item.catalog_number ?? "Null"}</span>
          <div className="space-y-2">
            <Badge tone={item.requires_procurement_check ? "amber" : "green"}>
              {item.requires_procurement_check ? "Requires procurement check" : "Source-backed"}
            </Badge>
            {item.price_status === "contact_supplier" && <Badge tone="blue">Contact supplier</Badge>}
            <p className="text-xs text-zinc-500">
              Price: {item.price ?? "Null"} | Status: {humanizePriceStatus(item.price_status)}
            </p>
            <div className="hidden lg:block">
              <SourceChips ids={item.evidence_source_ids} sourceById={sourceById} onSelectSource={onSelectSource} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function BudgetView({
  budget,
  sourceById,
  onSelectSource,
}: {
  budget: BudgetSummary;
  sourceById: Map<string, EvidenceSource>;
  onSelectSource: (sourceId: string) => void;
}) {
  return (
    <div className="space-y-5">
      <SectionView
        section={{
          title: budget.title,
          summary: budget.summary,
          bullets: budget.items.map((item) => `${item.name}: ${item.requires_procurement_check ? "requires procurement check" : "verified"}`),
          evidence_source_ids: budget.evidence_source_ids,
          confidence: budget.confidence,
          expert_review_required: budget.expert_review_required,
        }}
        sourceById={sourceById}
        onSelectSource={onSelectSource}
      />
      <MaterialsView materials={budget.items} sourceById={sourceById} onSelectSource={onSelectSource} />
    </div>
  );
}

function SourcesView({
  sources,
  sourceUsage,
  selectedSourceId,
  providerFilter,
  trustFilter,
  classFilter,
  providerOptions,
  onProviderFilter,
  onTrustFilter,
  onClassFilter,
  onClearSelected,
}: {
  sources: EvidenceSource[];
  sourceUsage: Map<string, string[]>;
  selectedSourceId: string | null;
  providerFilter: string;
  trustFilter: string;
  classFilter: string;
  providerOptions: string[];
  onProviderFilter: (value: string) => void;
  onTrustFilter: (value: string) => void;
  onClassFilter: (value: string) => void;
  onClearSelected: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 rounded-md border border-zinc-200 bg-zinc-50 p-4 md:grid-cols-4">
        <FilterSelect label="Provider" value={providerFilter} onChange={onProviderFilter} options={providerOptions} />
        <FilterSelect label="Trust level" value={trustFilter} onChange={onTrustFilter} options={["all", "high", "medium", "low"]} />
        <FilterSelect
          label="Evidence class"
          value={classFilter}
          onChange={onClassFilter}
          options={["all", "exact_match", "close_match", "adjacent_method", "generic_method", "supplier_reference", "safety_or_standard", "assumption"]}
        />
        <div className="flex items-end">
          <button
            type="button"
            onClick={onClearSelected}
            className="inline-flex min-h-11 items-center justify-center rounded-md border border-zinc-300 bg-white px-4 text-sm font-medium text-zinc-800 hover:border-zinc-950"
          >
            {selectedSourceId ? "Clear focused source" : "Show all sources"}
          </button>
        </div>
      </div>

      {sources.length === 0 ? (
        <div className="rounded-md border border-zinc-200 p-5 text-sm text-zinc-500">No sources match the active filters.</div>
      ) : (
        sources.map((source) => (
          <article
            key={source.id}
            className={`rounded-md border p-4 ${selectedSourceId === source.id ? "border-emerald-300 bg-emerald-50/40" : "border-zinc-200"}`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge>{source.id}</Badge>
              <Badge tone={trustLevelTone(source.trust_level)}>{humanizeTrustLevel(source.trust_level)}</Badge>
              <Badge tone={trustTierTone(source.trust_tier)}>{humanizeTrustTier(source.trust_tier)}</Badge>
              <Badge tone={evidenceTone(source)}>{humanizeEvidenceClass(source)}</Badge>
              <ConfidenceBadge value={source.confidence} />
            </div>
            <h3 className="mt-2 text-sm font-semibold text-zinc-950">{source.title}</h3>
            <p className="mt-2 text-sm leading-6 text-zinc-700">{source.snippet}</p>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
              <MetaField label="Provider" value={source.source_name} />
              <MetaField label="Trust level" value={humanizeTrustLevel(source.trust_level)} />
              <MetaField label="Provenance" value={humanizeTrustTier(source.trust_tier)} />
              <MetaField label="Evidence class" value={humanizeEvidenceClass(source)} />
              <MetaField label="Used in sections" value={(sourceUsage.get(source.id) ?? ["Not referenced"]).join(", ")} />
              <MetaField label="Confidence" value={`${Math.round(source.confidence * 100)}%`} />
              <MetaField label="URL" value={source.url ?? "Not available"} />
            </dl>
            {source.url && (
              <a className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-emerald-700" href={source.url} target="_blank" rel="noreferrer">
                Open source
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </article>
        ))
      )}
    </div>
  );
}

function ReviewView({
  runId,
  reviewState,
  runMode,
  revisionNumber,
  reviews,
  reviewerName,
  reviewSummary,
  reviewTargetType,
  reviewTargetKey,
  reviewAction,
  reviewComment,
  reviewReplacement,
  reviewConfidenceOverride,
  submitting,
  error,
  onReviewerName,
  onReviewSummary,
  onTargetType,
  onTargetKey,
  onAction,
  onComment,
  onReplacement,
  onConfidenceOverride,
  onSubmit,
  onRevise,
  revising,
}: {
  runId: string | null;
  reviewState: ReviewState;
  runMode: RunMode;
  revisionNumber: number;
  reviews: ReviewSessionRecord[];
  reviewerName: string;
  reviewSummary: string;
  reviewTargetType: ReviewSubmissionRequest["items"][number]["target_type"];
  reviewTargetKey: string;
  reviewAction: ReviewSubmissionRequest["items"][number]["action"];
  reviewComment: string;
  reviewReplacement: string;
  reviewConfidenceOverride: string;
  submitting: boolean;
  error: string | null;
  onReviewerName: (value: string) => void;
  onReviewSummary: (value: string) => void;
  onTargetType: (value: ReviewSubmissionRequest["items"][number]["target_type"]) => void;
  onTargetKey: (value: string) => void;
  onAction: (value: ReviewSubmissionRequest["items"][number]["action"]) => void;
  onComment: (value: string) => void;
  onReplacement: (value: string) => void;
  onConfidenceOverride: (value: string) => void;
  onSubmit: () => Promise<void>;
  onRevise: () => Promise<void>;
  revising: boolean;
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
      <div className="rounded-md border border-zinc-200 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="amber">{humanizeReviewState(reviewState)}</Badge>
          <Badge tone={runModeTone(runMode)}>{humanizeRunMode(runMode)}</Badge>
          <Badge>{reviews.length} review session{reviews.length === 1 ? "" : "s"}</Badge>
          {revisionNumber > 0 && <Badge>Revision {revisionNumber}</Badge>}
        </div>
        <h3 className="mt-3 text-lg font-semibold text-zinc-950">Scientist review</h3>
        <p className="mt-2 text-sm leading-6 text-zinc-600">
          Capture expert corrections in structured form so similar future plans can reuse the same operational judgment.
        </p>

        {!runId && <p className="mt-4 text-sm text-zinc-500">Generate a run before review can be submitted.</p>}

        <div className="mt-4 grid gap-3">
          <Input label="Reviewer name" value={reviewerName} onChange={onReviewerName} placeholder="Scientist or operator" />
          <Input label="Review summary" value={reviewSummary} onChange={onReviewSummary} placeholder="What changed and why" />
          <div className="grid gap-3 md:grid-cols-2">
            <SelectField
              label="Target type"
              value={reviewTargetType}
              onChange={(value) => onTargetType(value as ReviewSubmissionRequest["items"][number]["target_type"])}
              options={["section", "protocol_step", "material", "budget_item", "timeline", "validation", "risk"]}
            />
            <SelectField
              label="Action"
              value={reviewAction}
              onChange={(value) => onAction(value as ReviewSubmissionRequest["items"][number]["action"])}
              options={["comment", "edit", "replace", "approve", "reject", "unrealistic", "missing_dependency"]}
            />
          </div>
          <Input label="Target key" value={reviewTargetKey} onChange={onTargetKey} placeholder="overview, protocol.1, material:Trehalose" />
          <TextArea label="Review note" value={reviewComment} onChange={onComment} placeholder="Explain the scientific correction or operational concern." />
          <TextArea label="Replacement text" value={reviewReplacement} onChange={onReplacement} placeholder="Optional corrected wording or parameter." />
          <Input
            label="Confidence override"
            value={reviewConfidenceOverride}
            onChange={onConfidenceOverride}
            placeholder="0.0 to 1.0"
          />
          {error && <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
          <button
            type="button"
            disabled={!runId || submitting}
            onClick={() => void onSubmit()}
            className="inline-flex min-h-11 items-center justify-center rounded-md bg-zinc-950 px-4 text-sm font-semibold text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
          >
            {submitting ? "Submitting review..." : "Submit structured review"}
          </button>
          <button
            type="button"
            disabled={!runId || reviews.length === 0 || revising}
            onClick={() => void onRevise()}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-emerald-300 bg-emerald-50 px-4 text-sm font-semibold text-emerald-900 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:border-zinc-200 disabled:bg-zinc-100 disabled:text-zinc-400"
          >
            <RotateCcw className="h-4 w-4" />
            {revising ? "Generating revised plan..." : "Generate revised plan"}
          </button>
        </div>
      </div>

      <div className="space-y-4">
        {reviews.length === 0 ? (
          <div className="rounded-md border border-zinc-200 p-4 text-sm text-zinc-500">No reviews have been recorded for this run yet.</div>
        ) : (
          reviews.map((review) => (
            <article key={review.id} className="rounded-md border border-zinc-200 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="amber">{humanizeReviewState(review.review_state)}</Badge>
                {review.reviewer_name && <Badge>{review.reviewer_name}</Badge>}
                <Badge>{review.items.length} items</Badge>
              </div>
              {review.summary && <p className="mt-3 text-sm leading-6 text-zinc-700">{review.summary}</p>}
              <div className="mt-3 space-y-3">
                {review.items.map((item) => (
                  <div key={item.id} className="rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge>{item.target_type}</Badge>
                      <Badge tone="amber">{item.action}</Badge>
                      <Badge tone="blue">{item.target_key}</Badge>
                    </div>
                    {item.comment && <p className="mt-2 leading-6 text-zinc-700">{item.comment}</p>}
                    {item.replacement_text && (
                      <p className="mt-2 rounded-md border border-cyan-200 bg-cyan-50 p-2 text-cyan-900">{item.replacement_text}</p>
                    )}
                  </div>
                ))}
              </div>
            </article>
          ))
        )}
      </div>
    </div>
  );
}

function ComparisonView({
  comparison,
  runMode,
  parentRunId,
  revisionNumber,
}: {
  comparison: RunComparisonResponse | null;
  runMode: RunMode;
  parentRunId: string | null;
  revisionNumber: number;
}) {
  if (!comparison) {
    return (
      <div className="rounded-md border border-zinc-200 p-5 text-sm text-zinc-500">
        {parentRunId || revisionNumber > 0
          ? "Comparison will appear once both baseline and revised plan artifacts are available."
          : "Generate a revised plan after review to unlock before-and-after comparison."}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="rounded-md border border-zinc-200 bg-zinc-50 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <GitCompare className="h-4 w-4 text-zinc-600" />
          <Badge tone={runModeTone(runMode)}>{humanizeRunMode(runMode)}</Badge>
          {revisionNumber > 0 && <Badge>Revision {revisionNumber}</Badge>}
        </div>
        <h3 className="mt-3 text-lg font-semibold text-zinc-950">Before and after review</h3>
        <p className="mt-2 text-sm leading-6 text-zinc-600">
          Compare the baseline plan with the revised plan generated after structured scientist feedback.
        </p>
        <div className="mt-4 space-y-2">
          {comparison.summary.map((item) => (
            <div key={item} className="rounded-md border border-zinc-200 bg-white p-3 text-sm text-zinc-800">
              {item}
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {comparison.metrics.map((item) => (
          <ComparisonMetricCard key={item.label} metric={item} />
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <ChangeList title="Protocol changes" items={comparison.protocol_changes} />
        <ChangeList title="Material changes" items={comparison.material_changes} />
        <ChangeList title="Budget changes" items={comparison.budget_changes} />
      </div>
    </div>
  );
}

function ComparisonMetricCard({ metric }: { metric: ComparisonMetricRecord }) {
  const tone = metric.delta === null ? "neutral" : metric.delta >= 0 ? "green" : "amber";
  return (
    <div className="rounded-md border border-zinc-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-semibold text-zinc-950">{metric.label}</p>
        <Badge tone={tone}>{metric.delta === null ? "n/a" : `${metric.delta >= 0 ? "+" : ""}${Math.round(metric.delta * 100)} pts`}</Badge>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Baseline</p>
          <p className="mt-1 text-zinc-800">{metric.baseline}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Revised</p>
          <p className="mt-1 text-zinc-800">{metric.current}</p>
        </div>
      </div>
    </div>
  );
}

function ChangeList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-md border border-zinc-200 p-4">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">{title}</h3>
      <div className="mt-3 space-y-2">
        {items.length === 0 ? (
          <p className="text-sm text-zinc-500">No major changes captured yet.</p>
        ) : (
          items.map((item) => (
            <div key={item} className="rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-800">
              {item}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function SourceChips({
  ids,
  sourceById,
  onSelectSource,
}: {
  ids: string[];
  sourceById: Map<string, EvidenceSource>;
  onSelectSource: (sourceId: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {ids.map((id) => {
        const source = sourceById.get(id);
        return (
          <button key={id} type="button" onClick={() => onSelectSource(id)} className="rounded-full">
            <Badge tone={source?.trust_tier === "inferred" ? "red" : source?.trust_level === "high" ? "green" : "neutral"}>
              {id}
            </Badge>
          </button>
        );
      })}
    </div>
  );
}

function buildSourceUsage(plan: ExperimentPlan): Map<string, string[]> {
  const usage = new Map<string, Set<string>>();

  const track = (sourceIds: string[], label: string) => {
    sourceIds.forEach((sourceId) => {
      if (!usage.has(sourceId)) {
        usage.set(sourceId, new Set());
      }
      usage.get(sourceId)!.add(label);
    });
  };

  track(plan.overview.evidence_source_ids, "Overview");
  plan.literature_qc.references.forEach((source) => track([source.id], "Literature QC"));
  track(plan.study_design.evidence_source_ids, "Study Design");
  plan.protocol.forEach((step) => track(step.evidence_source_ids, `Protocol step ${step.step_number}`));
  plan.materials.forEach((material) => track(material.evidence_source_ids, `Materials: ${material.name}`));
  track(plan.budget.evidence_source_ids, "Budget");
  plan.budget.items.forEach((item) => track(item.evidence_source_ids, `Budget: ${item.name}`));
  track(plan.timeline.evidence_source_ids, "Timeline");
  track(plan.validation.evidence_source_ids, "Validation");
  track(plan.risks.evidence_source_ids, "Risks");

  return new Map(Array.from(usage.entries()).map(([sourceId, labels]) => [sourceId, Array.from(labels)]));
}

function humanizeTrustTier(trustTier: EvidenceSource["trust_tier"]) {
  const labels: Record<EvidenceSource["trust_tier"], string> = {
    literature_database: "Literature database",
    supplier_documentation: "Supplier documentation",
    community_protocol: "Community source",
    scientific_standard: "Scientific standard",
    inferred: "Inferred / expert review required",
  };
  return labels[trustTier];
}

function humanizeTrustLevel(trustLevel: EvidenceSource["trust_level"]) {
  const labels: Record<EvidenceSource["trust_level"], string> = {
    high: "High trust",
    medium: "Medium trust",
    low: "Low trust",
  };
  return labels[trustLevel];
}

function humanizeEvidenceClass(source: EvidenceSource) {
  if (source.trust_tier === "community_protocol") {
    return "Community source";
  }
  if (source.trust_tier === "inferred" || source.evidence_type === "assumption") {
    return "Inferred / expert review required";
  }
  if (source.evidence_type === "adjacent_method" || source.evidence_type === "close_match") {
    return "Adjacent evidence";
  }
  if (
    source.trust_level === "high" ||
    source.evidence_type === "exact_match" ||
    source.evidence_type === "supplier_reference"
  ) {
    return "Source-backed";
  }
  if (source.trust_tier === "scientific_standard" || source.evidence_type === "safety_or_standard") {
    return "Scientific standard";
  }
  if (source.evidence_type === "generic_method") {
    return "Generic method";
  }
  return "Source-backed";
}

function humanizeReviewState(reviewState: ReviewState) {
  const labels: Record<ReviewState, string> = {
    generated: "Generated",
    reviewed: "Reviewed",
    revised: "Revised",
    approved_for_proposal: "Approved for proposal",
  };
  return labels[reviewState];
}

function humanizeRunMode(runMode: RunMode) {
  const labels: Record<RunMode, string> = {
    fully_live: "Fully live",
    degraded_live: "Degraded live",
    demo_fallback: "Demo fallback",
  };
  return labels[runMode];
}

function runModeTone(runMode: RunMode): "green" | "amber" | "red" | "blue" {
  if (runMode === "fully_live") {
    return "green";
  }
  if (runMode === "demo_fallback") {
    return "amber";
  }
  return "blue";
}

function trustTierTone(trustTier: EvidenceSource["trust_tier"]): "green" | "amber" | "red" | "blue" {
  if (trustTier === "supplier_documentation" || trustTier === "literature_database" || trustTier === "scientific_standard") {
    return "green";
  }
  if (trustTier === "community_protocol") {
    return "blue";
  }
  return "red";
}

function trustLevelTone(trustLevel: EvidenceSource["trust_level"]): "green" | "amber" | "red" | "blue" {
  if (trustLevel === "high") {
    return "green";
  }
  if (trustLevel === "medium") {
    return "amber";
  }
  return "red";
}

function evidenceTone(source: EvidenceSource): "green" | "amber" | "red" | "blue" {
  if (source.evidence_type === "adjacent_method" || source.evidence_type === "close_match") {
    return "amber";
  }
  if (source.trust_tier === "community_protocol") {
    return "blue";
  }
  if (source.trust_tier === "scientific_standard" || source.evidence_type === "safety_or_standard") {
    return "green";
  }
  if (source.trust_tier === "inferred" || source.evidence_type === "assumption") {
    return "red";
  }
  return "green";
}

function humanizePriceStatus(status: MaterialItem["price_status"]) {
  const labels: Record<MaterialItem["price_status"], string> = {
    visible_price: "visible price",
    requires_procurement_check: "requires procurement check",
    contact_supplier: "contact supplier",
  };
  return labels[status];
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 min-h-11 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-zinc-950 focus:ring-2 focus:ring-emerald-200"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option === "all" ? "All" : option}
          </option>
        ))}
      </select>
    </label>
  );
}

function Input({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</span>
      <input
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 min-h-11 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-zinc-950 focus:ring-2 focus:ring-emerald-200"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  return <FilterSelect label={label} value={value} onChange={onChange} options={options} />;
}

function TextArea({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</span>
      <textarea
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 min-h-28 w-full rounded-md border border-zinc-300 bg-white px-3 py-3 text-sm outline-none focus:border-zinc-950 focus:ring-2 focus:ring-emerald-200"
      />
    </label>
  );
}

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-1 break-words text-zinc-800">{value}</dd>
    </div>
  );
}
