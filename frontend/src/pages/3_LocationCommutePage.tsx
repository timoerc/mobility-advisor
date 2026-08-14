import { useT } from "../i18n";
import type { TranslationKey } from "../i18n";
import type { CommutePattern, WeekDay } from "../types";
import { INPUT } from "../ui";

type LocationCommutePageProps = {
  homeCity: string;
  commute: CommutePattern;
  onCityChange: (city: string) => void;
  onCommuteChange: (commute: CommutePattern) => void;
};

const DAYS: { id: WeekDay; labelKey: TranslationKey }[] = [
  { id: "mon", labelKey: "day.mon" },
  { id: "tue", labelKey: "day.tue" },
  { id: "wed", labelKey: "day.wed" },
  { id: "thu", labelKey: "day.thu" },
  { id: "fri", labelKey: "day.fri" },
];

export function LocationCommutePage({
  homeCity,
  commute,
  onCityChange,
  onCommuteChange,
}: LocationCommutePageProps) {
  const t = useT();
  const toggleDay = (day: WeekDay) => {
    const isWfh = commute.wfh_days.includes(day);
    const wfh_days = isWfh
      ? commute.wfh_days.filter((d) => d !== day)
      : [...commute.wfh_days, day];
    const office_days = DAYS.map((d) => d.id).filter(
      (d) => !wfh_days.includes(d)
    );
    onCommuteChange({ wfh_days, office_days });
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold leading-tight mb-2">
          {t("onboarding.locationCommute.heading")}
        </h1>
        <p className="text-gray-500 leading-relaxed m-0">
          {t("onboarding.locationCommute.subheading")}
        </p>
      </div>

      <label className="flex flex-col gap-1">
        <span className="font-semibold text-sm text-gray-700">{t("onboarding.locationCommute.homeCity")}</span>
        <input
          type="text"
          value={homeCity}
          onChange={(e) => onCityChange(e.target.value)}
          placeholder={t("onboarding.locationCommute.homeCity.placeholder")}
          className={INPUT}
        />
      </label>

      <div className="flex flex-col gap-3">
        <span className="font-semibold text-sm text-gray-700">
          {t("onboarding.locationCommute.weeklyPattern")}
        </span>
        <p className="text-xs text-gray-400 m-0">
          {t("onboarding.locationCommute.clickToToggle")}
        </p>
        <div className="flex gap-2">
          {DAYS.map(({ id, labelKey }) => {
            const isWfh = commute.wfh_days.includes(id);
            return (
              <button
                key={id}
                type="button"
                onClick={() => toggleDay(id)}
                className={`flex-1 py-3 rounded-lg border-2 text-sm font-semibold cursor-pointer transition-colors duration-150 active:scale-[0.98] flex flex-col items-center gap-1 ${
                  isWfh
                    ? "border-brand-red bg-red-50 text-brand-red shadow-card"
                    : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50 hover:border-gray-300"
                }`}
              >
                <span>{t(labelKey)}</span>
                <span className="text-xs font-normal">
                  {isWfh ? t("onboarding.locationCommute.wfh") : t("onboarding.locationCommute.office")}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
