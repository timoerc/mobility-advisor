import type { TranslationKey } from "./types";
import { en } from "./locales/en";

export type Params = Record<string, string | number>;

export function interpolate(template: string, params?: Params): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}

/** Pure, non-React lookup — no hook, callable from plain modules with an explicit dict/locale.
 *  `dict` is the active locale's (possibly partial, during the migration) table; `fallbackDict`
 *  is always the English table, so a key not yet translated in `dict` still renders instead of
 *  showing raw key text. */
export function translate(
  dict: Partial<Record<TranslationKey, string>>,
  fallbackDict: Record<TranslationKey, string> = en,
  key: TranslationKey,
  params?: Params,
): string {
  const template = dict[key] ?? fallbackDict[key] ?? key;
  return interpolate(template, params);
}

/** Plural-aware variant: picks `${baseKey}_one` / `${baseKey}_other` via Intl.PluralRules, then
 *  interpolates (with `count` auto-added to params). Both keys must be declared in en.ts under
 *  that naming convention — see the header comment there. English and German are both plain
 *  CLDR one/other locales, so this single implementation covers both without extra categories. */
export function translatePlural(
  dict: Partial<Record<TranslationKey, string>>,
  fallbackDict: Record<TranslationKey, string>,
  baseKey: string,
  count: number,
  localeTag: string,
  params?: Params,
): string {
  const rule = new Intl.PluralRules(localeTag).select(count);
  const key = `${baseKey}_${rule}` as TranslationKey;
  const otherKey = `${baseKey}_other` as TranslationKey;
  const template =
    dict[key] ?? fallbackDict[key] ?? dict[otherKey] ?? fallbackDict[otherKey] ?? baseKey;
  return interpolate(template, { count, ...params });
}
