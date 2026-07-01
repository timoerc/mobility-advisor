import { useEffect, useRef, useState } from "react";
import { ChatBubble } from "../../components/ChatBubble";
import { ChatInput } from "../../components/ChatInput";
import type { Recommendation } from "../../types/recommendation";

type Message = { role: "agent" | "user"; text: string; id: string };

const CANNED_RESPONSES: [RegExp, string][] = [
  [/co.?2|carbon|emission/i, "Based on your travel history, your mobility CO₂ footprint is approximately 28 kg/month — well below the German average of 95 kg/month for transport."],
  [/budget|spend|cost|much/i, "Your current subscriptions cost roughly €20/month (BahnCard 50 annualised). Your declared budget is €350/month, so you have significant headroom."],
  [/deutschlandticket|d.ticket/i, "The Deutschlandticket (€49/month) makes sense if you use local public transit daily. For your current profile, it's not recommended since you mainly travel long-distance."],
  [/bahncard|bahn card|bc50|bc 50/i, "Your BahnCard 50 costs €244/year and saved you an estimated €72 in the last year. That's a net loss of €172 — the full analysis is on the dashboard."],
  [/hamburg|frankfurt|cologne|köln/i, "Your most frequent route is Cologne–Frankfurt. At full price that's ~€89 per trip. With BahnCard 25 you'd pay ~€67; with BC50 ~€45."],
  [/renew|renewal|cancel/i, "Your BahnCard 50 auto-renews on 31 December 2025. You need to cancel by 6 weeks before that date to avoid the charge."],
  [/full.?analysis|run analysis|analyse|analyze/i, "I can run a full portfolio analysis for you. Head back to the dashboard and tap 'Run analysis' to get an updated recommendation."],
];

function generateResponse(input: string, rec: Recommendation): string {
  for (const [pattern, response] of CANNED_RESPONSES) {
    if (pattern.test(input)) return response;
  }
  if (/what|should|recommend|advice|suggest/i.test(input)) {
    return `My top recommendation right now: ${rec.proposedAction.title}. ${rec.summaryText}`;
  }
  return "That's a good question. I don't have enough data to answer that precisely yet — try asking about your BahnCard, budget, CO₂ footprint, or upcoming travel.";
}

type ChatPageProps = {
  recommendation: Recommendation;
  onRunAnalysis: () => void;
};

const INITIAL_MESSAGE = "Hi! I'm your mobility advisor. Ask me anything about your travel costs, subscriptions, CO₂ footprint, or upcoming trips.";

export function ChatPage({ recommendation, onRunAnalysis }: ChatPageProps) {
  const [messages, setMessages] = useState<Message[]>([
    { role: "agent", text: INITIAL_MESSAGE, id: "init" },
  ]);
  const [thinking, setThinking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  const handleSend = (text: string) => {
    const userMsg: Message = { role: "user", text, id: crypto.randomUUID() };
    setMessages((m) => [...m, userMsg]);
    setThinking(true);

    const wantsAnalysis = /full.?analysis|run analysis|analyse|analyze/i.test(text);

    window.setTimeout(() => {
      setThinking(false);
      if (wantsAnalysis) {
        const agentMsg: Message = {
          role: "agent",
          text: "Sure — I'll kick off a fresh analysis now.",
          id: crypto.randomUUID(),
        };
        setMessages((m) => [...m, agentMsg]);
        window.setTimeout(onRunAnalysis, 900);
        return;
      }
      const response = generateResponse(text, recommendation);
      setMessages((m) => [...m, { role: "agent", text: response, id: crypto.randomUUID() }]);
    }, 900 + Math.random() * 600);
  };

  return (
    <div className="flex flex-col" style={{ minHeight: "calc(100vh - 57px)" }}>
      <div className="flex-1 flex flex-col gap-4 pb-4">
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
