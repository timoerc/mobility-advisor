export type OnboardingPreferences = {
  monthly_budget_eur: number;
  priorities: {
    money: number;
    time: number;
    sustainability: number;
  };
  flexibility: number;
  mobility_options: {
    owns_bike: boolean;
    owns_car: boolean;
  };
  notes: string;
};
