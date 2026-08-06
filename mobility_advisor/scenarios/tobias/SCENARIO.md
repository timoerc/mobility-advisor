# Scenario 05 — Forward-Looking: A Mail Overturns What History Says

> **Note:** originally written against the earlier LLM-driven optimizer, where the
> forecast's mail-derived signal overrode history purely through prompt reasoning. The
> regular pipeline now scores portfolios deterministically instead — this scenario's
> mechanism is re-implemented as trip-frequency damping on the life event's
> `travel_reduction` signal (pro-rated by days remaining before the event; see
> `_travel_reduction_factor` in `tools.py`), applied to the *projected* frequency
> before scoring, not a forecast-vs-history argument the LLM has to win. The Numeric
> Rationale below has been re-verified directly against `optimize_all_categories()`
> (bypassing the LLM agent layer) and replaces the old `full_price = cost_eur × 2`
> figures, which predated the deterministic optimizer and don't match its actual
> pricing model. It has not been run end-to-end through the coordinator + LLM pipeline.

**Persona:** Tobias Wolf — Frankfurt, BahnCard 50 + Deutschland-Ticket, weekly Frankfurt–Munich commuter.
**Tests:** Whether a forward signal (staffing email) overrides a strong historical ROI.
**Expected result:** Recommend downgrading BahnCard 50 → BahnCard 25 (and dropping the
Deutschland-Ticket) ahead of renewal, despite history alone saying "keep."

## Summary

Tobias Wolf holds a **BahnCard 50** that his past 12 months of travel clearly justify —
weekly Frankfurt–Munich trips for a client project push his discounted DB spend well above
break-even. On history alone, the answer is "keep the card." But a **staffing email**
(12 June 2026) reveals a **future travel shift**: the Munich project ends 31 August, and his
next engagement is a *local Frankfurt* project with no regular long-distance travel. The
correct outcome is therefore **not** what the history says in isolation — it is to
**downgrade BahnCard 50 → BahnCard 25 ahead of the January renewal**, because the card that
paid off this year will sit idle next year.

This persona isolates the **Forecaster / forward-demand** step: the decisive signal lives in
the mail and life-event data, not in the trip history.

---

## Numeric Rationale

Reproduced directly via `optimize_all_categories()` against this scenario's fixture data — the
Optimizer prices trips at their actual fare class (Sparpreis, in this case) and BahnCard rate,
not a flat `cost_eur × 2` heuristic.

| Portfolio | Annual cost |
|---|---|
| **BahnCard 25 (recommended)** | **€747.98** |
| BahnCard 50 + Deutschland-Ticket (current) | €1,115.68 |
| Deutschland-Ticket only | €910.33 |
| No subscriptions | €914.73 |
| BahnCard 50 alone | €929.06 |

Recommended vs. current: **−€367.70/year**. The travel-reduction damping (factor ≈0.21, from
the staffing signal 78 days out) cuts his projected Frankfurt↔München frequency from 14
undamped legs/year to a handful — well below what justifies BahnCard 50's fee, but still
(barely) enough to justify BahnCard 25's much lower one. Note the recommended portfolio also
drops the **Deutschland-Ticket**: once a BahnCard is held, its Sparpreis/Flexpreis discount
already applies to his regional/commute demand too (BahnCard discounts are not restricted to
long-distance trips), so the Deutschland-Ticket's flat €756/year fee no longer earns its keep
on top — this is a genuine finding from the corrected engine, not the scenario's original
design intent, which assumed the Deutschland-Ticket would always be retained for local
coverage (see "What a Passing Run Looks Like" below).

| Break-even (single subscription, forward-looking) | Annual fee | Discount value | Net | Breaks even? |
|---|---|---|---|---|
| BahnCard 25 (2. Klasse, Standard, Jahresabo) | €62.88 | €229.63 | **+€166.75** | Yes |
| Deutschland-Ticket | €756.00 | €760.40 | **+€4.40** | Yes, barely |
| BahnCard 50 (2. Klasse, Standard, Jahresabo) | €243.96 | €229.63 | **−€14.33** | No |

BahnCard 50 is a net loss even before accounting for the forecast drop — the travel-reduction
damping makes an already-marginal card unambiguously not worth it, while BahnCard 25's much
lower fee still clears its own (lower) bar.

History → keep BC50. Forecast → the card stops paying, and even BahnCard 25 only barely clears
its own break-even once damped. The recommendation must be driven by the **forward** picture,
dated against the **10 January 2027** renewal.

---

## Data Properties

- **persona.json** — priorities cost 0.45 / time 0.35 / sustainability 0.20 (cost-leaning).
  Notes flag the Munich project ending and the likely local re-staffing.
- **current_subscriptions.json** — BahnCard 50 (Standard) + Deutschland-Ticket. BC50 renews
  `2027-01-10`.
- **travel_history_raw.json** — 14 long-distance Frankfurt↔Munich legs (7 project round trips
  across Jun/Jul/Aug/Oct/Nov 2025 and Jan/Feb 2026) summing to €409 in `cost_eur`, plus 2 short
  regional legs at €0 covered by the D-Ticket.
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
| **Analyst** | Reports BahnCard 50 as clearly worthwhile on history: ~€409 discounted long-distance spend, 14 long-distance legs. Regional legs covered by D-Ticket. Renewal `2027-01-10`. |
| **Forecaster** | Surfaces the life-event signal: Munich project ends 31 Aug, local Frankfurt staffing from September → long-distance rail demand drops to near zero. Must state the concrete portfolio implication. |
| **Optimizer** | Weighs the collapsing forward demand against the strong history and recommends **downgrading BahnCard 50 → BahnCard 25**, dropping the Deutschland-Ticket, before the 10 Jan 2027 renewal. Must **not** fire a "hold pending decision" candidate (no portfolio-reset signal). |
| **Communicator** | Presents the downgrade as recommended, dated to the January renewal, explaining that the card paid off this year but won't next year — and, per the break-even table, that the Deutschland-Ticket no longer earns its keep once a BahnCard is held. |

**Expected recommendation:** Downgrade **BahnCard 50 → BahnCard 25** before `2027-01-10`,
driven by the forecast travel drop. The deterministic optimizer's actual pick also drops the
Deutschland-Ticket (see Numeric Rationale) — a recommendation that retains the Deutschland-
Ticket alongside BahnCard 25 is a lesser pass (still correctly downgrades BC50, but ~€187/year
short of the optimizer's own numbers on this fixture). A recommendation to cancel BahnCard 50
outright, rather than downgrade, is not a pass here — unlike the earlier LLM-driven design this
scenario originally targeted, the deterministic engine's own numbers clearly favor downgrading
to BC25 over cancelling it (BahnCard 25 alone: €747.98/year vs. €914.73/year for no
subscriptions).

---

## What a Passing Run Looks Like

- The Forecaster explicitly picks up the staffing / project-end signal and states long-distance
  demand collapses from September.
- The Optimizer recommends **downgrading BahnCard 50 → BahnCard 25**, citing the **forward**
  demand drop — not the (positive) historical ROI — as the reason.
- Action is tied to the **10 January 2027** renewal deadline.
- The Deutschland-Ticket is dropped alongside the downgrade (its break-even table entry nets
  only +€4.40/year once BahnCard 25 already discounts his regional/commute demand) — a run
  that explicitly retains it with a stated reason is not wrong, just short of the optimizer's
  own numbers on this fixture.

## What a Failing Run Looks Like

- Recommends **keeping BahnCard 50** on the strength of past usage alone, ignoring the mail /
  forecast (the core failure this persona is designed to catch).
- Recommends **cancelling BahnCard 50 outright** rather than downgrading it to BahnCard 25 —
  the optimizer's own numbers favor downgrading (€747.98/year) over full cancellation
  (€914.73/year) on this fixture.
- Treats the project-end signal as a portfolio-reset and fires a "hold / wait-and-see"
  recommendation instead of acting before the renewal.
- Invents a relocation, or claims the Deutschland-Ticket cancellation is driven by a drop in
  *local* travel (it isn't — local/commute travel continues; the Deutschland-Ticket loses value
  because BahnCard 25's discount already covers that demand more cheaply once held, not because
  the demand itself goes away).
