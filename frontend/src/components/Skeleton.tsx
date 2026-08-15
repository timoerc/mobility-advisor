/** A single shimmering placeholder block. Compose these to mirror the shape of the content
 *  that's still loading, instead of gating the whole screen behind a "Loading…" line. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

/** Mirrors HomePage's loaded layout: greeting, KPI band, two insight cards + aside.
 *  ariaLabel is required (not defaulted) so this component never silently falls back to an
 *  untranslated English string — HomePage always supplies t("home.loadingDashboard"). */
export function DashboardSkeleton({ ariaLabel }: { ariaLabel: string }) {
  return (
    <div className="flex flex-col gap-5" aria-label={ariaLabel} role="status">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-[76px] rounded-xl" />
        ))}
      </div>
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        <div className="flex flex-col gap-5 min-w-0 lg:flex-1">
          <Skeleton className="h-56 rounded-2xl" />
          <div className="grid gap-5 sm:grid-cols-2">
            <Skeleton className="h-40 rounded-2xl" />
            <Skeleton className="h-40 rounded-2xl" />
          </div>
          <Skeleton className="h-56 rounded-2xl" />
        </div>
        <aside className="flex flex-col gap-5 lg:w-[360px] lg:flex-shrink-0">
          <Skeleton className="h-48 rounded-2xl" />
          <Skeleton className="h-72 rounded-2xl" />
        </aside>
      </div>
    </div>
  );
}
