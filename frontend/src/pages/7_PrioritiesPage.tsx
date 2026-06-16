import { useState } from "react";
import type { PriorityWeights } from "../types";

type PrioritiesPageProps = {
  priorities: PriorityWeights;
  onChange: (priorities: PriorityWeights) => void;
};

const LABELS: Record<keyof PriorityWeights, string> = {
  cost: "Cost",
  time: "Time",
  sustainability: "Sustainability",
};

const DESCRIPTIONS: Record<keyof PriorityWeights, string> = {
  cost: "Keep monthly expenses low",
  time: "Arrive quickly, fewer delays",
  sustainability: "Prefer lower-emission options",
};

const PRIORITY_KEYS: Array<keyof PriorityWeights> = [
  "cost",
  "time",
  "sustainability",
];

const EQUAL_RAW: Record<keyof PriorityWeights, number> = {
  cost: 33,
  time: 33,
  sustainability: 34,
};

export function PrioritiesPage({ priorities, onChange }: PrioritiesPageProps) {
  const [raw, setRaw] = useState<Record<keyof PriorityWeights, number>>({
    cost: Math.round(priorities.cost * 100),
    time: Math.round(priorities.time * 100),
    sustainability: Math.round(priorities.sustainability * 100),
  });

  const total = PRIORITY_KEYS.reduce((sum, k) => sum + raw[k], 0);

  const handleReset = () => {
    setRaw({ ...EQUAL_RAW });
    onChange({ cost: 1 / 3, time: 1 / 3, sustainability: 1 / 3 });
  };

  const handleChange = (key: keyof PriorityWeights, value: number) => {
    const next = { ...raw, [key]: value };
    setRaw(next);

    const nextTotal = PRIORITY_KEYS.reduce((sum, k) => sum + next[k], 0);
    if (nextTotal === 0) return;

    onChange(
      Object.fromEntries(
        PRIORITY_KEYS.map((k) => [k, next[k] / nextTotal])
      ) as PriorityWeights
    );
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
          Adjust the sliders to reflect how much each factor matters. Values
          are automatically balanced.
        </p>
      </div>

      <div className="flex flex-col gap-5">
        {PRIORITY_KEYS.map((key) => {
          const pct = total > 0 ? Math.round((raw[key] / total) * 100) : 0;
          return (
            <label key={key} className="flex flex-col gap-1">
              <div className="flex justify-between items-baseline">
                <span className="font-semibold text-sm">{LABELS[key]}</span>
                <span className="text-sm text-brand-red font-bold tabular-nums">
                  {pct}%
                </span>
              </div>
              <p className="text-xs text-gray-400 m-0">{DESCRIPTIONS[key]}</p>
              <input
                type="range"
                min="0"
                max="100"
                step="1"
                value={raw[key]}
                onChange={(e) => handleChange(key, Number(e.target.value))}
                className="mt-1"
              />
            </label>
          );
        })}
      </div>
    </div>
  );
}
