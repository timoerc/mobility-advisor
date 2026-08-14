import type { en } from "./locales/en";

export type Language = "en" | "de";

// The full set of valid translation keys, derived from en.ts (the source of truth). de.ts is
// typed as Record<TranslationKey, string> once Phase 5 flips it from Partial<...> — at that
// point a missing German string becomes a `tsc` failure, not a silent runtime fallback.
export type TranslationKey = keyof typeof en;
