import { useI18n } from "../i18n";
import type { Language } from "../i18n";

const LANGUAGES: Language[] = ["en", "de"];

type LanguageSwitcherProps = {
  className?: string;
};

// Compact two-segment EN|DE pill — not a <select>, since two mutually-exclusive options don't
// warrant a dropdown, and this matches the app's existing rounded-full button idiom. Mounted in
// every header (see AppShell, App.tsx's onboarding/editing headers, PseudoLoginPage) so the
// language is switchable from any screen.
export function LanguageSwitcher({ className = "" }: LanguageSwitcherProps) {
  const { language, setLanguage, t } = useI18n();
  return (
    <div
      role="group"
      aria-label={t("nav.language")}
      className={`inline-flex items-center rounded-full border border-gray-200 bg-white p-0.5 flex-shrink-0 ${className}`}
    >
      {LANGUAGES.map((lang) => (
        <button
          key={lang}
          type="button"
          aria-pressed={language === lang}
          onClick={() => setLanguage(lang)}
          className={`px-2.5 py-1 rounded-full text-xs font-semibold cursor-pointer transition-colors border-0 ${
            language === lang
              ? "bg-brand-red text-white"
              : "bg-transparent text-gray-500 hover:text-gray-900"
          }`}
        >
          {lang.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
