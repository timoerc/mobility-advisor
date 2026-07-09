import type { OnboardingPreferences } from "./types";

export type ArchetypeId =
  | "committed_driver"
  | "rail_commuter"
  | "multimodal"
  | "eco_pioneer"
  | "budget_optimizer"
  | "remote_native";

export type MobilityArchetype = {
  id: ArchetypeId;
  name: string;
  tagline: string;
  description: string;
  /** Tailwind bg color class for the indicator dot */
  color: string;
  portfolioInsights: string[];
  source: string;
};

export const MOBILITY_ARCHETYPES: Record<ArchetypeId, MobilityArchetype> = {
  committed_driver: {
    id: "committed_driver",
    name: "Committed Driver",
    tagline: "Car-first mobility — high ownership cost, low transit use",
    description:
      "You rely primarily on your car for daily transport. With 57% of Germans choosing the car as their main mode (MiD 2017), you're in the largest segment — but also the one with the highest hidden costs.",
    color: "bg-blue-500",
    portfolioInsights: [
      "Total cost of car ownership (loan, insurance, fuel, parking) frequently exceeds €500/month — often invisible because costs are spread across multiple bills.",
      "A BahnCard 25 can pay off even at low rail frequency: it breaks even after just 2–3 long-distance business trips per year.",
      "Carsharing becomes cost-competitive once actual driving drops below ~800 km/month, which is common when office attendance is hybrid.",
    ],
    source: "MiD 2017 (infas/DLR); ADAC Autokostenrechner 2024",
  },

  rail_commuter: {
    id: "rail_commuter",
    name: "Rail Commuter",
    tagline: "Train as primary mode — subscription choices drive most savings",
    description:
      "You use Deutsche Bahn regularly and rely on rail subscriptions to manage costs. BahnCard holders make up DB's most loyal and savings-sensitive segment, where small tier decisions have outsized financial impact.",
    color: "bg-brand-red",
    portfolioInsights: [
      "BahnCard 50 break-even requires roughly €488 in annual full-price ticket spend (2nd class, 2024 pricing). Below that, BahnCard 25 or pay-per-use is cheaper.",
      "Flex Price caps (Sparpreis, Super Sparpreis) can save 30–60% on long-distance routes even without a BahnCard — stacking them with a BahnCard 25 is the typical optimal combination.",
      "Combining a Deutschlandticket (€49/month) with a BahnCard 25 is optimal for hybrid commuters who travel long-distance 1–2 times per month.",
    ],
    source: "VDV Jahresbericht 2023; DB Preisliste 2024; infas Pendlerstudie 2022",
  },

  multimodal: {
    id: "multimodal",
    name: "Multimodal Explorer",
    tagline: "Mixes modes flexibly — highest satisfaction, highest overlap risk",
    description:
      "You switch between transport modes depending on the trip. Multimodal users make up 18% of all German trips (MiD 2017) and report the highest satisfaction — but also carry the highest risk of redundant subscriptions.",
    color: "bg-violet-500",
    portfolioInsights: [
      "Subscription stacking is the biggest cost risk: Deutschlandticket + BahnCard + carsharing membership can overlap significantly for urban short trips.",
      "MaaS (Mobility as a Service) bundles like DB Connect or regional ÖPNV-Flatrates can replace 2–3 individual subscriptions at lower combined cost.",
      "Review each subscription against actual monthly usage — paying for 3 services but only using each 30% of the time means 70% of spend is wasted.",
    ],
    source: "BMVI MiD 2017; VDV-Studie Multimodalität 2022; mFUND MaaS-Report 2023",
  },

  eco_pioneer: {
    id: "eco_pioneer",
    name: "Eco Pioneer",
    tagline: "Sustainability-first — CO₂ is a decision variable, not a footnote",
    description:
      "Environmental impact is your primary mobility criterion. You're part of a fast-growing segment: 23% of Germans now cite climate as a top concern when choosing how to travel (ADAC 2023).",
    color: "bg-green-500",
    portfolioInsights: [
      "Rail travel emits ~32 g CO₂/pkm vs. 147 g CO₂/pkm by car — a single Munich–Hamburg return trip by train instead of car saves ~38 kg CO₂.",
      "Deutschlandticket + e-bike subscription covers >90% of trips for urban/suburban users at under €100/month total cost.",
      "Carbon savings have a monetary value: at the German shadow carbon price of €200/tonne, every tonne avoided is worth €200 in avoided social cost — a legitimate factor in ROI calculations.",
    ],
    source: "UBA Emissionsfaktoren 2024; ADAC Mobilitätsstudie 2023; Umweltbundesamt Schattenpreis CO₂",
  },

  budget_optimizer: {
    id: "budget_optimizer",
    name: "Budget Optimizer",
    tagline: "Cost is the primary lens — every subscription must justify itself",
    description:
      "You evaluate every mobility subscription against its real-world return. Cost is the #1 factor for 68% of public transit users in Germany (VDV-Erhebung 2022) — and subscription math is often more complex than it looks.",
    color: "bg-amber-500",
    portfolioInsights: [
      "Annual subscriptions should be stress-tested: if usage drops by 20% (holiday, illness, remote periods), break-even often tips negative.",
      "Pay-per-use outperforms fixed subscriptions when monthly trip count varies by more than ±30% — avoid locking in annual fees for variable needs.",
      "Deutschlandticket at €49/month has the lowest break-even of any German transit pass: it pays off after just 2 return ÖPNV journeys per month in most major cities.",
    ],
    source: "VDV-Erhebung Nahverkehr 2022; Stiftung Warentest Abonnement-Vergleich 2024",
  },

  remote_native: {
    id: "remote_native",
    name: "Remote Native",
    tagline: "Hybrid worker — occasional bursts, not daily commuting",
    description:
      "You work from home most days and travel only occasionally. Post-pandemic, 24% of German employees are in hybrid arrangements (IFO Institut 2023), which fundamentally changes the economics of fixed mobility subscriptions.",
    color: "bg-teal-500",
    portfolioInsights: [
      "Annual subscriptions built around a 5-day commute lose 30–60% of their value for hybrid workers — BahnCard 25 or month-to-month Deutschlandticket is usually the better fit.",
      "Carsharing is significantly cheaper than ownership for under ~600 km/month of actual driving — a threshold most hybrid workers fall below on remote days.",
      "Cluster your travel: grouping trips into multi-day blocks rather than spreading them thin increases the per-trip value extracted from any fixed subscription you do hold.",
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
