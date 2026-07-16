export type PriorityWeights = {
  cost: number;
  time: number;
  sustainability: number;
};

export type WeekDay = "mon" | "tue" | "wed" | "thu" | "fri";

export type PersonalProfile = {
  full_name: string;
  age: number | null;
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
  mode: "car_private";
  type: "Petrol" | "Diesel" | "Hybrid" | "Plug-in Hybrid" | "Electric" | null;
  size: "Small car" | "Medium car" | "Large car" | null;
  monthly_km_estimate: number | null;
};

export type MobilityMode =
  | "rail"
  | "car_share"
  | "car_rental"
  | "flight"
  | "bus";

export type SubscriptionEntry = {
  id: string;
  detected?: boolean;
  mode: MobilityMode;
  provider: string;
  product: string;
  next_renewal_date: string;
  started: string;
  // Present on subscriptions returned by /api/current-subscriptions (resolved server-side from the
  // catalog); absent on the leaner entries built during onboarding. Used by the home dashboard's
  // monthly-cost summary.
  monthly_cost_eur?: number;
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
  // additional providers connected via the "more" section
  additional_connections?: string[];
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
