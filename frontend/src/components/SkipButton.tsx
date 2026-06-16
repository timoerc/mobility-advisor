type SkipButtonProps = {
  onSkip: () => void;
};

export function SkipButton({ onSkip }: SkipButtonProps) {
  return (
    <div className="flex justify-end">
      <button
        type="button"
        onClick={onSkip}
        className="text-sm text-gray-400 hover:text-gray-600 bg-transparent border-0 cursor-pointer p-0 leading-none"
      >
        Skip →
      </button>
    </div>
  );
}
