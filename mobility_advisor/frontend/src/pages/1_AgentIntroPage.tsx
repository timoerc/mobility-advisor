import { useEffect, useState } from "react";

const introText =
  "Hi, I am your mobility advisor.\n\nI will help you understand your mobility portfolio and find travel options that fit your preferences.\n\nLet us get you started!";

export function AgentIntroPage() {
  const [visibleText, setVisibleText] = useState("");

  useEffect(() => {
    setVisibleText("");

    const typingTimer = window.setInterval(() => {
      setVisibleText((currentText) => {
        if (currentText.length >= introText.length) {
          window.clearInterval(typingTimer);
          return currentText;
        }

        return introText.slice(0, currentText.length + 1);
      });
    }, 28);

    return () => window.clearInterval(typingTimer);
  }, []);

  const [headline = "", firstParagraph = "", secondParagraph = ""] =
    visibleText.split("\n\n");
  const isTyping = visibleText.length < introText.length;
  const headlineIsTyping =
    headline.length < "Hi, I am your mobility advisor.".length;
  const firstParagraphIsTyping =
    !headlineIsTyping &&
    firstParagraph.length <
      "I will help you understand your mobility portfolio and find travel options that fit your preferences."
        .length;

  return (
    <div className="page-content agent-intro-page">
      <div className="agent-heading-row">
        <div className="agent-avatar" aria-hidden="true">
          <img src="/assets/advisor.svg" alt="" />
        </div>
        <h1>
          {headline}
          {headlineIsTyping && (
            <span className="typing-cursor" aria-hidden="true" />
          )}
        </h1>
      </div>

      <div className="agent-copy">
        <p className="intro-text">
          {firstParagraph}
          {firstParagraphIsTyping && (
            <span className="typing-cursor" aria-hidden="true" />
          )}
        </p>
        <p className="intro-text">
          {secondParagraph}
          {isTyping && !headlineIsTyping && !firstParagraphIsTyping && (
            <span className="typing-cursor" aria-hidden="true" />
          )}
        </p>
      </div>
    </div>
  );
}
