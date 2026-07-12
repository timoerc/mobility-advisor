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
  tradeoff: string;
  isRecommended: boolean;
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
