# Scenario 05 — Forward-Looking: A Mail Overturns What History Says

> **Note:** written against the earlier LLM-driven optimizer, where the forecast's
> mail-derived signal overrode history purely through prompt reasoning. The regular
> pipeline now scores portfolios deterministically instead — this scenario's mechanism
> is re-implemented as trip-frequency damping on the life event's `travel_reduction`
> signal (pro-rated by days remaining before the event; see `_travel_reduction_factor`
> in `tools.py`), applied to the *projected* frequency before scoring, not a
> forecast-vs-history argument the LLM has to win. Not yet re-verified end-to-end
> against a live pipeline run — see `scenarios/README.md`.

**Persona:** Tobias Wolf — Frankfurt, BahnCard 50 + Deutschland-Ticket, weekly Frankfurt–Munich commuter.
**Tests:** Whether a forward signal (staffing email) overrides a strong historical ROI.
**Expected result:** Recommend downgrading/cancelling BahnCard 50 ahead of renewal, despite history alone saying "keep."

## Summary

Tobias Wolf holds a **BahnCard 50** that his past 12 months of travel clearly justify —
weekly Frankfurt–Munich trips for a client project push his discounted DB spend well above
break-even. On history alone, the answer is "keep the card." But a **staffing email**
(12 June 2026) reveals a **future travel shift**: the Munich project ends 31 August, and his
next engagement is a *local Frankfurt* project with no regular long-distance travel. The
correct outcome is therefore **not** what the history says in isolation — it is to
**downgrade (or cancel) BahnCard 50 ahead of the January renewal**, because the card that paid
off this year will sit idle next year.

This persona isolates the **Forecaster / forward-demand** step: the decisive signal lives in
the mail and life-event data, not in the trip history.

---

## Numeric Rationale

All rail trips in history are treated by the Optimizer as priced at the BahnCard 50 discount,
so `full_price = cost_eur × 2`.

| Metric | Value |
|---|---|
| Long-distance rail `cost_eur` (14 legs, FRA↔MUC) | €409 |
| Implied full-price equivalent (×2) | **€818/year** |
| BahnCard 50 break-even (full-price) | €488 |
| Net benefit of BahnCard 50 **this year** | €818 × 0.50 − €244 = **+€165/yr** |
| Forecast long-distance travel **from September** | ≈ 0 (project ends; local staffing) |
| Saving from downgrading BC50 → BC25 | €244 − €111 = **€133/yr** |
| Saving from cancelling BC50 outright | **€244/yr** |

History → keep. Forecast → the card stops paying. The recommendation must be driven by the
**forward** picture, dated against the **10 January 2027** renewal.

---

## Data Properties

- **persona.json** — priorities cost 0.45 / time 0.35 / sustainability 0.20 (cost-leaning).
  Notes flag the Munich project ending and the likely local re-staffing.
- **current_subscriptions.json** — BahnCard 50 (Standard) + Deutschland-Ticket. BC50 renews
  `2027-01-10`.
- **travel_history_raw.json** — 14 long-distance Frankfurt↔Munich legs (7 project round trips,
  Sep 2025 – May 2026) summing to €409 in `cost_eur` (→ €818 full-price, well above
  break-even), plus 2 short regional legs at €0 covered by the D-Ticket.
- **mail_raw.json** — sparse, but **`mail_005` is the important one**: a staffing email
  stating the Munich (Helios) project ends 31 Aug 2026 and the next engagement is local
  Frankfurt work with no regular long-distance travel. The rest are booking confirmations and
  low-signal noise.
- **life_events.json** — one distilled event (`source_mail_id: mail_005`), category `other`,
  signals `travel_reduction` + `rail_card_relevance_change`. **Deliberately NOT**
  `home_base_change` / `work_pattern_change`, so `detect_pending_portfolio_decision` stays
  `exists=False` — this is a demand change to act on now, **not** a portfolio-reset to hold for
  (contrast Stefan's relocation hold).
- **calendar_events_live.json** — Munich project weeks through late August (winding down),
  then **local Frankfurt** events from 2 September onward — the calendar mirrors the collapse.

---

## Expected Agent Behaviour

| Agent | Expected Action |
|---|---|
| **Analyst** | Reports BahnCard 50 as clearly worthwhile on history: ~€409 discounted long-distance spend, 14 long-distance legs, ~€165/yr net benefit. Regional legs covered by D-Ticket. Renewal `2027-01-10`. |
| **Forecaster** | Surfaces the life-event signal: Munich project ends 31 Aug, local Frankfurt staffing from September → long-distance rail demand drops to near zero. Must state the concrete portfolio implication. |
| **Optimizer** | Weighs the collapsing forward demand against the strong history and recommends **downgrading BahnCard 50 → BahnCard 25** (hedge) — or **cancelling** it — before the 10 Jan 2027 renewal. Must **not** fire a "hold pending decision" candidate (no portfolio-reset signal). |
| **Communicator** | Presents the downgrade as recommended (with cancel as the more aggressive option and keep as the do-nothing), dated to the January renewal, explaining that the card paid off this year but won't next year. |

**Expected recommendation(s):** Downgrade **BahnCard 50 → BahnCard 25** *or* cancel BahnCard 50
before `2027-01-10`, driven by the forecast travel drop. Either is a pass.

---

## What a Passing Run Looks Like

- The Forecaster explicitly picks up the staffing / project-end signal and states long-distance
  demand collapses from September.
- The Optimizer recommends **downgrading or cancelling BahnCard 50**, citing the **forward**
  demand drop — not the (positive) historical ROI — as the reason.
- Action is tied to the **10 January 2027** renewal deadline.
- The Deutschland-Ticket is retained (still covers local Frankfurt travel).

## What a Failing Run Looks Like

- Recommends **keeping BahnCard 50** on the strength of past usage alone, ignoring the mail /
  forecast (the core failure this persona is designed to catch).
- Treats the project-end signal as a portfolio-reset and fires a "hold / wait-and-see"
  recommendation instead of acting before the renewal.
- Invents a relocation or claims the Deutschland-Ticket should also go (only long-distance
  demand drops; local travel continues).
