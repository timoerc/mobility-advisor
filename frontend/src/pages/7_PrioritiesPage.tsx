import { useState } from "react";
import type { PriorityWeights } from "../types";

type PrioritiesPageProps = {
  priorities: PriorityWeights;
  onChange: (priorities: PriorityWeights) => void;
};

// AHP intensity scale: score → how many times more important A is than B
const INTENSITY: Record<number, number> = {
  1: 1 / 5,
  2: 1 / 3,
  3: 1 / 2,
  4: 1,
  5: 2,
  6: 3,
  7: 5,
};

const LIKERT_LABELS: Record<number, string> = {
  1: "Strongly disagree",
  2: "Disagree",
  3: "Somewhat disagree",
  4: "Balanced",
  5: "Somewhat agree",
  6: "Agree",
  7: "Strongly agree",
};

function computeWeights(q1: number, q2: number, q3: number): PriorityWeights {
  // Q1: Time > Cost   → I(q1) = time:cost ratio
  // Q2: CO2 > Cost    → I(q2) = co2:cost ratio
  // Q3: Time > CO2    → I(q3) = time:co2 ratio
  //
  // Matrix [Cost, Time, CO2]:
  //   Cost row: [1,       1/I(q1), 1/I(q2)]
  //   Time row: [I(q1),   1,       I(q3)  ]
  //   CO2  row: [I(q2),   1/I(q3), 1      ]
  const i1 = INTENSITY[q1];
  const i2 = INTENSITY[q2];
  const i3 = INTENSITY[q3];

  const gCost = Math.cbrt(1 / (i1 * i2));
  const gTime = Math.cbrt(i1 * i3);
  const gCO2 = Math.cbrt(i2 / i3);
  const total = gCost + gTime + gCO2;

  return {
    cost: gCost / total,
    time: gTime / total,
    sustainability: gCO2 / total,
  };
}

type LikertQuestion = {
  id: "q1" | "q2" | "q3";
  statement: string;
  leftLabel: string;
  rightLabel: string;
};

const QUESTIONS: LikertQuestion[] = [
  {
    id: "q1",
    statement:
      "Getting to my destination quickly matters more to me than a low price.",
    leftLabel: "Low price",
    rightLabel: "Fast travel",
  },
  {
    id: "q2",
    statement:
      "A low CO₂ footprint matters more to me than a low price.",
    leftLabel: "Low price",
    rightLabel: "Low CO₂",
  },
  {
    id: "q3",
    statement:
      "Getting to my destination quickly matters more to me than a low CO₂ footprint.",
    leftLabel: "Low CO₂",
    rightLabel: "Fast travel",
  },
];

type LikertControlProps = {
  value: number;
  onChange: (v: number) => void;
  leftLabel: string;
  rightLabel: string;
};

function LikertControl({
  value,
  onChange,
  leftLabel,
  rightLabel,
}: LikertControlProps) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5, 6, 7].map((score) => (
          <button
            key={score}
            type="button"
            onClick={() => onChange(score)}
            title={LIKERT_LABELS[score]}
            aria-label={LIKERT_LABELS[score]}
            aria-pressed={value === score}
            className={`flex-1 py-2 rounded text-xs font-semibold border transition-colors cursor-pointer ${
              value === score
                ? "bg-brand-red text-white border-brand-red"
                : "bg-white text-gray-500 border-gray-200 hover:border-gray-400"
            }`}
          >
            {score === 4 ? "=" : score < 4 ? score : score}
          </button>
        ))}
      </div>
      <div className="flex justify-between text-xs text-gray-400 px-0.5">
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>
    </div>
  );
}

type WeightBarProps = {
  label: string;
  pct: number;
  color: string;
};

function WeightBar({ label, pct, color }: WeightBarProps) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 text-xs font-semibold text-gray-600 flex-shrink-0">
        {label}
      </span>
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-300 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 text-xs font-bold tabular-nums text-right text-gray-700">
        {pct}%
      </span>
    </div>
  );
}

const DEFAULT_ANSWERS = { q1: 4, q2: 4, q3: 4 };

export function PrioritiesPage({ onChange }: PrioritiesPageProps) {
  const [answers, setAnswers] = useState(DEFAULT_ANSWERS);
  const weights = computeWeights(answers.q1, answers.q2, answers.q3);

  const handleChange = (id: keyof typeof answers, value: number) => {
    const next = { ...answers, [id]: value };
    setAnswers(next);
    onChange(computeWeights(next.q1, next.q2, next.q3));
  };

  const handleReset = () => {
    setAnswers(DEFAULT_ANSWERS);
    onChange(computeWeights(4, 4, 4));
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-3xl font-bold leading-tight mb-2">
            What matters most to you?
          </h1>
          <button
            type="button"
            onClick={handleReset}
            className="text-sm text-gray-400 hover:text-gray-600 bg-transparent border-0 cursor-pointer p-0 whitespace-nowrap flex-shrink-0 mt-1"
          >
            Reset
          </button>
        </div>
        <p className="text-gray-500 leading-relaxed m-0">
          Answer three short comparisons and we'll calculate your priorities.
        </p>
      </div>

      <div className="flex flex-col gap-6">
        {QUESTIONS.map((q) => (
          <div key={q.id} className="flex flex-col gap-3">
            <p className="text-sm font-medium text-gray-800 m-0 leading-snug">
              {q.statement}
            </p>
            <LikertControl
              value={answers[q.id]}
              onChange={(v) => handleChange(q.id, v)}
              leftLabel={q.leftLabel}
              rightLabel={q.rightLabel}
            />
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-2 pt-2 border-t border-gray-100">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide m-0 mb-1">
          Your priorities
        </p>
        <WeightBar
          label="Cost"
          pct={Math.round(weights.cost * 100)}
          color="bg-brand-red"
        />
        <WeightBar
          label="Time"
          pct={Math.round(weights.time * 100)}
          color="bg-gray-700"
        />
        <WeightBar
          label="CO₂"
          pct={Math.round(weights.sustainability * 100)}
          color="bg-green-500"
        />
      </div>
    </div>
  );
}
