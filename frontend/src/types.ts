export type PriorityWeights = {
  cost: number;
  time: number;
  sustainability: number;
};

export type WeekDay = "mon" | "tue" | "wed" | "thu" | "fri";

export type PersonalProfile = {
  full_name: string;
  employment_status: "employed" | "self-employed" | "student" | "other";
  profession: string;
  household_context: "single" | "partner" | "family" | "";
};

export type CommutePattern = {
  wfh_days: WeekDay[];
  office_days: WeekDay[];
};

export type CarProfile = {
  owns_car: boolean;
  fuel_type: "Petrol" | "Diesel" | "Hybrid" | "Plug-in Hybrid" | "Electric" | null;
  car_size: "Small car" | "Medium car" | "Large car" | null;
  efficiency: number | null;
  efficiency_unit: "L/100km" | "kWh/100km" | null;
  monthly_km_estimate: number | null;
};

export type CostStructure =
  | "fixed_recurring"
  | "fixed_annual_discount"
  | "usage_membership"
  | "pay_per_use";

export type SubscriptionCategory =
  | "rail_subscription"
  | "carsharing"
  | "micromobility_ridehailing";

export type SubscriptionEntry = {
  id: string;
  detected?: boolean;
  category: SubscriptionCategory;
  cost_structure: CostStructure;
  provider: string;
  product: string;
  monthly_cost_eur: number;
  billing_cycle: string;
  next_renewal_date: string;
  started: string;
  coverage_scope: string;
  notes: string;
  // fixed_annual_discount
  annual_price?: number;
  discount_rate?: number;
  travel_class?: string;
  // usage_membership
  registration_fee?: number;
  monthly_fee?: number;
  per_minute_rate?: number;
  per_km_rate?: number;
  // pay_per_use
  usage_frequency?: "rarely" | "monthly" | "weekly";
};

export type Integrations = {
  // email & calendar
  outlook_connected: boolean;
  gmail_connected: boolean;
  calendar_connected: boolean;
  // mobility providers
  db_connected: boolean;
  miles_connected: boolean;
  deutschlandticket_connected: boolean;
};

export type OnboardingPreferences = {
  personal: PersonalProfile;
  location: { home_city: string };
  commute: CommutePattern;
  car: CarProfile;
  subscriptions: SubscriptionEntry[];
  priorities: PriorityWeights;
  integrations: Integrations;
  notes: string;
};
