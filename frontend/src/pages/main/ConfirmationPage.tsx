import { TypewriterHeading } from "../../components/TypewriterHeading";

type ConfirmationVariant = "executed" | "no-change";

type ConfirmationPageProps = {
  resultMessage: string;
  variant?: ConfirmationVariant;
  onBackToDashboard: () => void;
};

const HEADING: Record<ConfirmationVariant, string> = {
  executed: "Done!",
  "no-change": "Got it — no changes made",
};

const FOOTNOTE: Record<ConfirmationVariant, string> = {
  executed:
    "This updated your saved profile data for this prototype only — no real provider (e.g. Deutsche Bahn) was contacted.",
  "no-change": "No changes were made to your subscriptions or saved profile data.",
};

export function ConfirmationPage({
  resultMessage,
  variant = "executed",
  onBackToDashboard,
}: ConfirmationPageProps) {
  return (
    <div className="flex flex-col items-center gap-8 text-center py-12">
      <div
        className="w-20 h-20 bg-brand-red rounded-full flex items-center justify-center text-white text-3xl font-bold flex-shrink-0"
        aria-hidden="true"
      >
        ✓
      </div>

      <div className="flex flex-col gap-3 max-w-sm">
        <TypewriterHeading text={HEADING[variant]} />
        <p className="text-gray-500 leading-relaxed m-0 text-sm whitespace-pre-wrap">{resultMessage}</p>
      </div>

      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 max-w-sm w-full">
        <p className="text-xs text-gray-400 m-0 leading-relaxed text-center">
          {FOOTNOTE[variant]}
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
