# Scenario 06 — Under-Subscribed: Add the Membership That Pays for Itself

## Summary

Sofia Ricci gets around Berlin on her Deutschland-Ticket plus **frequent MILES car-share** —
but she books MILES **pay-per-use** (the free MILES Basis tier) and holds no paid membership.
Her usage is regular: about **one ride a month, always €10+**. At that cadence the **MILES
Silber Pass** effectively pays for itself — its **€10/month credit offsets the €9.99/month
fee** — and its 10% km discount saves ~€20/year on top. The correct outcome is a
**recommendation to add / upgrade to MILES Silber**, while keeping the Deutschland-Ticket.

This is the **"under-subscribed → add a product"** case (all other scenarios cancel, downgrade,
hedge, or hold). It also exercises the Optimizer picking the **right tier** rather than the
biggest one.

---

## Numeric Rationale

| Metric | Value |
|---|---|
| MILES rides in last 12 months | 14 (~1/month) |
| Total MILES spend (pay-per-use) | ≈ €200/year |
| Every month with a ride ≥ €10 | Yes (credit fully usable) |
| MILES Silber fee | €9.99/mo → €120/year |
| MILES Silber monthly credit | €10/mo → €120/year (offsets the fee at her usage) |
| Silber km discount (10%) + time (5%) | ≈ €20/year saved |
| **Net effect of adding Silber** | **membership ≈ free + ~€20/year saving** |
| Why not Gold/Platin (€50+/mo) | Most of the €50 credit would go unused at ~€200/yr spend |
| Why not stay on Basis | Full km-tariff every ride, no credit, no discount |

The 2 long-distance rail legs (Berlin↔Hamburg, ~€75 full price, no BahnCard) are far too few
to justify a BahnCard (BC25 break-even ≈ €444 full-price spend) — so the rail side needs no
change; the opportunity is purely the car-share membership.

---

## Data Properties

- **persona.json** — priorities cost 0.40 / time 0.30 / sustainability 0.30. Notes: uses MILES
  pay-as-you-go, no membership.
- **current_subscriptions.json** — Deutschland-Ticket + **MILES Basis (Pay-per-use, €0/mo)**.
  The car-share mode is present in the stack, so the recommendation is a Basis→Silber upgrade.
- **travel_history_raw.json** — 14 MILES car-share rides across Berlin (~€200, roughly monthly,
  each ≥ €10), 3 local rail legs at €0 (Deutschland-Ticket), and 1 Berlin↔Hamburg long-distance
  round trip at full price (no BahnCard).
- **calendar_events_live.json** — ongoing local Berlin activity + a `car_share_likely` errand +
  one long-distance rail weekend. No life-event signals.
- **life_events.json** — empty (deferral gate stays `exists=False`).
- **mail_raw.json** — sparse (5 mails): two MILES receipts (one nudges the Silber pass), a
  D-Ticket activation, a DB booking, and one newsletter noise mail. No future-shift mail.

---

## Expected Agent Behaviour

| Agent | Expected Action |
|---|---|
| **Analyst** | Reports MILES Basis usage: 14 rides, ~€200 spend, all pay-per-use; Deutschland-Ticket covers local rail; 2 long-distance rail legs at full price. No private car. |
| **Forecaster** | Continued local Berlin demand, occasional car-share errands, an occasional long-distance rail trip. **No life-event signals detected.** |
| **Optimizer** | Identifies the under-subscription: at ~monthly ≥€10 usage, **MILES Silber** is effectively free (credit ≈ fee) and adds a 10% km discount → recommend **upgrade MILES Basis → MILES Silber Pass**. Must pick **Silber**, explicitly rejecting Gold/Platin as over-tiered for her volume. Must **not** recommend a BahnCard (too few long-distance trips) or touch the Deutschland-Ticket. |
| **Communicator** | Presents the Silber upgrade as recommended, explaining the credit-offsets-fee logic, and keeps the Deutschland-Ticket. |

**Expected recommendation:** Add / upgrade to the **MILES Silber Pass** (replace MILES Basis),
keep the Deutschland-Ticket.

---

## What a Passing Run Looks Like

- The Optimizer recommends **adding/upgrading to MILES Silber**, explaining the €10/month credit
  offsets the €9.99 fee at her usage and the 10% km discount nets ~€20/year.
- It explicitly picks **Silber over Gold/Platin**, noting the higher tiers' credit would go
  unused at her spend level.
- It leaves the **Deutschland-Ticket** in place and does **not** propose a BahnCard.

## What a Failing Run Looks Like

- Recommends only cancellations/downgrades and misses the under-subscription entirely (the
  point of this persona is an **add**).
- Recommends **MILES Gold/Platin/Black**, over-tiering her modest ~€200/year usage.
- Proposes a BahnCard off the strength of a single long-distance round trip.
- Suggests dropping the Deutschland-Ticket (it covers her local rail; car-share does not).
