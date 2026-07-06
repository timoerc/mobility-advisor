import { useEffect, useRef, useState } from "react";
import { ChatBubble } from "../../components/ChatBubble";
import { ChatInput } from "../../components/ChatInput";
import { sendMessage } from "../../api";

type Message = { role: "agent" | "user"; text: string; id: string };

type ChatPageProps = {
  sessionId: string;
  onRunAnalysis: () => void;
};

const INITIAL_MESSAGE =
  "Hi! I'm your mobility advisor. Ask me anything about your travel costs, subscriptions, CO₂ footprint, or upcoming trips.";

export function ChatPage({ sessionId, onRunAnalysis }: ChatPageProps) {
  const [messages, setMessages] = useState<Message[]>([
    { role: "agent", text: INITIAL_MESSAGE, id: "init" },
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
      const response = await sendMessage(sessionId, text);

      // Let the backend handle run-analysis requests too, but also honour the
      // local trigger so the UI transitions immediately after the agent replies.
      const wantsAnalysis = /full.?analysis|run analysis|analyse|analyze/i.test(text);
      setThinking(false);
      setMessages((m) => [
        ...m,
        { role: "agent", text: response, id: crypto.randomUUID() },
      ]);
      if (wantsAnalysis) {
        window.setTimeout(onRunAnalysis, 900);
      }
    } catch (err) {
      console.warn("Chat API error:", err);
      setThinking(false);
      setMessages((m) => [
        ...m,
        {
          role: "agent",
          text: "I couldn't reach the advisor right now. Please try again.",
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
