export type ConfidenceLevel = "high" | "medium" | "low";

export type MetricDelta = {
  value: number;
  unit: string;
  direction: "save" | "extra_cost" | "reduce" | "increase" | "neutral";
  label: string;
};

export type Alternative = {
  id: string;
  name: string;
  annualCostEur: number;
  savingsVsCurrentEur: number;
  co2Impact?: string;
  tradeoff: string;
  isRecommended: boolean;
};

export type ProposedAction = {
  title: string;
  description: string;
  consequence: string;
};

export type Recommendation = {
  verdict: string;
  confidence: ConfidenceLevel;
  summaryText: string;
  metrics: MetricDelta[];
  reasoning: string[];
  assumptions: string[];
  alternatives: Alternative[];
  proposedAction: ProposedAction;
};
