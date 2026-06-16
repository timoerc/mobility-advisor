import type { CommutePattern, WeekDay } from "../types";

type LocationCommutePageProps = {
  homeCity: string;
  commute: CommutePattern;
  onCityChange: (city: string) => void;
  onCommuteChange: (commute: CommutePattern) => void;
};

const DAYS: { id: WeekDay; label: string }[] = [
  { id: "mon", label: "Mon" },
  { id: "tue", label: "Tue" },
  { id: "wed", label: "Wed" },
  { id: "thu", label: "Thu" },
  { id: "fri", label: "Fri" },
];

export function LocationCommutePage({
  homeCity,
  commute,
  onCityChange,
  onCommuteChange,
}: LocationCommutePageProps) {
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
          Where are you based?
        </h1>
        <p className="text-gray-500 leading-relaxed m-0">
          Your home city and commute pattern help estimate your regular travel
          needs.
        </p>
      </div>

      <label className="flex flex-col gap-1">
        <span className="font-semibold text-sm text-gray-700">Home city</span>
        <input
          type="text"
          value={homeCity}
          onChange={(e) => onCityChange(e.target.value)}
          placeholder="e.g. Frankfurt"
          className="border border-gray-300 rounded-lg px-3 py-2 w-full focus:outline-none focus:border-brand-red focus:ring-2 focus:ring-red-100 bg-white"
        />
      </label>

      <div className="flex flex-col gap-3">
        <span className="font-semibold text-sm text-gray-700">
          Weekly commute pattern
        </span>
        <p className="text-xs text-gray-400 m-0">
          Click a day to toggle between Office and WFH.
        </p>
        <div className="flex gap-2">
          {DAYS.map(({ id, label }) => {
            const isWfh = commute.wfh_days.includes(id);
            return (
              <button
                key={id}
                type="button"
                onClick={() => toggleDay(id)}
                className={`flex-1 py-3 rounded-lg border-2 text-sm font-semibold cursor-pointer transition-colors flex flex-col items-center gap-1 ${
                  isWfh
                    ? "border-brand-red bg-red-50 text-brand-red"
                    : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                <span>{label}</span>
                <span className="text-xs font-normal">
                  {isWfh ? "WFH" : "Office"}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
