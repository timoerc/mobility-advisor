import type { ProposedAction } from "../../types/recommendation";

type ApprovalPageProps = {
  action: ProposedAction;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ApprovalPage({ action, onConfirm, onCancel }: ApprovalPageProps) {
  return (
    <div className="flex flex-col gap-6 py-4">
      <div>
        <p className="text-sm font-semibold text-brand-red uppercase tracking-wide m-0 mb-2">
          Proposed action
        </p>
        <h1 className="text-3xl font-bold leading-tight text-[#1f1f1f] m-0">{action.title}</h1>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 p-5 flex flex-col gap-4">
        <div>
          <p className="text-xs font-bold text-gray-500 uppercase tracking-wide m-0 mb-1">What this means</p>
          <p className="text-sm text-gray-700 leading-relaxed m-0">{action.description}</p>
        </div>
        <div className="border-t border-gray-100 pt-4">
          <p className="text-xs font-bold text-gray-500 uppercase tracking-wide m-0 mb-1">What will NOT happen automatically</p>
          <p className="text-sm text-gray-500 leading-relaxed m-0">{action.consequence}</p>
        </div>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
        <p className="text-sm text-yellow-800 m-0 leading-relaxed">
          <span className="font-semibold">Prototype note:</span> Confirming applies this change to your saved profile data for this prototype — it does not contact Deutsche Bahn or any real provider.
        </p>
      </div>

      <div className="flex flex-col gap-3 pt-2">
        <button
          type="button"
          onClick={onConfirm}
          className="w-full bg-brand-red text-white rounded-full px-8 py-3.5 font-semibold hover:opacity-90 cursor-pointer border-0 text-sm transition-opacity"
        >
          Yes, proceed
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="w-full bg-white text-gray-600 rounded-full px-8 py-3.5 font-semibold hover:bg-gray-50 cursor-pointer border border-gray-300 text-sm transition-colors"
        >
          Not now
        </button>
      </div>
    </div>
  );
}
