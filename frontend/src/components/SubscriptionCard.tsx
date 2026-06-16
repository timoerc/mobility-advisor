import type { SubscriptionEntry } from "../types";

type SubscriptionCardProps = {
  entry: SubscriptionEntry;
  onRemove: (id: string) => void;
};

const CATEGORY_LABELS: Record<SubscriptionEntry["category"], string> = {
  rail_subscription: "Rail",
  carsharing: "Carsharing",
  micromobility_ridehailing: "Micromobility",
};

export function SubscriptionCard({ entry, onRemove }: SubscriptionCardProps) {
  return (
    <div className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200">
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm m-0 truncate">
          {entry.provider} — {entry.product}
        </p>
        <p className="text-xs text-gray-400 m-0">
          {CATEGORY_LABELS[entry.category]} ·{" "}
          {entry.monthly_cost_eur.toFixed(2)} €/mo
        </p>
      </div>
      <button
        type="button"
        onClick={() => onRemove(entry.id)}
        aria-label="Remove"
        className="text-gray-400 hover:text-red-500 bg-transparent border-0 cursor-pointer text-lg leading-none flex-shrink-0 p-1"
      >
        ×
      </button>
    </div>
  );
}
