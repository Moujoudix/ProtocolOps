export type DomainRoute =
  | "cell_biology"
  | "diagnostics_biosensor"
  | "animal_gut_health"
  | "microbial_electrochemistry";

export type EvidenceType =
  | "exact_evidence"
  | "adjacent_evidence"
  | "generic_protocol_evidence"
  | "supplier_evidence"
  | "assumption";

export type TrustTier =
  | "literature_database"
  | "supplier_documentation"
  | "community_protocol"
  | "inferred";

export type ProcurementStatus = "verified" | "requires_procurement_check";

export type PriceStatus =
  | "visible_price"
  | "requires_procurement_check"
  | "contact_supplier";

export type NoveltySignal =
  | "exact_match_found"
  | "similar_work_exists"
  | "not_found_in_searched_sources";

export interface Preset {
  id: string;
  label: string;
  domain: string;
  hypothesis: string;
  optimized_demo: boolean;
}

export interface ParsedHypothesis {
  original_text: string;
  domain: string;
  domain_route: DomainRoute;
  organism_or_system: string | null;
  intervention: string | null;
  comparator: string | null;
  outcome: string | null;
  effect_size: string | null;
  mechanism: string | null;
  key_terms: string[];
  safety_notes: string[];
}

export interface EvidenceSource {
  id: string;
  source_name: string;
  title: string;
  url: string | null;
  evidence_type: EvidenceType;
  trust_tier: TrustTier;
  snippet: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  confidence: number;
  retrieved_at: string;
}

export interface LiteratureQC {
  novelty_signal: NoveltySignal;
  confidence: number;
  references: EvidenceSource[];
  searched_sources: string[];
  rationale: string;
  evidence_gap_warnings: string[];
}

export interface LiteratureQcResponse {
  run_id: string;
  parsed_hypothesis: ParsedHypothesis;
  literature_qc: LiteratureQC;
}

export interface ExperimentPlanSection {
  title: string;
  summary: string;
  bullets: string[];
  evidence_source_ids: string[];
  confidence: number;
  expert_review_required: boolean;
}

export interface MaterialItem {
  name: string;
  role: string;
  vendor: string | null;
  catalog_number: string | null;
  price: string | null;
  currency: string | null;
  procurement_status: ProcurementStatus;
  price_status: PriceStatus;
  requires_procurement_check: boolean;
  evidence_source_ids: string[];
  notes: string;
  confidence: number;
}

export interface ProtocolStep {
  step_number: number;
  title: string;
  purpose: string;
  actions: string[];
  critical_parameters: string[];
  materials: string[];
  evidence_source_ids: string[];
  confidence: number;
  expert_review_required: boolean;
  review_reason: string | null;
}

export interface BudgetSummary {
  title: string;
  summary: string;
  items: MaterialItem[];
  evidence_source_ids: string[];
  confidence: number;
  expert_review_required: boolean;
}

export interface ExperimentPlan {
  plan_title: string;
  status_label: string;
  overview: ExperimentPlanSection;
  literature_qc: LiteratureQC;
  study_design: ExperimentPlanSection;
  protocol: ProtocolStep[];
  materials: MaterialItem[];
  budget: BudgetSummary;
  timeline: ExperimentPlanSection;
  validation: ExperimentPlanSection;
  risks: ExperimentPlanSection;
  sources: EvidenceSource[];
  generated_at: string;
}

export interface PlanResponse {
  run_id: string;
  plan: ExperimentPlan;
}
