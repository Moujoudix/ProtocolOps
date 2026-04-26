export type DomainRoute =
  | "cell_biology"
  | "diagnostics_biosensor"
  | "animal_gut_health"
  | "microbial_electrochemistry";

export type EvidenceType =
  | "exact_match"
  | "close_match"
  | "adjacent_method"
  | "generic_method"
  | "supplier_reference"
  | "safety_or_standard"
  | "assumption";

export type TrustTier =
  | "literature_database"
  | "supplier_documentation"
  | "community_protocol"
  | "scientific_standard"
  | "inferred";

export type TrustLevel = "high" | "medium" | "low";

export type ProcurementStatus = "verified" | "requires_procurement_check";

export type PriceStatus =
  | "visible_price"
  | "requires_procurement_check"
  | "contact_supplier";

export type ReviewState =
  | "generated"
  | "reviewed"
  | "revised"
  | "approved_for_proposal";

export type ReviewAction =
  | "approve"
  | "reject"
  | "edit"
  | "replace"
  | "unrealistic"
  | "missing_dependency"
  | "comment";

export type ReviewTargetType =
  | "section"
  | "protocol_step"
  | "material"
  | "budget_item"
  | "timeline"
  | "validation"
  | "risk";

export type ReadinessStatus =
  | "ready"
  | "missing_secret"
  | "public_mode"
  | "unreachable"
  | "degraded";

export type RunMode = "fully_live" | "degraded_live" | "demo_fallback";

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
  scientific_system: string | null;
  model_or_organism: string | null;
  organism_or_system: string | null;
  intervention: string | null;
  comparator: string | null;
  outcome_metric: string | null;
  success_threshold: string | null;
  outcome: string | null;
  effect_size: string | null;
  mechanism: string | null;
  literature_query_terms: string[];
  protocol_query_terms: string[];
  supplier_material_query_terms: string[];
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
  trust_level: TrustLevel;
  snippet: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  confidence: number;
  retrieved_at: string;
}

export interface ProviderTraceEntry {
  provider: string;
  attempted: boolean;
  succeeded: boolean;
  cached: boolean;
  query: string;
  result_count: number;
  error: string | null;
}

export interface ProviderReadiness {
  provider: string;
  status: ReadinessStatus;
  detail: string;
  configured: boolean;
  authenticated: boolean;
}

export interface ReadinessResponse {
  strict_live_mode: boolean;
  live_ready: boolean;
  providers: ProviderReadiness[];
}

export interface LiteratureQC {
  novelty_signal: NoveltySignal;
  confidence: number;
  references: EvidenceSource[];
  literature_sources: EvidenceSource[];
  searched_sources: string[];
  provider_trace: ProviderTraceEntry[];
  rationale: string;
  literature_synthesis: string | null;
  gaps: string[];
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

export interface ReviewMemoryReference {
  run_id: string;
  review_session_id: string;
  target_type: ReviewTargetType;
  target_key: string;
  action: ReviewAction;
  note: string;
  confidence: number | null;
}

export interface PlanQualitySummary {
  literature_confidence: number;
  protocol_confidence: number;
  materials_confidence: number;
  budget_confidence: number;
  evidence_completeness: number;
  operational_readiness: number;
  review_burden: number;
}

export interface ExperimentPlan {
  plan_title: string;
  status_label: string;
  quality_summary: PlanQualitySummary | null;
  memory_applied: ReviewMemoryReference[];
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

export interface ComparisonMetricRecord {
  label: string;
  baseline: string;
  current: string;
  delta: number | null;
}

export interface RunComparisonResponse {
  baseline_run_id: string;
  current_run_id: string;
  baseline_title: string;
  current_title: string;
  summary: string[];
  metrics: ComparisonMetricRecord[];
  protocol_changes: string[];
  material_changes: string[];
  budget_changes: string[];
}

export interface RunListItem {
  run_id: string;
  hypothesis: string;
  preset_id: string | null;
  status: string;
  review_state: ReviewState;
  run_mode: RunMode;
  created_at: string;
  updated_at: string;
  domain: string | null;
  plan_title: string | null;
  quality_summary: PlanQualitySummary | null;
  used_seed_data: boolean;
  is_presentation_anchor: boolean;
  parent_run_id: string | null;
  revision_number: number;
}

export interface RunStateResponse {
  run_id: string;
  hypothesis: string;
  preset_id: string | null;
  status: string;
  review_state: ReviewState;
  run_mode: RunMode;
  used_seed_data: boolean;
  is_presentation_anchor: boolean;
  parent_run_id: string | null;
  revision_number: number;
  parsed_hypothesis: ParsedHypothesis | null;
  literature_qc: LiteratureQC | null;
  plan: ExperimentPlan | null;
}

export interface RunEventRecord {
  id: string;
  run_id: string;
  stage: string;
  status: string;
  message: string;
  created_at: string;
}

export interface ReviewItemPayload {
  target_type: ReviewTargetType;
  target_key: string;
  action: ReviewAction;
  comment?: string | null;
  replacement_text?: string | null;
  confidence_override?: number | null;
}

export interface ReviewSubmissionRequest {
  reviewer_name?: string | null;
  summary?: string | null;
  review_state: ReviewState;
  items: ReviewItemPayload[];
}

export interface ReviewItemRecord {
  id: string;
  target_type: ReviewTargetType;
  target_key: string;
  action: ReviewAction;
  comment: string | null;
  replacement_text: string | null;
  confidence_override: number | null;
  created_at: string;
}

export interface ReviewSessionRecord {
  id: string;
  run_id: string;
  reviewer_name: string | null;
  summary: string | null;
  review_state: ReviewState;
  created_at: string;
  updated_at: string;
  items: ReviewItemRecord[];
}

export interface ReviewSubmissionResponse {
  review: ReviewSessionRecord;
}
