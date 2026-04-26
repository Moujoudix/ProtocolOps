import type { LiteratureQcResponse, PlanResponse, Preset } from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
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

