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
import { useI18n, formatInt, formatKg, formatDate as fmtDateFor, formatCurrency, formatCurrencyPrecise } from "../../i18n";
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

function greetingKey(): "home.greeting.morning" | "home.greeting.afternoon" | "home.greeting.evening" {
  const h = new Date().getHours();
  if (h < 12) return "home.greeting.morning";
  if (h < 18) return "home.greeting.afternoon";
  return "home.greeting.evening";
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
  const { language, t, tPlural, tDynamic } = useI18n();
  const mLabel = (mode: string) => modeLabel(mode, tDynamic);
  const fmtInt = (n: number) => formatInt(language, n);
  const fmtKg = (n: number) => formatKg(language, n);
  const fmtDate = (iso: string) => fmtDateFor(language, iso, "long");
  const fmtDateShort = (iso: string) => fmtDateFor(language, iso, "short");
  const fmtEur = (n: number) => formatCurrency(language, n);
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
      title={t("home.spend.title")}
      subtitle={t("home.spend.subtitle")}
    >
      {!hasSpend || !spend ? (
        <EmptyState text={t("home.spend.empty")} />
      ) : (
        <SpendChart buckets={spend.buckets} unit={spend.unit} />
      )}
    </Card>
  );

  const modesCard = (
    <Card title={t("home.modesByUsage")} subtitle={t("home.modesByUsage.subtitle")}>
      {usageSorted.length === 0 ? (
        <EmptyState text={t("home.noTripsInRange")} />
      ) : (
        <div className="flex flex-col gap-3">
          {usageSorted.map((b) => (
            <MeasureBar
              key={b.mode}
              label={mLabel(b.mode)}
              valueText={`${b.trips} ${tPlural("home.trip", b.trips)} · ${Math.round((b.trips / stats.count) * 100)}%`}
              pct={maxUsage ? (b.trips / maxUsage) * 100 : 0}
              color={USAGE_COLOR}
            />
          ))}
        </div>
      )}
    </Card>
  );

  const co2Card = (
    <Card title={t("home.co2ByMode")} subtitle={t("home.co2ByMode.subtitle")}>
      {co2Sorted.length === 0 ? (
        <EmptyState text={t("home.noEmissionsInRange")} />
      ) : (
        <div className="flex flex-col gap-3">
          {co2Sorted.map((b) => (
            <MeasureBar
              key={b.mode}
              label={mLabel(b.mode)}
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
    <Card title={t("home.recentActivity")} subtitle={t("home.recentActivity.subtitle")}>
      {recent.length === 0 ? (
        <EmptyState text={t("home.noTripsInRange")} />
      ) : (
        <div className="flex flex-col">
          {recent.map((t, i) => (
            <div
              key={`${t.date}-${t.origin}-${t.destination}-${i}`}
              className="flex items-center gap-3 py-2.5 border-b border-gray-100 last:border-0"
            >
              <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-500 bg-gray-100 rounded px-1.5 py-0.5 flex-shrink-0">
                {mLabel(t.mode)}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-900 m-0 truncate">
                  {t.origin} → {t.destination}
                </p>
                <p className="text-xs text-gray-400 m-0">{fmtDateShort(t.date)}</p>
              </div>
              <div className="text-right flex-shrink-0">
                {t.cost_eur != null && (
                  <p className="text-sm font-semibold text-gray-900 m-0 tabular-nums">{fmtEur(t.cost_eur)}</p>
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
    <Card title={t("home.yourSubscriptions")}>
      {!subscriptions || subscriptions.length === 0 ? (
        <EmptyState text={t("home.noActiveSubscriptions")} />
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
                    {mLabel(s.mode)}
                    {s.next_renewal_date ? ` · renews ${fmtDate(s.next_renewal_date)}` : ""}
                  </p>
                </div>
                {typeof s.monthly_cost_eur === "number" && (
                  <span className="text-sm font-semibold text-gray-900 tabular-nums flex-shrink-0">
                    {s.monthly_cost_eur === 0 ? t("home.free") : `${formatCurrencyPrecise(language, s.monthly_cost_eur)}/mo`}
                  </span>
                )}
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-200">
            <span className="text-sm text-gray-500">{t("home.total")}</span>
            <span className="text-sm font-bold text-gray-900 tabular-nums">{formatCurrencyPrecise(language, totalMonthly)}/mo</span>
          </div>
          {nextRenewal && (
            <p className="text-xs text-gray-400 m-0 mt-2">
              {t("home.nextRenewal", {
                provider: nextRenewal.entry.provider,
                product: nextRenewal.entry.product,
                days: nextRenewal.days,
                dayWord: tPlural("home.day", nextRenewal.days),
                date: fmtDate(nextRenewal.entry.next_renewal_date),
              })}
            </p>
          )}
        </>
      )}
    </Card>
  );

  const quickActions = (
    <div>
      <p className="text-sm font-bold text-gray-900 mb-3">{t("home.quickActions")}</p>
      <div className="flex flex-col gap-3">
        <ActionCard
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          }
          title={t("home.action.chat.title")}
          subtitle={t("home.action.chat.subtitle")}
          onClick={onChat}
        />
        <ActionCard
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          }
          title={t("home.action.analysis.title")}
          subtitle={t("home.action.analysis.subtitle")}
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
          title={t("home.action.annualReport.title")}
          subtitle={t("home.action.annualReport.subtitle")}
          onClick={onAnnualReport}
        />
        <ActionCard
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          }
          title={t("home.action.history.title")}
          subtitle={t("home.action.history.subtitle")}
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
          {t(greetingKey())}, {firstName}
        </h1>
        <p className="text-gray-500 text-sm m-0">{t("home.subheading")}</p>
      </div>

      {loading ? (
        <DashboardSkeleton ariaLabel={t("home.loadingDashboard")} />
      ) : (
        <>
          {/* Open-recommendation nudge — opens the decision screen for the newest, undecided analysis. */}
          {openRec && (
            <div className="rise-in flex items-center gap-3 bg-red-50 border border-red-100 rounded-2xl p-4 shadow-card">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold text-gray-900 m-0">
                  {pendingSavings > 0
                    ? t("home.saveUpTo", { amount: fmtEur(pendingSavings) })
                    : t("home.openRecommendation")}
                </p>
                <p className="text-xs text-gray-500 m-0 mt-0.5 truncate">{openRec.recommendation.verdict}</p>
              </div>
              <button
                type="button"
                onClick={() => onReviewRecommendation(openRec)}
                className={`${BTN_PRIMARY_SM} flex-shrink-0`}
              >
                {t("home.review")}
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
                  {t(opt.labelKey)}
                </button>
              ))}
            </div>
            {travel && (
              <span className="text-xs text-gray-400 flex-shrink-0">{t("home.rangeAsOf", { date: fmtDate(travel.referenceDate) })}</span>
            )}
          </div>

          {/* Full-width KPI band */}
          {!travelFailed && (
            <div className="rise-in grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatTile value={fmtKg(stats.totalCo2Kg)} unit="kg" label={t("home.kpi.co2Footprint")} />
              <StatTile value={fmtEur(stats.totalSpendEur)} label={t("home.kpi.travelSpend")} />
              <StatTile value={fmtInt(stats.totalDistanceKm)} unit="km" label={t("home.kpi.distance")} />
              <StatTile value={fmtInt(stats.count)} label={tPlural("home.kpi.trip", stats.count)} />
            </div>
          )}

          {/* Content: main column (trip insights) + sidebar (subscriptions & actions).
              Stacks to a single column below `lg`, matching the narrow/mobile view. */}
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
            <div className="rise-in flex flex-col gap-5 min-w-0 lg:flex-1" style={{ animationDelay: "40ms" }}>
              {travelFailed ? (
                <Card title={t("home.travelInsights")}>
                  <EmptyState text={t("home.travelDataLoadError")} />
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
