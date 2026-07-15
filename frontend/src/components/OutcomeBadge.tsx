import type { AnalysisOutcome } from "../types/recommendation";

const CONFIG: Record<AnalysisOutcome, { label: string; dot: string; text: string; bg: string }> = {
  pending: { label: "Pending decision", dot: "bg-gray-400", text: "text-gray-600", bg: "bg-gray-50 border-gray-200" },
  kept_current: { label: "Kept current setup", dot: "bg-yellow-400", text: "text-yellow-700", bg: "bg-yellow-50 border-yellow-200" },
  executed: { label: "Executed", dot: "bg-green-500", text: "text-green-700", bg: "bg-green-50 border-green-200" },
};

export function OutcomeBadge({ outcome }: { outcome: AnalysisOutcome }) {
  const c = CONFIG[outcome];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${c.bg} ${c.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}
