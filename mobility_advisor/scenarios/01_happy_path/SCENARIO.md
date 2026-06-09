# Scenario 01 — Happy Path: Clear Over-Subscription

## Summary

Maja holds BahnCard 50 but barely uses long-distance rail. Three short-haul DB trips in 12 months produce a total discounted DB spend of €36 — far below what is needed to justify the €244/year card cost. The expected agent outcome is an unambiguous recommendation to cancel BC50 or downgrade to BC25.

---

## Numeric Rationale

| Metric | Value |
|---|---|
| BC50 annual card cost | €244 (€20.33 × 12) |
| Required annual DB spend (full price) to break even | €244 ÷ 0.50 = **€488** |
| Actual discounted DB spend (12 months) | €36 |
| Implied full-price equivalent | €72 |
| Gap vs. breakeven | **€416 short** |
| Savings BC50 produced | €36 (equal to discounted spend) |
| Annual net loss from holding BC50 | €244 − €36 = **−€208** |

Even the cheaper BC25 (€111/year) would not break even at this usage level (breakeven: €111 ÷ 0.25 = €444 annual DB spend). The correct recommendation is full cancellation of BC50.

---

## Data Properties

- **travel_history.json** — 5 trips total: 3 short-haul DB rail trips (Frankfurt↔Mannheim, Frankfurt→Heidelberg), 2 local MILES car-share trips. No long-distance intercity rail.
- **calendar_events.json** — 8 events, all Frankfurt-local (recurring office days, a doctor appointment, one regional leisure trip to Heidelberg by D-Ticket). No `long_distance_rail_likely` signals.
- **current_subscriptions.json** — Standard Maja stack: BC50 + D-Ticket + MILES+ Abo. Each entry carries `billing_cycle` (`"annual"` / `"monthly"`) and `next_renewal_date` (BC50: `2027-01-15`; D-Ticket and MILES+: `2026-07-01`).
- **user_preferences.json** — Cost is top priority (`monthly_budget_eur: 80`, `values_time_over_money: false`), low flexibility need, sustainability secondary.
- **mobility_catalog.json** — Full catalog including BC25 as the cheaper alternative. Each option carries `billing_cycle`.

---

## Expected Agent Behaviour

| Agent | Expected Action |
|---|---|
| **Analyst** | Flags BC50 breakeven miss: actual savings (€36) << card cost (€244). Notes no long-distance demand signal in calendar. |
| **Optimizer** | Models three options: (a) cancel BC50 entirely — saves €244/year; (b) downgrade to BC25 — saves €133/year but still doesn't break even; (c) keep BC50 — loses €208/year. Recommends option (a). |
| **Communicator** | Drafts recommendation: cancel BC50 before `next_renewal_date` (`2027-01-15`); retain D-Ticket and MILES+ Abo. Includes estimated annual saving and the deadline. |

---

## What a Passing Run Looks Like

- Final output explicitly states BC50 should be cancelled or downgraded
- Includes a savings estimate (e.g., "saving ~€208/year")
- Includes the cancellation deadline: "Cancel before **15 January 2027** to avoid auto-renewal"
- Notes that D-Ticket fully covers observed local and regional travel
- No uncertainty flags — the signal is unambiguous

## What a Failing Run Looks Like

- Agent hedges or recommends keeping BC50
- Agent omits the breakeven calculation
- Agent treats the three rail trips as evidence of rail usage without checking the cost threshold
