import { useEffect } from "react";
import { StatusMessage } from "../../components/StatusMessage";

const STATUS_MESSAGES = [
  "Checking your subscriptions…",
  "Reviewing your past trips…",
  "Forecasting upcoming demand…",
  "Comparing contract alternatives…",
  "Preparing your recommendation…",
];

type AnalysisPageProps = {
  onComplete: () => void;
};

export function AnalysisPage({ onComplete }: AnalysisPageProps) {
  useEffect(() => {
    const t = window.setTimeout(onComplete, 3800);
    return () => window.clearTimeout(t);
  }, [onComplete]);

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center gap-8 py-12 text-center">
      <div className="w-24 h-24 flex-shrink-0" aria-hidden="true">
        <img className="w-full h-full object-contain" src="/assets/advisor.svg" alt="" />
      </div>

      <div className="flex flex-col gap-3 w-full max-w-xs">
        <h2 className="text-2xl font-bold text-[#1f1f1f] m-0">Analysing your setup…</h2>
        <StatusMessage messages={STATUS_MESSAGES} intervalMs={760} />
      </div>

      <div className="w-64 h-1 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-brand-red rounded-full"
          style={{ animation: "analysisProgress 3.8s ease-in-out forwards" }}
        />
      </div>

      <style>{`
        @keyframes analysisProgress {
          0%   { width: 0% }
          60%  { width: 75% }
          80%  { width: 88% }
          100% { width: 100% }
        }
      `}</style>
    </div>
  );
}
