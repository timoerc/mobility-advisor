import type { OnboardingPreferences } from "../types";

type MobilityOptions = OnboardingPreferences["mobility_options"];

type MobilityOptionsPageProps = {
  mobilityOptions: MobilityOptions;
  onChange: (mobilityOptions: MobilityOptions) => void;
};

export function MobilityOptionsPage({
  mobilityOptions,
  onChange,
}: MobilityOptionsPageProps) {
  const updateOption = (key: keyof MobilityOptions, value: boolean) => {
    onChange({ ...mobilityOptions, [key]: value });
  };

  return (
    <div className="page-content">
      <div>
        <h1>Which options do you already have?</h1>
        <p className="intro-text">
          This helps the advisor avoid suggesting things that do not fit your
          everyday setup.
        </p>
      </div>

      <label className="checkbox-card">
        <input
          type="checkbox"
          checked={mobilityOptions.owns_bike}
          onChange={(event) => updateOption("owns_bike", event.target.checked)}
        />
        <span>
          <strong>I own or regularly use a bike</strong>
          <small>Useful for station access and short city trips.</small>
        </span>
      </label>

      <label className="checkbox-card">
        <input
          type="checkbox"
          checked={mobilityOptions.owns_car}
          onChange={(event) => updateOption("owns_car", event.target.checked)}
        />
        <span>
          <strong>I own or regularly use a car</strong>
          <small>Useful for comparing train, car, and mixed journeys.</small>
        </span>
      </label>
    </div>
  );
}
