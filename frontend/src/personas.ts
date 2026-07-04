import type { OnboardingPreferences } from "./types";
import type { Recommendation } from "./types/recommendation";

export type Persona = {
  id: string;
  name: string;
  tagline: string;
  avatar: string;
  avatarBg: string;
  onboardingComplete: boolean;
  profileData: OnboardingPreferences;
  mockRecommendation: Recommendation;
};

const MAJA_RECOMMENDATION: Recommendation = {
  verdict: "Your BahnCard 50 did not pay off this year",
  confidence: "high",
  summaryText:
    "Based on your travel history, your BahnCard 50 cost €244 but only saved you an estimated €72. Cancelling it would save you €172 over the next 12 months.",
  metrics: [
    { value: 172, unit: "€/year", direction: "save", label: "Potential saving" },
    { value: 4, unit: "trips", direction: "neutral", label: "Long-distance trips (6 mo)" },
    { value: 3.1, unit: "kg CO₂", direction: "reduce", label: "CO₂ impact (negligible)" },
  ],
  reasoning: [
    "You made only 4 long-distance train trips in the last 6 months.",
    "Break-even for a BahnCard 50 (2nd class, €244/year) requires at least 6 qualifying trips per 6-month period.",
    "Your estimated BahnCard savings were €36 in 6 months — roughly €72 annualised.",
    "No long-distance travel is signalled in your calendar for the next 3 months.",
    "Your declared priority is cost (54%), reinforcing the case for cancellation.",
  ],
  assumptions: [
    "Average 2nd class long-distance ticket price: €89 (derived from your travel history).",
    "BahnCard 50 discount applied at 50% on full-price tickets only.",
    "Calendar data covers 90-day forward window with no Hamburg or other long-haul events.",
  ],
  alternatives: [
    {
      id: "cancel",
      name: "Cancel BahnCard 50",
      annualCostEur: 0,
      savingsVsCurrentEur: 172,
      co2Impact: "Neutral",
      tradeoff: "Pay full price per trip. Best if travel stays low.",
      isRecommended: true,
    },
    {
      id: "bc25",
      name: "Downgrade to BahnCard 25",
      annualCostEur: 62.90,
      savingsVsCurrentEur: 109,
      co2Impact: "Neutral",
      tradeoff: "25% discount, breaks even at just 1–2 trips/month.",
      isRecommended: false,
    },
    {
      id: "keep",
      name: "Keep BahnCard 50",
      annualCostEur: 244,
      savingsVsCurrentEur: -172,
      co2Impact: "Neutral",
      tradeoff: "Only pays off if you make 6+ long-distance trips per 6 months.",
      isRecommended: false,
    },
  ],
  proposedAction: {
    title: "Cancel your BahnCard 50 renewal",
    description:
      "Your current BahnCard 50 expires on 31 December 2025. Cancelling the auto-renewal now prevents the €244 charge in January.",
    consequence:
      "From 1 January 2026 you will pay full DB prices per trip. You can upgrade to a BahnCard again at any time if your travel frequency increases.",
  },
};

const STEFAN_RECOMMENDATION: Recommendation = {
  verdict: "Your car costs more than you think — consider carsharing",
  confidence: "medium",
  summaryText:
    "Your car ownership costs an estimated €520/month (loan, insurance, fuel, parking). On your actual usage, carsharing would save around €210/month.",
  metrics: [
    { value: 210, unit: "€/month", direction: "save", label: "Potential saving" },
    { value: 42, unit: "kg CO₂/mo", direction: "reduce", label: "CO₂ reduction" },
    { value: 0, unit: "", direction: "neutral", label: "Trips affected: 0" },
  ],
  reasoning: [
    "You drive an estimated 600 km/month, mostly within Munich city limits.",
    "Fixed ownership costs (insurance, loan, parking) total ~€380/month regardless of usage.",
    "MILES carsharing at your usage level would cost ~€190/month.",
    "Public transit covers 80% of your stated destinations.",
  ],
  assumptions: [
    "Car loan: €280/month. Insurance: €65/month. Parking: €90/month. Fuel: €85/month.",
    "MILES rate: €0.31/min. Average trip: 22 minutes.",
  ],
  alternatives: [
    {
      id: "carsharing",
      name: "Switch to MILES carsharing",
      annualCostEur: 2280,
      savingsVsCurrentEur: 2520,
      co2Impact: "–42 kg CO₂/month",
      tradeoff: "No vehicle available on demand; booking required.",
      isRecommended: true,
    },
    {
      id: "keep_car",
      name: "Keep the car",
      annualCostEur: 6240,
      savingsVsCurrentEur: 0,
      tradeoff: "Full flexibility but highest cost.",
      isRecommended: false,
    },
  ],
  proposedAction: {
    title: "Register for MILES Mobility",
    description:
      "Create a MILES account and return your parking space. We'll monitor your usage for 2 months before recommending next steps.",
    consequence:
      "No changes to your car ownership until you decide. This is a first step only.",
  },
};

const LENA_RECOMMENDATION: Recommendation = {
  verdict: "Your Deutschlandticket is the right choice",
  confidence: "high",
  summaryText:
    "At €49/month, the Deutschlandticket covers all your local transit needs in Hamburg. No changes recommended.",
  metrics: [
    { value: 0, unit: "€", direction: "neutral", label: "Saving potential" },
    { value: 49, unit: "€/month", direction: "neutral", label: "Current cost" },
    { value: 18, unit: "kg CO₂/mo", direction: "reduce", label: "vs. car equivalent" },
  ],
  reasoning: [
    "You use public transit daily for your commute to university.",
    "The Deutschlandticket covers all U-Bahn, S-Bahn, bus, and tram routes in Germany.",
    "Your monthly transit spend without the ticket would be ~€82 (zone tickets).",
    "You already save €33/month compared to buying individual tickets.",
  ],
  assumptions: [
    "Hamburg zone A+B monthly ticket: €82.40 without Deutschlandticket.",
    "No long-distance travel detected in the last 6 months.",
  ],
  alternatives: [
    {
      id: "keep_dt",
      name: "Keep Deutschlandticket",
      annualCostEur: 588,
      savingsVsCurrentEur: 0,
      co2Impact: "Best option",
      tradeoff: "Optimal for your current usage pattern.",
      isRecommended: true,
    },
    {
      id: "zone_ticket",
      name: "Switch to Hamburg zone A+B",
      annualCostEur: 988,
      savingsVsCurrentEur: -400,
      tradeoff: "Higher cost, no benefit unless Deutschlandticket is discontinued.",
      isRecommended: false,
    },
  ],
  proposedAction: {
    title: "No action needed",
    description: "Your current setup is optimal. We'll re-evaluate in 6 months or if your commute changes.",
    consequence: "Nothing changes. We'll notify you if conditions shift.",
  },
};

export const DEFAULT_PERSONAS: Persona[] = [
  {
    id: "maja",
    name: "Maja Hoffmann",
    tagline: "Frequent business traveller · BahnCard 50",
    avatar: "MH",
    avatarBg: "#ec0016",
    onboardingComplete: false,
    profileData: {
      personal: {
        full_name: "Maja Hoffmann",
        employment_status: "employed",
        profession: "Consultant",
        household_context: "single",
      },
      location: { home_city: "Köln" },
      commute: {
        office_days: ["mon", "tue", "wed", "thu"],
        wfh_days: ["fri"],
      },
      car: {
        owns_car: false,
        fuel_type: null,
        car_size: null,
        efficiency: null,
        efficiency_unit: null,
        monthly_km_estimate: null,
      },
      subscriptions: [
        {
          id: "bahncard50",
          category: "rail_subscription",
          cost_structure: "fixed_annual_discount",
          provider: "Deutsche Bahn",
          product: "BahnCard 50",
          monthly_cost_eur: 20.33,
          billing_cycle: "annual",
          next_renewal_date: "2025-12-31",
          started: "2024-01-01",
          coverage_scope: "Germany nationwide",
          notes: "",
          annual_price: 244,
          discount_rate: 50,
          travel_class: "2nd",
        },
      ],
      priorities: { cost: 0.54, time: 0.16, sustainability: 0.3 },
      integrations: {
        outlook_connected: true,
        gmail_connected: false,
        calendar_connected: false,
        db_connected: true,
        miles_connected: true,
        deutschlandticket_connected: true,
        additional_connections: ["KVB", "RMV", "FreeNow"],
      },
      notes: "Mostly travel Cologne–Frankfurt, sometimes Hamburg.",
    },
    mockRecommendation: MAJA_RECOMMENDATION,
  },
  {
    id: "stefan",
    name: "Stefan Kurz",
    tagline: "Car owner · Occasional train traveller",
    avatar: "SK",
    avatarBg: "#1f6feb",
    onboardingComplete: false,
    profileData: {
      personal: {
        full_name: "Stefan Kurz",
        employment_status: "employed",
        profession: "Engineer",
        household_context: "partner",
      },
      location: { home_city: "München" },
      commute: {
        office_days: ["mon", "tue", "wed", "thu", "fri"],
        wfh_days: [],
      },
      car: {
        owns_car: true,
        fuel_type: "Petrol",
        car_size: "Medium car",
        efficiency: 7.5,
        efficiency_unit: "L/100km",
        monthly_km_estimate: 600,
      },
      subscriptions: [
        {
          id: "stefan-bc50",
          category: "rail_subscription",
          cost_structure: "fixed_annual_discount",
          provider: "Deutsche Bahn",
          product: "BahnCard 50 (2. Klasse)",
          monthly_cost_eur: 20.33,
          billing_cycle: "annual",
          next_renewal_date: "2027-01-15",
          started: "2024-01-15",
          coverage_scope: "Germany nationwide",
          notes: "Annual card at €244/yr, auto-renews January. 50% discount on all DB long-distance fares.",
          annual_price: 244,
          discount_rate: 50,
          travel_class: "2nd",
        },
        {
          id: "stefan-dticket",
          category: "rail_subscription",
          cost_structure: "fixed_recurring",
          provider: "Deutschlandticket",
          product: "Deutschland-Ticket",
          monthly_cost_eur: 58,
          billing_cycle: "monthly",
          next_renewal_date: "2026-07-01",
          started: "2023-05-01",
          coverage_scope: "Germany nationwide",
          notes: "Unlimited travel on all local and regional public transport across Germany. Monthly, cancellable.",
        },
        {
          id: "stefan-miles",
          category: "carsharing",
          cost_structure: "usage_membership",
          provider: "MILES Mobility",
          product: "MILES+ Abo",
          monthly_cost_eur: 4.90,
          billing_cycle: "monthly",
          next_renewal_date: "2026-07-01",
          started: "2022-06-15",
          coverage_scope: "",
          notes: "Car-sharing membership tier. Provides 5% cashback on MILES trip costs and slightly reduced per-minute rate.",
          monthly_fee: 4.90,
        },
      ],
      priorities: { cost: 0.3, time: 0.5, sustainability: 0.2 },
      integrations: {
        outlook_connected: false,
        gmail_connected: true,
        calendar_connected: true,
        db_connected: true,
        miles_connected: true,
        deutschlandticket_connected: true,
        additional_connections: ["MVV", "Bolt"],
      },
      notes: "Drive to work daily within Munich. Regular business trips to Frankfurt by train (company HQ is in Frankfurt-Sachsenhausen).",
    },
    mockRecommendation: STEFAN_RECOMMENDATION,
  },
  {
    id: "lena",
    name: "Lena Brandt",
    tagline: "Student · Deutschlandticket",
    avatar: "LB",
    avatarBg: "#1a7f37",
    onboardingComplete: false,
    profileData: {
      personal: {
        full_name: "Lena Brandt",
        employment_status: "student",
        profession: "Student",
        household_context: "single",
      },
      location: { home_city: "Hamburg" },
      commute: {
        office_days: ["mon", "tue", "wed", "thu"],
        wfh_days: ["fri"],
      },
      car: {
        owns_car: false,
        fuel_type: null,
        car_size: null,
        efficiency: null,
        efficiency_unit: null,
        monthly_km_estimate: null,
      },
      subscriptions: [
        {
          id: "lena-bc50",
          category: "rail_subscription",
          cost_structure: "fixed_annual_discount",
          provider: "Deutsche Bahn",
          product: "BahnCard 50 (2. Klasse)",
          monthly_cost_eur: 20.33,
          billing_cycle: "annual",
          next_renewal_date: "2027-01-15",
          started: "2023-01-15",
          coverage_scope: "Germany nationwide",
          notes: "Annual card at €244/yr, auto-renews January. 50% discount on all DB long-distance fares.",
          annual_price: 244,
          discount_rate: 50,
          travel_class: "2nd",
        },
        {
          id: "dt",
          category: "rail_subscription",
          cost_structure: "fixed_recurring",
          provider: "HVV",
          product: "Deutschlandticket",
          monthly_cost_eur: 49,
          billing_cycle: "monthly",
          next_renewal_date: "2026-08-01",
          started: "2023-05-01",
          coverage_scope: "Germany nationwide",
          notes: "",
        },
      ],
      priorities: { cost: 0.5, time: 0.2, sustainability: 0.3 },
      integrations: {
        outlook_connected: false,
        gmail_connected: true,
        calendar_connected: false,
        db_connected: true,
        miles_connected: false,
        deutschlandticket_connected: true,
        additional_connections: ["HVV", "Nextbike"],
      },
      notes: "Commute to university by U-Bahn and S-Bahn.",
    },
    mockRecommendation: LENA_RECOMMENDATION,
  },
];
