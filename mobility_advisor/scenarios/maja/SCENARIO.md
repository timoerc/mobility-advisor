# Scenario 01 — Happy Path: Clear Over-Subscription

**Persona:** Maja Hoffmann — Köln consultant, BahnCard 50 + Enterprise Silver.
**Tests:** Basic over-subscription detection — the simple, unambiguous case.
**Expected result:** Recommend cancelling/downgrading BahnCard 50, no hedging.

## Summary

Maja holds BahnCard 50 but her rail usage doesn't come close to justifying its price. Five DB-provider rail trips (six rail-mode entries total, one a FlixTrain leg with unrecorded cost) produce a total discounted DB spend of €111.70 — a fraction of the €244/year card cost. These are genuinely long-distance Intercity trips (Köln↔Ulm 451 km, Köln↔Freiburg 429 km) — the issue is low *frequency*, not short distance. All observed tickets are Sparpreis fares (`ticket_type` contains "Sparpreis"), so BC50's applicable discount is its **25% Sparpreis rate**, not its 50% Flexpreis rate — on this usage pattern BC50 and BC25 unlock exactly the same discount, so BC50's extra fee buys nothing and BC25 always dominates it. The expected agent outcome is an unambiguous recommendation to downgrade to BC25 (or cancel outright), never to keep BC50.

---

## Numeric Rationale

All figures use BC50/BC25's **25% Sparpreis** discount rate — the rate that actually applies, since every observed trip is Sparpreis. Two figures matter, and they answer different questions:

**Why BC50 specifically is dominated (uses only the 5 raw historical DB trips):**

| Metric | Value |
|---|---|
| BC50 annual card cost | €244 (€20.33 × 12) |
| BC25 annual card cost | €62.88 (€5.24 × 12) |
| Actual discounted DB spend (5 DB trips) | €111.70 |
| Implied full-price equivalent | €111.70 ÷ 0.75 = €148.93 |
| Discount value realized (identical for both cards — both give 25% on Sparpreis) | €148.93 × 0.25 = €37.23 |
| Net loss from holding BC50 vs. no card | €37.23 − €244 = **−€206.77/year** |
| Net loss from holding BC25 vs. no card | €37.23 − €62.88 = **−€25.65/year** |

BC50 loses €181/year (its fee delta) more than BC25 for identical benefit — it is dominated regardless of any other assumption.

**Full-portfolio result (the deterministic optimizer's actual output — projects ALL of Maja's recurring routes forward 12 months, including her synthetic home-city commute demand, not just the 5 raw DB trips, so total rail volume is higher than the table above):**

| Portfolio | Annual cost |
|---|---|
| BahnCard 25 — **recommended** | €1,384.61 |
| BahnCard 50 (status quo) | €1,565.69 (+€181.08 vs. BC25) |
| No subscriptions | €1,633.22 (+€248.61 vs. BC25) |

On the forward-projected trip set, BC25 clearly earns back its fee: its break-even table entry
shows €311.49 of discount value against a €62.88 fee (net **+€248.61/year**), and BC25 beats
both "no subscriptions" and BC50 outright on the full portfolio ranking — this is not a close
call. BC50 remains unambiguously the worst option by a wide margin. Downgrading to BC25 is the
clear top recommendation; full cancellation is a distant, dominated second (it forgoes BC25's
real positive net value); **keeping BC50 is not competitive at all**.

---

## Data Properties

- **travel_history_raw.json** — a handful of genuinely long-distance DB Intercity trips (Köln↔Ulm, Köln↔Freiburg, Köln↔Karlsruhe) plus local MILES car-share and one car rental. Low frequency, not short distance, is what sinks BC50's case against BC25.
- **calendar_events_live.json** — recurring Köln-local events (office days, a doctor appointment, a team lunch — all `local_transit_regular`, all in Köln to match `persona.json`'s `home_city`) plus one regional leisure trip to Heidelberg. No `long_distance_rail_likely` signals — there is no forward-looking long-distance demand beyond what history already projects.
- **current_subscriptions.json** — Maja holds only BahnCard 50 (2. Klasse, Standard, Jahresabo) and the free Enterprise Silver loyalty tier. No Deutschlandticket, no MILES subscription. Each entry carries `billing_cycle` (`"annual"` / `"monthly"`) and `next_renewal_date`.
- **persona.json** — Cost is top priority (0.54), low flexibility need, sustainability secondary (0.30). (Car-usage data lives separately in `car_usage.json`; she does not own a car.)
- **mobility_advisor/static/mobility_catalog.json** — Full catalog (shared across all personas) including BC25 as the cheaper alternative. Each option carries `billing_cycle`.

---

## Expected Agent Behaviour

| Agent | Expected Action |
|---|---|
| **Analyst** | Flags that BC50's discount value on the 5 raw DB trips (€37.23) is far below its card cost (€244), and that BC50 and BC25 unlock the identical discount on Sparpreis fares. Notes no long-distance demand signal in calendar beyond what history projects. |
| **Optimizer** | Ranks BahnCard 25 above both "no subscriptions" and BahnCard 50; BahnCard 50 is the clear loser regardless of ranking method. Recommends BC25. |
| **Communicator** | Drafts recommendation: downgrade to BC25 before `next_renewal_date` (`2026-12-31`). States why BC50 specifically is dominated (same discount, higher fee) and the annual saving vs. keeping the card (~€181/year). |

---

## What a Passing Run Looks Like

- Final output recommends downgrading to BC25 (the numerically best option, and the deterministic optimizer's actual pick) — recommending full cancellation instead is a lesser pass, since it beats BC50 but is still ~€249/year worse than BC25 on the current fixture
- Includes a savings estimate vs. keeping BC50 (~€181/year for BC25)
- Includes the cancellation/downgrade deadline: "Act before **31 December 2026** to avoid auto-renewal"
- States why BC50 specifically loses to BC25 (same 25% Sparpreis discount, higher fee)
- No uncertainty flags — the signal is unambiguous

## What a Failing Run Looks Like

- Agent recommends keeping BC50
- Agent omits the discount-value-vs-card-cost comparison
- Agent treats the five rail trips as evidence of rail usage without checking the cost threshold
- Agent invents forward-looking demand (e.g. a recurring commute) not supported by either travel history or the calendar's `long_distance_rail_likely` signals
