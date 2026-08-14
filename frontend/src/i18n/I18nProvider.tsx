import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Language, TranslationKey } from "./types";
import { en } from "./locales/en";
import { de } from "./locales/de";
import { interpolate, translate, translatePlural, type Params } from "./translate";
import { getLanguage, setLanguage as setStoredLanguage, subscribeLanguage } from "./store";
import { LOCALE_TAG } from "./format";

const DICTS: Record<Language, Partial<Record<TranslationKey, string>>> = { en, de };

type I18nContextValue = {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: TranslationKey, params?: Params) => string;
  /** Plural-aware: picks `${baseKey}_one`/`${baseKey}_other` from en.ts's convention. */
  tPlural: (baseKey: string, count: number, params?: Params) => string;
  /** For dynamically-built keys the type system can't verify at compile time — e.g. an
   *  archetype id, a persona id, or a raw mode string off trip data (see labels.ts's
   *  modeLabel()). Always takes an explicit fallback, matching today's raw-value-fallback
   *  behavior for unrecognised values. */
  tDynamic: (key: string, fallback: string, params?: Params) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(getLanguage);

  // Stay in sync with the module-level store (store.ts) — the single source of truth, so any
  // caller of setLanguage() (including non-component code) is reflected here too.
  useEffect(() => subscribeLanguage(setLanguageState), []);

  // Keep <html lang> matching the active language (accessibility, spellcheck, font selection).
  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const changeLanguage = useCallback((lang: Language) => {
    setStoredLanguage(lang); // triggers the subscription above, which updates this state too
  }, []);

  const value = useMemo<I18nContextValue>(() => {
    const dict = DICTS[language];
    const localeTag = LOCALE_TAG[language];
    return {
      language,
      setLanguage: changeLanguage,
      t: (key, params) => translate(dict, en, key, params),
      tPlural: (baseKey, count, params) => translatePlural(dict, en, baseKey, count, localeTag, params),
      tDynamic: (key, fallback, params) =>
        interpolate((dict as Record<string, string>)[key] ?? fallback, params),
    };
  }, [language, changeLanguage]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n() must be used within an <I18nProvider>");
  return ctx;
}

/** Convenience hook for the common case of just needing the translate function. */
export function useT() {
  return useI18n().t;
}

export function useLanguage(): [Language, (lang: Language) => void] {
  const { language, setLanguage } = useI18n();
  return [language, setLanguage];
}
