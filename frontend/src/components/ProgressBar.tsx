type ProgressBarProps = {
  step: number;
  total: number;
};

export function ProgressBar({ step, total }: ProgressBarProps) {
  const percent = Math.round((step / (total - 1)) * 100);
  return (
    <div className="h-1 bg-gray-200 w-full">
      <div
        className="h-1 bg-brand-red transition-all duration-300"
        style={{ width: `${percent}%` }}
        role="progressbar"
        aria-valuenow={step}
        aria-valuemin={0}
        aria-valuemax={total - 1}
        aria-label={`Step ${step} of ${total - 1}`}
      />
    </div>
  );
}
