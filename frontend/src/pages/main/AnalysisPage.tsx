import { useEffect, useRef, useState } from "react";
import { StatusMessage } from "../../components/StatusMessage";
import { runAnalysis } from "../../api";
import type { Recommendation } from "../../types/recommendation";

const STATUS_MESSAGES = [
  "Loading your travel history…",
  "Checking subscription costs…",
  "Forecasting upcoming travel…",
  "Comparing contract alternatives…",
  "Computing CO₂ impact…",
  "Preparing your recommendation…",
  "Almost there…",
];

type AnalysisPageProps = {
  sessionId: string;
  onComplete: (recommendation: Recommendation) => void;
};

export function AnalysisPage({ sessionId, onComplete }: AnalysisPageProps) {
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startedRef = useRef(false);

  const start = () => {
    setError(null);
    setDone(false);
    runAnalysis(sessionId)
      .then((rec) => {
        setDone(true);
        // Brief pause so the progress bar visually completes before navigating
        window.setTimeout(() => onComplete(rec), 600);
      })
      .catch((err) => {
        console.error("Analysis failed:", err);
        setError(err instanceof Error ? err.message : "The analysis pipeline failed. Please try again.");
      });
  };

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  if (error) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-6 py-12 text-center">
        <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center flex-shrink-0" aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-brand-red">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <div className="flex flex-col gap-2 max-w-xs">
          <h2 className="text-xl font-bold text-[#1f1f1f] m-0">Analysis failed</h2>
          <p className="text-sm text-gray-500 m-0 leading-relaxed">{error}</p>
        </div>
        <button
          type="button"
          onClick={start}
          className="bg-brand-red text-white rounded-full px-8 py-3 font-semibold hover:opacity-90 cursor-pointer border-0 text-sm transition-opacity"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center gap-8 py-12 text-center">
      <div className="w-24 h-24 flex-shrink-0" aria-hidden="true">
        <img className="w-full h-full object-contain" src="/assets/advisor.svg" alt="" />
      </div>

      <div className="flex flex-col gap-3 w-full max-w-xs">
        <h2 className="text-2xl font-bold text-[#1f1f1f] m-0">Analysing your setup…</h2>
        <StatusMessage messages={STATUS_MESSAGES} intervalMs={4200} />
      </div>

      <div className="w-64 h-1 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-brand-red rounded-full transition-all duration-700"
          style={{
            width: done ? "100%" : undefined,
            animation: done ? "none" : "analysisProgress 40s ease-out forwards",
          }}
        />
      </div>

      <style>{`
        @keyframes analysisProgress {
          0%   { width: 0% }
          30%  { width: 40% }
          70%  { width: 72% }
          100% { width: 85% }
        }
      `}</style>
    </div>
  );
}
