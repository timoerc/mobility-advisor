type ProgressDotsProps = {
  currentStep: number;
  totalSteps: number;
};

export function ProgressDots({ currentStep, totalSteps }: ProgressDotsProps) {
  return (
    <div className="progress-dots" aria-label={`Step ${currentStep + 1}`}>
      {Array.from({ length: totalSteps }).map((_, index) => (
        <span
          className={index === currentStep ? "dot active" : "dot"}
          key={index}
        />
      ))}
    </div>
  );
}
