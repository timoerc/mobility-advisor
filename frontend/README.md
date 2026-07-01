# DB Mobility Advisor — Frontend

A React/TypeScript prototype for a personalised mobility portfolio advisor. Built as part of a BCG × Deutsche Bahn university project. The app guides users through an onboarding questionnaire, then presents AI-generated recommendations about their mobility subscriptions (e.g. whether to keep, cancel, or change a BahnCard 50).

---

## Quick Start

**Requirements:** Node.js 18+. No `.env` file or API key required — all data is mocked.

```bash
cd frontend
npm install
npm run dev
# App available at http://localhost:5173
```

To stop: `Ctrl + C`

---

## Tech Stack

| Dependency | Version | Purpose |
|---|---|---|
| React | 18 | UI rendering |
| TypeScript | 5 | Type safety across all components and data models |
| Vite + `@vitejs/plugin-react` | 6 | Dev server, HMR, production build |
| Tailwind CSS v4 + `@tailwindcss/vite` | 4 | Utility-first styling |

> **Tailwind v4 note:** config lives in `src/index.css` under `@theme { … }` — there is no `tailwind.config.js`. This is different from Tailwind v3.

---

## Architecture and Application Flow

Navigation is managed entirely by in-memory state in `App.tsx` — there is no URL router. The app has three sequential phases:

### Phase 1 — Pseudo Login (`PseudoLoginPage`)

Always shown first. The user selects one of the predefined personas (or starts a blank "new" profile). No real authentication happens — this is a demo convenience so reviewers can switch between different user profiles. The selected persona drives which mock data and recommendation are loaded for the session.

Persona completion state is stored in `localStorage` under the key `persona:{id}`. Selecting a persona whose onboarding is already complete skips straight to Phase 3.

### Phase 2 — Onboarding (`OnboardingFlow`)

Shown only when the selected persona has not yet completed onboarding (`onboardingComplete === false`). A self-contained multi-step wizard (steps 0–10) with a progress bar, skip logic, and prev/next navigation. Collects: personal profile, location, car ownership, data integrations, mobility subscriptions, AHP priority weights, monthly budget, and free-text notes.

On completion, `onboardingComplete` is set to `true` in `localStorage` and the collected data is saved as the persona's profile. The user transitions directly to Phase 3.

### Phase 3 — Main Application (`MainApp`)

The post-onboarding experience, wrapped in a persistent `AppShell` top bar. Contains five views navigated by in-memory state:

| View | Purpose |
|---|---|
| `analysis` | Animated loading screen; auto-advances after ~4 s |
| `dashboard` | Recommendation verdict, metrics, reasoning, alternatives |
| `approval` | User explicitly confirms or declines the proposed action |
| `confirmation` | Simulated success screen |
| `chat` | Ad-hoc question answering with canned smart responses |

The profile avatar button in the top bar opens the `ProfileDropdown` (see below).

---

## Directory Structure

```
frontend/
├── public/
│   └── assets/                  # db-logo.svg, advisor.svg, arrow.svg
├── src/
│   ├── index.css                # Tailwind v4 import + @theme tokens
│   ├── App.css                  # Animations: logoReveal, cursorBlink, nav-arrow
│   ├── main.tsx                 # ReactDOM.createRoot entry point
│   ├── App.tsx                  # Phase router: login → onboarding → main
│   │
│   ├── personas.ts              # Persona definitions + mock recommendations (add/edit here)
│   ├── mobility-archetypes.ts   # Archetype definitions + classifyArchetype() scoring function
│   │
│   ├── types.ts                 # Shared onboarding data types (OnboardingPreferences, etc.)
│   ├── types/
│   │   └── recommendation.ts    # Recommendation, Alternative, MetricDelta, ProposedAction
│   │
│   ├── components/
│   │   ├── ProgressBar.tsx
│   │   ├── ProgressDots.tsx
│   │   ├── SkipButton.tsx
│   │   ├── SliderField.tsx
│   │   ├── SubscriptionCard.tsx
│   │   ├── TypewriterHeading.tsx
│   │   ├── PersonaCard.tsx      # Login screen persona tile
│   │   ├── AppShell.tsx         # Persistent top bar for main app
│   │   ├── ProfileDropdown.tsx  # Avatar button + profile action menu
│   │   ├── StatusMessage.tsx    # Fading typewriter status line (analysis screen)
│   │   ├── ConfidenceBadge.tsx  # "High / Medium / Low confidence" indicator
│   │   ├── MetricTile.tsx       # Single metric value tile (savings, CO₂, etc.)
│   │   ├── AlternativeRow.tsx   # Contract alternative comparison card
│   │   ├── ChatBubble.tsx       # Agent or user message bubble
│   │   └── ChatInput.tsx        # Sticky textarea + send button bar
│   │
│   └── pages/
│       ├── login/
│       │   └── PseudoLoginPage.tsx
│       ├── 0_LogoIntroPage.tsx        # Onboarding pages live directly under pages/
│       ├── 1_AgentIntroPage.tsx       # Numbering prefix makes step order immediately visible
│       ├── 2_PersonalProfilePage.tsx
│       ├── 3_LocationCommutePage.tsx
│       ├── 4_CarProfilePage.tsx
│       ├── 5_MobilityStackPage.tsx
│       ├── 6_BudgetPage.tsx
│       ├── 7_PrioritiesPage.tsx
│       ├── 8_IntegrationsPage.tsx
│       ├── 9_NotesPage.tsx
│       ├── 10_FinalPage.tsx
│       └── main/
│           ├── AnalysisPage.tsx
│           ├── DashboardPage.tsx
│           ├── ApprovalPage.tsx
│           ├── ConfirmationPage.tsx
│           └── ChatPage.tsx
```

---

## Design System

All DB brand tokens are defined in `src/index.css` and available as Tailwind utilities.

| Token | Value | Usage |
|---|---|---|
| `brand-red` | `#ec0016` | CTAs, active states, progress bar, accents |
| `#f5f5f3` | Off-white | Page background |
| `#1f1f1f` | Near-black | Body text, headings |
| `gray-500` | `#6b7280` | Subtext, descriptions |
| `gray-200 / gray-300` | — | Borders, dividers, inactive states |
| Inter | System font | All text |

### Recurring Tailwind patterns

| Element | Classes |
|---|---|
| Page heading | `text-3xl font-bold leading-tight` |
| Body subtext | `text-gray-500 leading-relaxed` |
| Primary button | `bg-brand-red text-white rounded-full px-8 py-3 font-semibold hover:opacity-90` |
| Ghost button | `bg-white text-gray-600 rounded-full border border-gray-300 hover:bg-gray-50` |
| Text input | `border border-gray-300 rounded-lg px-3 py-2 focus:border-brand-red focus:ring-2 focus:ring-red-100` |
| Active toggle | `border-brand-red bg-red-50 text-brand-red` |
| Inactive toggle | `border-gray-200 bg-white text-gray-600 hover:bg-gray-50` |
| Card | `bg-white rounded-2xl border border-gray-200 p-5` |

CSS animations (`logoReveal`, `cursorBlink`) and the SVG-mask nav arrow (`.nav-arrow`) are defined in `src/App.css`.

---

## Onboarding Steps

| Step | Component | Collects | Skippable |
|---|---|---|---|
| 0 | `LogoIntroPage` | — | Auto-advances (2.6 s) |
| 1 | `AgentIntroPage` | — | No |
| 2 | `PersonalProfilePage` | Name, employment, profession, household | No |
| 3 | `LocationCommutePage` | Home city, office / WFH days | No |
| 4 | `CarProfilePage` | Car ownership, fuel type, size, efficiency, km/month | Yes |
| 5 | `IntegrationsPage` | Data source connections (all mock) | Yes |
| 6 | `MobilityStackPage` | Active subscriptions (rail, carsharing, micro) | Yes |
| 7 | `PrioritiesPage` | Cost / Time / CO₂ AHP weights (3 Likert questions) | No |
| 8 | `BudgetPage` | Monthly mobility budget (€) | No |
| 9 | `NotesPage` | Free-text notes for the agent | Yes |
| 10 | `FinalPage` | Completion + JSON profile download | — |

Step 10 shows a "Start analysis →" button instead of a Continue arrow. Clicking it marks onboarding complete in `localStorage` and transitions to the main app.

---

## Persona System

All personas are defined in `src/personas.ts` as an array of `Persona` objects. Each persona carries:

- **Display metadata:** `id`, `name`, `tagline`, `avatar` (initials), `avatarBg` (hex colour)
- **Pre-filled profile data:** a complete `OnboardingPreferences` object so a reviewer can click through the onboarding form without typing anything
- **Mock recommendation:** a full `Recommendation` object (verdict, metrics, reasoning, alternatives, proposed action) shown in the main app dashboard

`onboardingComplete` starts as `false` in the source file; the app updates it in `localStorage` at runtime. Refreshing the page restores the saved state.

**To add a new persona:** add an entry to `DEFAULT_PERSONAS` in `personas.ts` with a filled `profileData` and `mockRecommendation`. No other file needs to change.

---

## Profile Dropdown

The `ProfileDropdown` component (`src/components/ProfileDropdown.tsx`) is anchored to the avatar initials button in the `AppShell` top bar. It replaces the old settings icon.

**Opening / closing**
- Click the initials button to toggle the dropdown.
- Click anywhere outside the panel or press `Escape` to close.

**Dropdown items**

| Item | Deep-link target | Effect |
|---|---|---|
| Persona name + tagline | — | Non-interactive header, shows who is active |
| Edit preferences | Step 7 (AHP weights) | Opens onboarding at the priorities step |
| Edit profile | Step 2 (personal profile) | Opens onboarding at the personal details step |
| Mobility modes | Step 4 (car + subscriptions) | Opens onboarding at the car profile step |
| Re-do full onboarding | Step 0 | Resets `onboardingComplete` to `false`, restarts wizard |
| Switch profile | — | Returns to the persona selector (login screen) |

**Deep-link behaviour (Edit preferences / Edit profile / Mobility modes)**

When one of these items is selected, `App.tsx` saves `returnToMain` (the current main view) and jumps to the target onboarding step. While `returnToMain` is set the onboarding footer changes:
- The **back arrow** exits immediately back to the main app (without saving changes).
- The normal Continue arrow is replaced by a **"Save & return →"** button that persists changes to `localStorage` and returns to the original main view.

**Implementation details**
- Outside-click dismissal: `useRef` on the wrapper div + `document.addEventListener("mousedown", …)` inside a `useEffect` that is only active while `open === true`.
- Each dropdown action is wrapped with `wrap(fn)` which closes the panel before invoking the callback, so the parent never sees an open dropdown after navigation.

---

## Preference Weights (AHP)

Step 7 of onboarding (`PrioritiesPage`) asks three 7-point Likert questions:

1. "Getting to my destination quickly matters more to me than a low price." (Time vs. Cost)
2. "A low CO₂ footprint matters more to me than a low price." (CO₂ vs. Cost)
3. "Getting to my destination quickly matters more to me than a low CO₂ footprint." (Time vs. CO₂)

Each answer maps to an AHP intensity ratio (1 = strongly disagree → 1:5, 4 = balanced → 1:1, 7 = strongly agree → 5:1). A 3×3 pairwise comparison matrix is built from the three ratios, geometric means are computed per row, and the result is normalised to sum to 1.0, yielding `{ cost, time, sustainability }` weights stored on the persona profile.

The full calculation is inlined in `7_PrioritiesPage.tsx` in the `computeWeights` function. The live weight bars update as the user adjusts sliders.

---

## Mobility Archetype Classification

After onboarding completes, `classifyArchetype()` in `src/mobility-archetypes.ts` runs a scoring function against the collected `OnboardingPreferences` and returns one of six archetype IDs:

| Archetype | Trigger signals |
|---|---|
| `committed_driver` | Car owner, high km/month, strong time priority |
| `rail_commuter` | BahnCard held, DB connected, no car |
| `multimodal` | 3+ subscriptions across ≥2 categories |
| `eco_pioneer` | Sustainability priority > 40% |
| `budget_optimizer` | Cost priority > 40%, low monthly budget |
| `remote_native` | 4+ WFH days, low office attendance |

Each archetype carries a `name`, `tagline`, `description`, `portfolioInsights` (3 data-backed bullet points), and a `source` citation. These are displayed as a card on the dashboard. The classification is pure client-side logic — no backend call is made.

The archetype is recomputed whenever `classifyArchetype()` is called (on onboarding completion or after profile edits via the dropdown deep-links).

---

## Mock Data and API Layer

All data consumed by the frontend comes from one of three sources:

1. **Persona profile data** — defined statically in `src/personas.ts` and pre-populated into the onboarding form
2. **Mock recommendations** — also defined in `src/personas.ts` as `mockRecommendation` per persona, passed to `DashboardPage`, `ApprovalPage`, and `ChatPage`
3. **Archetype classification** — computed client-side by `classifyArchetype()` in `src/mobility-archetypes.ts` from the user's onboarding answers; no external data source

The `MobilityStackPage` (step 6) additionally attempts a `fetch('/api/detected-subscriptions.json')` to simulate auto-detection of subscriptions from connected accounts. If the file is not present (it isn't, by default), it fails silently and starts with an empty list.

To add a real API backend: replace the `mockRecommendation` lookup in `App.tsx`'s main-phase render with a real fetch, returning the same `Recommendation` shape defined in `src/types/recommendation.ts`.

---

## Current State

### Completed

- Pseudo login with 3 demo personas (Maja Hoffmann, Stefan Kurz, Lena Brandt)
- Full 11-step onboarding wizard with progress bar, skip logic, back navigation, and typewriter animations
- `localStorage` persistence of onboarding completion per persona; returning personas skip straight to the dashboard
- **ProfileDropdown** — avatar initials button opens a panel with deep-links to Edit preferences, Edit profile, Mobility modes, Re-do onboarding, and Switch profile; deep-links show a "Save & return →" footer so users exit back to where they were
- Back button in the `AppShell` top bar when inside the Chat view
- Back button on the persona selector when navigating to it from the main app ("Switch profile")
- **Analysis screen** — animated status messages + progress bar, auto-advances after ~4 s
- **Recommendation dashboard** — verdict, confidence badge, metric tiles, reasoning with collapsible assumptions, alternatives comparison, mobility archetype card
- **Mobility archetype classification** — pure client-side scoring of 6 archetypes from onboarding answers; recomputed on profile edits
- **Approval screen** — explicit user confirmation step with prototype disclaimer
- **Confirmation screen** — simulated success with TypewriterHeading
- **Chat screen** — full message thread, typing indicator, canned smart responses keyed to keywords (BahnCard, CO₂, budget, routes, renewals), "run analysis" trigger
- AHP priority weights with Consistency Ratio check (CR > 0.10 shows a warning)
- DB design system: brand-red, off-white background, Inter font, CSS animations
- TypeScript strict mode throughout; zero build errors

### Known Limitations

- No real authentication — the persona selector is for demo purposes only
- No live backend calls — analysis result is pre-computed per persona, not live
- No real contract execution — approval/confirmation screens simulate an action
- AHP consistency ratio warning is advisory only — users can proceed with inconsistent answers
- `localStorage` state is cleared if the user clears browser storage
- The `MobilityStackPage` auto-detection stub will silently 404 in dev (harmless)

---

## Asset Disclaimer

SVG assets in `public/assets/` were sourced for visual prototyping purposes. Licenses have not been fully verified. **Do not use these assets in a public or commercial release** without confirming usage rights or replacing them with properly licensed alternatives.
