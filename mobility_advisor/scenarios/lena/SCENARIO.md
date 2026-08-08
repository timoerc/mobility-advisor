# Scenario 03 — Failure Recovery: Broken Tool Data Mid-Pipeline

**Persona:** Lena — student, BahnCard 50 Young + Deutschland-Ticket; trip data deliberately corrupted.
**Tests:** Graceful degradation on malformed data (null costs, empty/invalid modes).
**Expected result:** Pipeline completes with a Data Quality Warnings section — never crashes, never treats null as €0.

## Summary

The `travel_history.json` fixture contains intentionally malformed entries — valid JSON that passes `python -m json.tool` but carries semantic breakage: null costs, empty mode strings, and unrecognized mode values. The expected agent outcome is **graceful degradation**: the pipeline completes with a partial result and an explicit data quality warning section. It must not crash, and must not silently treat null costs as €0.

---

## Malformed Entries — Explicit Index

| # | Date | Field | Bad Value | Entry Type |
|---|---|---|---|---|
| 15 | 2025-05-28 | `cost_eur` | `null` | Rail: Frankfurt → Nürnberg |
| 16 | 2024-11-30 | `cost_eur` | `null` | Car-share: Frankfurt Innenstadt → Frankfurt Bornheim |
| 17 | 2025-02-05 | `mode` | `""` (empty string) | Unknown: Frankfurt → Hannover |
| 18 | 2024-12-10 | `mode` | `""` (empty string) | Unknown: Frankfurt Bornheim → Airport |
| 19 | 2024-10-14 | `mode` | `"hovercraft"` | Unknown: Frankfurt → Bremen |
| 20 | 2024-08-19 | `mode` | `"hovercraft"` | Unknown: Frankfurt Westend → Frankfurt Nordend |

**Total:** 6 of 20 entries (30%) are semantically broken. All 20 entries are syntactically valid JSON.

---

## Data Properties

- **travel_history_raw.json** — 20 trips: 14 clean (12 rail + 2 car-share), 6 malformed as listed above. File passes `python -m json.tool`.
- **current_subscriptions.json** — Valid, simplified stack. Entries carry `billing_cycle` and `next_renewal_date`.
- **calendar_events_live.json** — Valid, sparse upcoming events, no strong demand signals.
- **mobility_advisor/static/mobility_catalog.json** — Valid, full catalog (shared across all personas); each option carries `billing_cycle`.
- **persona.json** — `home_city` is Frankfurt, matching her Frankfurt-origin travel history and Goethe-Universität-centered calendar (both malformed and clean entries alike). (Car-usage data lives separately in `car_usage.json`.)

---

## Expected Agent Behaviour

| Agent | Expected Action |
|---|---|
| **Analyst** | On encountering `cost_eur: null`: **skip** the entry and record it in a flagged list. **Do not** substitute €0 — this would silently undercount DB spend and corrupt the break-even calculation. On encountering `mode: ""` or `mode: "hovercraft"`: skip and flag — cannot classify trip type. Log all 6 skipped entries with date, route, and reason. |
| **Optimizer** | Runs analysis on clean 14 trips only. States explicitly: "Analysis based on 14 of 20 trips; 6 entries excluded due to data quality issues." |
| **Communicator** | Final output includes a **Data Quality Warnings** section listing all flagged entries before the recommendation. Recommendation is clearly scoped: "based on clean data subset." |

---

## What a Passing Failure-Recovery Run Looks Like

```
DATA QUALITY WARNINGS
=====================
The following 6 trip entries were excluded from analysis due to missing or unrecognized values:

  1. 2025-05-28 | Frankfurt → Nürnberg | cost_eur: null (cannot compute savings)
  2. 2024-11-30 | Frankfurt Innenstadt → Frankfurt Bornheim | cost_eur: null (cannot compute savings)
  3. 2025-02-05 | Frankfurt → Hannover | mode: "" (unrecognized, cannot classify)
  4. 2024-12-10 | Frankfurt Bornheim → Airport | mode: "" (unrecognized, cannot classify)
  5. 2024-10-14 | Frankfurt → Bremen | mode: "hovercraft" (unrecognized, cannot classify)
  6. 2024-08-19 | Frankfurt Westend → Frankfurt Nordend | mode: "hovercraft" (unrecognized, cannot classify)

Analysis is based on the remaining 14 trips (70% of history).

RECOMMENDATION (PARTIAL DATA)
==============================
Based on clean data subset (14 trips). Lena holds BahnCard 50 **Young** (€10.17/mo =
€122.04/yr, the age-eligible tier, not the €244/yr standard adult fee) plus a
Deutschland-Ticket, and all her tickets are Sparpreis (`ticket_type` contains "Sparpreis,
BahnCard 50"), so the applicable discount is BC50's **25% Sparpreis rate**, not its 50%
Flexpreis rate. Reproduced directly via `optimize_all_categories()` against the full
forward-projected trip set (not just the 14 clean raw trips — it also includes her synthetic
home-city commute demand):

| Portfolio | Total €/yr |
|---|---|
| BahnCard 25 Young — **recommended** | 2,130.97 |
| BahnCard 50 Young + Deutschland-Ticket (current) | 2,220.09 (+€89.12 vs. recommended) |
| No subscriptions | 2,126.19 (−€4.78 vs. recommended) |
| BahnCard 25 Young + Deutschland-Ticket | 2,139.93 (+€8.96 vs. recommended) |
| Deutschland-Ticket alone | 2,135.15 (+€4.18 vs. recommended) |

  → BahnCard 25 Young break-even: fee €41.88, discount value €37.10, net **−€4.78/year** — a
    marginal net loss on its own, but still €89.12/year cheaper than the current BC50 Young +
    Deutschland-Ticket combo, because BC50 Young's higher fee and the Deutschland-Ticket's flat
    €756/year fee both cost more than the regional/commute demand they cover is worth at her
    usage level. All five candidates in the table above land within ~€90 of each other — this
    is a low-stakes, near-flat comparison, not a dramatic overspend.
  → Next renewal: 15 January 2027 (from next_renewal_date in subscription data)

Note: If the 6 flagged entries include significant rail spend, the ranking above could shift.
Data quality fix recommended before the 2027-01-15 renewal deadline.
```

*(Numeric section regenerated 2026-08-08 directly against `optimize_all_categories()`. This
supersedes an earlier hand-calculated version of this table, which priced BC50 Young against
its 14 raw historical trips only and concluded "retain" — the full projected-year trip set the
deterministic engine now prices, including Lena's synthetic home-city commute, shows BahnCard
25 Young alone as marginally cheaper than the current BC50 Young + Deutschland-Ticket combo.
The qualitative point of this scenario — data-quality warnings must not block a recommendation
— is unaffected by which specific card comes out ahead.)*

---

## What a Failing Run Looks Like

- Pipeline crashes on `cost_eur: null` (e.g., Python `TypeError: unsupported operand type(s) for +: 'NoneType' and 'float'`)
- Agent silently treats `cost_eur: null` as `0` — produces artificially low DB spend
- Agent silently skips `mode: "hovercraft"` entries without logging them
- Final output contains no Data Quality Warnings section
- Recommendation is presented as certain without noting the incomplete data

---

## JSON Validity Check

All files in this scenario pass `python -m json.tool`. The breakage in `travel_history_raw.json` is semantic (wrong values), not syntactic (malformed JSON). Verify with:

```bash
python -m json.tool travel_history_raw.json > /dev/null && echo "valid"
```
