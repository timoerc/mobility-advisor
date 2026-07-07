import { useEffect, useRef, useState } from "react";
import { StatusMessage } from "../../components/StatusMessage";
import { runAnnualReport } from "../../api";

const STATUS_MESSAGES = [
  "Reviewing your year of travel…",
  "Calculating subscription ROI…",
  "Adding up CO₂ savings…",
  "Building your forward outlook…",
  "Finalizing your report…",
];

type AnnualReportPageProps = {
  sessionId: string;
  cachedReport: Blob | null;
  onReportReady: (report: Blob) => void;
};

export function AnnualReportPage({ sessionId, cachedReport, onReportReady }: AnnualReportPageProps) {
  const [report, setReport] = useState<Blob | null>(cachedReport);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const calledRef = useRef(false);

  useEffect(() => {
    if (cachedReport || calledRef.current) return;
    calledRef.current = true;

    runAnnualReport(sessionId)
      .then((pdf) => {
        setReport(pdf);
        onReportReady(pdf);
      })
      .catch((err) => {
        console.warn("Annual report failed:", err);
        setError("Couldn't generate your annual report right now. Please try again.");
      });
  }, [sessionId, cachedReport, onReportReady]);

  // Object URLs are only valid for the lifetime of the Blob they wrap and must be
  // revoked explicitly. Create one whenever `report` changes and revoke the previous
  // one on cleanup — covers both a blob swap and unmount.
  useEffect(() => {
    if (!report) {
      setPdfUrl(null);
      return;
    }
    const url = URL.createObjectURL(report);
    setPdfUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [report]);

  if (error) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3 text-center py-12">
        <p className="text-gray-500 text-sm">{error}</p>
      </div>
    );
  }

  if (!pdfUrl) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-8 py-12 text-center">
        <div className="w-24 h-24 flex-shrink-0" aria-hidden="true">
          <img className="w-full h-full object-contain" src="/assets/advisor.svg" alt="" />
        </div>
        <div className="flex flex-col gap-3 w-full max-w-xs">
          <h2 className="text-2xl font-bold text-[#1f1f1f] m-0">Building your annual report…</h2>
          <StatusMessage messages={STATUS_MESSAGES} intervalMs={4200} />
        </div>
      </div>
    );
  }

  return (
    <div className="py-4">
      <iframe
        src={pdfUrl}
        title="Your Annual Mobility Review"
        className="w-full h-[80vh] rounded-lg border border-gray-200 bg-white"
      />
    </div>
  );
}
