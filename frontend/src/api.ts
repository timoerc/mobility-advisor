import type { OnboardingPreferences } from "./types";
import type { Recommendation } from "./types/recommendation";

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

export async function saveProfile(personaId: string, prefs: OnboardingPreferences): Promise<void> {
  await post<{ ok: boolean }>("/profile", { persona_id: personaId, ...prefs });
}

export async function activatePersona(personaId: string): Promise<void> {
  await post<{ ok: boolean }>("/activate", { persona_id: personaId });
}

export async function runAnalysis(sessionId: string): Promise<Recommendation> {
  return post<Recommendation>("/analyze", { session_id: sessionId });
}

export async function sendMessage(sessionId: string, text: string): Promise<string> {
  const data = await post<{ text: string }>("/chat", { session_id: sessionId, text });
  return data.text;
}
