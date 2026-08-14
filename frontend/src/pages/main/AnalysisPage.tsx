import { useEffect, useMemo, useRef, useState } from "react";
import { StatusMessage } from "../../components/StatusMessage";
import { runAnalysis, ApiError } from "../../api";
import { useT } from "../../i18n";
import type { AnalysisRunResult } from "../../types/recommendation";
import { BTN_PRIMARY_COMPACT } from "../../ui";

type AnalysisPageProps = {
  sessionId: string;
  onComplete: (result: AnalysisRunResult) => void;
};

export function AnalysisPage({ sessionId, onComplete }: AnalysisPageProps) {
  const t = useT();
  const STATUS_MESSAGES = useMemo(
    () => [
      t("analysis.status.1"),
      t("analysis.status.2"),
      t("analysis.status.3"),
      t("analysis.status.4"),
      t("analysis.status.5"),
      t("analysis.status.6"),
      t("analysis.status.7"),
    ],
    [t],
  );
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startedRef = useRef(false);

  const start = () => {
    setError(null);
    setDone(false);
    runAnalysis(sessionId)
      .then((result) => {
        setDone(true);
        // Brief pause so the progress bar visually completes before navigating
        window.setTimeout(() => onComplete(result), 600);
      })
      .catch((err) => {
        console.error("Analysis failed:", err);
        // ApiError.detail is the backend's message on its own, without the "POST /path 500:"
        // transport prefix — cleaner to show.
        setError(err instanceof ApiError ? err.detail : t("analysis.fallbackError"));
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
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-6 py-12 text-center rise-in">
        <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center flex-shrink-0" aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-brand-red">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <div className="flex flex-col gap-2 max-w-xs">
          <h2 className="text-xl font-bold text-ink m-0">{t("analysis.failed")}</h2>
          <p className="text-sm text-gray-500 m-0 leading-relaxed">{error}</p>
        </div>
        <button type="button" onClick={start} className={BTN_PRIMARY_COMPACT}>
          {t("common.tryAgain")}
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center gap-8 py-12 text-center rise-in">
      <div className="w-24 h-24 flex-shrink-0" aria-hidden="true">
        <img className="w-full h-full object-contain" src="/assets/advisor.svg" alt="" />
      </div>

      <div className="flex flex-col gap-3 w-full max-w-xs">
        <h2 className="text-2xl font-bold text-ink m-0">{t("analysis.heading")}</h2>
        <StatusMessage messages={STATUS_MESSAGES} intervalMs={4200} />
      </div>

      <div className="w-64 h-1 bg-gray-200 rounded-full overflow-hidden progress-shimmer">
        <div
          className="h-full bg-brand-red rounded-full transition-all duration-700"
          style={{
            width: done ? "100%" : undefined,
            animation: done ? "none" : "fakeProgress 40s ease-out forwards",
          }}
        />
      </div>
    </div>
  );
}
