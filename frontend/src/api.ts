import type { OnboardingPreferences } from "./types";
import type {
  AnalysisHistoryEntry,
  AnalysisOutcome,
  AnalysisRunResult,
  ExecutionResult,
  ProposedAction,
} from "./types/recommendation";
import type { Persona } from "./personas";
import { getLanguage } from "./i18n";

const BASE = "/api";

// Structured request-failure error. Carries `status`/`detail` as fields (not just baked into
// `message`) so callers can render a localized wrapper — e.g. t("error.api.request", { status,
// detail }) — around a backend detail string instead of a hardcoded English template.
export class ApiError extends Error {
  constructor(
    public readonly method: string,
    public readonly path: string,
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`${method} ${path} ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

// Read from the module-level i18n store (not a hook — this file has no React component to call
// one from). The backend's X-Language middleware (main.py) reads this on every request,
// including the GET endpoints below that carry no request body of their own.
function languageHeaders(extra?: Record<string, string>): Record<string, string> {
  return { "X-Language": getLanguage(), ...extra };
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: languageHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new ApiError("POST", path, res.status, detail);
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: languageHeaders() });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new ApiError("GET", path, res.status, detail);
  }
  return res.json() as Promise<T>;
}

export async function saveProfile(personaId: string, prefs: OnboardingPreferences, avatarBg?: string): Promise<void> {
  await post<{ ok: boolean }>("/profile", { persona_id: personaId, ...prefs, ...(avatarBg !== undefined ? { avatarBg } : {}) });
}

export async function activatePersona(personaId: string): Promise<void> {
  await post<{ ok: boolean }>("/activate", { persona_id: personaId });
}

export async function runAnalysis(sessionId: string): Promise<AnalysisRunResult> {
  return post<AnalysisRunResult>("/analyze", { session_id: sessionId });
}

export async function executeAction(
  sessionId: string,
  action: ProposedAction,
  analysisId: string | null,
  alternativeId: string
): Promise<ExecutionResult> {
  // analysis_id + alternative_id let the backend record the executed outcome (and its revert
  // snapshot) server-side, in the same request that applies the change — no second call to lose.
  const data = await post<{ success: boolean; message: string }>("/execute", {
    session_id: sessionId,
    action_title: action.title,
    action_description: action.description,
    action_consequence: action.consequence,
    analysis_id: analysisId,
    alternative_id: alternativeId,
  });
  return { success: data.success, message: data.message };
}

export async function resolveAnalysis(
  entryId: string,
  // Only the kept-current decision is resolved here; an executed change is recorded by executeAction.
  body: { outcome: Extract<AnalysisOutcome, "kept_current">; alternativeId: string; message: string }
): Promise<void> {
  await post<{ ok: boolean }>(`/analysis-history/${entryId}/resolve`, {
    outcome: body.outcome,
    alternative_id: body.alternativeId,
    message: body.message,
  });
}

export async function revertAnalysis(entryId: string): Promise<{ success: boolean; message: string }> {
  return post<{ success: boolean; message: string }>(`/analysis-history/${entryId}/revert`, {});
}

export async function fetchAnalysisHistory(): Promise<AnalysisHistoryEntry[]> {
  return get<AnalysisHistoryEntry[]>("/analysis-history");
}

export async function sendMessage(
  sessionId: string,
  text: string,
): Promise<{ text: string; actionTaken: boolean; ranOptimization: boolean }> {
  const data = await post<{ text: string; action_taken: boolean; ran_optimization: boolean }>(
    "/chat",
    { session_id: sessionId, text },
  );
  return { text: data.text, actionTaken: data.action_taken, ranOptimization: data.ran_optimization };
}

export async function runAnnualReport(sessionId: string): Promise<Blob> {
  const res = await fetch(`${BASE}/annual-report`, {
    method: "POST",
    headers: languageHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new ApiError("POST", "/annual-report", res.status, detail);
  }
  return res.blob();
}

export type CatalogOption = {
  id: string;
  provider: string;
  product: string;
  mode: string;
  monthly_cost_eur: number;
  billing_cycle: string;
  eligibility: { min_age: number | null; max_age: number | null } | null;
};

export async function fetchCatalog(): Promise<CatalogOption[]> {
  const data = await get<{ options: CatalogOption[] }>("/catalog");
  return data.options;
}

export type TripRecord = {
  date: string;
  mode: string;
  origin: string;
  destination: string;
  provider: string;
  cost_eur: number | null;
  distance_km: number | null;
  co2_emission_kg: number | null;
};

export type TravelHistory = {
  trips: TripRecord[];
  // Frozen "today" (MOCK_TODAY) the trips are dated against — the client anchors time-range
  // filtering to this, not the real clock.
  referenceDate: string;
};

export async function fetchTravelHistory(): Promise<TravelHistory> {
  const data = await get<{ trips: TripRecord[]; reference_date: string }>("/travel-history");
  return { trips: data.trips, referenceDate: data.reference_date };
}

export async function fetchCurrentSubscriptions(): Promise<OnboardingPreferences["subscriptions"]> {
  const data = await get<{ subscriptions: OnboardingPreferences["subscriptions"] }>("/current-subscriptions");
  return data.subscriptions;
}

export async function fetchPersonas(): Promise<Persona[]> {
  return get<Persona[]>("/personas");
}
