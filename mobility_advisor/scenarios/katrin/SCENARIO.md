# Scenario 04 — Neither Card Breaks Even: Cancel Both Rail Subscriptions

**Persona:** Katrin Berger — Düsseldorf, BahnCard 25 + Deutschland-Ticket.
**Tests:** Break-even math against real trip volume, and that the generalized-cost model
(cost + time + CO2, weighted by the persona's own priorities) can outrank a subscription on
cost and time even when it's the only dimension that comes out worse.
**Expected result:** Recommend cancelling both the BahnCard 25 and the Deutschland-Ticket —
neither pays for itself at her current travel volume.

## Summary

Katrin Berger holds a **BahnCard 25** and a **Deutschland-Ticket**. Run against the
deterministic optimizer, neither breaks even: the BahnCard 25's Flexpreis/Sparpreis discount
is worth **€54.49/year** against a **€111/year** fee (net **−€56.51**), and the
Deutschland-Ticket's regional coverage is worth **€0** against its **€756/year** fee (its 3
regional legs in the trip history were already free-adjacent local hops, not journeys that
would otherwise cost real money). A BahnCard 50 fares worse still — €118.26/year of discount
value against a €243.96/year fee (net **−€125.70**).

Cancelling both drops annual cost from **€1,099.95 to €287.44** (**−€812.51/year**). The
generalized-cost model — which reallocates trip mode-share by the persona's own cost/time/CO2
weights when a subscription's discount disappears — also comes out **17.7 minutes/year
faster** (rail becomes relatively less price-competitive without a card, so a sliver of trip
share shifts to a quicker alternative on a few routes), at a cost of **+15.1 kg CO2/year**.
With her priorities weighted cost 0.3 / time 0.5 / sustainability 0.2, the two
highest-weighted dimensions (time, then cost) both favor cancelling, and sustainability — her
lowest-weighted dimension — is the only one that argues to keep a subscription. That's not
enough to flip the recommendation.

This supersedes the scenario's original design, which targeted the **earlier, LLM-driven**
optimizer's prompt-embedded PREFERENCE WEIGHTING reasoning: with that optimizer, Katrin's
BC25/BC50 cost math landed almost exactly on the crossover point (a ~€1/year wash), so her
time-dominant priority profile was needed to break the tie toward upgrading to BahnCard 50.
The current deterministic pipeline scores portfolios (and BahnCard ROI) differently enough
that the €1/year wash no longer occurs — both cards are unambiguously net losses at her usage,
so cost alone already picks a winner before preference-weighting has anything to break a tie
over. The per-route fare-class detection this scenario originally exercised
(`_dominant_fare_class`/`apply_subscription_discount` in `tools.py`, Flexpreis discounted at
BC50's 50% vs. BC25's 25%) is still live and still shapes the break-even numbers above — it's
just no longer close enough to be the deciding factor.

---

## Numeric Rationale

Reproduced directly via `optimize_all_categories()` against this scenario's fixture data.

| Portfolio | Subs €/yr | Trips €/yr | Total €/yr | Time min/yr | CO2 kg/yr |
|---|---|---|---|---|---|
| **No subscriptions (recommended)** | 0 | 287.44 | **287.44** | 1,259.1 | 229.347 |
| BahnCard 25 + Deutschland-Ticket (current) | 867.00 | 232.95 | 1,099.95 | 1,276.8 | 214.21 |
| Deutschland-Ticket only | 756.00 | 287.44 | 1,043.44 | 1,259.1 | 229.347 |
| BahnCard 25 + MILES Basis | 111.00 | 232.95 | 343.95 | 1,276.8 | 214.21 |
| MILES Silber Pass | 119.88 | 287.44 | 407.32 | 1,259.1 | 229.347 |

Recommended vs. current: **−€812.51/year, −17.7 min/year (faster), +15.1 kg CO2/year
(dirtier)**.

| Break-even (single subscription, forward-looking) | Annual fee | Discount value | Net | Breaks even? |
|---|---|---|---|---|
| Deutschland-Ticket | €756.00 | €0.00 | **−€756.00** | No |
| BahnCard 25 (2. Klasse, Standard, Jahresabo) | €111.00 | €54.49 | **−€56.51** | No |
| BahnCard 50 (2. Klasse, Standard, Jahresabo) | €243.96 | €118.26 | **−€125.70** | No |

---

## Data Properties

- **persona.json** — priorities cost 0.30 / **time 0.50 (dominant)** / sustainability 0.20;
  `values_time_over_money` true. Notes flag last-minute booking + frequent rescheduling.
- **current_subscriptions.json** — BahnCard 25 (Standard) + Deutschland-Ticket. BC25 renews
  `2026-11-30`, Deutschland-Ticket `2026-07-01`.
- **travel_history_raw.json** — 10 long-distance Intercity legs (5 round trips: Düsseldorf ↔
  Berlin / München / Hamburg / Frankfurt / Stuttgart), all **Flexpreis**, summing to €268 in
  `cost_eur` (BC25-discounted). Plus 3 short regional legs at €0 (covered by the
  Deutschland-Ticket) — too few and too low-value to justify the ticket's €756/year fee on
  their own.
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
| **Analyst** | Reports BahnCard 25 usage: ~€268 discounted long-distance spend, 10 long-distance legs, all Flexpreis; regional legs covered by the D-Ticket. States renewal dates for both subscriptions. |
| **Forecaster** | Continued long-distance demand on the Düsseldorf corridors; flags several trips as date-uncertain. **No life-event signals detected.** |
| **Optimizer** | Calls `optimize_all_categories()`, which ranks "No subscriptions" first. Reports the break-even table showing both BC25 and the Deutschland-Ticket as net losses (BC50 worse still). Outputs both delta families verbatim — vs.-recommended and vs.-current — so the Communicator doesn't have to hand-negate a sign. |
| **Communicator** | Presents cancelling both subscriptions as recommended, "Keep current setup" as an alternative. States all three dimensions using the vs.-current deltas: cheaper (−€813/yr), faster (−18 min/yr), more CO2 (+15 kg/yr) — and names time and cost, not sustainability, as the dimensions that decided it. Action-by dates for both current subscriptions' renewals. |

**Expected recommendation:** Cancel **BahnCard 25** and the **Deutschland-Ticket**, saving
€812.51/year, driven by both subscriptions running a net loss against actual usage — not a
preference-weight tie-break.

---

## What a Passing Run Looks Like

- The Optimizer's break-even table shows both current subscriptions as net losses (negative
  `net_eur`), and BahnCard 50 as an even larger loss.
- It recommends cancelling both, quoting cost, time, AND CO2 for the recommended option —
  not cost alone.
- The CO2 and travel-time direction words match their signs: cost and time both improve
  (cheaper, faster); CO2 gets worse (more) — the report must not describe this backwards
  (e.g. "greener" or "slower") relative to the tiles.
- It notes that sustainability — her lowest-weighted priority — is the one dimension arguing
  to keep a subscription, and that it isn't enough to outweigh the cost + time verdict.

## What a Failing Run Looks Like

- Recommends upgrading to BahnCard 50 (that was the old LLM-optimizer's answer for this
  scenario; the current deterministic pipeline's break-even math no longer supports it).
- States a euro saving without also stating the CO2 and travel-time deltas.
- Describes the CO2 or travel-time change in the wrong direction relative to the numbers
  (e.g. claims cancelling is "greener" when it actually adds +15 kg CO2/year, or "slower"
  when it's actually 18 min/year faster).
- Fires a "hold pending decision" candidate (there is no portfolio-reset life event).
