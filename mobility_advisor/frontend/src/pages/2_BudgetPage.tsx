type BudgetPageProps = {
  monthlyBudgetEur: number;
  onChange: (monthlyBudgetEur: number) => void;
};

export function BudgetPage({ monthlyBudgetEur, onChange }: BudgetPageProps) {
  return (
    <div className="page-content budget-page">
      <div className="budget-question">
        <h1>What is your monthly mobility budget?</h1>
        <p className="intro-text">
          Enter the approximate amount you want to spend on transport each month.
        </p>
      </div>

      <label className="budget-field" aria-label="Monthly budget in euros">
        <div className="budget-input-wrap">
          <span>&euro;</span>
          <input
            type="number"
            min="0"
            step="10"
            value={monthlyBudgetEur}
            onChange={(event) => onChange(Number(event.target.value))}
            inputMode="numeric"
          />
        </div>
      </label>
    </div>
  );
}
