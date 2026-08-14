import { useEffect, useMemo, useState } from "react";
import { useI18n } from "../i18n";

export function AgentIntroPage() {
  const { t, language } = useI18n();

  // Rebuilt whenever the language changes. Joined from three separate translation keys (rather
  // than one key with embedded "\n\n") so each paragraph is independently translatable text
  // in en.ts/de.ts, not an opaque blob with baked-in formatting.
  const introText = useMemo(
    () =>
      [
        t("onboarding.agentIntro.headline"),
        t("onboarding.agentIntro.paragraph1"),
        t("onboarding.agentIntro.paragraph2"),
      ].join("\n\n"),
    [t],
  );
  // Derived once from introText itself, rather than duplicated as separate literals, so the
  // typing-progress comparisons below stay correct regardless of which language introText is in.
  const [fullHeadline = "", fullFirstParagraph = ""] = introText.split("\n\n");

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
    // Re-run (and restart the typewriter from scratch) whenever the language changes, since
    // introText itself changed — `language` is otherwise unused here but is the real trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [introText, language]);

  const [headline = "", firstParagraph = "", secondParagraph = ""] =
    visibleText.split("\n\n");
  const isTyping = visibleText.length < introText.length;
  const headlineIsTyping = headline.length < fullHeadline.length;
  const firstParagraphIsTyping =
    !headlineIsTyping && firstParagraph.length < fullFirstParagraph.length;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-5">
        <div className="w-20 h-20 flex-shrink-0" aria-hidden="true">
          <img
            className="w-full h-full object-contain"
            src="/assets/advisor.svg"
            alt=""
          />
        </div>
        <h1 className="text-3xl font-bold leading-tight m-0">
          {headline}
          {headlineIsTyping && (
            <span className="typing-cursor" aria-hidden="true" />
          )}
        </h1>
      </div>

      <div className="flex flex-col gap-4">
        <p className="text-gray-500 leading-relaxed m-0">
          {firstParagraph}
          {firstParagraphIsTyping && (
            <span className="typing-cursor" aria-hidden="true" />
          )}
        </p>
        <p className="text-gray-500 leading-relaxed m-0">
          {secondParagraph}
          {isTyping && !headlineIsTyping && !firstParagraphIsTyping && (
            <span className="typing-cursor" aria-hidden="true" />
          )}
        </p>
      </div>
    </div>
  );
}
