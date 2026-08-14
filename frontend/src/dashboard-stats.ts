import type { TripRecord } from "./api";
import type { TranslationKey } from "./i18n";

/** Time-range presets for the home dashboard, in display order. */
export type RangeKey = "1m" | "6m" | "1y" | "ytd" | "5y" | "all";

// labelKey, not label — the component resolves it via t() so this module stays pure/testable
// and doesn't need a language argument threaded through.
export const RANGE_OPTIONS: { key: RangeKey; labelKey: TranslationKey }[] = [
  { key: "1m", labelKey: "range.1m" },
  { key: "6m", labelKey: "range.6m" },
  { key: "1y", labelKey: "range.1y" },
  { key: "ytd", labelKey: "range.ytd" },
  { key: "5y", labelKey: "range.5y" },
  { key: "all", labelKey: "range.all" },
];

export const DEFAULT_RANGE: RangeKey = "1y";

/** Inclusive lower bound for a range, anchored to the frozen reference date (`ref`). Returns null
 *  for "all" (no lower bound). */
function rangeStart(range: RangeKey, ref: Date): Date | null {
  const d = new Date(ref);
  switch (range) {
    case "1m":
      d.setMonth(d.getMonth() - 1);
      return d;
    case "6m":
      d.setMonth(d.getMonth() - 6);
      return d;
    case "1y":
      d.setFullYear(d.getFullYear() - 1);
      return d;
    case "5y":
      d.setFullYear(d.getFullYear() - 5);
      return d;
    case "ytd":
      return new Date(ref.getFullYear(), 0, 1);
    case "all":
      return null;
  }
}

/** Keep trips within [rangeStart, referenceDate]. Trips after the frozen "today" or with an
 *  unparseable date are dropped. The reference date — not the real clock — is the upper anchor,
 *  because the mock trips are all dated relative to it. */
export function filterTripsByRange(
  trips: TripRecord[],
  referenceDate: string,
  range: RangeKey,
): TripRecord[] {
  const ref = new Date(referenceDate);
  const start = rangeStart(range, ref);
  return trips.filter((t) => {
    const d = new Date(t.date);
    if (Number.isNaN(d.getTime())) return false;
    if (d > ref) return false;
    if (start && d < start) return false;
    return true;
  });
}

export type TripStats = {
  count: number;
  totalCo2Kg: number;
  totalSpendEur: number;
  totalDistanceKm: number;
};

/** Sum CO2, spend, distance and count over a set of trips; nulls count as zero. */
export function aggregateTrips(trips: TripRecord[]): TripStats {
  return trips.reduce<TripStats>(
    (acc, t) => ({
      count: acc.count + 1,
      totalCo2Kg: acc.totalCo2Kg + (t.co2_emission_kg ?? 0),
      totalSpendEur: acc.totalSpendEur + (t.cost_eur ?? 0),
      totalDistanceKm: acc.totalDistanceKm + (t.distance_km ?? 0),
    }),
    { count: 0, totalCo2Kg: 0, totalSpendEur: 0, totalDistanceKm: 0 },
  );
}

export type ModeBucket = {
  mode: string;
  trips: number;
  co2Kg: number;
  spendEur: number;
  distanceKm: number;
};

/** Group trips by mode, summing each measure. Order is not defined here — callers sort by whichever
 *  measure the widget ranks on (trip count for modes-by-usage, CO2 for the emissions breakdown). */
export function bucketByMode(trips: TripRecord[]): ModeBucket[] {
  const map = new Map<string, ModeBucket>();
  for (const t of trips) {
    const b =
      map.get(t.mode) ?? { mode: t.mode, trips: 0, co2Kg: 0, spendEur: 0, distanceKm: 0 };
    b.trips += 1;
    b.co2Kg += t.co2_emission_kg ?? 0;
    b.spendEur += t.cost_eur ?? 0;
    b.distanceKm += t.distance_km ?? 0;
    map.set(t.mode, b);
  }
  return [...map.values()];
}

/** Most recent trips first (by date), capped at `limit`. */
export function recentTrips(trips: TripRecord[], limit: number): TripRecord[] {
  return [...trips]
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0))
    .slice(0, limit);
}
