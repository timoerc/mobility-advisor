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
              value={car.type ?? ""}
              onChange={(e) =>
                set(
                  "type",
                  (e.target.value || null) as CarProfile["type"]
                )
              }
              className={inputClass}
            >
              <option value="">— select —</option>
              <option value="Petrol">Petrol</option>
              <option value="Diesel">Diesel</option>
              <option value="Hybrid">Hybrid</option>
              <option value="Plug-in Hybrid">Plug-in Hybrid</option>
              <option value="Electric">Electric</option>
            </select>
          </label>

          <label className={labelClass}>
            <span className={labelTextClass}>Car size</span>
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
              <option value="">— select —</option>
              <option value="Small car">Small car</option>
              <option value="Medium car">Medium car</option>
              <option value="Large car">Large car</option>
            </select>
          </label>

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
