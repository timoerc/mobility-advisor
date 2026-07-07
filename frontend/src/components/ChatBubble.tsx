type ChatBubbleProps = {
  role: "agent" | "user";
  text: string;
};

export function ChatBubble({ role, text }: ChatBubbleProps) {
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] rounded-2xl rounded-tr-sm px-4 py-2.5 bg-red-50 border border-red-100">
          <p className="text-sm text-[#1f1f1f] m-0 leading-relaxed whitespace-pre-wrap">{text}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-end gap-2">
      <div className="w-7 h-7 flex-shrink-0 rounded-full overflow-hidden bg-gray-100">
        <img src="/assets/advisor.svg" alt="" className="w-full h-full object-contain" />
      </div>
      <div className="max-w-[78%] rounded-2xl rounded-bl-sm px-4 py-2.5 bg-white border border-gray-200">
        <p className="text-sm text-[#1f1f1f] m-0 leading-relaxed whitespace-pre-wrap">{text}</p>
      </div>
    </div>
  );
}
