import type { OnboardingPreferences } from "./types";

export type Persona = {
  id: string;
  name: string;
  tagline: string;
  avatar: string;
  avatarBg: string;
  onboardingComplete: boolean;
  profileData: OnboardingPreferences;
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
        age: 32,
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
        mode: "car_private",
        type: null,
        size: null,
        monthly_km_estimate: null,
      },
      subscriptions: [
        {
          id: "db_bc50_2nd_annual_standard",
          mode: "rail",
          provider: "Deutsche Bahn",
          product: "BahnCard 50 (2. Klasse, Standard, Jahresabo)",
          next_renewal_date: "2025-12-31",
          started: "2024-01-01",
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
        age: 41,
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
        mode: "car_private",
        type: "Petrol",
        size: "Medium car",
        monthly_km_estimate: 600,
      },
      subscriptions: [
        {
          id: "db_bc50_2nd_annual_standard",
          mode: "rail",
          provider: "Deutsche Bahn",
          product: "BahnCard 50 (2. Klasse, Standard, Jahresabo)",
          next_renewal_date: "2027-01-15",
          started: "2024-01-15",
        },
        {
          id: "db_deutschlandticket",
          mode: "rail",
          provider: "Deutsche Bahn",
          product: "Deutschland-Ticket",
          next_renewal_date: "2026-07-01",
          started: "2023-05-01",
        },
        {
          id: "miles_silber",
          mode: "car_share",
          provider: "MILES Mobility",
          product: "MILES Silber Pass",
          next_renewal_date: "2026-07-01",
          started: "2022-06-15",
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
        age: 22,
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
        mode: "car_private",
        type: null,
        size: null,
        monthly_km_estimate: null,
      },
      subscriptions: [
        {
          id: "db_bc50_2nd_annual_young",
          mode: "rail",
          provider: "Deutsche Bahn",
          product: "BahnCard 50 Young (2. Klasse, Jahresabo)",
          next_renewal_date: "2027-01-15",
          started: "2023-01-15",
        },
        {
          id: "db_deutschlandticket",
          mode: "rail",
          provider: "Deutsche Bahn",
          product: "Deutschland-Ticket",
          next_renewal_date: "2026-08-01",
          started: "2023-05-01",
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
  },
];
