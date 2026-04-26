import { AlertTriangle, ExternalLink, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";

import type {
  BudgetSummary,
  EvidenceSource,
  ExperimentPlan,
  ExperimentPlanSection,
  MaterialItem,
  ParsedHypothesis,
  ProtocolStep,
} from "../types/api";
import { Badge, ConfidenceBadge } from "./Badge";
import { LiteratureQcPanel } from "./LiteratureQcPanel";

interface PlanTabsProps {
  plan: ExperimentPlan;
  parsedHypothesis: ParsedHypothesis | null;
}

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
] as const;

type Tab = (typeof tabLabels)[number];

export function PlanTabs({ plan, parsedHypothesis }: PlanTabsProps) {
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const sourceById = useMemo(() => new Map(plan.sources.map((source) => [source.id, source])), [plan.sources]);
  const sourceUsage = useMemo(() => buildSourceUsage(plan), [plan]);

  return (
    <section className="enter-up rounded-md border border-zinc-200 bg-white shadow-crisp">
      <div className="border-b border-zinc-200 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">{plan.status_label}</p>
            <h2 className="mt-1 text-2xl font-semibold tracking-normal text-zinc-950">{plan.plan_title}</h2>
          </div>
          <Badge tone="amber">Expert review required</Badge>
        </div>
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
        {activeTab === "Overview" && <SectionView section={plan.overview} sourceById={sourceById} />}
        {activeTab === "Literature QC" && (
          <LiteratureQcPanel
            parsed={parsedHypothesis ?? fallbackParsedHypothesis(plan)}
            qc={plan.literature_qc}
          />
        )}
        {activeTab === "Study Design" && <SectionView section={plan.study_design} sourceById={sourceById} />}
        {activeTab === "Protocol" && <ProtocolView steps={plan.protocol} sourceById={sourceById} />}
        {activeTab === "Materials" && <MaterialsView materials={plan.materials} sourceById={sourceById} />}
        {activeTab === "Budget" && <BudgetView budget={plan.budget} sourceById={sourceById} />}
        {activeTab === "Timeline" && <SectionView section={plan.timeline} sourceById={sourceById} />}
        {activeTab === "Validation" && <SectionView section={plan.validation} sourceById={sourceById} />}
        {activeTab === "Risks" && <SectionView section={plan.risks} sourceById={sourceById} warning />}
        {activeTab === "Sources" && <SourcesView sources={plan.sources} sourceUsage={sourceUsage} />}
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

function SectionView({
  section,
  sourceById,
  warning = false,
}: {
  section: ExperimentPlanSection;
  sourceById: Map<string, EvidenceSource>;
  warning?: boolean;
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
      <SourceChips ids={section.evidence_source_ids} sourceById={sourceById} />
    </div>
  );
}

function ProtocolView({ steps, sourceById }: { steps: ProtocolStep[]; sourceById: Map<string, EvidenceSource> }) {
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
            <SourceChips ids={step.evidence_source_ids} sourceById={sourceById} />
          </div>
        </article>
      ))}
    </div>
  );
}

function MaterialsView({ materials, sourceById }: { materials: MaterialItem[]; sourceById: Map<string, EvidenceSource> }) {
  return (
    <div className="overflow-hidden rounded-md border border-zinc-200">
      <div className="grid grid-cols-[1.2fr_1fr_0.9fr_0.8fr] gap-3 bg-zinc-100 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 max-lg:hidden">
        <span>Material</span>
        <span>Vendor</span>
        <span>Catalog</span>
        <span>Procurement</span>
      </div>
      {materials.map((item) => (
        <div key={item.name} className="grid gap-3 border-t border-zinc-200 px-4 py-4 text-sm lg:grid-cols-[1.2fr_1fr_0.9fr_0.8fr]">
          <div>
            <p className="font-semibold text-zinc-950">{item.name}</p>
            <p className="mt-1 leading-6 text-zinc-600">{item.role}</p>
            <p className="mt-1 leading-6 text-zinc-500">{item.notes}</p>
            <div className="mt-2 lg:hidden">
              <SourceChips ids={item.evidence_source_ids} sourceById={sourceById} />
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
              <SourceChips ids={item.evidence_source_ids} sourceById={sourceById} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function BudgetView({ budget, sourceById }: { budget: BudgetSummary; sourceById: Map<string, EvidenceSource> }) {
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
      />
      <MaterialsView materials={budget.items} sourceById={sourceById} />
    </div>
  );
}

function SourcesView({ sources, sourceUsage }: { sources: EvidenceSource[]; sourceUsage: Map<string, string[]> }) {
  return (
    <div className="space-y-4">
      {sources.map((source) => (
        <article key={source.id} className="rounded-md border border-zinc-200 p-4">
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
      ))}
    </div>
  );
}

function SourceChips({ ids, sourceById }: { ids: string[]; sourceById: Map<string, EvidenceSource> }) {
  return (
    <div className="flex flex-wrap gap-2">
      {ids.map((id) => {
        const source = sourceById.get(id);
        return (
          <Badge key={id} tone={source?.trust_tier === "inferred" ? "red" : source?.trust_level === "high" ? "green" : "neutral"}>
            {id}
          </Badge>
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

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-1 break-words text-zinc-800">{value}</dd>
    </div>
  );
}
