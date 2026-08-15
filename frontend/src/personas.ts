import type { OnboardingPreferences } from "./types";

// This file is the OFFLINE FALLBACK only — App.tsx:171-184 overwrites DEFAULT_PERSONAS with
// GET /api/personas on every successful mount, so in normal operation none of this data is
// actually shown to a user. It's only visible if that fetch fails.
//
// Deliberately left English-only rather than half-mirroring the backend's `_de` sibling-field
// pattern (see CLAUDE.md / mobility_advisor/models.py) here: this is only reachable when the
// initial GET /api/personas failed, so it's already an offline/degraded path, and duplicating
// German copy for six personas' `tagline`/`profession`/`notes` here just to cover that rare
// case isn't worth the upkeep of keeping two copies in sync. The six real personas' actual
// served tagline/profession/notes ARE localized via `_de` siblings on
// mobility_advisor/scenarios/*/persona.json, resolved by pick() in api/routes/personas.py —
// see list_personas().
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
  {
    id: "katrin",
    name: "Katrin Berger",
    tagline: "Key Account Manager · BahnCard 25, values flexibility",
    avatar: "KB",
    avatarBg: "#7c3aed",
    onboardingComplete: false,
    profileData: {
      personal: {
        full_name: "Katrin Berger",
        age: 44,
        employment_status: "employed",
        profession: "Key Account Manager",
        household_context: "family",
      },
      location: { home_city: "Düsseldorf" },
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
          id: "db_bc25_2nd_annual_standard",
          mode: "rail",
          provider: "Deutsche Bahn",
          product: "BahnCard 25 (2. Klasse, Standard, Jahresabo)",
          next_renewal_date: "2026-11-30",
          started: "2023-12-01",
        },
        {
          id: "db_deutschlandticket",
          mode: "rail",
          provider: "Deutsche Bahn",
          product: "Deutschland-Ticket",
          next_renewal_date: "2026-07-01",
          started: "2023-05-01",
        },
      ],
      priorities: { cost: 0.3, time: 0.5, sustainability: 0.2 },
      integrations: {
        outlook_connected: true,
        gmail_connected: false,
        calendar_connected: true,
        db_connected: true,
        miles_connected: false,
        deutschlandticket_connected: true,
        additional_connections: ["VRR", "FreeNow"],
      },
      notes: "Lots of last-minute client travel across Germany. Books late and reschedules often — flexible tickets matter more to me than the cheapest fare.",
    },
  },
  {
    id: "tobias",
    name: "Tobias Wolf",
    tagline: "Management consultant · BahnCard 50, travel about to drop",
    avatar: "TW",
    avatarBg: "#d97706",
    onboardingComplete: false,
    profileData: {
      personal: {
        full_name: "Tobias Wolf",
        age: 36,
        employment_status: "employed",
        profession: "Management Consultant",
        household_context: "partner",
      },
      location: { home_city: "Frankfurt" },
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
          next_renewal_date: "2027-01-10",
          started: "2025-01-10",
        },
        {
          id: "db_deutschlandticket",
          mode: "rail",
          provider: "Deutsche Bahn",
          product: "Deutschland-Ticket",
          next_renewal_date: "2026-07-01",
          started: "2023-05-01",
        },
      ],
      priorities: { cost: 0.45, time: 0.35, sustainability: 0.2 },
      integrations: {
        outlook_connected: true,
        gmail_connected: false,
        calendar_connected: true,
        db_connected: true,
        miles_connected: false,
        deutschlandticket_connected: true,
        additional_connections: ["RMV"],
      },
      notes: "On a Munich client project since last autumn — lots of Frankfurt–Munich train travel. Project wraps end of August; next staffing looks like a local Frankfurt engagement.",
    },
  },
  {
    id: "sofia",
    name: "Sofia Ricci",
    tagline: "UX designer · Deutschlandticket + frequent car-share",
    avatar: "SR",
    avatarBg: "#db2777",
    onboardingComplete: false,
    profileData: {
      personal: {
        full_name: "Sofia Ricci",
        age: 29,
        employment_status: "employed",
        profession: "UX Designer",
        household_context: "single",
      },
      location: { home_city: "Berlin" },
      commute: {
        office_days: ["mon", "tue", "wed"],
        wfh_days: ["thu", "fri"],
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
          id: "db_deutschlandticket",
          mode: "rail",
          provider: "Deutsche Bahn",
          product: "Deutschland-Ticket",
          next_renewal_date: "2026-07-01",
          started: "2023-09-01",
        },
        {
          id: "miles_basis",
          mode: "car_share",
          provider: "MILES Mobility",
          product: "MILES Basis (Pay-per-use)",
          next_renewal_date: "",
          started: "2023-09-10",
        },
      ],
      priorities: { cost: 0.4, time: 0.3, sustainability: 0.3 },
      integrations: {
        outlook_connected: false,
        gmail_connected: true,
        calendar_connected: true,
        db_connected: true,
        miles_connected: true,
        deutschlandticket_connected: true,
        additional_connections: ["BVG", "Nextbike"],
      },
      notes: "Get around Berlin by U-/S-Bahn and MILES car-share for evenings and errands. No membership — I just book MILES pay-as-you-go.",
    },
  },
];
