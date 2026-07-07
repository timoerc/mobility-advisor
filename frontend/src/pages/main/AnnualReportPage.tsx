import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
  cachedReport: string | null;
  onReportReady: (report: string) => void;
};

export function AnnualReportPage({ sessionId, cachedReport, onReportReady }: AnnualReportPageProps) {
  const [report, setReport] = useState<string | null>(cachedReport);
  const [error, setError] = useState<string | null>(null);
  const calledRef = useRef(false);

  useEffect(() => {
    if (cachedReport || calledRef.current) return;
    calledRef.current = true;

    runAnnualReport(sessionId)
      .then((text) => {
        setReport(text);
        onReportReady(text);
      })
      .catch((err) => {
        console.warn("Annual report failed:", err);
        setError("Couldn't generate your annual report right now. Please try again.");
      });
  }, [sessionId, cachedReport, onReportReady]);

  if (error) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3 text-center py-12">
        <p className="text-gray-500 text-sm">{error}</p>
      </div>
    );
  }

  if (!report) {
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
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ node, ...p }) => <h1 className="text-2xl font-bold mt-0 mb-3 text-[#1f1f1f]" {...p} />,
          h2: ({ node, ...p }) => <h2 className="text-lg font-bold mt-6 mb-2 text-[#1f1f1f]" {...p} />,
          h3: ({ node, ...p }) => <h3 className="text-base font-bold mt-4 mb-1 text-[#1f1f1f]" {...p} />,
          p: ({ node, ...p }) => <p className="text-sm text-[#1f1f1f] leading-relaxed mb-3" {...p} />,
          strong: ({ node, ...p }) => <strong className="font-semibold" {...p} />,
          hr: () => <hr className="border-gray-200 my-4" />,
          ul: ({ node, ...p }) => <ul className="list-disc pl-5 mb-3 text-sm text-[#1f1f1f]" {...p} />,
          li: ({ node, ...p }) => <li className="mb-1" {...p} />,
          blockquote: ({ node, ...p }) => (
            <blockquote className="border-l-4 border-brand-red pl-3 italic text-gray-600 my-3 text-sm" {...p} />
          ),
          table: ({ node, ...p }) => (
            <div className="overflow-x-auto my-3">
              <table className="w-full text-sm border-collapse" {...p} />
            </div>
          ),
          thead: ({ node, ...p }) => <thead className="bg-[#f5f5f3]" {...p} />,
          th: ({ node, ...p }) => <th className="text-left px-3 py-2 border-b border-gray-200 font-semibold" {...p} />,
          td: ({ node, ...p }) => <td className="px-3 py-2 border-b border-gray-100" {...p} />,
        }}
      >
        {report}
      </ReactMarkdown>
    </div>
  );
}
