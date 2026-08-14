import { TypewriterHeading } from "../../components/TypewriterHeading";
import { useI18n } from "../../i18n";
import { BTN_PRIMARY_COMPACT } from "../../ui";

type ConfirmationVariant = "executed" | "no-change";

type ConfirmationPageProps = {
  resultMessage: string;
  variant?: ConfirmationVariant;
  onBackToDashboard: () => void;
};

const HEADING_KEY: Record<ConfirmationVariant, "confirmation.heading.executed" | "confirmation.heading.no_change"> = {
  executed: "confirmation.heading.executed",
  "no-change": "confirmation.heading.no_change",
};

const FOOTNOTE_KEY: Record<ConfirmationVariant, "confirmation.footnote.executed" | "confirmation.footnote.no_change"> = {
  executed: "confirmation.footnote.executed",
  "no-change": "confirmation.footnote.no_change",
};

export function ConfirmationPage({
  resultMessage,
  variant = "executed",
  onBackToDashboard,
}: ConfirmationPageProps) {
  const { t, language } = useI18n();
  return (
    <div className="flex flex-col items-center gap-8 text-center py-12 rise-in">
      <div
        className="w-20 h-20 bg-brand-red rounded-full flex items-center justify-center text-white text-3xl font-bold flex-shrink-0 shadow-lift"
        aria-hidden="true"
      >
        ✓
      </div>

      <div className="flex flex-col gap-3 max-w-sm">
        {/* key={language} restarts the typewriter cleanly on a language switch instead of
            stranding a half-typed string in the previous language. */}
        <TypewriterHeading key={language} text={t(HEADING_KEY[variant])} />
        <p className="text-gray-500 leading-relaxed m-0 text-sm whitespace-pre-wrap">{resultMessage}</p>
      </div>

      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 max-w-sm w-full">
        <p className="text-xs text-gray-400 m-0 leading-relaxed text-center">
          {t(FOOTNOTE_KEY[variant])}
        </p>
      </div>

      <button type="button" onClick={onBackToDashboard} className={BTN_PRIMARY_COMPACT}>
        {t("common.backToDashboard")}
      </button>
    </div>
  );
}
