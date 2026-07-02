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
  onComplete: (recommendation?: Recommendation) => void;
};

export function AnalysisPage({ sessionId, onComplete }: AnalysisPageProps) {
  const [done, setDone] = useState(false);
  const calledRef = useRef(false);

  useEffect(() => {
    if (calledRef.current) return;
    calledRef.current = true;

    runAnalysis(sessionId)
      .then((rec) => {
        setDone(true);
        // Brief pause so the progress bar visually completes before navigating
        window.setTimeout(() => onComplete(rec), 600);
      })
      .catch((err) => {
        console.warn("Analysis API failed, falling back to mock data:", err);
        setDone(true);
        window.setTimeout(() => onComplete(undefined), 600);
      });
  }, [sessionId, onComplete]);

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
