import { useEffect, useRef, useState } from "react";
import { ChatBubble } from "../../components/ChatBubble";
import { ChatInput } from "../../components/ChatInput";
import { sendMessage } from "../../api";
import { useT } from "../../i18n";

type Message = { role: "agent" | "user"; text: string; id: string };

type ChatPageProps = {
  sessionId: string;
  onRunAnalysis: () => void;
  onDataChanged?: () => void;
};

export function ChatPage({ sessionId, onRunAnalysis, onDataChanged }: ChatPageProps) {
  const t = useT();
  const [messages, setMessages] = useState<Message[]>(() => [
    { role: "agent", text: t("chat.initialMessage"), id: "init" },
  ]);
  const [thinking, setThinking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  const handleSend = async (text: string) => {
    const userMsg: Message = { role: "user", text, id: crypto.randomUUID() };
    setMessages((m) => [...m, userMsg]);
    setThinking(true);

    try {
      const { text: response, actionTaken, ranOptimization } = await sendMessage(sessionId, text);

      setThinking(false);
      setMessages((m) => [
        ...m,
        { role: "agent", text: response, id: crypto.randomUUID() },
      ]);
      // Navigate based on what the coordinator actually did this turn (ran_optimization,
      // set server-side from whether it called the optimization_pipeline tool) — not a
      // regex guess against the user's own wording. The old regex
      // (/full.?analysis|run analysis|analyse|analyze/i) matched phrasing like "don't run
      // a full analysis, just tell me X" and navigated away from the answer even though
      // the coordinator correctly routed that to a lookup instead.
      if (ranOptimization) {
        window.setTimeout(onRunAnalysis, 900);
      }
      if (actionTaken) {
        onDataChanged?.();
      }
    } catch (err) {
      console.warn("Chat API error:", err);
      setThinking(false);
      setMessages((m) => [
        ...m,
        {
          role: "agent",
          text: t("chat.error"),
          id: crypto.randomUUID(),
        },
      ]);
    }
  };

  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 105px)" }}>
      <div className="flex-1 overflow-y-auto flex flex-col gap-4 pb-4">
        {messages.map((msg) => (
          <ChatBubble key={msg.id} role={msg.role} text={msg.text} />
        ))}
        {thinking && (
          <div className="flex items-end gap-2">
            <div className="w-7 h-7 flex-shrink-0 rounded-full overflow-hidden bg-gray-100">
              <img src="/assets/advisor.svg" alt="" className="w-full h-full object-contain" />
            </div>
            <div className="rounded-2xl rounded-bl-sm px-4 py-3 bg-white border border-gray-200">
              <div className="flex gap-1 items-center">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 bg-gray-400 rounded-full"
                    style={{ animation: `dotBounce 1.2s ${i * 0.2}s ease-in-out infinite` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <style>{`
        @keyframes dotBounce {
          0%, 60%, 100% { transform: translateY(0) }
          30%            { transform: translateY(-5px) }
        }
      `}</style>
      <ChatInput onSend={handleSend} disabled={thinking} />
    </div>
  );
}
