import { useEffect, useState } from "react";

type StatusMessageProps = {
  messages: string[];
  intervalMs?: number;
};

export function StatusMessage({ messages, intervalMs = 1800 }: StatusMessageProps) {
  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (messages.length <= 1) return;
    const timer = window.setInterval(() => {
      setVisible(false);
      window.setTimeout(() => {
        setIndex((i) => (i + 1) % messages.length);
        setVisible(true);
      }, 300);
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [messages, intervalMs]);

  return (
    <p
      className="text-gray-500 text-sm text-center leading-relaxed transition-opacity duration-300"
      style={{ opacity: visible ? 1 : 0 }}
    >
      {messages[index]}
    </p>
  );
}
