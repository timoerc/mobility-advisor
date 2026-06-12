type SliderFieldProps = {
  label: string;
  value: number;
  minLabel: string;
  maxLabel: string;
  onChange: (value: number) => void;
};

export function SliderField({
  label,
  value,
  minLabel,
  maxLabel,
  onChange,
}: SliderFieldProps) {
  return (
    <label className="slider-field">
      <span className="field-title">{label}</span>
      <input
        type="range"
        min="0"
        max="1"
        step="0.1"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <span className="range-labels">
        <span>{minLabel}</span>
        <strong>{value.toFixed(1)}</strong>
        <span>{maxLabel}</span>
      </span>
    </label>
  );
}
