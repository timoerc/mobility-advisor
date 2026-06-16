import { useEffect, useState } from "react";

type TypewriterHeadingProps = {
  text: string;
  className?: string;
};

export function TypewriterHeading({
  text,
  className = "text-3xl font-bold leading-tight",
}: TypewriterHeadingProps) {
  const [visibleText, setVisibleText] = useState("");

  useEffect(() => {
    setVisibleText("");

    const typingTimer = window.setInterval(() => {
      setVisibleText((currentText) => {
        if (currentText.length >= text.length) {
          window.clearInterval(typingTimer);
          return currentText;
        }
        return text.slice(0, currentText.length + 1);
      });
    }, 30);

    return () => window.clearInterval(typingTimer);
  }, [text]);

  return (
    <h1 className={className}>
      {visibleText}
      {visibleText.length < text.length && (
        <span className="typing-cursor" aria-hidden="true" />
      )}
    </h1>
  );
}
