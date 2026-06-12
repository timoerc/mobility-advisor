import { SliderField } from "../components/SliderField";

type FlexibilityPageProps = {
  flexibility: number;
  onChange: (flexibility: number) => void;
};

export function FlexibilityPage({
  flexibility,
  onChange,
}: FlexibilityPageProps) {
  return (
    <div className="page-content">
      <div>
        <h1>How flexible are your trips?</h1>
        <p className="intro-text">
          Tell us whether your plans are usually fixed or easy to adjust.
        </p>
      </div>

      <SliderField
        label="Flexibility"
        value={flexibility}
        minLabel="Fixed"
        maxLabel="Flexible"
        onChange={onChange}
      />
    </div>
  );
}
