# Scenario Testing Framework

Each subdirectory is a self-contained set of fixture files that replaces `data/` for a specific demo or evaluation run. Scenarios are fully isolated — every directory contains all eight required JSON files (`persona.json`, `current_subscriptions.json`, `travel_history_raw.json`, `mail_raw.json`, `calendar_events_live.json`, `car_usage.json`, `analysis_history.json`, `life_events.json`) so that no shared state exists between scenarios. The mobility catalog is not part of this set — it's a single shared file at `mobility_advisor/static/mobility_catalog.json`, identical for every persona.

Use `activate_scenario.sh` to switch scenarios. The script creates a timestamped backup of `data/` before overwriting it, so the previous state is always recoverable.

**Note on all six rows below (2026-08-08):** every row's numeric rationale was regenerated
directly against `optimize_all_categories()` on this date (see each `SCENARIO.md`'s "Numeric
Rationale" / "Updated Numeric Rationale" section for the reproducible figures). The engine has
had several rounds of bug fixes since these scenarios were originally authored — most recently a
fix for a BahnCard-discount leak onto the synthetic home-city commute leg, duplicate flight
alternatives, one-off routes being miscounted as recurring, and current-portfolio deduplication
(see the git history) — so absolute totals in some scenarios shifted noticeably even where the
qualitative recommendation didn't change (`maja`), and in a few cases the top-ranked candidate
itself changed (`lena`, `sofia`) or became a near-tie between two close candidates rather than a
clear win (`katrin`, `tobias`). This has not been re-run end-to-end through the coordinator +
LLM pipeline for every persona — only the deterministic engine (`optimize_all_categories()` and
its upstream trip-projection tools) was re-verified directly; treat the qualitative direction as
confirmed and the exact wording an LLM run would produce as unverified until a live pipeline run
is checked against it.

**Note on `stefan`:** `detect_pending_portfolio_decision()` fires for this persona
(`revisit_after: 2026-09-01`, from the relocation/job-change life event), so the deterministic
pipeline overrides whatever `optimize_all_categories()` ranks first with a single **"Hold
pending decision"** recommendation — not the two hand-written hypothetical branches the
scenario was originally documented with. See `scenarios/stefan/SCENARIO.md` for the mechanism
and the current would-be-top-ranked-if-acting-now numbers.

**Note on `katrin`:** re-verified directly against the current deterministic optimizer. The
originally-authored expected outcome (an LLM-optimizer-era BC25→BC50 preference tie-break, and
before that a since-corrected "cancel both" result from two now-fixed engine bugs) no longer
applies either way: BahnCard 50 now clearly beats her current BahnCard 25 + Deutschland-Ticket
setup, and whether the Deutschland-Ticket survives alongside BahnCard 50 is a near-tie
(€7.46/year) rather than a clear drop. See `scenarios/katrin/SCENARIO.md`.

**Note on `sofia`:** the deterministic optimizer now also proposes adding a BahnCard 25 and
dropping the Deutschland-Ticket alongside the MILES Silber upgrade this scenario was designed
to test — driven by regional/commute demand a BahnCard discounts more cheaply than the ticket's
flat fee, the same mechanism already documented for `katrin`/`tobias`, not by her single
long-distance round trip. The MILES Basis→Silber upgrade itself (this scenario's core point) is
unaffected. See `scenarios/sofia/SCENARIO.md`.

---

## Scenarios

Scenario folder names match the frontend persona IDs. Selecting a persona in the UI automatically activates its scenario on the backend.

| Scenario | Persona | Key Signal | Expected Outcome | Activate Command |
|---|---|---|---|---|
| `maja` | Maja Hoffmann | BC50's discount value (€151.11/yr) falls well short of its €244 card cost; no upcoming long-distance travel beyond history | Downgrade **BahnCard 50 → BahnCard 25**, saving €181.08/yr — unambiguous, BC50 is dominated on identical discounted demand | `./scenarios/activate_scenario.sh maja` |
| `stefan` | Stefan Kurz | Car owner who also holds a full rail/carsharing stack (BC50 + D-Ticket + MILES) he uses irregularly; a pending relocation/job-change life event (`revisit_after: 2026-09-01`) trips the deterministic hold gate | **Hold pending decision** — the pipeline's deterministic gate overrides the ranked pick with a single hold recommendation (not a hand-written conditional branch), showing BahnCard 25 + Deutschland-Ticket (−€293/yr if adopted now) as the deferred alternative | `./scenarios/activate_scenario.sh stefan` |
| `lena` | Lena Brandt | Several of 20 travel history entries are semantically malformed (null costs, empty mode, unknown mode value) | Pipeline completes with partial result and explicit data quality warnings; recommends downgrading to **BahnCard 25 Young alone**, saving €89.12/yr vs. her current BC50 Young + D-Ticket | `./scenarios/activate_scenario.sh lena` |
| `katrin` | Katrin Berger | Holds BahnCard 25 + Deutschland-Ticket; BahnCard 50 discounts her Flexpreis-heavy long-distance legs far more than BC25 does | Upgrade to **BahnCard 50** (+ Deutschland-Ticket, kept by a €7.46/yr near-tie over dropping it), saving €318.32/yr, 16.4 min/yr, and 68.5 kg CO2/yr vs. current | `./scenarios/activate_scenario.sh katrin` |
| `tobias` | Tobias Wolf | Weekly Frankfurt–Munich trips clearly justify BC50 on history, but a staffing mail signals long-distance travel collapses from September (project ends, local re-staffing) | **Forward-looking:** downgrade **BahnCard 50 → BahnCard 25** before the Jan renewal (D-Ticket kept, by a €6.44/yr near-tie) — the mail/forecast overrides the positive history | `./scenarios/activate_scenario.sh tobias` |
| `sofia` | Sofia Ricci | Frequent MILES car-share (~monthly, ≥€10/ride) on pay-per-use with no membership; regional/commute demand a BahnCard now discounts more cheaply than the flat Deutschland-Ticket fee | **Under-subscribed (add):** add BahnCard 25, upgrade MILES Basis → **MILES Silber** (credit offsets fee → effectively free + ~€20/yr), drop the Deutschland-Ticket — saving €267.59/yr | `./scenarios/activate_scenario.sh sofia` |

---

## Usage

Run from the `mobility_advisor/` directory:

```bash
./scenarios/activate_scenario.sh maja
```

The script will:
1. Validate that the named scenario directory exists
2. Back up the current `data/` directory to `data_backup_<timestamp>/`
3. Copy all `.json` files from `scenarios/<name>/` into `data/`
4. Print which scenario is now active and where the backup was saved

To restore a backup:

```bash
cp data_backup_<timestamp>/*.json data/
```

---

## Notes

- Each scenario folder also contains a `persona.json` file with the full persona profile (name, display metadata, onboarding preferences). This is served by `GET /api/personas` (merged with `current_subscriptions.json` and `car_usage.json`) and used by the frontend to load persona data from a single authoritative source.
- `mobility_advisor/static/mobility_catalog.json` is shared by all scenarios — it is not part of any scenario directory and is never copied by activation.
- All JSON files are valid and pass `python -m json.tool`. In scenario `lena`, the breakage in `travel_history_raw.json` is **semantic** (null values, unrecognized mode strings), not syntactic.
- Do not modify files directly inside `scenarios/` subdirectories during a demo run — activate the scenario first, then let the agent read from `data/`.
- The `activate_scenario.sh` script always creates a timestamped backup before switching, so switching between scenarios is non-destructive.
