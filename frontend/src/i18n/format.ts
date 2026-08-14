import type { Language } from "./types";

// en-GB (not en-US): this is a German-market product, and en-GB gives day-first dates that read
// consistently alongside de-DE rather than switching date order between languages.
export const LOCALE_TAG: Record<Language, string> = { en: "en-GB", de: "de-DE" };

export function formatNumber(lang: Language, n: number, opts?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat(LOCALE_TAG[lang], opts).format(n);
}

// de-DE renders EUR as "1.234,00 €" — trailing symbol, dot thousands separator, comma decimal —
// vs. en-GB's "€1,234.00". This is a real, intentional visual change from the app's previous
// literal "€" + toFixed()/Math.round() concatenation everywhere; widen-check tight number
// displays (MetricTile, StatTile, AlternativeRow chips) once this rolls out.
export function formatCurrency(lang: Language, amountEur: number, opts?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat(LOCALE_TAG[lang], {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
    ...opts,
  }).format(amountEur);
}

export function formatCurrencyPrecise(lang: Language, amountEur: number): string {
  return formatCurrency(lang, amountEur, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatInt(lang: Language, n: number): string {
  return formatNumber(lang, Math.round(n));
}

// Matches the previous fmtKg behavior: below 10kg, show one decimal place (small CO2 figures
// are otherwise rounded to 0 and look like "no emissions"); at/above 10kg, round to an integer.
export function formatKg(lang: Language, n: number): string {
  return n >= 10
    ? formatNumber(lang, Math.round(n))
    : formatNumber(lang, n, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

export type DateStyle = "long" | "short";

export function formatDate(lang: Language, iso: string, style: DateStyle = "long"): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso; // unparsable → show the raw value rather than "Invalid Date"
  const opts: Intl.DateTimeFormatOptions =
    style === "long"
      ? { day: "2-digit", month: "short", year: "numeric" }
      : { day: "2-digit", month: "short" };
  return d.toLocaleDateString(LOCALE_TAG[lang], opts);
}

// Self-contained (doesn't route through the translation catalog) since "min"/"h" vs. "min"/"Std."
// are near-universal abbreviations reused across many call sites, not full sentences.
export function formatDurationMin(lang: Language, totalMinutes: number): string {
  const sign = totalMinutes < 0 ? "-" : "";
  const abs = Math.round(Math.abs(totalMinutes));
  const hours = Math.floor(abs / 60);
  const mins = abs % 60;
  const hourUnit = lang === "de" ? "Std." : "h";
  if (hours === 0) return `${sign}${mins} min`;
  if (mins === 0) return `${sign}${hours} ${hourUnit}`;
  return `${sign}${hours} ${hourUnit} ${mins} min`;
}
