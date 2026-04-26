import { AlertTriangle, ExternalLink } from "lucide-react";

import type { EvidenceSource, LiteratureQC, ParsedHypothesis } from "../types/api";
import { Badge, ConfidenceBadge } from "./Badge";

interface LiteratureQcPanelProps {
  parsed: ParsedHypothesis;
  qc: LiteratureQC;
}

const noveltyLabels: Record<LiteratureQC["novelty_signal"], string> = {
  exact_match_found: "Exact match found",
  similar_work_exists: "Similar work exists",
  not_found_in_searched_sources: "Not found in searched sources",
};

export function LiteratureQcPanel({ parsed, qc }: LiteratureQcPanelProps) {
  return (
    <section className="enter-up space-y-5">
      <div className="rounded-md border border-zinc-200 bg-white p-5 shadow-crisp">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={qc.novelty_signal === "exact_match_found" ? "green" : qc.novelty_signal === "similar_work_exists" ? "amber" : "red"}>
            {noveltyLabels[qc.novelty_signal]}
          </Badge>
          <ConfidenceBadge value={qc.confidence} />
        </div>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-zinc-700">{qc.rationale}</p>
        {qc.literature_synthesis && (
          <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600">{qc.literature_synthesis}</p>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          {qc.searched_sources.map((source) => (
            <Badge key={source}>{source}</Badge>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="rounded-md border border-zinc-200 bg-white p-5 shadow-crisp">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Parsed Hypothesis</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <Field label="Domain" value={parsed.domain} />
            <Field label="Scientific system" value={parsed.scientific_system} />
            <Field label="Model or organism" value={parsed.model_or_organism} />
            <Field label="Intervention" value={parsed.intervention} />
            <Field label="Comparator" value={parsed.comparator} />
            <Field label="Outcome metric" value={parsed.outcome_metric} />
            <Field label="Success threshold" value={parsed.success_threshold} />
          </dl>
          <QueryTerms label="Literature query terms" values={parsed.literature_query_terms} />
          <QueryTerms label="Protocol query terms" values={parsed.protocol_query_terms} />
          <QueryTerms label="Supplier/material query terms" values={parsed.supplier_material_query_terms} />
        </div>

        <div className="rounded-md border border-zinc-200 bg-white p-5 shadow-crisp">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">References</h2>
          <div className="mt-4 space-y-4">
            {qc.references.map((source) => (
              <article key={source.id} className="border-t border-zinc-100 pt-4 first:border-t-0 first:pt-0">
                <div className="flex flex-wrap items-center gap-2">
                  {sourceContextBadges(source).map((badge) => (
                    <Badge key={`${source.id}-${badge.label}`} tone={badge.tone}>
                      {badge.label}
                    </Badge>
                  ))}
                  <ConfidenceBadge value={source.confidence} />
                </div>
                <h3 className="mt-2 text-sm font-semibold leading-5 text-zinc-950">{source.title}</h3>
                <p className="mt-1 text-sm leading-6 text-zinc-600">{source.snippet}</p>
                {source.url ? (
                  <a
                    className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-emerald-700 hover:text-emerald-900"
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {source.source_name}
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                ) : (
                  <p className="mt-2 text-xs text-zinc-500">{source.source_name}</p>
                )}
              </article>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-md border border-zinc-200 bg-white p-5 shadow-crisp">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Provider Trace</h2>
        <div className="mt-4 space-y-3">
          {qc.provider_trace.length === 0 ? (
            <p className="text-sm text-zinc-500">No provider trace recorded for this run.</p>
          ) : (
            qc.provider_trace.map((entry) => (
              <article key={`${entry.provider}-${entry.query}-${entry.cached}`} className="rounded-md border border-zinc-200 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={entry.succeeded ? "green" : "red"}>{entry.provider}</Badge>
                  {entry.cached && <Badge tone="blue">cache hit</Badge>}
                  <Badge>{entry.result_count} results</Badge>
                </div>
                <p className="mt-2 text-sm leading-6 text-zinc-700">{entry.query}</p>
                {entry.error && <p className="mt-1 text-xs text-rose-700">{entry.error}</p>}
              </article>
            ))
          )}
        </div>
      </div>

      <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <div className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="space-y-1">
            {(qc.gaps.length > 0 ? qc.gaps : qc.evidence_gap_warnings).map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function sourceContextBadges(source: EvidenceSource): Array<{ label: string; tone: "green" | "amber" | "red" | "blue" }> {
  const badges: Array<{ label: string; tone: "green" | "amber" | "red" | "blue" }> = [];
  if (
    source.trust_level === "high" ||
    source.evidence_type === "exact_match" ||
    source.evidence_type === "supplier_reference"
  ) {
    badges.push({ label: "Source-backed", tone: "green" });
  }
  if (source.evidence_type === "adjacent_method" || source.evidence_type === "close_match") {
    badges.push({ label: "Adjacent evidence", tone: "amber" });
  }
  if (source.trust_tier === "community_protocol") {
    badges.push({ label: "Community source", tone: "blue" });
  }
  if (source.trust_tier === "inferred") {
    badges.push({ label: "Inferred / expert review required", tone: "red" });
  }
  return badges;
}

function QueryTerms({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="mt-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {values.length === 0 ? (
          <p className="text-sm text-zinc-500">Not specified</p>
        ) : (
          values.map((value) => (
            <Badge key={`${label}-${value}`} tone="blue">
              {value}
            </Badge>
          ))
        )}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-1 break-words text-zinc-900">{value ?? "Not specified"}</dd>
    </div>
  );
}
