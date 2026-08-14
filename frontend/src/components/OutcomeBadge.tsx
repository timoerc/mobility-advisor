import { useT } from "../i18n";
import type { AnalysisOutcome } from "../types/recommendation";

// `outcome` (the backend's enum) stays untranslated — only the display label is localized, via
// the outcome.* family in en.ts/de.ts.
const CONFIG: Record<AnalysisOutcome, { labelKey: "outcome.pending" | "outcome.kept_current" | "outcome.executed"; dot: string; text: string; bg: string }> = {
  pending: { labelKey: "outcome.pending", dot: "bg-gray-400", text: "text-gray-600", bg: "bg-gray-50 border-gray-200" },
  kept_current: { labelKey: "outcome.kept_current", dot: "bg-yellow-400", text: "text-yellow-700", bg: "bg-yellow-50 border-yellow-200" },
  executed: { labelKey: "outcome.executed", dot: "bg-green-500", text: "text-green-700", bg: "bg-green-50 border-green-200" },
};

export function OutcomeBadge({ outcome }: { outcome: AnalysisOutcome }) {
  const t = useT();
  const c = CONFIG[outcome];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${c.bg} ${c.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {t(c.labelKey)}
    </span>
  );
}
