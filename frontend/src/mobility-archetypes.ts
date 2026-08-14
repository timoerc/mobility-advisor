import type { TranslationKey } from "./i18n";
import type { OnboardingPreferences } from "./types";

export type ArchetypeId =
  | "committed_driver"
  | "rail_commuter"
  | "multimodal"
  | "eco_pioneer"
  | "budget_optimizer"
  | "remote_native";

// Prose lives entirely in en.ts/de.ts under archetype.<id>.* — this module holds only ids,
// translation keys, and the numeric classifyArchetype() scorer, per the i18n rule of stripping
// prose out of data modules rather than keeping a parallel dictionary here.
export type MobilityArchetype = {
  id: ArchetypeId;
  nameKey: TranslationKey;
  taglineKey: TranslationKey;
  descriptionKey: TranslationKey;
  /** Tailwind bg color class for the indicator dot */
  color: string;
  insightKeys: TranslationKey[];
  // Bibliographic citation — intentionally NOT a translation key; see en.ts's header comment
  // on this field. A citation reads the same regardless of UI language.
  source: string;
};

export const MOBILITY_ARCHETYPES: Record<ArchetypeId, MobilityArchetype> = {
  committed_driver: {
    id: "committed_driver",
    nameKey: "archetype.committed_driver.name",
    taglineKey: "archetype.committed_driver.tagline",
    descriptionKey: "archetype.committed_driver.description",
    color: "bg-blue-500",
    insightKeys: [
      "archetype.committed_driver.insight1",
      "archetype.committed_driver.insight2",
      "archetype.committed_driver.insight3",
    ],
    source: "MiD 2017 (infas/DLR); ADAC Autokostenrechner 2024",
  },

  rail_commuter: {
    id: "rail_commuter",
    nameKey: "archetype.rail_commuter.name",
    taglineKey: "archetype.rail_commuter.tagline",
    descriptionKey: "archetype.rail_commuter.description",
    color: "bg-brand-red",
    insightKeys: [
      "archetype.rail_commuter.insight1",
      "archetype.rail_commuter.insight2",
      "archetype.rail_commuter.insight3",
    ],
    source: "VDV Jahresbericht 2023; DB Preisliste 2024; infas Pendlerstudie 2022",
  },

  multimodal: {
    id: "multimodal",
    nameKey: "archetype.multimodal.name",
    taglineKey: "archetype.multimodal.tagline",
    descriptionKey: "archetype.multimodal.description",
    color: "bg-violet-500",
    insightKeys: [
      "archetype.multimodal.insight1",
      "archetype.multimodal.insight2",
      "archetype.multimodal.insight3",
    ],
    source: "BMVI MiD 2017; VDV-Studie Multimodalität 2022; mFUND MaaS-Report 2023",
  },

  eco_pioneer: {
    id: "eco_pioneer",
    nameKey: "archetype.eco_pioneer.name",
    taglineKey: "archetype.eco_pioneer.tagline",
    descriptionKey: "archetype.eco_pioneer.description",
    color: "bg-green-500",
    insightKeys: [
      "archetype.eco_pioneer.insight1",
      "archetype.eco_pioneer.insight2",
      "archetype.eco_pioneer.insight3",
    ],
    source: "UBA Emissionsfaktoren 2024; ADAC Mobilitätsstudie 2023; Umweltbundesamt Schattenpreis CO₂",
  },

  budget_optimizer: {
    id: "budget_optimizer",
    nameKey: "archetype.budget_optimizer.name",
    taglineKey: "archetype.budget_optimizer.tagline",
    descriptionKey: "archetype.budget_optimizer.description",
    color: "bg-amber-500",
    insightKeys: [
      "archetype.budget_optimizer.insight1",
      "archetype.budget_optimizer.insight2",
      "archetype.budget_optimizer.insight3",
    ],
    source: "VDV-Erhebung Nahverkehr 2022; Stiftung Warentest Abonnement-Vergleich 2024",
  },

  remote_native: {
    id: "remote_native",
    nameKey: "archetype.remote_native.name",
    taglineKey: "archetype.remote_native.tagline",
    descriptionKey: "archetype.remote_native.description",
    color: "bg-teal-500",
    insightKeys: [
      "archetype.remote_native.insight1",
      "archetype.remote_native.insight2",
      "archetype.remote_native.insight3",
    ],
    source: "IFO Institut Homeoffice-Barometer 2023; ADAC Carsharing-Vergleich 2024; DB Flex-Ticket-Studie",
  },
};

// ── Classification ───────────────────────────────────────────────────────────

export function classifyArchetype(prefs: OnboardingPreferences): ArchetypeId {
  const scores: Record<ArchetypeId, number> = {
    committed_driver: 0,
    rail_commuter: 0,
    multimodal: 0,
    eco_pioneer: 0,
    budget_optimizer: 0,
    remote_native: 0,
  };

  const wfhCount = prefs.commute.wfh_days.length;
  const officeCount = prefs.commute.office_days.length;
  const km = prefs.car.monthly_km_estimate ?? 0;
  const hasRailSub = prefs.subscriptions.some((s) => s.mode === "rail");
  const hasBahnCard = prefs.subscriptions.some((s) =>
    s.product.toLowerCase().includes("bahncard")
  );
  const hasCarShare = prefs.subscriptions.some((s) => s.mode === "car_share");
  const hasFlight = prefs.subscriptions.some((s) => s.mode === "flight");
  const modeCount = new Set(prefs.subscriptions.map((s) => s.mode)).size;

  // Remote native
  if (wfhCount >= 4) scores.remote_native += 4;
  else if (wfhCount >= 3) scores.remote_native += 2;
  if (officeCount <= 1) scores.remote_native += 1;
  if (officeCount >= 4) scores.remote_native -= 1;

  // Committed driver
  if (prefs.car.owns_car) {
    scores.committed_driver += 2;
    if (km > 1000) scores.committed_driver += 3;
    else if (km > 500) scores.committed_driver += 2;
    if (officeCount >= 4 && km > 300) scores.committed_driver += 1;
  } else {
    scores.committed_driver -= 2;
  }
  if (prefs.priorities.time > 0.4) scores.committed_driver += 1;
  if (wfhCount >= 3) scores.committed_driver -= 1;

  // Rail commuter
  if (hasBahnCard) scores.rail_commuter += 3;
  if (prefs.integrations.db_connected) scores.rail_commuter += 2;
  if (hasRailSub && !hasBahnCard) scores.rail_commuter += 1;
  if (officeCount >= 3 && !prefs.car.owns_car) scores.rail_commuter += 2;
  if (wfhCount >= 3) scores.rail_commuter -= 1;

  // Multimodal
  if (prefs.subscriptions.length >= 3) scores.multimodal += 3;
  else if (prefs.subscriptions.length >= 2) scores.multimodal += 1;
  if (modeCount >= 2) scores.multimodal += 2;
  if (hasCarShare && hasRailSub) scores.multimodal += 2;
  if (hasFlight) scores.multimodal += 1;

  // Eco pioneer
  if (prefs.priorities.sustainability > 0.4) scores.eco_pioneer += 4;
  else if (prefs.priorities.sustainability > 0.3) scores.eco_pioneer += 2;
  if (!prefs.car.owns_car) scores.eco_pioneer += 1;
  if (prefs.integrations.deutschlandticket_connected) scores.eco_pioneer += 1;

  // Budget optimizer
  if (prefs.priorities.cost > 0.4) scores.budget_optimizer += 3;
  else if (prefs.priorities.cost > 0.3) scores.budget_optimizer += 1;
  if (prefs.personal.employment_status === "student") scores.budget_optimizer += 1;

  return (Object.entries(scores) as [ArchetypeId, number][]).sort(([, a], [, b]) => b - a)[0][0];
}
