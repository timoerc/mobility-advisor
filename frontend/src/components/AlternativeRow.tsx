import type { Alternative } from "../types/recommendation";

export function AlternativeRow({ alt }: { alt: Alternative }) {
  const savingsPositive = alt.savingsVsCurrentEur > 0;
  const savingsNeutral = alt.savingsVsCurrentEur === 0;

  return (
    <div
      className={`rounded-xl border-2 p-4 flex flex-col gap-2 transition-colors ${
        alt.isRecommended ? "border-brand-red bg-red-50" : "border-gray-200 bg-white"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-sm text-[#1f1f1f]">{alt.name}</span>
          {alt.isRecommended && (
            <span className="text-xs bg-brand-red text-white rounded-full px-2 py-0.5 font-semibold">
              Recommended
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
              {savingsPositive ? `–€${alt.savingsVsCurrentEur}` : `+€${Math.abs(alt.savingsVsCurrentEur)}`}
              {" vs. status quo"}
            </p>
          )}
        </div>
      </div>
      <p className="text-xs text-gray-500 m-0 leading-relaxed">{alt.tradeoff}</p>
      {alt.co2Impact && (
        <p className="text-xs text-green-600 m-0 font-medium">{alt.co2Impact}</p>
      )}
    </div>
  );
}
