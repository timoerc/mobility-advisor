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
  const [done, setDone] = useState(false);
  const calledRef = useRef(false);

  useEffect(() => {
    if (cachedReport || calledRef.current) return;
    calledRef.current = true;

    runAnnualReport(sessionId)
      .then((pdf) => {
        setDone(true);
        // Brief pause so the progress bar visually completes before showing the PDF
        window.setTimeout(() => {
          setReport(pdf);
          onReportReady(pdf);
        }, 600);
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
    // #zoom=page-width forces the browser's PDF viewer to fit the page to the
    // iframe's width instead of its default fit-whole-page zoom, which leaves
    // large gray margins on tall/narrow viewports.
    setPdfUrl(`${url}#zoom=page-width`);
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

        <div className="w-64 h-1 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-brand-red rounded-full transition-all duration-700"
            style={{
              width: done ? "100%" : undefined,
              animation: done ? "none" : "annualReportProgress 40s ease-out forwards",
            }}
          />
        </div>

        <style>{`
          @keyframes annualReportProgress {
            0%   { width: 0% }
            30%  { width: 40% }
            70%  { width: 72% }
            100% { width: 85% }
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="py-4">
      <iframe
        src={pdfUrl}
        title="Your Annual Mobility Review"
        className="w-full h-[88vh] rounded-lg border border-gray-200 bg-white"
      />
    </div>
  );
}
