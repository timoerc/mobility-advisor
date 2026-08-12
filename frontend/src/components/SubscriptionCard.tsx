import type { SubscriptionEntry } from "../types";
import { MODE_LABELS } from "../labels";

type SubscriptionCardProps = {
  entry: SubscriptionEntry;
  onRemove: (id: string) => void;
  onEdit?: (entry: SubscriptionEntry) => void;
};

export function SubscriptionCard({ entry, onRemove, onEdit }: SubscriptionCardProps) {
  return (
    <div className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200 shadow-card">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="font-semibold text-sm m-0 truncate">
            {entry.provider} — {entry.product}
          </p>
          {entry.detected && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-400 font-medium leading-none flex-shrink-0">
              Detected
            </span>
          )}
        </div>
        <p className="text-xs text-gray-400 m-0">
          {MODE_LABELS[entry.mode]}
        </p>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        {onEdit && (
          <button
            type="button"
            onClick={() => onEdit(entry)}
            aria-label="Edit"
            className="text-gray-400 hover:text-gray-600 bg-transparent border-0 cursor-pointer text-sm leading-none p-1"
          >
            ✎
          </button>
        )}
        <button
          type="button"
          onClick={() => onRemove(entry.id)}
          aria-label="Remove"
          className="text-gray-400 hover:text-red-500 bg-transparent border-0 cursor-pointer text-lg leading-none p-1"
        >
          ×
        </button>
      </div>
    </div>
  );
}
