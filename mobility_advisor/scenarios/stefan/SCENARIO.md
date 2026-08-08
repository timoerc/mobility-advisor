# Scenario 02 — Edge Case: Contradictory Signals

**Persona:** Stefan Kurz — München, car owner + BahnCard 50 + Deutschland-Ticket + MILES Silber, possible Hamburg relocation.
**Tests:** Whether the pipeline hedges correctly under genuine ambiguity instead of forcing a confident answer.
**Expected result:** A conditional/hedged recommendation branching on the relocation decision — not a single confident action.

## Summary

Stefan Kurz owns a car and drives to work in München five days a week — yet he also
holds a full rail-and-carsharing stack (BahnCard 50, Deutschland-Ticket, MILES Silber
Pass) for his regular business trips to the Frankfurt HQ. Rail usage is irregular
(feast-or-famine across months), BC50 runs a modest net loss at this usage level, MILES
usage is similarly clustered rather than steady, and the calendar suggests a possible
relocation to Hamburg that would upend his whole commute pattern. His own stated priorities
put time (0.5) well ahead of cost (0.3) and sustainability (0.2) — yet he's paying for
three transit products he uses inconsistently while also running a car. The ambiguity here
is not that BC50's arithmetic is a coin flip — it clearly loses money on the observed
data — but that the relocation decision could invalidate the whole portfolio within weeks,
which is what should stop the agent from confidently acting on the BC50 number alone. The
expected agent outcome is a **hedged, conditional recommendation** — not a single
confident action.

---

## Why the Data Is Deliberately Ambiguous

All observed DB tickets are Sparpreis (`ticket_type` contains "Sparpreis, BahnCard 50"), so
BC50's applicable discount is its **25% Sparpreis rate**, not its 50% Flexpreis rate.

| Signal | Value | Interpretation |
|---|---|---|
| BC50 discounted DB spend (11 trips) | €239.00 | Full-price equivalent: €239.00 ÷ 0.75 = €318.67 |
| BC50 discount value realized | €318.67 × 0.25 = €79.67 | vs. card cost €244 → net loss **−€164.33/year** |
| BC50 break-even threshold | €244 ÷ 0.25 = €976 full-price DB spend required | Actual full-price equivalent (€318.67) is well short — not a coin flip on its own, but small next to the relocation uncertainty below |
| Rail usage distribution | Trips cluster in Aug, Oct, Dec, and a few in Mar/May; several months with zero rail activity | Irregular, no stable monthly pattern |
| MILES usage distribution | Car-share trips cluster in Aug and Nov, quiet the rest of the year | Irregular; a standard Abo is hard to justify on usage alone |
| Car ownership | Owns a petrol medium car, ~600 km/month, commutes by car 5 days/week (no WFH days) | Already paying for door-to-door mobility independent of any subscription |
| Relocation signal | Apartment viewing in Hamburg (2026-07-18) + job offer decision (2026-08-15) + potential Hamburg start (2026-09-01) | If Hamburg: daily car commute in München disappears, D-Ticket zone relevance changes, rail demand pattern resets entirely |
| International trip | Amsterdam business trip (2026-08-02) — neither D-Ticket nor BahnCard valid | Adds opaque cost not captured in the BC50 analysis |
| User priorities | cost 0.3 / **time 0.5 (dominant)** / sustainability 0.2 — `values_time_over_money: true` | Time-first preferences sit awkwardly next to three underused, cost-bearing rail products |

---

## Numeric Rationale

> **Note (2026-08-08):** the bullets below are the original hand-derived figures from the 11 raw
> historical DB trips, kept for the qualitative signal (BC50 is not a clear win on the numbers
> alone). They predate the deterministic optimizer and use a simpler `full_price = cost_eur ÷
> 0.75` heuristic, so they will not match `optimize_all_categories()`'s output, which prices the
> full forward-projected trip set (including the daily München commute) rather than the 11 raw
> trips alone. See "Numeric Rationale — deterministic optimizer" below for the reproducible,
> engine-verified numbers and how the pending-decision mechanism actually resolves this scenario.

- **BC50 net position (raw history only):** €79.67 discount value realized (25% Sparpreis rate — all observed tickets are Sparpreis, not Flexpreis) vs. card cost €244/year → net loss: **−€164.33/year**
- **Combined rail/carsharing subscription spend:** BC50 €244/yr + D-Ticket €756/yr (€63 × 12) + MILES Silber ≈ €120/yr (€9.99 × 12) ≈ **€1,120/year** — on top of running a car
- **If relocation to Hamburg:** commute pattern resets entirely; biweekly on-site travel could make BC50/D-Ticket clearly worth keeping (or clearly redundant, depending on the new base) — not resolvable before the 2026-08-15 decision
- **If no relocation:** current irregular pattern continues → BC50 marginally not worth it, and the case for holding all three rail products alongside a daily-driven car weakens further
- **Data quality note:** no cost figure exists for car ownership (fuel/insurance/maintenance) in the mock data — the agent should flag this as an unquantified cost rather than inventing one, not silently ignore it

### Numeric Rationale — deterministic optimizer (reproduced 2026-08-08)

`detect_pending_portfolio_decision()` fires for Stefan: `exists=True`, gated by the
`job_change`/`relocation` life event landing 2026-09-01 (within the ~9-month decision horizon).
This is the deterministic "hold" gate — `main.py`'s `_enforce_hold_when_decision_pending()`
forces the recommended alternative to a **"Hold pending decision"** row regardless of what
`optimize_all_categories()` itself ranks first, so the pipeline's actual output is a single
hold recommendation with a `revisit_after: 2026-09-01` date, not two hand-computed hypothetical
branches. The table below is what the optimizer would rank if forced to act today — this is
exactly the "value being left on the table by holding" figure the Hold row's headline tile
shows, not a competing recommendation:

| Portfolio | Subs €/yr | Trips €/yr | Total €/yr | Time min/yr | CO2 kg/yr |
|---|---|---|---|---|---|
| BahnCard 25 + Deutschland-Ticket (top-ranked if acting now) | 818.88 | 2,558.04 | **3,376.92** | 15,104.6 | 3,411.47 |
| BahnCard 50 + Deutschland-Ticket + MILES Silber (current) | 1,119.84 | 2,550.37 | 3,670.21 | 15,109.5 | 3,408.34 |
| No subscriptions | 0 | 4,642.01 | 4,642.01 | 14,168.4 | 3,913.21 |
| Deutschland-Ticket alone | 756.00 | 2,895.32 | 3,651.32 | 14,954.7 | 3,557.00 |
| BahnCard 50 + Deutschland-Ticket | 999.96 | 2,558.04 | 3,558.00 | 15,104.6 | 3,411.47 |

The would-be top pick (BahnCard 25 + Deutschland-Ticket, dropping MILES Silber) would save
€293.29/year vs. current, 4.9 min/year, and 3.1 kg CO2/year — a real but modest edge, and
exactly the kind of number that isn't worth acting on when the underlying commute pattern it's
computed against may not exist in six weeks. This is the concrete case for holding: the gap
between "act now" and "current" is small next to what a Hamburg relocation would change.

Break-even for BC50 alone against the full projected trip set: fee €243.96, discount value
€515.51, net **+€271.55/year (breaks even)** — unlike the raw-history-only figure above, BC50
does clear its own break-even once the full year's projected demand (including the München
commute) is priced in. This does not overturn the hold recommendation: the pending relocation
still governs, and the point of this scenario is that the agent must not act confidently on
either figure while the decision is open.

---

## Expected Agent Behaviour

| Agent | Expected Action |
|---|---|
| **Analyst** | Flags three contradictions: (1) BC50's ROI is genuinely marginal (clearly negative on the 11 raw historical trips alone, but positive once the full projected year — including the München commute — is priced by the deterministic optimizer); (2) possible_relocation signal with material impact on all three subscriptions at once; (3) a car owner with a full rail/carsharing stack he uses irregularly, despite time being his top stated priority. Must **not** resolve these — surface all three. |
| **Forecaster** | Surfaces the relocation life-event signal (apartment viewing, job offer decision 2026-08-15, potential Hamburg start 2026-09-01) and notes it as a material near-term uncertainty for the whole portfolio. |
| **Optimizer** | Calls `optimize_all_categories()`, which ranks BahnCard 25 + Deutschland-Ticket first among the "act now" candidates — but `detect_pending_portfolio_decision()` gates on the relocation signal (`exists=True`, `revisit_after: 2026-09-01`), so the pipeline's deterministic hold logic overrides the ranked pick with a single **"Hold pending decision"** recommendation. Must not fire a confident "cancel/downgrade BC50" action in its place. |
| **Communicator** | Drafts the hold as the recommended action, states the 2026-09-01 revisit date, and states the "value on hold" — what the best act-now alternative (BahnCard 25 + Deutschland-Ticket) would have saved (€293.29/yr) — as context for why holding has a real but modest opportunity cost, without recommending it. |

---

## What a Correct Output Looks Like

This is what the actual pipeline produces (`_enforce_hold_when_decision_pending()` in
`main.py`), not two hand-written hypothetical branches — the deterministic gate collapses the
"if relocation / if not" framing into a single recommendation once a qualifying pending-decision
signal exists:

```
RECOMMENDATION: Hold your current setup until the pending decision resolves (2026-09-01)

Confidence: low
Revisit by: 2026-09-01
Value on hold: €293/year (what BahnCard 25 + Deutschland-Ticket would save if adopted now)
Decision pending: relocation / job change

Reasoning: A pending relocation/job change is expected to take effect by 2026-09-01, which
would reset the current commute-based portfolio. Acting now (e.g. dropping to BahnCard 25 +
Deutschland-Ticket, or trimming MILES Silber) risks a change the relocation decision could
immediately reverse. The best available act-now alternative is shown as a non-recommended
option so the deferred value is visible, not hidden.

Data quality note: Amsterdam trip cost not captured in the BC50 analysis (card not applicable).
No cost figure exists for car ownership in the mock data — flagged as unquantified, not assumed zero.
```

---

## What a Failing Output Looks Like

- A single confident recommendation ("cancel BC50" or "switch to BahnCard 25 + Deutschland-Ticket") without surfacing the relocation signal — i.e. `detect_pending_portfolio_decision()`'s hold gate did not fire or was overridden
- A recommendation that ignores the tension between owning a car, holding three transit
  subscriptions, and stating time as the top priority
- Treating the irregular history as a trend (e.g., "usage is declining")
- No mention of a revisit/decision date as a key information trigger — the deterministic gate
  surfaces **2026-09-01** (the qualifying life event's own `event_date`, i.e. the relocation/job
  start taking effect) as `revisit_after`; the calendar separately shows **2026-08-15** as the
  job-offer decision deadline itself. Either date missing from the output is a gap.
- Inventing a car-ownership cost figure that isn't present in the mock data

---

## Signals by File

- **travel_history_raw.json** — irregular monthly distribution; BC50 nets a loss on the 11 raw historical trips alone but breaks even (+€271.55/yr) once the full projected-year trip set (including the München commute) is priced by the deterministic optimizer — see Numeric Rationale above; no long-haul flights, all trips centered on the München/Frankfurt business-travel pattern
- **calendar_events_live.json** — relocation signals in July–September 2026; international trip with no subscription coverage; recurring Frankfurt office days tagged `long_distance_rail_likely` (München→Frankfurt is a ~300 km intercity trip, not a local commute)
- **persona.json** — car owner with time-dominant priorities (cost 0.3 / time 0.5 / sustainability 0.2), commutes by car 5 days/week. (Car-usage data lives separately in `car_usage.json`.)
- **current_subscriptions.json** — full rail/carsharing stack (BC50 + D-Ticket + MILES Silber) despite car ownership. Each entry carries `billing_cycle` and `next_renewal_date`.
- **mobility_advisor/static/mobility_catalog.json** — full catalog (shared across all personas); each option carries `billing_cycle`.
