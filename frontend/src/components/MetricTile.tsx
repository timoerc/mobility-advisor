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
  return (
    <div className={`flex-1 rounded-xl p-4 border ${s.bg} ${s.border} text-center`}>
      <p className={`text-2xl font-black m-0 leading-none ${s.value}`}>
        {prefix}{metric.value}
        <span className="text-sm font-semibold ml-1">{metric.unit}</span>
      </p>
      <p className="text-xs text-gray-500 m-0 mt-1.5 leading-snug">{metric.label}</p>
    </div>
  );
}
