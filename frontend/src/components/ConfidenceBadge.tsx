import { useT } from "../i18n";
import type { ConfidenceLevel } from "../types/recommendation";

// `level` (the backend's confidence enum) stays untranslated — only the display label below is
// localized, via the confidence.* family in en.ts/de.ts.
const CONFIG: Record<ConfidenceLevel, { labelKey: "confidence.high" | "confidence.medium" | "confidence.low"; dot: string; text: string; bg: string }> = {
  high: { labelKey: "confidence.high", dot: "bg-green-500", text: "text-green-700", bg: "bg-green-50 border-green-200" },
  medium: { labelKey: "confidence.medium", dot: "bg-yellow-400", text: "text-yellow-700", bg: "bg-yellow-50 border-yellow-200" },
  low: { labelKey: "confidence.low", dot: "bg-gray-400", text: "text-gray-600", bg: "bg-gray-50 border-gray-200" },
};

export function ConfidenceBadge({ level }: { level: ConfidenceLevel }) {
  const t = useT();
  const c = CONFIG[level];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${c.bg} ${c.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {t(c.labelKey)}
    </span>
  );
}
