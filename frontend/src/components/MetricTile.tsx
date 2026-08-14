import type { MetricDelta } from "../types/recommendation";

const DIRECTION_STYLE: Record<MetricDelta["direction"], { value: string; bg: string; border: string }> = {
  save: { value: "text-green-700", bg: "bg-green-50", border: "border-green-100" },
  extra_cost: { value: "text-red-600", bg: "bg-red-50", border: "border-red-100" },
  reduce: { value: "text-green-700", bg: "bg-green-50", border: "border-green-100" },
  increase: { value: "text-red-600", bg: "bg-red-50", border: "border-red-100" },
  neutral: { value: "text-gray-700", bg: "bg-gray-50", border: "border-gray-100" },
};

const DIRECTION_PREFIX: Record<MetricDelta["direction"], string> = {
  save: "–",
  extra_cost: "+",
  reduce: "–",
  increase: "+",
  neutral: "",
};

export function MetricTile({ metric }: { metric: MetricDelta }) {
  const s = DIRECTION_STYLE[metric.direction];
  const prefix = DIRECTION_PREFIX[metric.direction];
  // A headline tile can carry a date or a word instead of a number (e.g. a pending-decision
  // tile showing "2026-09-01" or "relocation" — see _build_pending_decision_metrics in
  // main.py). At the numeric-tuned text-2xl/font-black/leading-none/no-wrap sizing, a
  // 10-character string overflows or gets clipped in this flex-1 tile sitting 3-across.
  // Numbers stay large and tight; strings get a smaller size and are allowed to wrap.
  const isNumeric = typeof metric.value === "number";
  return (
    <div className={`flex-1 min-w-0 rounded-xl p-4 border shadow-card ${s.bg} ${s.border} text-center`}>
      <p
        className={`m-0 ${s.value} ${
          isNumeric
            ? "text-2xl font-black leading-none"
            : "text-base font-bold leading-tight break-words"
        }`}
      >
        {prefix}{metric.value}
        <span className="text-sm font-semibold ml-1">{metric.unit}</span>
      </p>
      <p className="text-xs text-gray-500 m-0 mt-1.5 leading-snug">{metric.label}</p>
    </div>
  );
}
