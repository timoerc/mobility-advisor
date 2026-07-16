import type { OnboardingPreferences } from "./types";
import type {
  AnalysisHistoryEntry,
  AnalysisOutcome,
  AnalysisRunResult,
  ExecutionResult,
  ProposedAction,
} from "./types/recommendation";
import type { Persona } from "./personas";

const BASE = "/api";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`POST ${path} ${res.status}: ${detail}`);
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

export async function executeAction(sessionId: string, action: ProposedAction): Promise<ExecutionResult> {
  return post<ExecutionResult>("/execute", {
    session_id: sessionId,
    action_title: action.title,
    action_description: action.description,
    action_consequence: action.consequence,
  });
}

export async function resolveAnalysis(
  entryId: string,
  body: { outcome: Extract<AnalysisOutcome, "kept_current" | "executed">; alternativeId: string; message: string }
): Promise<void> {
  await post<{ ok: boolean }>(`/analysis-history/${entryId}/resolve`, {
    outcome: body.outcome,
    alternative_id: body.alternativeId,
    message: body.message,
  });
}

export async function fetchAnalysisHistory(): Promise<AnalysisHistoryEntry[]> {
  const res = await fetch(`${BASE}/analysis-history`);
  if (!res.ok) throw new Error(`GET /api/analysis-history ${res.status}`);
  return res.json() as Promise<AnalysisHistoryEntry[]>;
}

export async function sendMessage(sessionId: string, text: string): Promise<{ text: string; actionTaken: boolean }> {
  const data = await post<{ text: string; action_taken: boolean }>("/chat", { session_id: sessionId, text });
  return { text: data.text, actionTaken: data.action_taken };
}

export async function runAnnualReport(sessionId: string): Promise<Blob> {
  const res = await fetch(`${BASE}/annual-report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`POST /annual-report ${res.status}: ${detail}`);
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
  const res = await fetch(`${BASE}/catalog`);
  if (!res.ok) throw new Error(`GET /api/catalog ${res.status}`);
  const data = await res.json() as { options: CatalogOption[] };
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
  const res = await fetch(`${BASE}/travel-history`);
  if (!res.ok) throw new Error(`GET /api/travel-history ${res.status}`);
  const data = await res.json() as { trips: TripRecord[]; reference_date: string };
  return { trips: data.trips, referenceDate: data.reference_date };
}

export async function fetchCurrentSubscriptions(): Promise<OnboardingPreferences["subscriptions"]> {
  const res = await fetch(`${BASE}/current-subscriptions`);
  if (!res.ok) throw new Error(`GET /api/current-subscriptions ${res.status}`);
  const data = await res.json() as { subscriptions: OnboardingPreferences["subscriptions"] };
  return data.subscriptions;
}

export async function fetchPersonas(): Promise<Persona[]> {
  const res = await fetch(`${BASE}/personas`);
  if (!res.ok) throw new Error(`GET /api/personas ${res.status}`);
  return res.json() as Promise<Persona[]>;
}
