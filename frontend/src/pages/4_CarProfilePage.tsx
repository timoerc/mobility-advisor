import type { CarProfile } from "../types";

type CarProfilePageProps = {
  car: CarProfile;
  onChange: (car: CarProfile) => void;
};

const inputClass =
  "border border-gray-300 rounded-lg px-3 py-2 w-full focus:outline-none focus:border-brand-red focus:ring-2 focus:ring-red-100 bg-white";
const labelClass = "flex flex-col gap-1";
const labelTextClass = "font-semibold text-sm text-gray-700";

export function CarProfilePage({ car, onChange }: CarProfilePageProps) {
  const set = <K extends keyof CarProfile>(key: K, value: CarProfile[K]) =>
    onChange({ ...car, [key]: value });

  const toggleCar = (owns: boolean) => {
    if (!owns) {
      onChange({
        owns_car: false,
        fuel_type: null,
        efficiency: null,
        efficiency_unit: null,
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
          Do you own a car?
        </h1>
        <p className="text-gray-500 leading-relaxed m-0">
          If you drive regularly, we can factor your car into the cost and
          emissions comparison.
        </p>
      </div>

      <div className="flex gap-3">
        {[
          { value: true, label: "Yes" },
          { value: false, label: "No" },
        ].map(({ value, label }) => (
          <button
            key={label}
            type="button"
            onClick={() => toggleCar(value)}
            className={`flex-1 py-3 rounded-lg border-2 text-sm font-semibold cursor-pointer transition-colors ${
              car.owns_car === value
                ? "border-brand-red bg-red-50 text-brand-red"
                : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {car.owns_car && (
        <div className="flex flex-col gap-4 p-4 bg-white rounded-lg border border-gray-200">
          <label className={labelClass}>
            <span className={labelTextClass}>Fuel type</span>
            <select
              value={car.fuel_type ?? ""}
              onChange={(e) =>
                set(
                  "fuel_type",
                  (e.target.value || null) as CarProfile["fuel_type"]
                )
              }
              className={inputClass}
            >
              <option value="">— select —</option>
              <option value="petrol">Petrol</option>
              <option value="diesel">Diesel</option>
              <option value="electric">Electric</option>
              <option value="hybrid">Hybrid</option>
            </select>
          </label>

          <div className="flex gap-3">
            <label className={`${labelClass} flex-1`}>
              <span className={labelTextClass}>Efficiency</span>
              <input
                type="number"
                min="0"
                step="0.1"
                value={car.efficiency ?? ""}
                onChange={(e) =>
                  set(
                    "efficiency",
                    e.target.value ? Number(e.target.value) : null
                  )
                }
                placeholder="e.g. 6.5"
                className={inputClass}
              />
            </label>
            <label className={`${labelClass} w-36`}>
              <span className={labelTextClass}>Unit</span>
              <select
                value={car.efficiency_unit ?? ""}
                onChange={(e) =>
                  set(
                    "efficiency_unit",
                    (e.target.value || null) as CarProfile["efficiency_unit"]
                  )
                }
                className={inputClass}
              >
                <option value="">—</option>
                <option value="L/100km">L/100km</option>
                <option value="kWh/100km">kWh/100km</option>
              </select>
            </label>
          </div>

          <label className={labelClass}>
            <span className={labelTextClass}>Estimated monthly km</span>
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
              placeholder="e.g. 800"
              className={inputClass}
            />
          </label>
        </div>
      )}
    </div>
  );
}
