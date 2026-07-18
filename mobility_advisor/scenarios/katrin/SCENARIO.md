# Scenario 04 — Preference-Decisive: Break-Even Travel, Preference Breaks the Tie

**Persona:** Katrin Berger — Düsseldorf, BahnCard 25 + Deutschland-Ticket.
**Tests:** Preference-weighting — cost math is a near-wash, so priorities must decide.
**Expected result:** Recommend upgrading BC25 → BC50, driven by her time/flexibility weight, not cost.

## Summary

Katrin Berger holds a **BahnCard 25** and a Deutschland-Ticket. Her long-distance rail
usage lands **almost exactly on the BahnCard 25 ↔ BahnCard 50 crossover** — on cost alone
the two cards are within ~€1–2/year of each other, so the travel data by itself does **not**
pick a winner. What decides it is her **preference profile**: time is her highest-weighted
priority (0.50) and `values_time_over_money` is true. Because all her fares are flexible,
last-minute *Flexpreis* tickets — which BahnCard 50 discounts at 50% vs. BahnCard 25's 25% —
the tie breaks toward **upgrading to BahnCard 50**.

This is the persona that isolates the **preference-weighting** step of the Optimizer: hold the
cost math at a dead heat and let the priority weights be the deciding variable.

---

## Numeric Rationale

All rail trips in history are treated by the Optimizer as priced at the BahnCard 50 discount,
so `full_price = cost_eur × 2`.

| Metric | Value |
|---|---|
| Sum of long-distance rail `cost_eur` (10 legs) | €268 |
| Implied full-price equivalent (×2) | **€536/year** |
| BahnCard 25 ↔ 50 crossover (full-price) | €532 |
| Net value of BahnCard 50 at this spend | €536 × 0.50 − €244 = **+€24/yr** |
| Net value of BahnCard 25 at this spend | €536 × 0.25 − €111 = **+€23/yr** |
| Cost delta between the two cards | **≈ €1/year — a wash** |

The two cards are financially indistinguishable at her usage. The **only** differentiator is
fare flexibility: her tickets are Flexpreis (freely rebookable), and BahnCard 50 halves those
(50%) while BahnCard 25 only takes 25% off. The extra €133/year card fee is almost entirely
recovered by the deeper flex-fare discount, so the upgrade is roughly cost-neutral **and**
buys back travel-time protection when plans change.

---

## Data Properties

- **persona.json** — priorities cost 0.30 / **time 0.50 (dominant)** / sustainability 0.20;
  `values_time_over_money` true. Notes flag last-minute booking + frequent rescheduling.
- **current_subscriptions.json** — BahnCard 25 (Standard) + Deutschland-Ticket. BC25 renews
  `2026-11-30`.
- **travel_history_raw.json** — 10 long-distance Intercity legs (5 round trips: Düsseldorf ↔
  Berlin / München / Hamburg / Frankfurt / Stuttgart), all **Flexpreis**, summing to €268 in
  `cost_eur` (→ €536 full-price equivalent, right on the crossover). Plus 3 short regional
  legs at €0 (covered by the Deutschland-Ticket) that justify keeping the D-Ticket.
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
| **Analyst** | Reports BahnCard 25 usage: ~€268 discounted long-distance spend, 10 long-distance legs, all Flexpreis; regional legs covered by the D-Ticket. States renewal `2026-11-30`. |
| **Forecaster** | Continued long-distance demand on the Düsseldorf corridors; flags several trips as date-uncertain. **No life-event signals detected.** |
| **Optimizer** | Runs the BahnCard ROI check → BC25 and BC50 net values within ~€1/yr (a wash). Applies **PREFERENCE WEIGHTING**: with time = 0.50 dominant and `values_time_over_money` true, and fares being flexible Flexpreis (50% vs 25%), recommends **upgrade to BahnCard 50 (2. Klasse, Standard, Jahresabo)**. Must state explicitly that the **time/flexibility weight** — not cost — drove the pick. |
| **Communicator** | Presents the upgrade as recommended and a "keep BahnCard 25" option, making clear cost is a tie and flexibility is the tiebreaker. Action-by date `30 November 2026`. |

**Expected recommendation:** Upgrade **BahnCard 25 → BahnCard 50 (2. Klasse, Standard,
Jahresabo)**, driven by the time/flexibility preference over a cost near-tie.

---

## What a Passing Run Looks Like

- The Optimizer computes BC25 and BC50 net values and shows they are within ~€1–2/year.
- It recommends the **BahnCard 50** upgrade and names the **time / flexibility preference
  weight** as the deciding factor — not a cost saving.
- It notes the counterfactual: a **cost-first** traveller with the same trips would keep
  BahnCard 25 (or only upgrade if they book flexible fares).
- The Deutschland-Ticket is retained (covers the regional legs).

## What a Failing Run Looks Like

- Recommends a card purely on the ~€1 cost edge without invoking the preference weights (the
  point of this persona is that cost does **not** decide it).
- Claims a large euro saving in either direction (there isn't one — it's a wash).
- Ignores that the fares are Flexpreis and treats BC25 vs BC50 as identical on flexibility.
- Fires a "hold pending decision" candidate (there is no portfolio-reset life event).
