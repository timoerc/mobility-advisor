// Shared Tailwind utility-class constants for interactive elements. Centralizes the
// hover/press/focus treatment so every CTA and card behaves consistently instead of each screen
// re-deriving its own hover:opacity-90 / border tweak. Follows the existing convention in this
// codebase of module-scope class-string constants (see the `inputClass` pattern in the
// onboarding pages) rather than introducing a wrapper component.

const BTN_PRIMARY_BASE =
  "bg-brand-red text-white font-semibold border-0 cursor-pointer " +
  "shadow-[0_1px_2px_rgba(236,0,22,0.25)] hover:bg-brand-red-hover hover:shadow-[0_5px_14px_-3px_rgba(236,0,22,0.4)] " +
  "active:bg-brand-red-deep active:translate-y-px active:shadow-none " +
  "disabled:opacity-40 disabled:cursor-not-allowed disabled:translate-y-0 disabled:shadow-none " +
  "transition-[background-color,box-shadow,transform] duration-150 ease-soft";

/** Full-size pill CTA — the main "Continue" / "Confirm" button pinned to the bottom of a screen. */
export const BTN_PRIMARY = `${BTN_PRIMARY_BASE} rounded-full px-8 py-3.5 text-sm`;

/** Same, slightly shorter vertical padding — used inline rather than screen-bottom pinned. */
export const BTN_PRIMARY_COMPACT = `${BTN_PRIMARY_BASE} rounded-full px-8 py-3 text-sm`;

/** Small pill CTA — inline actions like "Review" or "Connect". */
export const BTN_PRIMARY_SM = `${BTN_PRIMARY_BASE} rounded-full px-4 py-2 text-sm`;

const BTN_SECONDARY_BASE =
  "bg-white text-gray-600 font-semibold border border-gray-300 cursor-pointer " +
  "hover:bg-gray-50 hover:border-gray-400 active:bg-gray-100 " +
  "disabled:opacity-50 disabled:cursor-not-allowed " +
  "transition-colors duration-150 ease-soft";

/** Secondary pill button — bordered, neutral, for a "Cancel" / "Back" next to a primary CTA. */
export const BTN_SECONDARY = `${BTN_SECONDARY_BASE} rounded-full px-8 py-3.5 text-sm`;

/** Small secondary pill button — inline, next to a small primary CTA. */
export const BTN_SECONDARY_SM = `${BTN_SECONDARY_BASE} rounded-full px-4 py-2 text-sm`;

/** Circular icon-only button (header actions: back, chat, ...) — bordered white, subtle lift on hover. */
export const BTN_ICON =
  "h-8 w-8 rounded-full border border-gray-200 bg-white flex items-center justify-center cursor-pointer " +
  "text-gray-500 hover:bg-gray-50 hover:border-gray-300 hover:shadow-card active:scale-95 flex-shrink-0 " +
  "transition-[background-color,border-color,box-shadow,transform] duration-150 ease-soft";

/** Static content card — the flat white bordered box used throughout the dashboard / recommendation screens. */
export const CARD = "bg-white rounded-2xl border border-hairline shadow-card";

/** Same, but clickable — adds hover lift + press feedback. */
export const CARD_INTERACTIVE =
  `${CARD} cursor-pointer transition-[box-shadow,transform,border-color] duration-200 ease-soft ` +
  "hover:shadow-lift hover:-translate-y-0.5 active:translate-y-0 active:shadow-card";

/** Text input / select — the border+focus-ring treatment used on every onboarding form field. */
export const INPUT =
  "border border-gray-300 rounded-lg px-3 py-2 w-full bg-white " +
  "focus:outline-none focus:border-brand-red focus:ring-2 focus:ring-red-100 " +
  "transition-[border-color,box-shadow] duration-150";
