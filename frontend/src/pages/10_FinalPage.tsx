import { TypewriterHeading } from "../components/TypewriterHeading";
import { useI18n } from "../i18n";
import { BTN_PRIMARY_COMPACT } from "../ui";

type FinalPageProps = {
  onGoHome: () => void;
};

export function FinalPage({ onGoHome }: FinalPageProps) {
  const { t, language } = useI18n();
  return (
    <div className="flex flex-col items-center gap-8 text-center py-8 rise-in">
      <div
        className="w-20 h-20 bg-brand-red rounded-full flex items-center justify-center text-white text-3xl font-bold flex-shrink-0 shadow-lift"
        aria-hidden="true"
      >
        ✓
      </div>

      <div className="flex flex-col gap-3">
        <TypewriterHeading key={language} text={t("onboarding.final.heading")} />
        <p className="text-gray-500 leading-relaxed m-0">
          {t("onboarding.final.body")}
        </p>
      </div>

      <button
        type="button"
        onClick={onGoHome}
        className={BTN_PRIMARY_COMPACT}
      >
        {t("onboarding.final.goHome")}
      </button>
    </div>
  );
}
