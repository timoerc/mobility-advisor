# Scenario 04 — Fare-Class-Driven Upgrade: BahnCard 50, Drop the Deutschland-Ticket

**Persona:** Katrin Berger — Düsseldorf, BahnCard 25 + Deutschland-Ticket.
**Tests:** Break-even math against real trip volume, and that BahnCard tier selection is
driven by the route's dominant *fare class* (Sparpreis vs. Flexpreis — see
`_dominant_fare_class`/`apply_subscription_discount` in `tools.py`), not by cost alone.
**Expected result:** Upgrade to **BahnCard 50** and cancel the **Deutschland-Ticket** — BC50's
50%-off-Flexpreis rate dominates her Flexpreis-heavy long-distance spend, and once BC50 is
held the Deutschland-Ticket's flat €756/year fee no longer earns back its keep on top of it.

## Summary

Katrin Berger holds a **BahnCard 25** and a **Deutschland-Ticket**. Her 10 long-distance
Intercity legs (5 round trips: Düsseldorf ↔ Berlin / München / Hamburg / Frankfurt / Stuttgart)
are all booked **Flexpreis** — BahnCard 50 discounts Flexpreis by 50% vs. BahnCard 25's 25%,
so the fare-class distinction, not raw cost, decides which card wins here. Run against the
deterministic optimizer, upgrading to **BahnCard 50 alone** (dropping the Deutschland-Ticket)
is the clear winner: **−€237.20/year cheaper, 3.9 min/year faster, and 5.9 kg CO2/year
greener** than her current setup — all three dimensions agree, so no preference-weight
tie-break is needed even though her priorities (cost 0.3 / time 0.5 / sustainability 0.2) are
time-dominant.

The Deutschland-Ticket does technically break even on its own (+€11.65/year against its
€756/year fee, from her 3 regional legs plus a share of local/commute demand) — but stacked on
top of BahnCard 50 it stops paying for itself: BahnCard 50 already discounts most of what the
Deutschland-Ticket would additionally cover, so the combined portfolio (**€1,742.99/year**)
costs **€181.18/year more** than BahnCard 50 alone (**€1,561.81/year**). This is why the
optimizer's break-even table (which prices each candidate against the "no subscriptions"
baseline in isolation) and the full portfolio ranking (which prices every combination against
each other) can disagree on a combo even though neither is wrong — the break-even table answers
"does this pay for itself on its own", the ranking answers "is this combination the cheapest
way to cover the same demand."

This supersedes the scenario's original design, which targeted the **earlier, LLM-driven**
optimizer's prompt-embedded PREFERENCE WEIGHTING reasoning and, in a since-corrected revision,
briefly recommended cancelling both subscriptions outright. That intermediate result was an
artifact of two now-fixed engine bugs, not a real finding about Katrin's usage:
1. The rail-fare calibration ratio (fitted against her real Flexpreis fares) was being applied
   to the synthetic home-city commute leg as well as her real intercity routes — inflating her
   ~8km commute to ~€5.29/leg (vs. an uncalibrated ~€2.03) and swamping the ranking with
   fabricated commute cost that had nothing to do with her actual rail card usage.
2. The commute and other local/regional aggregates were, like every persona's, incorrectly
   damped by unrelated life-event signals in some builds of the engine.
With both fixed, her real signal — 10 Flexpreis-booked long-distance legs — decides the
recommendation cleanly, and BahnCard 50 wins on fare class exactly as this scenario was
originally designed to demonstrate.

---

## Numeric Rationale

Reproduced directly via `optimize_all_categories()` against this scenario's fixture data.

| Portfolio | Subs €/yr | Trips €/yr | Total €/yr | Time min/yr | CO2 kg/yr |
|---|---|---|---|---|---|
| **BahnCard 50 (recommended)** | 243.96 | 1,317.85 | **1,561.81** | 5,265.3 | 770.407 |
| BahnCard 25 + Deutschland-Ticket (current) | 818.88 | 980.13 | 1,799.01 | 5,269.2 | 776.271 |
| BahnCard 50 + Deutschland-Ticket | 999.96 | 743.03 | 1,742.99 | 5,265.3 | 770.407 |
| BahnCard 25 alone | 62.88 | 1,554.95 | 1,617.83 | 5,269.2 | 776.271 |
| No subscriptions | 0 | 1,976.15 | 1,976.15 | 5,340.1 | 801.52 |

Recommended vs. current: **−€237.20/year, −3.9 min/year (faster), −5.864 kg CO2/year
(greener)**. All three dimensions favor the upgrade — there is no trade-off to name.

| Break-even (single subscription, forward-looking) | Annual fee | Discount value | Net | Breaks even? |
|---|---|---|---|---|
| BahnCard 50 (2. Klasse, Standard, Jahresabo) | €243.96 | €658.30 | **+€414.34** | Yes |
| BahnCard 25 (2. Klasse, Standard, Jahresabo) | €62.88 | €421.20 | **+€358.32** | Yes |
| Deutschland-Ticket | €756.00 | €767.65 | **+€11.65** | Yes, barely |

BahnCard 50's discount value (€658.30) is roughly 55% higher than BahnCard 25's (€421.20) on
the *same* trip set — almost exactly the 50%-vs-25% Flexpreis discount ratio the two cards
carry, confirming the fare-class mechanism (not a raw-cost tie-break) is what separates them.

---

## Data Properties

- **persona.json** — priorities cost 0.30 / **time 0.50 (dominant)** / sustainability 0.20;
  `values_time_over_money` true. Notes flag last-minute booking + frequent rescheduling.
- **current_subscriptions.json** — BahnCard 25 (Standard) + Deutschland-Ticket. BC25 renews
  `2026-11-30`, Deutschland-Ticket `2026-07-01`.
- **travel_history_raw.json** — 10 long-distance Intercity legs (5 round trips: Düsseldorf ↔
  Berlin / München / Hamburg / Frankfurt / Stuttgart), all **Flexpreis**, summing to **€968.00**
  in `cost_eur` (already BC25-discounted at 25% off). Plus 3 short regional legs at €0
  (covered by the Deutschland-Ticket).
- **calendar_events_live.json** — continued long-distance client trips (Berlin/München/
  Stuttgart), several explicitly noted as *likely to move* — reinforcing the flexibility need.
  No life-event / portfolio-reset signals.
- **life_events.json** — empty (no relocation or work-pattern change; the deferral gate must
  stay `exists=False`).
- **mail_raw.json** — sparse (5 mails): two DB booking confirmations noting the Flexpreis
  free-rebooking benefit, a D-Ticket activation, and two low-signal noise mails. No
  future-shift mail.

---

## Expected Agent Behaviour

| Agent | Expected Action |
|---|---|
| **Analyst** | Reports BahnCard 25 usage: ~€968 BC25-discounted long-distance spend, 10 long-distance legs, all Flexpreis; regional legs covered by the D-Ticket. States renewal dates for both subscriptions. |
| **Forecaster** | Continued long-distance demand on the Düsseldorf corridors; flags several trips as date-uncertain. **No life-event signals detected.** |
| **Optimizer** | Calls `optimize_all_categories()`, which ranks "BahnCard 50" first. Reports the break-even table showing BahnCard 50's discount value clearly outweighing BahnCard 25's on the same Flexpreis-heavy trip set. Outputs both delta families verbatim — vs.-recommended and vs.-current — so the Communicator doesn't have to hand-negate a sign. |
| **Communicator** | Presents upgrading to BahnCard 50 (and cancelling the Deutschland-Ticket) as recommended, "Keep current setup" as an alternative. States all three dimensions using the vs.-current deltas: cheaper (−€237/yr), faster (−4 min/yr), greener (−6 kg CO2/yr) — no trade-off framing needed since all three agree. Action-by dates for both current subscriptions' renewals. |

**Expected recommendation:** Upgrade to **BahnCard 50** and cancel the **Deutschland-Ticket**,
saving €237.20/year, driven by BahnCard 50's 50%-off-Flexpreis rate against her Flexpreis-heavy
long-distance travel — a fare-class distinction, not a raw cost comparison.

---

## What a Passing Run Looks Like

- The Optimizer's break-even table shows BahnCard 50's discount value clearly ahead of
  BahnCard 25's on the same trip set (roughly the 50%-vs-25% Flexpreis ratio).
- It recommends BahnCard 50 (with the Deutschland-Ticket dropped), quoting cost, time, AND CO2
  for the recommended option — not cost alone.
- The CO2 and travel-time direction words match their signs: all three dimensions improve
  (cheaper, faster, greener) — the report must not describe any of them backwards relative to
  the tiles.
- It attributes the upgrade to fare class (Flexpreis discount rate), not merely "it's cheaper."

## What a Failing Run Looks Like

- Recommends BahnCard 25 (tie-breaking on raw cost without engaging the fare-class mechanism),
  or recommends cancelling both subscriptions outright (the since-corrected intermediate
  result — see Summary above for the two engine bugs that produced it).
- States a euro saving without also stating the CO2 and travel-time deltas.
- Describes the CO2 or travel-time change in the wrong direction relative to the numbers.
- Fires a "hold pending decision" candidate (there is no portfolio-reset life event).
