import { TypewriterHeading } from "../../components/TypewriterHeading";

type ConfirmationPageProps = {
  actionTitle: string;
  onBackToDashboard: () => void;
};

export function ConfirmationPage({ actionTitle, onBackToDashboard }: ConfirmationPageProps) {
  return (
    <div className="flex flex-col items-center gap-8 text-center py-12">
      <div
        className="w-20 h-20 bg-brand-red rounded-full flex items-center justify-center text-white text-3xl font-bold flex-shrink-0"
        aria-hidden="true"
      >
        ✓
      </div>

      <div className="flex flex-col gap-3 max-w-xs">
        <TypewriterHeading text="Done!" />
        <p className="text-gray-500 leading-relaxed m-0 text-sm">
          We've noted your intent to: <span className="font-semibold text-[#1f1f1f]">{actionTitle}</span>
        </p>
        <p className="text-gray-500 leading-relaxed m-0 text-sm">
          We'll follow up when the renewal date approaches and re-run the analysis to confirm the recommendation.
        </p>
      </div>

      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 max-w-xs w-full">
        <p className="text-xs text-gray-400 m-0 leading-relaxed text-center">
          No contract change has happened yet — this is a simulation. Nothing was sent to Deutsche Bahn.
        </p>
      </div>

      <button
        type="button"
        onClick={onBackToDashboard}
        className="bg-brand-red text-white rounded-full px-8 py-3 font-semibold hover:opacity-90 cursor-pointer border-0 text-sm transition-opacity"
      >
        Back to dashboard
      </button>
    </div>
  );
}
