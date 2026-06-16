type BudgetPageProps = {
  monthlyBudgetEur: number;
  onChange: (monthlyBudgetEur: number) => void;
};

export function BudgetPage({ monthlyBudgetEur, onChange }: BudgetPageProps) {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-bold leading-tight mb-2">
          What is your monthly mobility budget?
        </h1>
        <p className="text-gray-500 leading-relaxed m-0">
          Enter the approximate amount you want to spend on transport each
          month.
        </p>
      </div>

      <label aria-label="Monthly budget in euros">
        <div className="flex items-baseline gap-2 text-brand-red text-5xl font-black">
          <span>&euro;</span>
          <input
            type="number"
            min="0"
            step="10"
            value={monthlyBudgetEur}
            onChange={(event) => onChange(Number(event.target.value))}
            inputMode="numeric"
            className="border-0 text-brand-red text-5xl font-black min-w-0 w-32 outline-0 bg-transparent"
          />
        </div>
      </label>
    </div>
  );
}
