import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  fetchAnalysisHistory,
  fetchCurrentSubscriptions,
  fetchTravelHistory,
  type TravelHistory,
} from "../../api";
import type { SubscriptionEntry } from "../../types";
import type { AnalysisHistoryEntry } from "../../types/recommendation";
import { modeLabel } from "../../labels";
import { StatTile } from "../../components/StatTile";
import { DashboardSkeleton } from "../../components/Skeleton";
import { SpendChart } from "../../components/SpendChart";
import { CARD, CARD_INTERACTIVE, BTN_PRIMARY_SM } from "../../ui";
import {
  aggregateTrips,
  bucketByMode,
  bucketSpendOverTime,
  DEFAULT_RANGE,
  filterTripsByRange,
  RANGE_OPTIONS,
  recentTrips,
  type RangeKey,
} from "../../dashboard-stats";

type HomePageProps = {
  personaName: string;
  onChat: () => void;
  onAnalysis: () => void;
  onAnnualReport: () => void;
  onHistory: () => void;
  onReviewRecommendation: (entry: AnalysisHistoryEntry) => void;
};

// ── formatting helpers ────────────────────────────────────────────────────────
const fmtInt = (n: number) => Math.round(n).toLocaleString("de-DE");
const fmtKg = (n: number) => (n >= 10 ? Math.round(n).toLocaleString("de-DE") : n.toFixed(1));
const fmtDate = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("de-DE", { day: "2-digit", month: "short", year: "numeric" });
};
const fmtDateShort = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("de-DE", { day: "2-digit", month: "short" });
};

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

// ── small presentational pieces ───────────────────────────────────────────────
function Card({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className={`${CARD} p-5`}>
      <div className="mb-3">
        <p className="text-sm font-bold text-gray-900 m-0">{title}</p>
        {subtitle && <p className="text-xs text-gray-400 m-0 mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="text-sm text-gray-400 m-0 py-2">{text}</p>;
}

/** A single labelled magnitude bar (single hue — mode identity is carried by the label, not color). */
function MeasureBar({ label, valueText, pct, color }: { label: string; valueText: string; pct: number; color: string }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-gray-700">{label}</span>
        <span className="text-sm font-semibold text-gray-900 tabular-nums">{valueText}</span>
      </div>
      <div className="h-2 rounded-full bg-gray-100">
        <div
          className="h-full rounded-full bar-fill"
          style={{ width: `${Math.max(pct, 3)}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

type ActionCardProps = { icon: ReactNode; title: string; subtitle: string; onClick?: () => void };
function ActionCard({ icon, title, subtitle, onClick }: ActionCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-center gap-4 rounded-xl px-5 py-4 text-left hover:border-brand-red/50 active:scale-[0.99] ${CARD_INTERACTIVE}`}
    >
      <div className="w-11 h-11 rounded-xl bg-canvas flex items-center justify-center flex-shrink-0 text-gray-700">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-bold text-sm text-gray-900 m-0">{title}</p>
        <p className="text-xs text-gray-500 m-0 mt-0.5">{subtitle}</p>
      </div>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-gray-400 flex-shrink-0">
        <polyline points="9 18 15 12 9 6" />
      </svg>
    </button>
  );
}

// Bar hues: neutral for pure usage magnitude, a muted red to signal emissions. Both single-hue.
const USAGE_COLOR = "#374151"; // gray-700
const CO2_COLOR = "#ef4444"; // red-500

export function HomePage({ personaName, onChat, onAnalysis, onAnnualReport, onHistory, onReviewRecommendation }: HomePageProps) {
  const [travel, setTravel] = useState<TravelHistory | null>(null);
  const [travelFailed, setTravelFailed] = useState(false);
  const [subscriptions, setSubscriptions] = useState<SubscriptionEntry[] | null>(null);
  const [history, setHistory] = useState<AnalysisHistoryEntry[] | null>(null);
  const [range, setRange] = useState<RangeKey>(DEFAULT_RANGE);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.allSettled([fetchTravelHistory(), fetchCurrentSubscriptions(), fetchAnalysisHistory()]).then(
      ([t, s, h]) => {
        if (cancelled) return;
        if (t.status === "fulfilled") setTravel(t.value);
        else setTravelFailed(true);
        if (s.status === "fulfilled") setSubscriptions(s.value);
        if (h.status === "fulfilled") setHistory(h.value);
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  // Range-scoped derivations, anchored to the frozen reference date.
  const filtered = useMemo(
    () => (travel ? filterTripsByRange(travel.trips, travel.referenceDate, range) : []),
    [travel, range],
  );
  const stats = useMemo(() => aggregateTrips(filtered), [filtered]);
  const usageSorted = useMemo(() => bucketByMode(filtered).sort((a, b) => b.trips - a.trips), [filtered]);
  const co2Sorted = useMemo(
    () => bucketByMode(filtered).filter((b) => b.co2Kg > 0).sort((a, b) => b.co2Kg - a.co2Kg),
    [filtered],
  );
  const recent = useMemo(() => recentTrips(filtered, 5), [filtered]);
  const maxUsage = usageSorted[0]?.trips ?? 0;
  const maxCo2 = co2Sorted[0]?.co2Kg ?? 0;
  const spend = useMemo(
    () => (travel ? bucketSpendOverTime(travel.trips, subscriptions, travel.referenceDate, range) : null),
    [travel, subscriptions, range],
  );
  const hasSpend = !!spend && spend.buckets.some((b) => b.tripEur > 0 || b.subEur > 0);

  // General (non-range) derivations. Only the newest analysis is "live" — nudge on it iff it's still
  // undecided (pending), so a stale older pending never resurfaces here.
  const openRec = history?.[0]?.outcome === "pending" ? history[0] : null;
  const pendingSavings = openRec?.recommendation.alternatives.find((a) => a.isRecommended)?.savingsVsCurrentEur ?? 0;

  const totalMonthly = (subscriptions ?? []).reduce((sum, s) => sum + (s.monthly_cost_eur ?? 0), 0);
  const renewalAnchor = travel?.referenceDate ? new Date(travel.referenceDate) : new Date();
  const nextRenewal = useMemo(() => {
    const upcoming = (subscriptions ?? [])
      .filter((s) => s.next_renewal_date)
      .map((s) => ({ s, d: new Date(s.next_renewal_date) }))
      .filter((x) => !Number.isNaN(x.d.getTime()) && x.d >= renewalAnchor)
      .sort((a, b) => a.d.getTime() - b.d.getTime());
    if (!upcoming[0]) return null;
    const days = Math.round((upcoming[0].d.getTime() - renewalAnchor.getTime()) / 86_400_000);
    return { entry: upcoming[0].s, days };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subscriptions, travel]);

  const firstName = personaName.trim().split(/\s+/)[0] || personaName;

  // ── widget blocks (declared once, placed by the responsive layout below) ─────
  const spendCard = (
    <Card
      title="Mobility spend"
      subtitle="Trip costs plus subscriptions, assumed active since they started"
    >
      {!hasSpend || !spend ? (
        <EmptyState text="No spend in this range." />
      ) : (
        <SpendChart buckets={spend.buckets} unit={spend.unit} />
      )}
    </Card>
  );

  const modesCard = (
    <Card title="Modes by usage" subtitle="Ranked by number of trips">
      {usageSorted.length === 0 ? (
        <EmptyState text="No trips in this range." />
      ) : (
        <div className="flex flex-col gap-3">
          {usageSorted.map((b) => (
            <MeasureBar
              key={b.mode}
              label={modeLabel(b.mode)}
              valueText={`${b.trips} ${b.trips === 1 ? "trip" : "trips"} · ${Math.round((b.trips / stats.count) * 100)}%`}
              pct={maxUsage ? (b.trips / maxUsage) * 100 : 0}
              color={USAGE_COLOR}
            />
          ))}
        </div>
      )}
    </Card>
  );

  const co2Card = (
    <Card title="CO₂ by mode" subtitle="Which modes drive your footprint">
      {co2Sorted.length === 0 ? (
        <EmptyState text="No emissions data in this range." />
      ) : (
        <div className="flex flex-col gap-3">
          {co2Sorted.map((b) => (
            <MeasureBar
              key={b.mode}
              label={modeLabel(b.mode)}
              valueText={`${fmtKg(b.co2Kg)} kg`}
              pct={maxCo2 ? (b.co2Kg / maxCo2) * 100 : 0}
              color={CO2_COLOR}
            />
          ))}
        </div>
      )}
    </Card>
  );

  const recentCard = (
    <Card title="Recent activity" subtitle="Your latest trips in this range">
      {recent.length === 0 ? (
        <EmptyState text="No trips in this range." />
      ) : (
        <div className="flex flex-col">
          {recent.map((t, i) => (
            <div
              key={`${t.date}-${t.origin}-${t.destination}-${i}`}
              className="flex items-center gap-3 py-2.5 border-b border-gray-100 last:border-0"
            >
              <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-500 bg-gray-100 rounded px-1.5 py-0.5 flex-shrink-0">
                {modeLabel(t.mode)}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-900 m-0 truncate">
                  {t.origin} → {t.destination}
                </p>
                <p className="text-xs text-gray-400 m-0">{fmtDateShort(t.date)}</p>
              </div>
              <div className="text-right flex-shrink-0">
                {t.cost_eur != null && (
                  <p className="text-sm font-semibold text-gray-900 m-0 tabular-nums">€{fmtInt(t.cost_eur)}</p>
                )}
                {t.co2_emission_kg != null && (
                  <p className="text-xs text-gray-400 m-0 tabular-nums">{fmtKg(t.co2_emission_kg)} kg CO₂</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );

  const subscriptionsCard = (
    <Card title="Your subscriptions">
      {!subscriptions || subscriptions.length === 0 ? (
        <EmptyState text="No active subscriptions." />
      ) : (
        <>
          <div className="flex flex-col">
            {subscriptions.map((s) => (
              <div key={s.id} className="flex items-center gap-3 py-2.5 border-b border-gray-100 last:border-0">
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-sm text-gray-900 m-0 truncate">
                    {s.provider} — {s.product}
                  </p>
                  <p className="text-xs text-gray-400 m-0">
                    {modeLabel(s.mode)}
                    {s.next_renewal_date ? ` · renews ${fmtDate(s.next_renewal_date)}` : ""}
                  </p>
                </div>
                {typeof s.monthly_cost_eur === "number" && (
                  <span className="text-sm font-semibold text-gray-900 tabular-nums flex-shrink-0">
                    {s.monthly_cost_eur === 0 ? "Free" : `€${s.monthly_cost_eur.toFixed(2)}/mo`}
                  </span>
                )}
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-200">
            <span className="text-sm text-gray-500">Total</span>
            <span className="text-sm font-bold text-gray-900 tabular-nums">€{totalMonthly.toFixed(2)}/mo</span>
          </div>
          {nextRenewal && (
            <p className="text-xs text-gray-400 m-0 mt-2">
              Next renewal: {nextRenewal.entry.provider} — {nextRenewal.entry.product} in {nextRenewal.days}{" "}
              {nextRenewal.days === 1 ? "day" : "days"} ({fmtDate(nextRenewal.entry.next_renewal_date)})
            </p>
          )}
        </>
      )}
    </Card>
  );

  const quickActions = (
    <div>
      <p className="text-sm font-bold text-gray-900 mb-3">Quick actions</p>
      <div className="flex flex-col gap-3">
        <ActionCard
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          }
          title="Chat"
          subtitle="Ask me anything about your trips, costs, and subscriptions."
          onClick={onChat}
        />
        <ActionCard
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          }
          title="Start Analysis"
          subtitle="Run a full analysis of your mobility portfolio."
          onClick={onAnalysis}
        />
        <ActionCard
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
          }
          title="Generate Annual Report"
          subtitle="Get your full year-in-review: spend, CO₂, and subscription ROI."
          onClick={onAnnualReport}
        />
        <ActionCard
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          }
          title="History"
          subtitle="Review past analyses and the decisions you made."
          onClick={onHistory}
        />
      </div>
    </div>
  );

  return (
    <div className="flex flex-col gap-5 py-4">
      {/* Greeting */}
      <div>
        <h1 className="text-2xl font-bold leading-tight mb-1">
          {greeting()}, {firstName}
        </h1>
        <p className="text-gray-500 text-sm m-0">Here's your mobility at a glance.</p>
      </div>

      {loading ? (
        <DashboardSkeleton />
      ) : (
        <>
          {/* Open-recommendation nudge — opens the decision screen for the newest, undecided analysis. */}
          {openRec && (
            <div className="rise-in flex items-center gap-3 bg-red-50 border border-red-100 rounded-2xl p-4 shadow-card">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold text-gray-900 m-0">
                  {pendingSavings > 0
                    ? `Save up to €${fmtInt(pendingSavings)}/yr`
                    : "You have an open recommendation"}
                </p>
                <p className="text-xs text-gray-500 m-0 mt-0.5 truncate">{openRec.recommendation.verdict}</p>
              </div>
              <button
                type="button"
                onClick={() => onReviewRecommendation(openRec)}
                className={`${BTN_PRIMARY_SM} flex-shrink-0`}
              >
                Review
              </button>
            </div>
          )}

          {/* Time-range selector */}
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div className="flex gap-1 overflow-x-auto -mx-1 px-1 py-0.5">
              {RANGE_OPTIONS.map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  aria-pressed={range === opt.key}
                  onClick={() => setRange(opt.key)}
                  className={`px-3 py-1.5 rounded-full text-sm font-semibold flex-shrink-0 cursor-pointer transition-colors duration-150 active:scale-95 ${
                    range === opt.key
                      ? "bg-brand-red text-white"
                      : "bg-white border border-gray-200 text-gray-600 hover:border-gray-300"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {travel && (
              <span className="text-xs text-gray-400 flex-shrink-0">as of {fmtDate(travel.referenceDate)}</span>
            )}
          </div>

          {/* Full-width KPI band */}
          {!travelFailed && (
            <div className="rise-in grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatTile value={fmtKg(stats.totalCo2Kg)} unit="kg" label="CO₂ footprint" />
              <StatTile value={`€${fmtInt(stats.totalSpendEur)}`} label="Travel spend" />
              <StatTile value={fmtInt(stats.totalDistanceKm)} unit="km" label="Distance" />
              <StatTile value={fmtInt(stats.count)} label={stats.count === 1 ? "Trip" : "Trips"} />
            </div>
          )}

          {/* Content: main column (trip insights) + sidebar (subscriptions & actions).
              Stacks to a single column below `lg`, matching the narrow/mobile view. */}
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
            <div className="rise-in flex flex-col gap-5 min-w-0 lg:flex-1" style={{ animationDelay: "40ms" }}>
              {travelFailed ? (
                <Card title="Travel insights">
                  <EmptyState text="Couldn't load travel data right now." />
                </Card>
              ) : (
                <>
                  {spendCard}
                  <div className="grid gap-5 sm:grid-cols-2">
                    {modesCard}
                    {co2Card}
                  </div>
                  {recentCard}
                </>
              )}
            </div>

            <aside
              className="rise-in flex flex-col gap-5 lg:w-[360px] lg:flex-shrink-0"
              style={{ animationDelay: "80ms" }}
            >
              {subscriptionsCard}
              {quickActions}
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
