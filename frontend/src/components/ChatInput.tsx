import { useRef, useState } from "react";

type ChatInputProps = {
  onSend: (text: string) => void;
  disabled?: boolean;
};

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  };

  return (
    <div className="sticky bottom-0 bg-canvas border-t border-gray-200 px-4 py-3">
      <div className="max-w-2xl mx-auto flex items-end gap-2">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about your mobility…"
          disabled={disabled}
          className="flex-1 resize-none border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-brand-red focus:ring-2 focus:ring-red-100 bg-white disabled:opacity-50 leading-relaxed transition-[border-color,box-shadow] duration-150"
          style={{ minHeight: "44px", maxHeight: "120px" }}
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!value.trim() || disabled}
          aria-label="Send"
          className="w-10 h-10 rounded-full bg-brand-red text-white flex items-center justify-center flex-shrink-0 hover:bg-brand-red-hover active:bg-brand-red-deep active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer border-0 shadow-[0_1px_2px_rgba(236,0,22,0.25)] hover:shadow-[0_5px_14px_-3px_rgba(236,0,22,0.4)] transition-[background-color,box-shadow,transform] duration-150 ease-soft"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
    </div>
  );
}
