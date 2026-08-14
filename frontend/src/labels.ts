import type { TranslationKey } from "./i18n";
import type { MobilityMode } from "./types";

/** Translation keys for the five mobility modes (mode.* family — see en.ts's header comment on
 *  protected enum families). `mode` itself (from backend trip/subscription data) is never
 *  translated; only this display label is. */
export const MODE_LABEL_KEYS: Record<MobilityMode, TranslationKey> = {
  rail: "mode.rail",
  car_share: "mode.car_share",
  car_rental: "mode.car_rental",
  flight: "mode.flight",
  bus: "mode.bus",
};

/** Label for a raw mode string coming off trip data (typed as `string`, not the union) — falls
 *  back to the raw value for any unrecognised mode, same as before this was localized. Takes
 *  `t` (specifically `tDynamic`, from useI18n()) as a parameter rather than reading the current
 *  language itself, since this is a plain function called from render bodies, not a hook. */
export function modeLabel(mode: string, tDynamic: (key: string, fallback: string) => string): string {
  const key = (MODE_LABEL_KEYS as Record<string, TranslationKey>)[mode];
  return key ? tDynamic(key, mode) : mode;
}
