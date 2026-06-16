# Mobility Advisor — Onboarding Frontend

A React/TypeScript prototype that collects user preferences through a structured onboarding flow and exports them as a JSON profile for the Mobility Advisor backend agent.

---

## Overview

The onboarding flow guides users through 9 data-collection steps. On completion, the collected profile can be downloaded as `user_profile.json`, which serves as the input for the AI agent pipeline.

The frontend is intentionally stateless — all data lives in React component state and is never sent to a server during the prototype phase.

---

## Onboarding Flow

| Step | Page | Data collected |
|------|------|----------------|
| 1 | Agent Introduction | Informational — no input |
| 2 | Personal Profile | Name, employment status, profession, household context |
| 3 | Location & Commute | Home city, WFH days, office days |
| 4 | Car Profile | Car ownership, fuel type, efficiency, monthly km |
| 5 | Mobility Stack | Current subscriptions (rail, car-share, micro-mobility) |
| 6 | Budget | Monthly mobility budget (€) |
| 7 | Priorities | Relative weights for cost, time, and sustainability |
| 8 | Integrations | Calendar/email connections (Outlook, Gmail) |
| 9 | Notes | Free-text notes for the agent |

At the end, the user can download their complete profile as a structured JSON file.

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| [React 18](https://react.dev) | UI framework |
| [Vite](https://vitejs.dev) | Dev server and bundler |
| [TypeScript](https://www.typescriptlang.org) | Static typing across all components and data models |
| [Tailwind CSS](https://tailwindcss.com) | Utility-first styling |

All shared data models are defined in `src/types.ts` and enforced end-to-end via TypeScript.

---

## Getting Started

**Prerequisites:** [Node.js](https://nodejs.org) 18+

```bash
# Install dependencies
npm install

# Start the development server
npm run dev
```

Open the URL shown in the terminal (typically `http://localhost:5173`) in your browser.

To stop the server: `Ctrl + C`

---

## Project Structure

```
frontend/
├── public/
│   └── assets/          # SVG icons and logos
├── src/
│   ├── pages/           # One file per onboarding step (numbered for flow order)
│   │   ├── 0_LogoIntroPage.tsx
│   │   ├── 1_AgentIntroPage.tsx
│   │   ├── 2_PersonalProfilePage.tsx
│   │   └── ...
│   ├── components/      # Reusable UI elements (ProgressBar, SliderField, SkipButton, …)
│   ├── types.ts         # Shared TypeScript types for all onboarding data
│   ├── App.tsx          # Root component — controls step routing and shared state
│   └── App.css          # Global styles and CSS custom properties
├── index.html
├── vite.config.ts
└── tsconfig.json
```

Page files are prefixed with their step index (e.g. `2_PersonalProfilePage.tsx`) to make the flow order immediately visible in the file tree.

---

## Exported JSON Schema

The downloaded `user_profile.json` follows this structure:

```json
{
  "personal": { "full_name": "", "employment_status": "", "profession": "", "household_context": "" },
  "location": { "home_city": "" },
  "commute": { "wfh_days": [], "office_days": [] },
  "car": { "owns_car": false, "fuel_type": null, "efficiency": null, "monthly_km_estimate": null },
  "subscriptions": [],
  "preferences": {
    "monthly_budget_eur": 100,
    "priorities": { "cost": 0.33, "time": 0.33, "sustainability": 0.34 },
    "notes": ""
  },
  "integrations": { "outlook_connected": false, "gmail_connected": false, "calendar_connected": false }
}
```

---

## Asset Disclaimer

Some SVG icons were sourced from the web for visual prototyping purposes. Their licenses have not been fully verified. **Do not use these assets in a public or commercial release** without confirming usage rights or replacing them with properly licensed alternatives.
