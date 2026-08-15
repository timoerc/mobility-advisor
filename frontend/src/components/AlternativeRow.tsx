import { useI18n, formatInt as fmtInt, formatDurationMin, formatCurrency } from "../i18n";
import type { Alternative } from "../types/recommendation";
import type { Language } from "../i18n";

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

// Signed delta formatters. Take `lang` explicitly (rather than reading useI18n() themselves)
// because they're built once per render into plain `(value) => string` closures below and
// handed to <DeltaBadge format={...}> — that keeps DeltaBadge itself formatting-agnostic.
function formatEurDelta(lang: Language, value: number, perYear: string): string {
  const sign = value < 0 ? "−" : "+"; // U+2212 minus sign, not a hyphen — matches the design's typography
  return `${sign}${formatCurrency(lang, Math.abs(value))} ${perYear}`;
}

function formatCo2Delta(lang: Language, value: number): string {
  const sign = value < 0 ? "−" : "+";
  return `${sign}${fmtInt(lang, Math.abs(value))} kg`;
}

function formatTimeDelta(lang: Language, value: number): string {
  const body = formatDurationMin(lang, value);
  return value < 0 ? body : `+${body}`;
}

// Renders the structured added/removed product lists as distinct chips (one per product,
// colored by direction) instead of the caller having to parse them back out of `alt.name` /
// `alt.tradeoff`'s free-text sentence.
function ActionChips({ added, removed }: { added: string[]; removed: string[] }) {
  if (added.length === 0 && removed.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {removed.map((product) => (
        <span
          key={`remove-${product}`}
          className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-red-50 text-red-600"
        >
          − {product}
        </span>
      ))}
      {added.map((product) => (
        <span
          key={`add-${product}`}
          className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-green-50 text-green-700"
        >
          + {product}
        </span>
      ))}
    </div>
  );
}

function DeltaBadge({
  value,
  threshold,
  format,
  noChangeLabel,
}: {
  value: number;
  threshold: number;
  format: (value: number) => string;
  noChangeLabel: string;
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
      {isNeutral ? noChangeLabel : format(value)}
    </span>
  );
}

export function AlternativeRow({ alt, selected, onSelect, readOnly = false }: AlternativeRowProps) {
  const { language, t } = useI18n();
  const formatEur = (value: number) => formatEurDelta(language, value, t("alternativeRow.perYearShort"));
  const formatCo2 = (value: number) => formatCo2Delta(language, value);
  const formatTime = (value: number) => formatTimeDelta(language, value);
  const savingsPositive = alt.savingsVsCurrentEur > 0;
  const savingsNeutral = alt.savingsVsCurrentEur === 0;
  const slots = vsCurrentSlots(alt);

  const borderClass = readOnly
    ? selected
      ? "border-green-300 bg-green-50/60"
      : "border-gray-200"
    : selected
      ? "border-brand-red bg-red-50 ring-2 ring-brand-red/30 shadow-card"
      : alt.isRecommended
        ? "border-red-200 hover:border-brand-red/60 hover:shadow-lift hover:-translate-y-0.5"
        : "border-gray-200 hover:border-gray-300 hover:shadow-lift hover:-translate-y-0.5";

  const content = (
    <>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-sm text-ink">{alt.name}</span>
          {alt.isRecommended && (
            <span className="text-xs bg-brand-red text-white rounded-full px-2 py-0.5 font-semibold">
              {t("alternativeRow.recommended")}
            </span>
          )}
          {!readOnly && selected && (
            <span className="text-xs bg-white text-brand-red border border-brand-red rounded-full px-2 py-0.5 font-semibold">
              {t("alternativeRow.selected")}
            </span>
          )}
          {readOnly && selected && (
            <span className="text-xs bg-green-600 text-white rounded-full px-2 py-0.5 font-semibold">
              {t("alternativeRow.executed")}
            </span>
          )}
        </div>
        <div className="text-right flex-shrink-0">
          <p className="text-sm font-bold text-ink m-0">
            {formatCurrency(language, alt.annualCostEur)} {t("alternativeRow.perYear")}
          </p>
          {!savingsNeutral && (
            <p
              className={`text-xs font-semibold m-0 ${
                savingsPositive ? "text-green-700" : "text-red-600"
              }`}
            >
              {savingsPositive ? `–${formatCurrency(language, alt.savingsVsCurrentEur)}` : `+${formatCurrency(language, Math.abs(alt.savingsVsCurrentEur))}`}
              {" "}{t("alternativeRow.vsStatusQuo")}
            </p>
          )}
        </div>
      </div>

      <ActionChips added={alt.addedProducts ?? []} removed={alt.removedProducts ?? []} />

      <div className="mt-0.5">
        <span className="text-[11px] text-gray-400">{t("alternativeRow.vsCurrentSetup")}</span>
        <div className="flex flex-wrap gap-4 mt-1">
          <div className="flex flex-col gap-0.5 items-start">
            <DeltaBadge value={slots.costEur} threshold={1} format={formatEur} noChangeLabel={t("alternativeRow.noChange")} />
            <span className="text-[10px] text-gray-400 uppercase tracking-wide">{t("alternativeRow.cost")}</span>
          </div>
          <div className="flex flex-col gap-0.5 items-start">
            <DeltaBadge value={slots.co2Kg} threshold={1} format={formatCo2} noChangeLabel={t("alternativeRow.noChange")} />
            <span className="text-[10px] text-gray-400 uppercase tracking-wide">{t("alternativeRow.co2")}</span>
          </div>
          {slots.timeMin !== null && (
            <div className="flex flex-col gap-0.5 items-start">
              <DeltaBadge value={slots.timeMin} threshold={15} format={formatTime} noChangeLabel={t("alternativeRow.noChange")} />
              <span className="text-[10px] text-gray-400 uppercase tracking-wide">{t("alternativeRow.travelTime")}</span>
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
      className={`w-full text-left rounded-xl border-2 p-4 flex flex-col gap-2 cursor-pointer bg-white active:translate-y-0 transition-[border-color,box-shadow,transform,background-color] duration-200 ease-soft ${borderClass}`}
    >
      {content}
    </button>
  );
}
