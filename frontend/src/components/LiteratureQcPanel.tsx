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

const evidenceLabels: Record<EvidenceSource["evidence_type"], string> = {
  exact_evidence: "Exact",
  adjacent_evidence: "Adjacent",
  generic_protocol_evidence: "Generic protocol",
  supplier_evidence: "Supplier",
  assumption: "Assumption",
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
            <Field label="System" value={parsed.organism_or_system} />
            <Field label="Intervention" value={parsed.intervention} />
            <Field label="Comparator" value={parsed.comparator} />
            <Field label="Outcome" value={parsed.outcome} />
            <Field label="Effect" value={parsed.effect_size} />
          </dl>
          <div className="mt-4 flex flex-wrap gap-2">
            {parsed.key_terms.map((term) => (
              <Badge key={term} tone="blue">
                {term}
              </Badge>
            ))}
          </div>
        </div>

        <div className="rounded-md border border-zinc-200 bg-white p-5 shadow-crisp">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">References</h2>
          <div className="mt-4 space-y-4">
            {qc.references.map((source) => (
              <article key={source.id} className="border-t border-zinc-100 pt-4 first:border-t-0 first:pt-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={source.evidence_type === "exact_evidence" ? "green" : source.evidence_type === "assumption" ? "red" : "amber"}>
                    {evidenceLabels[source.evidence_type]}
                  </Badge>
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

      <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <div className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="space-y-1">
            {qc.evidence_gap_warnings.map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        </div>
      </div>
    </section>
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

