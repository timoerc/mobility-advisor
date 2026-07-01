import { useState } from "react";
import type { PriorityWeights } from "../types";

type PrioritiesPageProps = {
  priorities: PriorityWeights;
  onChange: (priorities: PriorityWeights) => void;
};

// AHP intensity scale: Likert score → ratio (first criterion : second criterion)
// 1 = "Stimme gar nicht zu" → second crit. is 5× more important (1:5)
// 4 = "Ausgeglichen"        → equal importance (1:1)
// 7 = "Stimme sehr zu"      → first crit. is 5× more important (5:1)
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

// Three questions — each captures a pairwise comparison:
//   Q1: Time vs. Cost  (agree → Time more important)
//   Q2: CO₂  vs. Cost  (agree → CO₂  more important)
//   Q3: Time vs. CO₂   (agree → Time more important)
//
// Pairwise matrix [Cost, Time, CO₂]:
//   Cost row: [ 1,      1/i1,  1/i2 ]
//   Time row: [ i1,     1,     i3   ]
//   CO₂  row: [ i2,     1/i3,  1    ]
//
// Geometric mean per row, then normalise → weights sum to 1.
function computeWeights(q1: number, q2: number, q3: number): PriorityWeights {
  const i1 = INTENSITY[q1]; // time:cost
  const i2 = INTENSITY[q2]; // co2:cost
  const i3 = INTENSITY[q3]; // time:co2

  const gCost = Math.cbrt(1 * (1 / i1) * (1 / i2));
  const gTime = Math.cbrt(i1 * 1 * i3);
  const gCO2  = Math.cbrt(i2 * (1 / i3) * 1);
  const total = gCost + gTime + gCO2;

  return {
    cost:           gCost / total,
    time:           gTime / total,
    sustainability: gCO2  / total,
  };
}

// Consistency Ratio (CR) — detects logically contradictory answers.
// For n=3 the Random Index RI = 0.58.  CR < 0.10 is considered consistent.
function computeCR(q1: number, q2: number, q3: number): number {
  const i1 = INTENSITY[q1];
  const i2 = INTENSITY[q2];
  const i3 = INTENSITY[q3];

  const { cost: wC, time: wT, sustainability: wCO2 } = computeWeights(q1, q2, q3);

  // Weighted sum vector: A × w
  const awC   = 1 * wC + (1 / i1) * wT + (1 / i2) * wCO2;
  const awT   = i1 * wC + 1 * wT + i3 * wCO2;
  const awCO2 = i2 * wC + (1 / i3) * wT + 1 * wCO2;

  const lambdaMax = (awC / wC + awT / wT + awCO2 / wCO2) / 3;
  const ci = (lambdaMax - 3) / 2;
  return ci / 0.58; // RI for n = 3
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
    statement: "Getting to my destination quickly matters more to me than a low price.",
    leftLabel: "Low price",
    rightLabel: "Fast travel",
  },
  {
    id: "q2",
    statement: "A low CO₂ footprint matters more to me than a low price.",
    leftLabel: "Low price",
    rightLabel: "Low CO₂",
  },
  {
    id: "q3",
    statement: "Getting to my destination quickly matters more to me than a low CO₂ footprint.",
    leftLabel: "Low CO₂",
    rightLabel: "Fast travel",
  },
];

function LikertControl({
  value,
  onChange,
  leftLabel,
  rightLabel,
}: {
  value: number;
  onChange: (v: number) => void;
  leftLabel: string;
  rightLabel: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
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
            {score === 4 ? "=" : score}
          </button>
        ))}
      </div>
      <div className="flex justify-between text-[11px] text-gray-400 px-0.5">
        <span>← {leftLabel}</span>
        <span>{rightLabel} →</span>
      </div>
    </div>
  );
}

function WeightBar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 text-xs font-semibold text-gray-600 flex-shrink-0">{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-300 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 text-xs font-bold tabular-nums text-right text-gray-700">{pct}%</span>
    </div>
  );
}

const DEFAULT_ANSWERS = { q1: 4, q2: 4, q3: 4 };

export function PrioritiesPage({ onChange }: PrioritiesPageProps) {
  const [answers, setAnswers] = useState(DEFAULT_ANSWERS);

  const weights = computeWeights(answers.q1, answers.q2, answers.q3);
  const cr = computeCR(answers.q1, answers.q2, answers.q3);
  const isInconsistent = cr > 0.10;
  // Only warn when all three answers have been touched away from neutral
  const allAnswered = answers.q1 !== 4 || answers.q2 !== 4 || answers.q3 !== 4;

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
            <p className="text-sm font-medium text-gray-800 m-0 leading-snug">{q.statement}</p>
            <LikertControl
              value={answers[q.id]}
              onChange={(v) => handleChange(q.id, v)}
              leftLabel={q.leftLabel}
              rightLabel={q.rightLabel}
            />
          </div>
        ))}
      </div>

      {/* Consistency warning — only shown when answers are contradictory */}
      {allAnswered && isInconsistent && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl px-4 py-3 flex gap-2 items-start">
          <span className="text-yellow-500 text-base leading-none mt-0.5">⚠</span>
          <p className="text-xs text-yellow-800 m-0 leading-relaxed">
            Your answers are slightly inconsistent (CR = {cr.toFixed(2)}). This can happen when, for example, you say Time &gt; Price, Price &gt; CO₂, but also CO₂ &gt; Time. Would you like to review your answers?
          </p>
        </div>
      )}

      <div className="flex flex-col gap-2 pt-2 border-t border-gray-100">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide m-0 mb-1">
          Your priorities
        </p>
        <WeightBar label="Cost"  pct={Math.round(weights.cost * 100)}           color="bg-brand-red" />
        <WeightBar label="Time"  pct={Math.round(weights.time * 100)}            color="bg-gray-700" />
        <WeightBar label="CO₂"   pct={Math.round(weights.sustainability * 100)}  color="bg-green-500" />
      </div>
    </div>
  );
}
