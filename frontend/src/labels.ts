import type { MobilityMode } from "./types";

/** Human-readable labels for the five mobility modes. Shared by the subscription cards and the
 *  home dashboard's mode widgets so the wording stays in one place. */
export const MODE_LABELS: Record<MobilityMode, string> = {
  rail: "Rail",
  car_share: "Carsharing",
  car_rental: "Car Rental",
  flight: "Flight",
  bus: "Bus",
};

/** Label for a raw mode string coming off trip data (typed as `string`, not the union); falls back
 *  to the raw value for any unrecognised mode. */
export function modeLabel(mode: string): string {
  return (MODE_LABELS as Record<string, string>)[mode] ?? mode;
}
