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
    <label className="flex flex-col gap-3">
      <span className="font-semibold text-sm">{label}</span>
      <input
        type="range"
        min="0"
        max="1"
        step="0.1"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <div className="flex justify-between text-sm text-gray-500">
        <span>{minLabel}</span>
        <strong className="text-gray-900">{value.toFixed(1)}</strong>
        <span>{maxLabel}</span>
      </div>
    </label>
  );
}
