import type { BucketUnit, SpendBucket } from "../dashboard-stats";

// Trip spend is the variable part the advisor can act on; subscriptions are the fixed,
// already-committed base. Validated (dataviz palette check) against the white card surface:
// lightness band, chroma floor, and CVD separation all pass (worst adjacent ΔE 19.1 normal-vision).
const TRIP_COLOR = "#ec0016"; // --color-brand-red
const SUB_COLOR = "#2f6f9f"; // muted steel blue

const CHART_HEIGHT = 160; // px

const fmtEur = (n: number) => `€${Math.round(n).toLocaleString("de-DE")}`;

function unitNoun(unit: BucketUnit): string {
  return unit === "week" ? "week" : unit === "month" ? "month" : "quarter";
}

/** Home-dashboard spend-over-time chart: stacked bars of trip spend + inferred subscription
 *  cost per bucket. Hand-rolled divs (no charting lib in this project), matching the
 *  MeasureBar idiom used elsewhere on the dashboard. */
export function SpendChart({ buckets, unit }: { buckets: SpendBucket[]; unit: BucketUnit }) {
  const maxTotal = Math.max(...buckets.map((b) => b.tripEur + b.subEur), 0);
  const totalTrip = buckets.reduce((s, b) => s + b.tripEur, 0);
  const totalSub = buckets.reduce((s, b) => s + b.subEur, 0);

  // Thin out x-axis labels once bars get numerous, so they never collide on narrow viewports.
  const labelEvery = buckets.length <= 8 ? 1 : buckets.length <= 16 ? 2 : 3;

  return (
    <div>
      {/* Legend — always present for 2 series; identity never rests on color alone. */}
      <div className="flex items-center gap-4 mb-4">
        <span className="flex items-center gap-1.5 text-xs text-gray-500">
          <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: TRIP_COLOR }} />
          Trips
        </span>
        <span className="flex items-center gap-1.5 text-xs text-gray-500">
          <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: SUB_COLOR }} />
          Subscriptions
        </span>
      </div>

      <div className="relative" style={{ height: CHART_HEIGHT }}>
        {maxTotal > 0 && (
          <span className="absolute -top-4 right-0 text-[10px] text-gray-400 tabular-nums">
            {fmtEur(maxTotal)}
          </span>
        )}
        <div className="absolute inset-x-0 top-0 border-t border-gray-100" aria-hidden="true" />
        <div className="absolute inset-x-0 bottom-0 border-t border-gray-200" aria-hidden="true" />

        <div className="absolute inset-0 flex items-end gap-1">
          {buckets.map((b) => {
            const total = b.tripEur + b.subEur;
            const subPx = maxTotal ? (b.subEur / maxTotal) * CHART_HEIGHT : 0;
            const tripPx = maxTotal ? (b.tripEur / maxTotal) * CHART_HEIGHT : 0;
            const tooltip = `${b.label} · Trips ${fmtEur(b.tripEur)} · Subscriptions ${fmtEur(
              b.subEur,
            )} · Total ${fmtEur(total)}`;
            return (
              <div key={b.key} className="group relative flex-1 min-w-0 h-full flex flex-col justify-end">
                <div className="mx-auto w-full max-w-6 flex flex-col items-stretch">
                  {tripPx > 0 && (
                    <div
                      className="col-fill rounded-t-[4px]"
                      style={{
                        height: tripPx,
                        backgroundColor: TRIP_COLOR,
                        marginBottom: subPx > 0 ? 2 : 0,
                        // Grows in after the subscription base finishes, not simultaneously with it —
                        // the fixed base settles first, then the variable trip spend stacks on top.
                        animationDelay: subPx > 0 ? "0.6s" : "0s",
                      }}
                    />
                  )}
                  {subPx > 0 && (
                    <div
                      className="col-fill"
                      style={{
                        height: subPx,
                        backgroundColor: SUB_COLOR,
                        borderRadius: tripPx > 0 ? 0 : "4px 4px 0 0",
                      }}
                    />
                  )}
                </div>

                {/* Hover/focus tooltip. The whole slot is the hit target, not just the drawn bar. */}
                <button
                  type="button"
                  tabIndex={0}
                  aria-label={tooltip}
                  className="absolute inset-0 cursor-default"
                >
                  <span
                    className="pop-in pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block group-focus-visible:block whitespace-nowrap rounded-lg bg-ink text-white text-xs px-2.5 py-1.5 shadow-pop z-10"
                    aria-hidden="true"
                  >
                    <span className="block font-semibold">{b.label}</span>
                    <span className="block text-gray-300">Trips {fmtEur(b.tripEur)}</span>
                    <span className="block text-gray-300">Subscriptions {fmtEur(b.subEur)}</span>
                  </span>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* X-axis labels */}
      <div className="flex gap-1 mt-1.5">
        {buckets.map((b, i) => (
          <div key={b.key} className="flex-1 min-w-0 text-center">
            {i % labelEvery === 0 && (
              <span className="text-[10px] text-gray-400 tabular-nums">{b.label}</span>
            )}
          </div>
        ))}
      </div>

      <p className="text-xs text-gray-400 m-0 mt-3 pt-3 border-t border-gray-100">
        {fmtEur(totalTrip + totalSub)} across {buckets.length} {unitNoun(unit)}
        {buckets.length === 1 ? "" : "s"} · {fmtEur(totalTrip)} trips + {fmtEur(totalSub)} subscriptions
      </p>
    </div>
  );
}
