export type ConfidenceLevel = "high" | "medium" | "low";

export type MetricDelta = {
  // Usually the numeric delta a tile is built from; a headline tile can instead carry a
  // date or a word (e.g. a pending-decision tile showing "2026-09-01" or "relocation").
  value: number | string;
  unit: string;
  direction: "save" | "extra_cost" | "reduce" | "increase" | "neutral";
  label: string;
};

export type ProposedAction = {
  title: string;
  description: string;
  consequence: string;
};

// This alternative's projected impact vs. the user's current portfolio, on all three
// preference dimensions. Single sign convention: negative = better than current
// (cheaper / faster / less CO2), so all three fields read the same way.
export type DeltaVsCurrent = {
  costEur: number;
  timeMin: number;
  co2Kg: number;
};

export type Alternative = {
  id: string;
  name: string;
  annualCostEur: number;
  savingsVsCurrentEur: number;
  co2Impact?: string;
  // Signed kg CO2/year, same convention as savingsVsCurrentEur: positive = saves CO2
  // vs. current, negative = emits more.
  co2ImpactKg?: number;
  tradeoff: string;
  isRecommended: boolean;
  // Deltas vs. the recommended portfolio (0 for the recommended itself).
  deltaCostVsRecommendedEur?: number;
  deltaTimeVsRecommendedMin?: number;
  deltaCo2VsRecommendedKg?: number;
  // Absent on entries seeded before this field existed — the presentation layer falls
  // back to the legacy savingsVsCurrentEur/co2ImpactKg pair in that case.
  deltaVsCurrent?: DeltaVsCurrent;
  // null only for the always-present "Keep current setup" row; every other
  // alternative carries the action that gets executed if the user selects it.
  action: ProposedAction | null;
  // Structured product-name lists behind `name`/`action.title`, so cancel vs. add can be
  // rendered as distinct chips instead of parsed out of a sentence. Empty for no-change rows.
  addedProducts?: string[];
  removedProducts?: string[];
};

export type Recommendation = {
  verdict: string;
  confidence: ConfidenceLevel;
  summaryText: string;
  metrics: MetricDelta[];
  reasoning: string[];
  assumptions: string[];
  alternatives: Alternative[];
  // Deterministic data-quality/methodology warnings from the trip-projection engine
  // (malformed travel-history entries, travel-reduction damping applied, rail-fare
  // calibration notes, etc.) — absent or empty when nothing was flagged. Populated
  // server-side regardless of what the narrative text mentions.
  dataQualityWarnings?: string[];
};

export type ExecutionResult = {
  success: boolean;
  message: string;
};

export type AnalysisRunResult = {
  id: string;
  recommendation: Recommendation;
};

export type AnalysisOutcome = "pending" | "kept_current" | "executed";

export type AnalysisHistoryEntry = {
  id: string;
  date: string;
  recommendation: Recommendation;
  outcome: AnalysisOutcome;
  resolvedAlternativeId: string | null;
  resolvedMessage: string | null;
  resolvedAt: string | null;
  // Present (non-null) only while an executed change on the newest entry can still be reverted.
  revertSnapshot?: unknown | null;
};
