import { SliderField } from "../components/SliderField";
import type { OnboardingPreferences } from "../types";

type Priorities = OnboardingPreferences["priorities"];

type PrioritiesPageProps = {
  priorities: Priorities;
  onChange: (priorities: Priorities) => void;
};

export function PrioritiesPage({ priorities, onChange }: PrioritiesPageProps) {
  const updatePriority = (key: keyof Priorities, value: number) => {
    onChange({ ...priorities, [key]: value });
  };

  return (
    <div className="page-content">
      <div>
        <h1>What matters most?</h1>
        <p className="intro-text">
          Balance the priorities DB should consider when planning your mobility
          options.
        </p>
      </div>

      <SliderField
        label="Saving money"
        value={priorities.money}
        minLabel="Less"
        maxLabel="More"
        onChange={(value) => updatePriority("money", value)}
      />
      <SliderField
        label="Saving time"
        value={priorities.time}
        minLabel="Less"
        maxLabel="More"
        onChange={(value) => updatePriority("time", value)}
      />
      <SliderField
        label="Sustainability"
        value={priorities.sustainability}
        minLabel="Less"
        maxLabel="More"
        onChange={(value) => updatePriority("sustainability", value)}
      />
    </div>
  );
}
