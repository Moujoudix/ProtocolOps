import type {
  LiteratureQcResponse,
  PlanResponse,
  Preset,
  ReadinessResponse,
  RunComparisonResponse,
  ReviewSessionRecord,
  ReviewSubmissionRequest,
  ReviewSubmissionResponse,
  RunEventRecord,
  RunListItem,
  RunStateResponse,
} from "../types/api";

const API_BASE = normalizeApiBase(import.meta.env.VITE_API_BASE_URL);

export function normalizeApiBase(apiBase: string | undefined): string {
  if (!apiBase) {
    return "";
  }

  return apiBase.replace(/\/+$/, "");
}

export function resolveApiUrl(path: string, apiBase = API_BASE): string {
  return apiBase ? `${apiBase}${path}` : path;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(resolveApiUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function fetchPresets(): Promise<Preset[]> {
  return request<Preset[]>("/api/presets");
}

export function fetchReadiness(): Promise<ReadinessResponse> {
  return request<ReadinessResponse>("/api/readiness");
}

export function fetchRuns(): Promise<RunListItem[]> {
  return request<RunListItem[]>("/api/runs");
}

export function fetchRun(runId: string): Promise<RunStateResponse> {
  return request<RunStateResponse>(`/api/runs/${runId}`);
}

export function fetchRunEvents(runId: string): Promise<RunEventRecord[]> {
  return request<RunEventRecord[]>(`/api/runs/${runId}/events`);
}

export function fetchReviews(runId: string): Promise<ReviewSessionRecord[]> {
  return request<ReviewSessionRecord[]>(`/api/runs/${runId}/reviews`);
}

export function submitReview(runId: string, payload: ReviewSubmissionRequest): Promise<ReviewSubmissionResponse> {
  return request<ReviewSubmissionResponse>(`/api/runs/${runId}/reviews`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function exportJsonUrl(runId: string): string {
  return resolveApiUrl(`/api/runs/${runId}/export/json`);
}

export function exportCitationsUrl(runId: string): string {
  return resolveApiUrl(`/api/runs/${runId}/export/citations`);
}

export function exportProcurementUrl(runId: string): string {
  return resolveApiUrl(`/api/runs/${runId}/export/procurement`);
}

export function exportPdfUrl(runId: string): string {
  return resolveApiUrl(`/api/runs/${runId}/export/pdf`);
}

export function runLiteratureQc(hypothesis: string, presetId: string | null): Promise<LiteratureQcResponse> {
  return request<LiteratureQcResponse>("/api/literature-qc", {
    method: "POST",
    body: JSON.stringify({ hypothesis, preset_id: presetId }),
  });
}

export function generatePlan(runId: string): Promise<PlanResponse> {
  return request<PlanResponse>(`/api/runs/${runId}/plan`, {
    method: "POST",
  });
}

export function revisePlan(runId: string): Promise<PlanResponse> {
  return request<PlanResponse>(`/api/runs/${runId}/revise`, {
    method: "POST",
  });
}

export function fetchComparison(runId: string): Promise<RunComparisonResponse> {
  return request<RunComparisonResponse>(`/api/runs/${runId}/comparison`);
}

export function markPresentationAnchor(runId: string): Promise<RunStateResponse> {
  return request<RunStateResponse>(`/api/runs/${runId}/presentation-anchor`, {
    method: "POST",
  });
}
