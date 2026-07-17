import type { Alternative } from "../types/recommendation";

type AlternativeRowProps = {
  alt: Alternative;
  selected: boolean;
  onSelect: () => void;
  // When true, render a static, non-interactive row (used by the read-only History ledger). The
  // `selected` flag then means "this is the alternative that was executed" and shows an "Executed"
  // marker instead of the interactive "Selected" pill.
  readOnly?: boolean;
};

export function AlternativeRow({ alt, selected, onSelect, readOnly = false }: AlternativeRowProps) {
  const savingsPositive = alt.savingsVsCurrentEur > 0;
  const savingsNeutral = alt.savingsVsCurrentEur === 0;
  const co2Kg = alt.co2ImpactKg ?? 0;
  const co2Positive = co2Kg > 0; // saves CO2 vs. current
  const co2Negative = co2Kg < 0; // emits more CO2 vs. current

  const borderClass = readOnly
    ? selected
      ? "border-green-300 bg-green-50/60"
      : "border-gray-200"
    : selected
      ? "border-brand-red bg-red-50 ring-2 ring-brand-red/30"
      : alt.isRecommended
        ? "border-red-200 hover:border-brand-red/60"
        : "border-gray-200 hover:border-gray-300";

  const content = (
    <>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-sm text-[#1f1f1f]">{alt.name}</span>
          {alt.isRecommended && (
            <span className="text-xs bg-brand-red text-white rounded-full px-2 py-0.5 font-semibold">
              Recommended
            </span>
          )}
          {!readOnly && selected && (
            <span className="text-xs bg-white text-brand-red border border-brand-red rounded-full px-2 py-0.5 font-semibold">
              Selected
            </span>
          )}
          {readOnly && selected && (
            <span className="text-xs bg-green-600 text-white rounded-full px-2 py-0.5 font-semibold">
              Executed
            </span>
          )}
        </div>
        <div className="text-right flex-shrink-0">
          <p className="text-sm font-bold text-[#1f1f1f] m-0">
            {alt.annualCostEur === 0 ? "€0 / year" : `€${alt.annualCostEur.toFixed(0)} / year`}
          </p>
          {!savingsNeutral && (
            <p
              className={`text-xs font-semibold m-0 ${
                savingsPositive ? "text-green-700" : "text-red-600"
              }`}
            >
              {savingsPositive ? `–€${Math.round(alt.savingsVsCurrentEur)}` : `+€${Math.round(Math.abs(alt.savingsVsCurrentEur))}`}
              {" vs. status quo"}
            </p>
          )}
        </div>
      </div>
      <p className="text-xs text-gray-500 m-0 leading-relaxed">{alt.tradeoff}</p>
      {(co2Kg !== 0 || alt.co2Impact) && (
        <p
          className={`text-xs font-medium m-0 ${
            co2Positive ? "text-green-600" : co2Negative ? "text-red-600" : "text-gray-500"
          }`}
        >
          <span className="font-semibold">CO₂ impact: </span>
          {co2Kg !== 0
            ? `${co2Positive ? "–" : "+"}${Math.round(Math.abs(co2Kg))} kg CO₂/year`
            : "Neutral"}
        </p>
      )}
    </>
  );

  if (readOnly) {
    return (
      <div className={`w-full text-left rounded-xl border-2 p-4 flex flex-col gap-2 bg-white ${borderClass}`}>
        {content}
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`w-full text-left rounded-xl border-2 p-4 flex flex-col gap-2 transition-colors cursor-pointer bg-white ${borderClass}`}
    >
      {content}
    </button>
  );
}
