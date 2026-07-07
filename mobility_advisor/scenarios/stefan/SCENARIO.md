# Scenario 02 — Edge Case: Contradictory Signals

## Summary

Maja's mobility data contains no dominant pattern. Rail usage is erratic (feast-or-famine across months), BC50 is borderline break-even, carsharing is similarly irregular, the calendar suggests a possible relocation to Hamburg, and her stated preferences set flexibility, sustainability, and budget on a collision course. The expected agent outcome is a **hedged, conditional recommendation** — not a single confident action.

---

## Why the Data Is Deliberately Ambiguous

| Signal | Value | Interpretation |
|---|---|---|
| BC50 actual savings (12 months) | €239 | Almost exactly equal to card cost €244 — within €5 |
| BC50 break-even threshold | €244 annual savings = €488 full-price DB spend | Borderline: break-even not conclusively met or missed |
| Rail usage distribution | Months 1,3,4,5,7,8,10,11,12 = 0 trips; months 2,6,9 = 4–5 trips | Highly erratic, no stable pattern |
| MILES usage distribution | 3 heavy months, 6 empty months | Erratic; standard Abo hard to justify |
| Relocation signal | Apartment viewing in Hamburg + job offer decision in Aug 2026 | If Hamburg: D-Ticket value changes (Hamburg zone vs. Frankfurt zone); BC50 usage may spike or collapse |
| International trip | Amsterdam — neither D-Ticket nor BahnCard valid | Adds opaque cost not captured in BC50 analysis |
| User preferences | Budget €90/mo + high flexibility + sustainability_weight 0.8 + values_time_over_money: true | Three goals in direct tension at current spend level |

---

## Numeric Rationale

- **BC50 savings:** €239 over 12 months vs. card cost €244/year → net loss: **−€5** (breakeven effectively tied)
- **If relocation to Hamburg:** biweekly Frankfurt↔Hamburg rail trips would push annual DB spend to ~€1,100+ → BC50 clearly worth keeping (or upgrading)
- **If no relocation:** current erratic pattern continues → BC50 marginally not worth it
- **Budget constraint:** Current monthly spend ≈ €83.23 (€20.33 + €58 + €4.90) — just under €90 cap, but leaves no buffer for ad-hoc trips

---

## Expected Agent Behaviour

| Agent | Expected Action |
|---|---|
| **Analyst** | Flags three contradictions: (1) borderline BC50 break-even with no trend; (2) possible_relocation signal with material impact on all subscriptions; (3) user preferences internally conflicting (flexibility + CO2 + budget). Must **not** resolve these — surface all three. |
| **Forecaster** | Produces two demand branches: (a) Hamburg relocation confirmed → high Frankfurt↔Hamburg rail demand; (b) no relocation → demand continues erratic. Must explicitly label both branches and note the decision date (Aug 2026). |
| **Optimizer** | Outputs conditional recommendations for each branch, not a single action. |
| **Communicator** | Drafts conditional output: "If relocation proceeds: [action X]. If not: [action Y]. Recommend revisiting after Aug 15 decision date." |

---

## What a Correct Output Looks Like

```
RECOMMENDATION (CONDITIONAL — HIGH UNCERTAINTY)

If relocation to Hamburg is confirmed (decision by 2026-08-15):
  → Keep BahnCard 50: Frankfurt↔Hamburg trips (~490 km) justify the card within 2 months
  → Re-evaluate Deutschland-Ticket: Hamburg zone coverage needs verification
  → Estimated annual saving vs. status quo: −€0 (card becomes clearly worth keeping)

If no relocation (Frankfurt base continues):
  → Cancel BahnCard 50: savings (€239) nearly equal card cost (€244); erratic pattern makes
    forecasting unreliable; net expected loss €5–€50/year depending on future usage
  → Action by: 15 January 2027 to avoid auto-renewal (next_renewal_date from subscription data)
  → Retain Deutschland-Ticket and MILES+ Abo
  → Estimated annual saving: ~€244

Data quality note: Amsterdam trip cost not captured in BC50 analysis (card not applicable).
Recommendation should be revisited after 2026-08-15 job offer decision.
```

---

## What a Failing Output Looks Like

- A single confident recommendation ("cancel BC50") without surfacing the relocation signal
- A recommendation that ignores the budget vs. flexibility vs. CO2 tension
- Treating the erratic history as a trend (e.g., "usage is declining")
- No mention of the Aug 15 decision date as a key information trigger

---

## Signals by File

- **travel_history.json** — 19 trips; erratic monthly distribution; DB spend borderline break-even
- **calendar_events.json** — relocation signals in July–September 2026; international trip with no subscription coverage; recurring Frankfurt office days
- **user_preferences.json** — three conflicting goals at `monthly_budget_eur: 90`
- **current_subscriptions.json** — standard stack. Each entry carries `billing_cycle` and `next_renewal_date` (BC50: `2027-01-15` annual; D-Ticket and MILES+: `2026-07-01` monthly).
- **mobility_catalog.json** — full catalog; each option carries `billing_cycle`.
