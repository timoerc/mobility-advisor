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

// vs. current setup slots: negative always means better than current (cheaper / greener /
// faster), so all three read the same way and share one color rule.
type VsCurrentSlots = {
  costEur: number;
  co2Kg: number;
  timeMin: number | null; // null => omit the slot (legacy history entries with no time data)
};

function vsCurrentSlots(alt: Alternative): VsCurrentSlots {
  if (alt.deltaVsCurrent) {
    return {
      costEur: alt.deltaVsCurrent.costEur,
      co2Kg: alt.deltaVsCurrent.co2Kg,
      timeMin: alt.deltaVsCurrent.timeMin,
    };
  }
  // Legacy fallback for analysis_history.json entries seeded before deltaVsCurrent existed:
  // savingsVsCurrentEur/co2ImpactKg use the opposite sign convention (positive = better).
  return {
    costEur: -alt.savingsVsCurrentEur,
    co2Kg: -(alt.co2ImpactKg ?? 0),
    timeMin: null,
  };
}

function formatEur(value: number): string {
  const sign = value < 0 ? "−" : "+";
  return `${sign}€${Math.round(Math.abs(value))} /yr`;
}

function formatCo2(value: number): string {
  const sign = value < 0 ? "−" : "+";
  return `${sign}${Math.round(Math.abs(value))} kg`;
}

function formatTime(value: number): string {
  const sign = value < 0 ? "−" : "+";
  const absMin = Math.abs(value);
  if (absMin < 90) return `${sign}${Math.round(absMin)} min`;
  const hours = Math.floor(absMin / 60);
  const mins = Math.round(absMin % 60);
  return `${sign}${hours} h ${mins}`;
}

function DeltaBadge({
  value,
  threshold,
  format,
}: {
  value: number;
  threshold: number;
  format: (value: number) => string;
}) {
  const isNeutral = Math.abs(value) < threshold;
  const isGood = !isNeutral && value < 0;
  const isBad = !isNeutral && value > 0;
  const color = isGood
    ? "text-green-700 bg-green-50"
    : isBad
      ? "text-red-600 bg-red-50"
      : "text-gray-500 bg-gray-50";
  return (
    <span className={`text-[11px] font-medium px-1.5 py-0.5 rounded ${color}`}>
      {isNeutral ? "no change" : format(value)}
    </span>
  );
}

export function AlternativeRow({ alt, selected, onSelect, readOnly = false }: AlternativeRowProps) {
  const savingsPositive = alt.savingsVsCurrentEur > 0;
  const savingsNeutral = alt.savingsVsCurrentEur === 0;
  const slots = vsCurrentSlots(alt);

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

      <div className="mt-0.5">
        <span className="text-[11px] text-gray-400">vs. your current setup</span>
        <div className="flex flex-wrap gap-4 mt-1">
          <div className="flex flex-col gap-0.5 items-start">
            <DeltaBadge value={slots.costEur} threshold={1} format={formatEur} />
            <span className="text-[10px] text-gray-400 uppercase tracking-wide">cost</span>
          </div>
          <div className="flex flex-col gap-0.5 items-start">
            <DeltaBadge value={slots.co2Kg} threshold={1} format={formatCo2} />
            <span className="text-[10px] text-gray-400 uppercase tracking-wide">CO₂</span>
          </div>
          {slots.timeMin !== null && (
            <div className="flex flex-col gap-0.5 items-start">
              <DeltaBadge value={slots.timeMin} threshold={15} format={formatTime} />
              <span className="text-[10px] text-gray-400 uppercase tracking-wide">travel time</span>
            </div>
          )}
        </div>
      </div>

      <p className="text-xs text-gray-500 m-0 leading-relaxed">{alt.tradeoff}</p>
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
