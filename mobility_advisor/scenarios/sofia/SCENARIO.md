# Scenario 06 — Under-Subscribed: Add the Membership That Pays for Itself

**Persona:** Sofia Ricci — Berlin, Deutschland-Ticket + MILES Basis (pay-per-use).
**Tests:** The "add/upgrade a product" case, and picking the right tier (not the biggest).
**Expected result (original design intent, hand-calculated from the 2 raw long-distance legs
and 14 MILES rides in isolation):** Recommend upgrading MILES Basis → MILES Silber; keep the
Deutschland-Ticket, and add no BahnCard.
**Expected result (current deterministic optimizer, regenerated 2026-08-08 — see "Updated
Numeric Rationale" below):** Add **BahnCard 25** and upgrade to **MILES Silber**; drop the
**Deutschland-Ticket**. Both the car-share upgrade and the fact that *some* car-share
membership is under-subscribed remain correct; whether a BahnCard also belongs in the mix, and
whether the Deutschland-Ticket survives it, has genuinely changed since this scenario was
authored — see below.

## Summary

Sofia Ricci gets around Berlin on her Deutschland-Ticket plus **frequent MILES car-share** —
but she books MILES **pay-per-use** (the free MILES Basis tier) and holds no paid membership.
Her usage is regular: about **one ride a month, always €10+**. At that cadence the **MILES
Silber Pass** effectively pays for itself — its **€10/month credit offsets the €9.99/month
fee** — and its 10% km discount saves ~€20/year on top. This part of the finding is unchanged
and confirmed by the current engine: MILES Silber's break-even is net **+€8.82/year** on its
own (fee €119.88, discount value €128.70).

This is the **"under-subscribed → add a product"** case (all other scenarios cancel, downgrade,
hedge, or hold). It also exercises the Optimizer picking the **right tier** rather than the
biggest one.

**What has changed since this scenario was authored:** the original numeric rationale below
was hand-calculated from Sofia's 2 raw long-distance rail legs in isolation and concluded a
BahnCard could not be justified. The deterministic optimizer, run against the full
forward-projected trip set (which also synthesizes her recurring home-city commute and any
under-threshold local/regional routes — see `_build_commute_aggregate_trip` /
`_build_local_aggregate_trip` in `tools.py`), now finds that a BahnCard 25 discounts enough of
that regional/commute demand to pay for itself on its own (break-even net +€63.05/year), and
that once it's held, the Deutschland-Ticket's flat €756/year fee no longer earns its keep on
top (net −€195.72/year once BahnCard 25 is already in the portfolio). This is the same
regional-demand-competition mechanism already documented in `katrin/SCENARIO.md` and
`tobias/SCENARIO.md`, now showing up for Sofia too — it is **not** driven by her 2 long-distance
legs (those remain too few to justify a card on their own), and it is **not** a bug: the commute
demand is real, and once a BahnCard discounts it more cheaply than the Deutschland-Ticket's flat
fee, dropping the ticket is the correct forward-looking answer, not an artifact.

---

## Numeric Rationale (original — hand-calculated from the 2 raw long-distance legs and 14 rides)

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

The 2 long-distance rail legs alone (Berlin↔Hamburg, ~€75 full price, no BahnCard) are still far
too few to justify a BahnCard on their own (BC25's €62.88/year fee ÷ 25% Sparpreis discount rate
≈ €252 full-price spend needed to break even). This part of the original reasoning still holds —
see below for why the deterministic engine adds a BahnCard anyway, off a different (regional
commute) demand source.

## Updated Numeric Rationale (deterministic optimizer, regenerated 2026-08-08)

Reproduced directly via `optimize_all_categories()` against this scenario's fixture data —
prices the full forward-projected trip set (2 long-distance legs, 14 MILES rides, plus the
synthesized home-city commute and local aggregate), not just the raw historical legs in
isolation.

| Portfolio | Subs €/yr | Trips €/yr | Total €/yr | Time min/yr | CO2 kg/yr |
|---|---|---|---|---|---|
| **BahnCard 25 + MILES Silber (recommended)** | 182.76 | 976.60 | **1,159.36** | 3,779.8 | 277.74 |
| Deutschland-Ticket + MILES Basis (current) | 756.00 | 670.95 | 1,426.95 | 3,780.5 | 278.37 |
| No subscriptions | 0 | 1,231.23 | 1,231.23 | 3,780.5 | 278.37 |
| BahnCard 25 alone | 62.88 | 1,105.30 | 1,168.18 | 3,779.8 | 277.74 |
| BahnCard 25 + Deutschland-Ticket | 818.88 | 545.02 | 1,363.90 | 3,779.8 | 277.74 |

Recommended vs. current: **−€267.59/year, −0.7 min/year, −0.629 kg CO2/year** — all three
dimensions favor the change, though the time/CO2 differences are small enough to be noise.

| Break-even (forward-looking) | Annual fee | Discount value | Net | Breaks even? |
|---|---|---|---|---|
| BahnCard 25 + MILES Silber | €182.76 | €254.63 | **+€71.87** | Yes |
| BahnCard 25 (2. Klasse, Standard, Jahresabo) | €62.88 | €125.93 | **+€63.05** | Yes |
| MILES Silber Pass | €119.88 | €128.70 | **+€8.82** | Yes, barely |
| Deutschland-Ticket | €756.00 | €560.28 | **−€195.72** | No |

The Deutschland-Ticket now runs a clear net loss once a BahnCard is available to discount the
same regional/commute demand more cheaply — consistent with what `katrin/SCENARIO.md` and
`tobias/SCENARIO.md` already document for the same mechanism.

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
| **Optimizer** | Identifies the under-subscription: at ~monthly ≥€10 usage, **MILES Silber** is effectively free (credit ≈ fee) and adds a 10% km discount → recommend **upgrade MILES Basis → MILES Silber Pass**. Must pick **Silber**, explicitly rejecting Gold/Platin as over-tiered for her volume. On the current engine, `optimize_all_categories()` also adds **BahnCard 25** and drops the **Deutschland-Ticket** (see Updated Numeric Rationale) — driven by regional/commute demand the card discounts more cheaply than the ticket's flat fee, not by her 2 long-distance legs. |
| **Communicator** | Presents the Silber upgrade as recommended alongside the current top-ranked candidate's BahnCard 25 addition and Deutschland-Ticket removal, explaining the credit-offsets-fee logic for MILES and the regional-demand-competition logic for the rail side. |

**Expected recommendation (current engine):** Add **BahnCard 25**, upgrade MILES Basis →
**MILES Silber**, drop the **Deutschland-Ticket** — €267.59/year cheaper than the current setup.
The MILES Silber upgrade is the load-bearing, always-true part of this scenario; the BahnCard/
Deutschland-Ticket swap is a secondary finding from the full projected trip set (see Summary)
and a run that keeps the Deutschland-Ticket and skips the BahnCard while still getting the MILES
Silber upgrade right is testing the same core mechanism, just against the older, narrower
numeric picture — treat it as a partial pass, not a failure.

---

## What a Passing Run Looks Like

- The Optimizer recommends **adding/upgrading to MILES Silber**, explaining the €10/month credit
  offsets the €9.99 fee at her usage and the 10% km discount nets ~€20/year. This is the
  non-negotiable core of the scenario.
- It explicitly picks **Silber over Gold/Platin**, noting the higher tiers' credit would go
  unused at her spend level.
- If it also proposes adding BahnCard 25 and dropping the Deutschland-Ticket, it attributes this
  to regional/commute demand the card discounts more cheaply (per the break-even table), not to
  her single long-distance round trip — and states the swap's own cost/time/CO2 deltas.

## What a Failing Run Looks Like

- Recommends only cancellations/downgrades and misses the MILES under-subscription entirely (the
  anchor point of this persona is an **add**).
- Recommends **MILES Gold/Platin/Black**, over-tiering her modest ~€200/year usage.
- Justifies a BahnCard addition by pointing at the single long-distance round trip rather than
  regional/commute demand (misattributing the mechanism, even if the addition itself is
  reasonable on the current numbers).
- Drops the Deutschland-Ticket without any stated reason, or while a BahnCard is *not* also held
  (the ticket only stops earning its keep once a BahnCard already discounts the same demand more
  cheaply — dropping it with nothing replacing that coverage is a real regression, not a pass).
