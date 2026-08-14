import { useState } from "react";
import { useT } from "../i18n";
import type { TranslationKey } from "../i18n";
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

const LIKERT_KEYS: Record<number, TranslationKey> = {
  1: "priorities.likert.1",
  2: "priorities.likert.2",
  3: "priorities.likert.3",
  4: "priorities.likert.4",
  5: "priorities.likert.5",
  6: "priorities.likert.6",
  7: "priorities.likert.7",
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
  statementKey: TranslationKey;
  leftLabelKey: TranslationKey;
  rightLabelKey: TranslationKey;
};

const QUESTIONS: LikertQuestion[] = [
  { id: "q1", statementKey: "priorities.q1.statement", leftLabelKey: "priorities.q1.leftLabel", rightLabelKey: "priorities.q1.rightLabel" },
  { id: "q2", statementKey: "priorities.q2.statement", leftLabelKey: "priorities.q2.leftLabel", rightLabelKey: "priorities.q2.rightLabel" },
  { id: "q3", statementKey: "priorities.q3.statement", leftLabelKey: "priorities.q3.leftLabel", rightLabelKey: "priorities.q3.rightLabel" },
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
  const t = useT();
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5, 6, 7].map((score) => (
          <button
            key={score}
            type="button"
            onClick={() => onChange(score)}
            title={t(LIKERT_KEYS[score])}
            aria-label={t(LIKERT_KEYS[score])}
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

// AHP weight derivation isn't invertible in closed form (3 answers → 3 weights,
// but the mapping isn't 1:1), so to pre-fill the sliders for an existing persona's
// weights we brute-force the 7×7×7 answer grid for the combination whose resulting
// weights are closest (least-squares) to the persona's stored priorities.
function bestFitAnswers(target: PriorityWeights): { q1: number; q2: number; q3: number } {
  let best = DEFAULT_ANSWERS;
  let bestError = Infinity;
  for (let q1 = 1; q1 <= 7; q1++) {
    for (let q2 = 1; q2 <= 7; q2++) {
      for (let q3 = 1; q3 <= 7; q3++) {
        const w = computeWeights(q1, q2, q3);
        const error =
          (w.cost - target.cost) ** 2 +
          (w.time - target.time) ** 2 +
          (w.sustainability - target.sustainability) ** 2;
        if (error < bestError) {
          bestError = error;
          best = { q1, q2, q3 };
        }
      }
    }
  }
  return best;
}

export function PrioritiesPage({ priorities, onChange }: PrioritiesPageProps) {
  const t = useT();
  const [answers, setAnswers] = useState(() => bestFitAnswers(priorities));

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
            {t("priorities.heading")}
          </h1>
          <button
            type="button"
            onClick={handleReset}
            className="text-sm text-gray-400 hover:text-gray-600 bg-transparent border-0 cursor-pointer p-0 whitespace-nowrap flex-shrink-0 mt-1"
          >
            {t("common.reset")}
          </button>
        </div>
        <p className="text-gray-500 leading-relaxed m-0">
          {t("priorities.subheading")}
        </p>
      </div>

      <div className="flex flex-col gap-6">
        {QUESTIONS.map((q) => (
          <div key={q.id} className="flex flex-col gap-3">
            <p className="text-sm font-medium text-gray-800 m-0 leading-snug">{t(q.statementKey)}</p>
            <LikertControl
              value={answers[q.id]}
              onChange={(v) => handleChange(q.id, v)}
              leftLabel={t(q.leftLabelKey)}
              rightLabel={t(q.rightLabelKey)}
            />
          </div>
        ))}
      </div>

      {/* Consistency warning — only shown when answers are contradictory */}
      {allAnswered && isInconsistent && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl px-4 py-3 flex gap-2 items-start">
          <span className="text-yellow-500 text-base leading-none mt-0.5">⚠</span>
          <p className="text-xs text-yellow-800 m-0 leading-relaxed">
            {t("priorities.consistencyWarning", { cr: cr.toFixed(2) })}
          </p>
        </div>
      )}

      <div className="flex flex-col gap-2 pt-2 border-t border-gray-100">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide m-0 mb-1">
          {t("priorities.yourPriorities")}
        </p>
        <WeightBar label={t("priorities.weight.cost")} pct={Math.round(weights.cost * 100)}           color="bg-brand-red" />
        <WeightBar label={t("priorities.weight.time")} pct={Math.round(weights.time * 100)}            color="bg-gray-700" />
        <WeightBar label={t("priorities.weight.co2")}  pct={Math.round(weights.sustainability * 100)}  color="bg-green-500" />
      </div>
    </div>
  );
}
