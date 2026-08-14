import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

type ChatBubbleProps = {
  role: "agent" | "user";
  text: string;
};

const markdownComponents: Components = {
  p: ({ children }) => <p className="m-0 mb-2 last:mb-0 leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="m-0 mb-2 last:mb-0 pl-5 list-disc space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="m-0 mb-2 last:mb-0 pl-5 list-decimal space-y-0.5">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  h1: ({ children }) => <h1 className="text-base font-semibold mt-1 mb-2 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="text-sm font-semibold mt-3 mb-1.5 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1 first:mt-0">{children}</h3>,
  hr: () => <hr className="my-3 border-gray-200" />,
  code: ({ children }) => (
    <code className="rounded bg-gray-100 px-1 py-0.5 text-[0.85em] font-mono">{children}</code>
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-gray-50">{children}</thead>,
  th: ({ children }) => (
    <th className="border-b border-gray-200 px-2.5 py-1.5 text-left font-semibold whitespace-nowrap">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-gray-100 px-2.5 py-1.5 last:border-b-0 whitespace-nowrap">{children}</td>
  ),
};

export function ChatBubble({ role, text }: ChatBubbleProps) {
  if (role === "user") {
    return (
      <div className="rise-in flex justify-end">
        <div className="max-w-[78%] rounded-2xl rounded-tr-sm px-4 py-2.5 bg-red-50 border border-red-100">
          <p className="text-sm text-ink m-0 leading-relaxed whitespace-pre-wrap">{text}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rise-in flex items-end gap-2">
      <div className="w-7 h-7 flex-shrink-0 rounded-full overflow-hidden bg-gray-100">
        <img src="/assets/advisor.svg" alt="" className="w-full h-full object-contain" />
      </div>
      <div className="max-w-[78%] rounded-2xl rounded-bl-sm px-4 py-2.5 bg-white border border-gray-200 shadow-card">
        <div className="text-sm text-ink">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {text}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
