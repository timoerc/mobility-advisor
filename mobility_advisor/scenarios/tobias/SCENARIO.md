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
**Expected result:** Recommend downgrading BahnCard 50 → BahnCard 25 ahead of renewal, despite
history alone saying "keep." Whether the Deutschland-Ticket is kept alongside the downgrade is
a near-tie on the current numbers (€6.44/year) — see Numeric Rationale below.

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

Reproduced directly via `optimize_all_categories()` against this scenario's fixture data
(regenerated 2026-08-08) — the Optimizer prices trips at their actual fare class (Sparpreis, in
this case) and BahnCard rate, not a flat `cost_eur × 2` heuristic.

| Portfolio | Annual cost |
|---|---|
| **BahnCard 25 + Deutschland-Ticket (recommended)** | **€1,163.17** |
| BahnCard 50 + Deutschland-Ticket (current) | €1,344.25 (+€181.08 vs. recommended) |
| No subscriptions | €1,226.63 (+€63.46 vs. recommended) |
| BahnCard 25 alone | €1,169.61 (+€6.44 vs. recommended) |
| Deutschland-Ticket alone | €1,215.03 (+€51.86 vs. recommended) |

Recommended vs. current: **−€181.08/year**. The travel-reduction damping (factor ≈0.21, from
the staffing signal 78 days out) cuts his projected Frankfurt↔München frequency from 14
undamped legs/year to a handful — well below what justifies BahnCard 50's fee, but still
(barely) enough to justify BahnCard 25's much lower one. The top-ranked candidate keeps the
**Deutschland-Ticket** alongside BahnCard 25, but only by €6.44/year over BahnCard 25 alone —
essentially a tie, well within the model's own precision, so either reading is an acceptable
pass (see "What a Passing Run Looks Like" below).

| Break-even (single subscription, forward-looking) | Annual fee | Discount value | Net | Breaks even? |
|---|---|---|---|---|
| BahnCard 25 + Deutschland-Ticket | €818.88 | €882.34 | **+€63.46** | Yes |
| BahnCard 25 (2. Klasse, Standard, Jahresabo) | €62.88 | €119.90 | **+€57.02** | Yes |
| Deutschland-Ticket | €756.00 | €767.60 | **+€11.60** | Yes, barely |
| BahnCard 50 + Deutschland-Ticket | €999.96 | €882.34 | **−€117.62** | No |
| BahnCard 50 (2. Klasse, Standard, Jahresabo) | €243.96 | €119.90 | **−€124.06** | No |

BahnCard 50 is a net loss (alone or combined with the Deutschland-Ticket) even before separately
accounting for the forecast drop — the travel-reduction damping makes an already-marginal card
unambiguously not worth it, while BahnCard 25 (alone or combined) still clears its own
(much lower) bar.

History → keep BC50. Forecast → the card stops paying, and even BahnCard 25 only barely clears
its own break-even once damped. The recommendation must be driven by the **forward** picture,
dated against the **10 January 2027** renewal.

*(Note: an earlier snapshot of this table showed BahnCard 25 alone — with the Deutschland-Ticket
dropped — as the clear top pick, €187/year better than keeping the ticket. The current numbers,
regenerated against the same `optimize_all_categories()` call, show the opposite ordering by a
narrow €6.44/year: the Deutschland-Ticket is now kept in the top-ranked candidate. This reflects
further engine fixes since that snapshot, not a change in Tobias's underlying data — see the
commute-discount-leak and current-portfolio-dedup fixes noted in the git history. Given the
margin involved, treat "drop the Deutschland-Ticket" and "keep it" as equally valid passes; the
load-bearing finding this scenario tests is the BC50→BC25 downgrade itself.)*

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
| **Optimizer** | Weighs the collapsing forward demand against the strong history and recommends **downgrading BahnCard 50 → BahnCard 25**, before the 10 Jan 2027 renewal. Whether the Deutschland-Ticket is kept alongside it is a near-tie (see Numeric Rationale) — the optimizer's current top pick keeps it. Must **not** fire a "hold pending decision" candidate (no portfolio-reset signal). |
| **Communicator** | Presents the downgrade as recommended, dated to the January renewal, explaining that the card paid off this year but won't next year. |

**Expected recommendation:** Downgrade **BahnCard 50 → BahnCard 25** before `2027-01-10`,
driven by the forecast travel drop. Whether the Deutschland-Ticket is kept or dropped alongside
the downgrade is a near-tie on the current numbers (€6.44/year apart, see Numeric Rationale) —
either is an acceptable pass. A recommendation to cancel BahnCard 50 outright, rather than
downgrade, is not a pass here — the deterministic engine's own numbers clearly favor downgrading
to BC25 over cancelling it (BahnCard 25 + Deutschland-Ticket: €1,163.17/year vs. €1,226.63/year
for no subscriptions).

---

## What a Passing Run Looks Like

- The Forecaster explicitly picks up the staffing / project-end signal and states long-distance
  demand collapses from September.
- The Optimizer recommends **downgrading BahnCard 50 → BahnCard 25**, citing the **forward**
  demand drop — not the (positive) historical ROI — as the reason.
- Action is tied to the **10 January 2027** renewal deadline.
- Whether the Deutschland-Ticket is kept or dropped alongside the downgrade is not load-bearing
  (the two candidates are ~€6/year apart on the current numbers) — either is a pass as long as
  the reasoning is consistent with which one is actually shown as recommended.

## What a Failing Run Looks Like

- Recommends **keeping BahnCard 50** on the strength of past usage alone, ignoring the mail /
  forecast (the core failure this persona is designed to catch).
- Recommends **cancelling BahnCard 50 outright** rather than downgrading it to BahnCard 25 —
  the optimizer's own numbers favor downgrading (€1,163.17/year with the Deutschland-Ticket, or
  €1,169.61/year without) over full cancellation (€1,226.63/year) on this fixture.
- Treats the project-end signal as a portfolio-reset and fires a "hold / wait-and-see"
  recommendation instead of acting before the renewal.
- Invents a relocation, or claims a stated Deutschland-Ticket cancellation is driven by a drop
  in *local* travel (it isn't — local/commute travel continues; if the ticket is dropped, it's
  because BahnCard 25's discount already covers that demand about as cheaply once held, not
  because the demand itself goes away).
