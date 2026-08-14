import { useT } from "../i18n";
import type { TranslationKey } from "../i18n";
import type { CarProfile } from "../types";
import { INPUT } from "../ui";

type CarProfilePageProps = {
  car: CarProfile;
  onChange: (car: CarProfile) => void;
};

const inputClass = INPUT;
const labelClass = "flex flex-col gap-1";
const labelTextClass = "font-semibold text-sm text-gray-700";

// CarProfile.type/.size store these exact English strings as DATA VALUES (they round-trip
// through the backend's ProfilePayload and the six scenario persona.json fixtures) — only the
// <option> DISPLAY TEXT is localized here, via this lookup into car.type.*/car.size.*.
const FUEL_TYPE_LABEL_KEYS: Record<string, TranslationKey> = {
  "Petrol": "car.type.Petrol",
  "Diesel": "car.type.Diesel",
  "Hybrid": "car.type.Hybrid",
  "Plug-in Hybrid": "car.type.Plug-in Hybrid",
  "Electric": "car.type.Electric",
};
const CAR_SIZE_LABEL_KEYS: Record<string, TranslationKey> = {
  "Small car": "car.size.Small car",
  "Medium car": "car.size.Medium car",
  "Large car": "car.size.Large car",
};

export function CarProfilePage({ car, onChange }: CarProfilePageProps) {
  const t = useT();
  const set = <K extends keyof CarProfile>(key: K, value: CarProfile[K]) =>
    onChange({ ...car, [key]: value });

  const toggleCar = (owns: boolean) => {
    if (!owns) {
      onChange({
        owns_car: false,
        mode: "car_private",
        type: null,
        size: null,
        monthly_km_estimate: null,
      });
    } else {
      onChange({ ...car, owns_car: true });
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold leading-tight mb-2">
          {t("onboarding.carProfile.heading")}
        </h1>
        <p className="text-gray-500 leading-relaxed m-0">
          {t("onboarding.carProfile.subheading")}
        </p>
      </div>

      <div className="flex gap-3">
        {[
          { value: true, labelKey: "onboarding.carProfile.yes" as const },
          { value: false, labelKey: "onboarding.carProfile.no" as const },
        ].map(({ value, labelKey }) => (
          <button
            key={labelKey}
            type="button"
            onClick={() => toggleCar(value)}
            className={`flex-1 py-3 rounded-lg border-2 text-sm font-semibold cursor-pointer transition-colors duration-150 active:scale-[0.98] ${
              car.owns_car === value
                ? "border-brand-red bg-red-50 text-brand-red shadow-card"
                : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50 hover:border-gray-300"
            }`}
          >
            {t(labelKey)}
          </button>
        ))}
      </div>

      {car.owns_car && (
        <div className="flex flex-col gap-4 p-4 bg-white rounded-lg border border-gray-200">
          <label className={labelClass}>
            <span className={labelTextClass}>{t("onboarding.carProfile.fuelType")}</span>
            <select
              value={car.type ?? ""}
              onChange={(e) =>
                set(
                  "type",
                  (e.target.value || null) as CarProfile["type"]
                )
              }
              className={inputClass}
            >
              <option value="">{t("common.selectPlaceholder")}</option>
              {Object.entries(FUEL_TYPE_LABEL_KEYS).map(([value, labelKey]) => (
                <option key={value} value={value}>{t(labelKey)}</option>
              ))}
            </select>
          </label>

          <label className={labelClass}>
            <span className={labelTextClass}>{t("onboarding.carProfile.carSize")}</span>
            <select
              value={car.size ?? ""}
              onChange={(e) =>
                set(
                  "size",
                  (e.target.value || null) as CarProfile["size"]
                )
              }
              className={inputClass}
            >
              <option value="">{t("common.selectPlaceholder")}</option>
              {Object.entries(CAR_SIZE_LABEL_KEYS).map(([value, labelKey]) => (
                <option key={value} value={value}>{t(labelKey)}</option>
              ))}
            </select>
          </label>

          <label className={labelClass}>
            <span className={labelTextClass}>{t("onboarding.carProfile.estimatedMonthlyKm")}</span>
            <input
              type="number"
              min="0"
              step="50"
              value={car.monthly_km_estimate ?? ""}
              onChange={(e) =>
                set(
                  "monthly_km_estimate",
                  e.target.value ? Number(e.target.value) : null
                )
              }
              placeholder={t("onboarding.carProfile.estimatedMonthlyKm.placeholder")}
              className={inputClass}
            />
          </label>
        </div>
      )}
    </div>
  );
}
