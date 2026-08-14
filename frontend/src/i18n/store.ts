import type { Language } from "./types";

// Module-level mutable language state, kept OUTSIDE React. This exists for the one legitimate
// non-component consumer: api.ts needs the current language synchronously (to set the
// X-Language request header) from plain async functions that aren't components and can't call a
// hook. React code should use useLanguage()/useT() from I18nProvider.tsx instead, which stays in
// sync with this store via subscribeLanguage() and re-renders on change.
const STORAGE_KEY = "mobility_advisor_language";
const DEFAULT_LANGUAGE: Language = "en";

function isLanguage(value: string | null): value is Language {
  return value === "en" || value === "de";
}

function readStoredLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return isLanguage(stored) ? stored : DEFAULT_LANGUAGE;
  } catch {
    // localStorage unavailable (private mode / disabled) — fall back to the default for this tab.
    return DEFAULT_LANGUAGE;
  }
}

let currentLanguage: Language = readStoredLanguage();
const listeners = new Set<(lang: Language) => void>();

export function getLanguage(): Language {
  return currentLanguage;
}

export function setLanguage(lang: Language): void {
  if (lang === currentLanguage) return;
  currentLanguage = lang;
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // Language still applies for this tab; it just won't persist across reloads.
  }
  listeners.forEach((listener) => listener(lang));
}

/** Subscribe to language changes made anywhere (including outside React). I18nProvider is the
 *  primary subscriber, so its own React state always mirrors this store. */
export function subscribeLanguage(listener: (lang: Language) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
