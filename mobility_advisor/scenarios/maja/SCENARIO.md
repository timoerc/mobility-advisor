# Scenario 01 — Happy Path: Clear Over-Subscription

**Persona:** Maja Hoffmann — Köln consultant, BahnCard 50 + Enterprise Silver.
**Tests:** Basic over-subscription detection — the simple, unambiguous case.
**Expected result:** Recommend cancelling/downgrading BahnCard 50, no hedging.

## Summary

Maja holds BahnCard 50 but rarely uses it enough to justify the card. Five DB-provider rail trips (six rail-mode entries total, one a FlixTrain leg with unrecorded cost) produce a total discounted DB spend of €111.70 — far below what is needed to justify the €244/year card cost. These are genuinely long-distance Intercity trips (Köln↔Ulm 451 km, Köln↔Freiburg 429 km) — the issue is low *frequency*, not short distance. The expected agent outcome is an unambiguous recommendation to cancel BC50 or downgrade to BC25.

---

## Numeric Rationale

| Metric | Value |
|---|---|
| BC50 annual card cost | €244 (€20.33 × 12) |
| Required annual DB spend (full price) to break even | €244 ÷ 0.50 = **€488** |
| Actual discounted DB spend (5 DB trips) | €111.70 |
| Implied full-price equivalent | €223.40 |
| Gap vs. breakeven | **€264.60 short** |
| Savings BC50 produced | €111.70 (equal to discounted spend) |
| Annual net loss from holding BC50 | €244 − €111.70 = **−€132.30** |

Even the cheaper BC25 (€111/year) would not break even at this usage level (breakeven: €111 ÷ 0.25 = €444 annual DB spend, vs. an implied full-price equivalent of only €223.40). The correct recommendation is full cancellation of BC50.

---

## Data Properties

- **travel_history_raw.json** — a handful of genuinely long-distance DB Intercity trips (Köln↔Ulm, Köln↔Freiburg, Köln↔Karlsruhe) plus local MILES car-share and one car rental. Low frequency, not short distance, is what sinks BC50's breakeven case.
- **calendar_events_live.json** — recurring Frankfurt-local events (office days, a doctor appointment, one regional leisure trip to Heidelberg by D-Ticket). No `long_distance_rail_likely` signals.
- **current_subscriptions.json** — Standard Maja stack including BC50 + D-Ticket. Each entry carries `billing_cycle` (`"annual"` / `"monthly"`) and `next_renewal_date`.
- **persona.json** — Cost is top priority, low flexibility need, sustainability secondary. (Car-usage data lives separately in `car_usage.json`.)
- **mobility_advisor/static/mobility_catalog.json** — Full catalog (shared across all personas) including BC25 as the cheaper alternative. Each option carries `billing_cycle`.

---

## Expected Agent Behaviour

| Agent | Expected Action |
|---|---|
| **Analyst** | Flags BC50 breakeven miss: actual savings (€111.70) << card cost (€244). Notes no long-distance demand signal in calendar. |
| **Optimizer** | Models three options: (a) cancel BC50 entirely — saves €244/year; (b) downgrade to BC25 — saves €133/year but still doesn't break even; (c) keep BC50 — loses €132.30/year. Recommends option (a). |
| **Communicator** | Drafts recommendation: cancel BC50 before `next_renewal_date` (`2026-12-31`); retain D-Ticket and MILES+ Abo. Includes estimated annual saving and the deadline. |

---

## What a Passing Run Looks Like

- Final output explicitly states BC50 should be cancelled or downgraded
- Includes a savings estimate (e.g., "saving ~€132/year")
- Includes the cancellation deadline: "Cancel before **31 December 2026** to avoid auto-renewal"
- Notes that D-Ticket fully covers observed local and regional travel
- No uncertainty flags — the signal is unambiguous

## What a Failing Run Looks Like

- Agent hedges or recommends keeping BC50
- Agent omits the breakeven calculation
- Agent treats the three rail trips as evidence of rail usage without checking the cost threshold
