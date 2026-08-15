import type { TripRecord } from "./api";
import type { Language, TranslationKey } from "./i18n";
import { LOCALE_TAG } from "./i18n";
import type { SubscriptionEntry } from "./types";

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
export function rangeStart(range: RangeKey, ref: Date): Date | null {
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

// ── spend-over-time bucketing (home dashboard chart) ───────────────────────────

export type BucketUnit = "week" | "month" | "quarter";

export type SpendBucket = {
  key: string;
  label: string;
  start: Date;
  /** Exclusive. */
  end: Date;
  tripEur: number;
  subEur: number;
};

const MS_PER_DAY = 86_400_000;

function startOfWeek(d: Date): Date {
  const r = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const day = (r.getDay() + 6) % 7; // Monday = 0
  r.setDate(r.getDate() - day);
  return r;
}

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function startOfQuarter(d: Date): Date {
  return new Date(d.getFullYear(), Math.floor(d.getMonth() / 3) * 3, 1);
}

function addUnit(d: Date, unit: BucketUnit): Date {
  const r = new Date(d);
  if (unit === "week") r.setDate(r.getDate() + 7);
  else if (unit === "month") r.setMonth(r.getMonth() + 1);
  else r.setMonth(r.getMonth() + 3);
  return r;
}

/** How many months' worth of a subscription's monthly_cost_eur one bucket of this unit covers. */
function unitMonths(unit: BucketUnit): number {
  return unit === "week" ? 7 / 30.44 : unit === "month" ? 1 : 3;
}

/** Parses a date string, rejecting both unparseable strings and falsy values. Needed because
 *  `new Date(null)` resolves to the Unix epoch instead of Invalid Date — and subscriptions with
 *  no resolvable catalog entry (e.g. Enterprise Silver) carry `started: null` despite the field
 *  being typed as `string`. Without this guard such a subscription reads as "started in 1970"
 *  and blows up the "all"-range window to hundreds of empty buckets. */
function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

function bucketLabel(start: Date, unit: BucketUnit, spansMultipleYears: boolean, language: Language): string {
  const localeTag = LOCALE_TAG[language];
  if (unit === "week") {
    return start.toLocaleDateString(localeTag, { day: "2-digit", month: "2-digit" });
  }
  if (unit === "month") {
    return start.toLocaleDateString(
      localeTag,
      spansMultipleYears ? { month: "short", year: "2-digit" } : { month: "short" },
    );
  }
  const q = Math.floor(start.getMonth() / 3) + 1;
  return `Q${q} '${String(start.getFullYear()).slice(2)}`;
}

/** Buckets trip spend and inferred fixed subscription cost per period across the selected range,
 *  for the home dashboard's spend-over-time chart. Bucket width (week/month/quarter) is picked
 *  from the range's span so a 1-month view doesn't collapse into a single bar and a 5-year view
 *  doesn't produce hundreds of them. Every bucket in the window is emitted, including ones with
 *  no trips, so a quiet month reads as a gap rather than being skipped.
 *
 *  Trip spend is summed from actual trip dates. Subscription spend is *inferred*: only
 *  currently-active subscriptions are known (past/cancelled ones aren't in the data), so each
 *  is assumed to have run unchanged from its `started` date through today, contributing its
 *  monthly-equivalent cost to every bucket from `started` onward — with no proration for the
 *  bucket it starts in. */
export function bucketSpendOverTime(
  trips: TripRecord[],
  subscriptions: SubscriptionEntry[] | null,
  referenceDate: string,
  range: RangeKey,
  language: Language,
): { buckets: SpendBucket[]; unit: BucketUnit } {
  const ref = new Date(referenceDate);
  if (Number.isNaN(ref.getTime())) return { buckets: [], unit: "month" };

  const subs = subscriptions ?? [];
  let start = rangeStart(range, ref);
  if (!start) {
    // "all": fall back to the earliest known trip date or subscription start date.
    const candidates: number[] = [];
    for (const t of trips) {
      const d = new Date(t.date);
      if (!Number.isNaN(d.getTime())) candidates.push(d.getTime());
    }
    for (const s of subs) {
      const d = parseDate(s.started);
      if (d) candidates.push(d.getTime());
    }
    start = candidates.length ? new Date(Math.min(...candidates)) : new Date(ref);
  }

  const spanDays = (ref.getTime() - start.getTime()) / MS_PER_DAY;
  const unit: BucketUnit = spanDays <= 70 ? "week" : spanDays <= 365 * 3 ? "month" : "quarter";

  const alignStart =
    unit === "week" ? startOfWeek(start) : unit === "month" ? startOfMonth(start) : startOfQuarter(start);
  const spansMultipleYears = alignStart.getFullYear() !== ref.getFullYear();

  const inRange = filterTripsByRange(trips, referenceDate, range);

  const buckets: SpendBucket[] = [];
  let cursor = alignStart;
  while (cursor <= ref) {
    const bucketEnd = addUnit(cursor, unit);
    const key =
      unit === "week"
        ? cursor.toISOString().slice(0, 10)
        : unit === "month"
          ? `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}`
          : `${cursor.getFullYear()}-Q${Math.floor(cursor.getMonth() / 3) + 1}`;

    const tripEur = inRange.reduce((sum, t) => {
      const d = new Date(t.date);
      if (Number.isNaN(d.getTime()) || d < cursor || d >= bucketEnd) return sum;
      return sum + (t.cost_eur ?? 0);
    }, 0);

    const subEur = subs.reduce((sum, s) => {
      const started = parseDate(s.started);
      if (!started || started > bucketEnd) return sum;
      return sum + (s.monthly_cost_eur ?? 0) * unitMonths(unit);
    }, 0);

    buckets.push({ key, label: bucketLabel(cursor, unit, spansMultipleYears, language), start: cursor, end: bucketEnd, tripEur, subEur });
    cursor = bucketEnd;
  }

  return { buckets, unit };
}
