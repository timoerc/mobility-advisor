import { useState } from "react";
import { ConfidenceBadge } from "../../components/ConfidenceBadge";
import { MetricTile } from "../../components/MetricTile";
import { AlternativeRow } from "../../components/AlternativeRow";
import type { Alternative, Recommendation } from "../../types/recommendation";
import type { MobilityArchetype } from "../../mobility-archetypes";
import { CARD, BTN_PRIMARY } from "../../ui";

type DashboardPageProps = {
  recommendation: Recommendation;
  mobilityArchetype?: MobilityArchetype;
  onProceed: (alt: Alternative) => void;
};

export function DashboardPage({
  recommendation: rec,
  mobilityArchetype,
  onProceed,
}: DashboardPageProps) {
  const [showAssumptions, setShowAssumptions] = useState(false);
  const [selectedId, setSelectedId] = useState(
    () =>
      rec.alternatives.find((a) => a.isRecommended)?.id ??
      rec.alternatives[0]?.id,
  );
  const selected =
    rec.alternatives.find((a) => a.id === selectedId) ?? rec.alternatives[0];

  return (
    <div className="flex flex-col gap-4">
      {/* Summary card */}
      <div className={`${CARD} p-5 flex flex-col gap-3`}>
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-2xl font-bold leading-tight text-ink m-0">
            {rec.verdict}
          </h1>
          <ConfidenceBadge level={rec.confidence} />
        </div>
        <p className="text-gray-500 leading-relaxed m-0 text-sm">
          {rec.summaryText}
        </p>
      </div>

      {/* Metrics */}
      <div className="flex gap-3">
        {rec.metrics.map((m, i) => (
          <MetricTile key={i} metric={m} />
        ))}
      </div>

      {/* Reasoning */}
      <div className={`${CARD} p-5 flex flex-col gap-3`}>
        <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide m-0">
          Why this recommendation?
        </h2>
        <ul className="m-0 pl-4 flex flex-col gap-2">
          {rec.reasoning.map((r, i) => (
            <li key={i} className="text-sm text-gray-600 leading-relaxed">
              {r}
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={() => setShowAssumptions((v) => !v)}
          className="text-xs text-gray-400 hover:text-gray-600 bg-transparent border-0 cursor-pointer p-0 text-left w-fit underline underline-offset-2 transition-colors"
        >
          {showAssumptions ? "Hide assumptions" : "Show assumptions"}
        </button>
        {showAssumptions && (
          <ul className="m-0 pl-4 flex flex-col gap-1.5 border-t border-gray-100 pt-3">
            {rec.assumptions.map((a, i) => (
              <li key={i} className="text-xs text-gray-400 leading-relaxed">
                {a}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Data quality warnings — deterministic, from the trip-projection engine, not the
          narrative text, so they surface even if the LLM's prose doesn't mention them */}
      {rec.dataQualityWarnings && rec.dataQualityWarnings.length > 0 && (
        <div className="bg-amber-50 rounded-2xl border border-amber-200 p-5 flex flex-col gap-2 shadow-card">
          <h2 className="text-sm font-bold text-amber-800 uppercase tracking-wide m-0">
            Data quality notes
          </h2>
          <ul className="m-0 pl-4 flex flex-col gap-1.5">
            {rec.dataQualityWarnings.map((w, i) => (
              <li key={i} className="text-xs text-amber-700 leading-relaxed">
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Mobility archetype */}
      {mobilityArchetype && (
        <div className={`${CARD} p-5 flex flex-col gap-3`}>
          <div className="flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${mobilityArchetype.color}`}
            />
            <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wide m-0">
              Your mobility profile
            </h2>
          </div>
          <div>
            <p className="font-semibold text-ink m-0 text-sm">
              {mobilityArchetype.name}
            </p>
            <p className="text-xs text-gray-500 m-0 mt-0.5">
              {mobilityArchetype.tagline}
            </p>
          </div>
          <p className="text-xs text-gray-600 leading-relaxed m-0">
            {mobilityArchetype.description}
          </p>
          <div className="border-t border-gray-100 pt-3 flex flex-col gap-2">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide m-0">
              Portfolio implications
            </p>
            <ul className="m-0 pl-4 flex flex-col gap-1.5">
              {mobilityArchetype.portfolioInsights.map((insight, i) => (
                <li key={i} className="text-xs text-gray-600 leading-relaxed">
                  {insight}
                </li>
              ))}
            </ul>
          </div>
          <p className="text-[10px] text-gray-400 m-0 leading-relaxed">
            Source: {mobilityArchetype.source}
          </p>
        </div>
      )}

      {/* Alternatives */}
      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide m-0 px-1">
          Alternatives
        </h2>
        <div className="flex flex-col gap-2">
          {rec.alternatives.map((alt) => (
            <AlternativeRow
              key={alt.id}
              alt={alt}
              selected={alt.id === selectedId}
              onSelect={() => setSelectedId(alt.id)}
            />
          ))}
        </div>
      </div>

      {/* CTA */}
      <div className="pt-2 pb-4">
        <button
          type="button"
          onClick={() => onProceed(selected)}
          className={`w-full ${BTN_PRIMARY}`}
        >
          {selected.action === null
            ? "Confirm: keep my current setup →"
            : "Continue →"}
        </button>
      </div>
    </div>
  );
}
