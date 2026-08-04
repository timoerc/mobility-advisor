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

- **BC50 net position:** €79.67 discount value realized (25% Sparpreis rate — all observed tickets are Sparpreis, not Flexpreis) vs. card cost €244/year → net loss: **−€164.33/year**
- **Combined rail/carsharing subscription spend:** BC50 €244/yr + D-Ticket €756/yr (€63 × 12) + MILES Silber ≈ €120/yr (€9.99 × 12) ≈ **€1,120/year** — on top of running a car
- **If relocation to Hamburg:** commute pattern resets entirely; biweekly on-site travel could make BC50/D-Ticket clearly worth keeping (or clearly redundant, depending on the new base) — not resolvable before the 2026-08-15 decision
- **If no relocation:** current irregular pattern continues → BC50 marginally not worth it, and the case for holding all three rail products alongside a daily-driven car weakens further
- **Data quality note:** no cost figure exists for car ownership (fuel/insurance/maintenance) in the mock data — the agent should flag this as an unquantified cost rather than inventing one, not silently ignore it

---

## Expected Agent Behaviour

| Agent | Expected Action |
|---|---|
| **Analyst** | Flags three contradictions: (1) BC50 running a net loss (−€164.33/yr) with no stable usage trend; (2) possible_relocation signal with material impact on all three subscriptions at once; (3) a car owner with a full rail/carsharing stack he uses irregularly, despite time being his top stated priority. Must **not** resolve these — surface all three. |
| **Forecaster** | Produces two demand branches: (a) Hamburg relocation confirmed → commute pattern resets, high uncertainty on rail demand; (b) no relocation → demand continues irregular around the München–Frankfurt route. Must explicitly label both branches and note the decision date (2026-08-15). |
| **Optimizer** | Outputs conditional recommendations for each branch, not a single action. |
| **Communicator** | Drafts conditional output: "If relocation proceeds: [action X]. If not: [action Y]. Recommend revisiting after Aug 15 decision date." |

---

## What a Correct Output Looks Like

```
RECOMMENDATION (CONDITIONAL — HIGH UNCERTAINTY)

If relocation to Hamburg is confirmed (decision by 2026-08-15):
  → Hold all three subscriptions pending the move: the new commute pattern will determine
    whether BC50/D-Ticket become clearly worth keeping or clearly redundant
  → Re-evaluate Deutschland-Ticket: Hamburg zone coverage needs verification
  → Estimated annual saving vs. status quo: not determinable before the decision date

If no relocation (München base + car commute continues):
  → Cancel BahnCard 50: discount value realized (€79.67) falls well short of the card cost
    (€244) at this usage level — a clear net loss of €164.33/year, before even accounting
    for irregular usage making forecasting unreliable
  → Action by: 15 January 2027 to avoid auto-renewal (next_renewal_date from subscription data)
  → Re-examine whether D-Ticket and MILES Silber are still worth holding alongside daily car use
  → Estimated annual saving: €164.33 from BC50 alone, more if D-Ticket/MILES are also trimmed

Data quality note: Amsterdam trip cost not captured in BC50 analysis (card not applicable).
No cost figure exists for car ownership in the mock data — flagged as unquantified, not assumed zero.
Recommendation should be revisited after the 2026-08-15 job offer decision.
```

---

## What a Failing Output Looks Like

- A single confident recommendation ("cancel BC50") without surfacing the relocation signal
- A recommendation that ignores the tension between owning a car, holding three transit
  subscriptions, and stating time as the top priority
- Treating the irregular history as a trend (e.g., "usage is declining")
- No mention of the Aug 15 decision date as a key information trigger
- Inventing a car-ownership cost figure that isn't present in the mock data

---

## Signals by File

- **travel_history_raw.json** — irregular monthly distribution; DB spend well short of BC50 break-even (net −€164.33/yr); no long-haul flights, all trips centered on the München/Frankfurt business-travel pattern
- **calendar_events_live.json** — relocation signals in July–September 2026; international trip with no subscription coverage; recurring Frankfurt office days tagged `long_distance_rail_likely` (München→Frankfurt is a ~300 km intercity trip, not a local commute)
- **persona.json** — car owner with time-dominant priorities (cost 0.3 / time 0.5 / sustainability 0.2), commutes by car 5 days/week. (Car-usage data lives separately in `car_usage.json`.)
- **current_subscriptions.json** — full rail/carsharing stack (BC50 + D-Ticket + MILES Silber) despite car ownership. Each entry carries `billing_cycle` and `next_renewal_date`.
- **mobility_advisor/static/mobility_catalog.json** — full catalog (shared across all personas); each option carries `billing_cycle`.
