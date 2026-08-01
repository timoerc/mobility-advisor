export type ConfidenceLevel = "high" | "medium" | "low";

export type MetricDelta = {
  value: number;
  unit: string;
  direction: "save" | "extra_cost" | "reduce" | "increase" | "neutral";
  label: string;
};

export type ProposedAction = {
  title: string;
  description: string;
  consequence: string;
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
  // null only for the always-present "Keep current setup" row; every other
  // alternative carries the action that gets executed if the user selects it.
  action: ProposedAction | null;
};

export type Recommendation = {
  verdict: string;
  confidence: ConfidenceLevel;
  summaryText: string;
  metrics: MetricDelta[];
  reasoning: string[];
  assumptions: string[];
  alternatives: Alternative[];
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
