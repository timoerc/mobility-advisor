import { useEffect, useState } from "react";
import { fetchAnalysisHistory } from "../../api";
import { ConfidenceBadge } from "../../components/ConfidenceBadge";
import { OutcomeBadge } from "../../components/OutcomeBadge";
import { MetricTile } from "../../components/MetricTile";
import { AlternativeRow } from "../../components/AlternativeRow";
import type { AnalysisHistoryEntry } from "../../types/recommendation";

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function HistoryCard({ entry, expanded, onToggle }: { entry: AnalysisHistoryEntry; expanded: boolean; onToggle: () => void }) {
  const rec = entry.recommendation;
  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="w-full text-left p-4 flex flex-col gap-2 cursor-pointer border-0 bg-transparent"
      >
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-gray-400 font-medium">{formatDate(entry.date)}</span>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`text-gray-400 flex-shrink-0 transition-transform ${expanded ? "rotate-180" : ""}`}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
        <p className="font-semibold text-sm text-[#1f1f1f] m-0 leading-snug">{rec.verdict}</p>
        <div className="flex items-center gap-2 flex-wrap">
          <ConfidenceBadge level={rec.confidence} />
          <OutcomeBadge outcome={entry.outcome} />
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 flex flex-col gap-4 border-t border-gray-100 pt-4">
          <p className="text-sm text-gray-500 leading-relaxed m-0">{rec.summaryText}</p>

          <div className="flex gap-3">
            {rec.metrics.map((m, i) => (
              <MetricTile key={i} metric={m} />
            ))}
          </div>

          <div className="flex flex-col gap-2">
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wide m-0">Why this recommendation?</h3>
            <ul className="m-0 pl-4 flex flex-col gap-1.5">
              {rec.reasoning.map((r, i) => (
                <li key={i} className="text-sm text-gray-600 leading-relaxed">{r}</li>
              ))}
            </ul>
          </div>

          {rec.assumptions.length > 0 && (
            <div className="flex flex-col gap-1.5 border-t border-gray-100 pt-3">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wide m-0">Assumptions</h3>
              <ul className="m-0 pl-4 flex flex-col gap-1">
                {rec.assumptions.map((a, i) => (
                  <li key={i} className="text-xs text-gray-400 leading-relaxed">{a}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-col gap-2">
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wide m-0">Alternatives</h3>
            <div className="flex flex-col gap-2">
              {rec.alternatives.map((alt) => (
                <AlternativeRow
                  key={alt.id}
                  alt={alt}
                  selected={alt.id === entry.resolvedAlternativeId}
                  onSelect={() => {}}
                />
              ))}
            </div>
          </div>

          {entry.resolvedMessage && (
            <p className="text-xs text-gray-500 leading-relaxed m-0 border-t border-gray-100 pt-3">
              {entry.resolvedMessage}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function HistoryPage() {
  const [entries, setEntries] = useState<AnalysisHistoryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalysisHistory()
      .then(setEntries)
      .catch((err) => {
        console.error("Failed to load analysis history:", err);
        setError(err instanceof Error ? err.message : "Could not load your analysis history.");
      });
  }, []);

  if (error) {
    return (
      <div className="min-h-[40vh] flex flex-col items-center justify-center gap-3 py-12 text-center">
        <p className="text-sm text-gray-500 m-0">{error}</p>
      </div>
    );
  }

  if (entries === null) {
    return (
      <div className="min-h-[40vh] flex flex-col items-center justify-center gap-3 py-12 text-center">
        <p className="text-sm text-gray-400 m-0">Loading your analysis history…</p>
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="min-h-[40vh] flex flex-col items-center justify-center gap-2 py-12 text-center">
        <h2 className="text-lg font-bold text-[#1f1f1f] m-0">No analyses yet</h2>
        <p className="text-sm text-gray-500 m-0 max-w-xs">
          Run your first analysis from Home and it'll show up here.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold leading-tight mb-1">History</h1>
        <p className="text-gray-500 text-sm m-0">Past analyses and the decisions you made.</p>
      </div>

      <div className="flex flex-col gap-3 pb-4">
        {entries.map((entry) => (
          <HistoryCard
            key={entry.id}
            entry={entry}
            expanded={expandedId === entry.id}
            onToggle={() => setExpandedId((current) => (current === entry.id ? null : entry.id))}
          />
        ))}
      </div>
    </div>
  );
}
