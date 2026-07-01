import type { Recommendation } from "../../types/recommendation";

type ApprovalPageProps = {
  recommendation: Recommendation;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ApprovalPage({ recommendation: rec, onConfirm, onCancel }: ApprovalPageProps) {
  const { proposedAction: action } = rec;

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
          <span className="font-semibold">Prototype note:</span> No real changes will be made. This is a simulation — confirming does not contact Deutsche Bahn or modify any contract.
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
        <button
          type="button"
          className="text-xs text-gray-400 hover:text-gray-600 bg-transparent border-0 cursor-pointer p-0 text-center w-full underline underline-offset-2 transition-colors"
        >
          Remind me in 3 months
        </button>
      </div>
    </div>
  );
}
