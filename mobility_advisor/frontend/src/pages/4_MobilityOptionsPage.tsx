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

      <div className="mobility-option-grid">
      <label
        className={
          mobilityOptions.owns_bike
            ? "mobility-option-card selected"
            : "mobility-option-card"
        }
      >
        <input
          type="checkbox"
          checked={mobilityOptions.owns_bike}
          onChange={(event) => updateOption("owns_bike", event.target.checked)}
        />
        <img className="mobility-icon" src="/assets/bike.svg" alt="" />
        <span>
          <strong>Bike</strong>
          <small>I own or regularly use a bike.</small>
        </span>
        <span className="checkbox-indicator" aria-hidden="true" />
      </label>

      <label
        className={
          mobilityOptions.owns_car
            ? "mobility-option-card selected"
            : "mobility-option-card"
        }
      >
        <input
          type="checkbox"
          checked={mobilityOptions.owns_car}
          onChange={(event) => updateOption("owns_car", event.target.checked)}
        />
        <img className="mobility-icon" src="/assets/car.svg" alt="" />
        <span>
          <strong>Car</strong>
          <small>I own or regularly use a car.</small>
        </span>
        <span className="checkbox-indicator" aria-hidden="true" />
      </label>
      </div>
    </div>
  );
}
