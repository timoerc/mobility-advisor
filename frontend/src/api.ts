import type { OnboardingPreferences } from "./types";
import type { ExecutionResult, ProposedAction, Recommendation } from "./types/recommendation";
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

export async function runAnalysis(sessionId: string): Promise<Recommendation> {
  return post<Recommendation>("/analyze", { session_id: sessionId });
}

export async function executeAction(sessionId: string, action: ProposedAction): Promise<ExecutionResult> {
  return post<ExecutionResult>("/execute", {
    session_id: sessionId,
    action_title: action.title,
    action_description: action.description,
    action_consequence: action.consequence,
  });
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

export async function fetchPersonas(): Promise<Persona[]> {
  const res = await fetch(`${BASE}/personas`);
  if (!res.ok) throw new Error(`GET /api/personas ${res.status}`);
  return res.json() as Promise<Persona[]>;
}
