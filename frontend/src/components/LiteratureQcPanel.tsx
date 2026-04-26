import { AlertTriangle, ChevronDown, ExternalLink } from "lucide-react";

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
  const references = qc.references.slice(0, 3);
  const evidenceNotes = qc.gaps.length > 0 ? qc.gaps : qc.evidence_gap_warnings;

  return (
    <section className="enter-up space-y-6">
      <div className="rounded-xl border border-zinc-200 bg-white p-6">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            tone={
              qc.novelty_signal === "exact_match_found"
                ? "green"
                : qc.novelty_signal === "similar_work_exists"
                  ? "amber"
                  : "red"
            }
          >
            {noveltyLabels[qc.novelty_signal]}
          </Badge>
          <ConfidenceBadge value={qc.confidence} />
        </div>
        <h2 className="mt-4 text-2xl font-semibold tracking-normal text-zinc-950">Literature QC</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-700">{qc.rationale}</p>
        {qc.literature_synthesis && (
          <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600">{truncateParagraph(qc.literature_synthesis, 420)}</p>
        )}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <div className="rounded-xl border border-zinc-200 bg-white p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">References</p>
              <p className="mt-1 text-sm text-zinc-500">Closest supporting literature from the configured search path.</p>
            </div>
            <span className="text-sm text-zinc-500">{references.length} shown</span>
          </div>

          <div className="mt-5 space-y-5">
            {references.length === 0 ? (
              <p className="text-sm text-zinc-500">No references were attached to this QC result.</p>
            ) : (
              references.map((source) => (
                <article key={source.id} className="border-t border-zinc-100 pt-5 first:border-t-0 first:pt-0">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                    <span className="font-medium text-zinc-800">{source.source_name}</span>
                    {source.year && <span>{source.year}</span>}
                    <span>{humanizeEvidenceLabel(source)}</span>
                    <ConfidenceBadge value={source.confidence} />
                  </div>
                  <h3 className="mt-2 text-base font-semibold leading-6 text-zinc-950">{source.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-zinc-600">{source.snippet}</p>
                  {source.url && (
                    <a
                      className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-emerald-700 hover:text-emerald-900"
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open reference
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </article>
              ))
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-zinc-200 bg-white p-6">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Parsed hypothesis</p>
            <dl className="mt-4 space-y-4 text-sm">
              <Field label="Scientific system" value={parsed.scientific_system} />
              <Field label="Model or organism" value={parsed.model_or_organism} />
              <Field label="Intervention" value={parsed.intervention} />
              <Field label="Comparator" value={parsed.comparator} />
              <Field label="Outcome metric" value={parsed.outcome_metric} />
              <Field label="Success threshold" value={parsed.success_threshold} />
            </dl>
          </div>

          <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-5">
            <div className="flex gap-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              <div className="space-y-2">
                <p className="text-sm font-semibold text-zinc-900">What still needs scientific judgment</p>
                {evidenceNotes.map((warning) => (
                  <p key={warning} className="text-sm leading-6 text-zinc-600">
                    {warning}
                  </p>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <details className="rounded-xl border border-zinc-200 bg-white">
        <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-4">
          <div>
            <p className="text-sm font-semibold text-zinc-950">Search details</p>
            <p className="mt-1 text-xs text-zinc-500">Parsed query terms, provider trace, and evidence-gap details.</p>
          </div>
          <ChevronDown className="h-4 w-4 text-zinc-400" />
        </summary>
        <div className="space-y-6 border-t border-zinc-200 px-6 py-5">
          <div className="grid gap-5 lg:grid-cols-3">
            <QueryTerms label="Literature query terms" values={parsed.literature_query_terms} />
            <QueryTerms label="Protocol query terms" values={parsed.protocol_query_terms} />
            <QueryTerms label="Supplier/material query terms" values={parsed.supplier_material_query_terms} />
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Provider trace</p>
            <div className="mt-3 space-y-3">
              {qc.provider_trace.length === 0 ? (
                <p className="text-sm text-zinc-500">No provider trace recorded for this run.</p>
              ) : (
                qc.provider_trace.map((entry) => (
                  <article key={`${entry.provider}-${entry.query}-${entry.cached}`} className="rounded-lg border border-zinc-200 p-4">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-zinc-600">
                      <span className="font-semibold text-zinc-900">{entry.provider}</span>
                      <span>{(entry.stage ?? "literature_qc").replace(/_/g, " ")}</span>
                      <span>{entry.result_count} results</span>
                      {entry.cached && <span>Cache hit</span>}
                      {entry.fallback_used && <span>Fallback used</span>}
                    </div>
                    <p className="mt-2 text-sm leading-6 text-zinc-700">{entry.query}</p>
                    {entry.error && <p className="mt-2 text-sm text-rose-700">{entry.error}</p>}
                  </article>
                ))
              )}
            </div>
          </div>
        </div>
      </details>
    </section>
  );
}

function humanizeEvidenceLabel(source: EvidenceSource) {
  if (source.trust_tier === "community_protocol") {
    return "Community source";
  }
  if (source.trust_tier === "inferred" || source.evidence_type === "assumption") {
    return "Inferred / expert review required";
  }
  if (source.evidence_type === "adjacent_method" || source.evidence_type === "close_match") {
    return "Adjacent evidence";
  }
  return "Source-backed";
}

function truncateParagraph(text: string, limit: number) {
  return text.length <= limit ? text : `${text.slice(0, limit).trimEnd()}...`;
}

function QueryTerms({ label, values }: { label: string; values: string[] }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
      <div className="mt-2 space-y-2">
        {values.length === 0 ? (
          <p className="text-sm text-zinc-500">Not specified</p>
        ) : (
          values.map((value) => (
            <p key={`${label}-${value}`} className="text-sm leading-6 text-zinc-700">
              {value}
            </p>
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
