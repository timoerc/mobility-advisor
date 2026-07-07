import { TypewriterHeading } from "../components/TypewriterHeading";

type FinalPageProps = {
  onGoHome: () => void;
};

export function FinalPage({ onGoHome }: FinalPageProps) {
  return (
    <div className="flex flex-col items-center gap-8 text-center py-8">
      <div
        className="w-20 h-20 bg-brand-red rounded-full flex items-center justify-center text-white text-3xl font-bold flex-shrink-0"
        aria-hidden="true"
      >
        ✓
      </div>

      <div className="flex flex-col gap-3">
        <TypewriterHeading text="Thank you!" />
        <p className="text-gray-500 leading-relaxed m-0">
          I will now analyze your mobility portfolio and prepare personalized
          recommendations for your next trips.
        </p>
      </div>

      <button
        type="button"
        onClick={onGoHome}
        className="bg-brand-red text-white rounded-full px-8 py-3 font-semibold hover:opacity-90 cursor-pointer border-0 text-sm"
      >
        Go to homepage →
      </button>
    </div>
  );
}
