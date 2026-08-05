# Scenario Testing Framework

Each subdirectory is a self-contained set of fixture files that replaces `data/` for a specific demo or evaluation run. Scenarios are fully isolated — every directory contains all eight required JSON files (`persona.json`, `current_subscriptions.json`, `travel_history_raw.json`, `mail_raw.json`, `calendar_events_live.json`, `car_usage.json`, `analysis_history.json`, `life_events.json`) so that no shared state exists between scenarios. The mobility catalog is not part of this set — it's a single shared file at `mobility_advisor/static/mobility_catalog.json`, identical for every persona.

Use `activate_scenario.sh` to switch scenarios. The script creates a timestamped backup of `data/` before overwriting it, so the previous state is always recoverable.

**Note on the `tobias` row below:** this scenario was authored against the earlier LLM-driven optimizer (prompt-embedded forecast-override reasoning). The regular pipeline now scores portfolios deterministically instead (see CLAUDE.md's Four-stage pipelines section); the mechanism it exercises has been re-implemented as deterministic logic (`tobias` via life-event-driven trip-frequency damping, `_travel_reduction_factor` in `tools.py`) but end-to-end reproduction against a live pipeline run has not yet been re-verified since that change; only the underlying function is unit-tested (`tests/test_optimization_engine.py`). Treat that row's "Expected Outcome" as the design intent, not a confirmed-passing result, until re-run.

**Note on `katrin`:** this scenario's SCENARIO.md and the table row below were re-verified directly against the current deterministic optimizer (`optimize_all_categories()`) — see `scenarios/katrin/SCENARIO.md` for the full numeric rationale. The originally-authored expected outcome (an LLM-optimizer-era BC25→BC50 preference tie-break) no longer applies: the deterministic break-even math shows both current subscriptions running a net loss at her usage, so the current pipeline recommends cancelling both instead.

---

## Scenarios

Scenario folder names match the frontend persona IDs. Selecting a persona in the UI automatically activates its scenario on the backend.

| Scenario | Persona | Key Signal | Expected Outcome | Activate Command |
|---|---|---|---|---|
| `maja` | Maja Hoffmann | BC50 savings (€36) far below card cost (€244); no upcoming long-distance travel | Unambiguous recommendation to cancel BC50 | `./scenarios/activate_scenario.sh maja` |
| `stefan` | Stefan Kurz | Car owner who also holds a full rail/carsharing stack (BC50 + D-Ticket + MILES) he uses irregularly; BC50 near breakeven; Hamburg relocation uncertainty affects all three subscriptions at once; time priority conflicts with cost savings | Hedged conditional recommendation — no single dominant action | `./scenarios/activate_scenario.sh stefan` |
| `lena` | Lena Brandt | Several of 20 travel history entries are semantically malformed (null costs, empty mode, unknown mode value) | Pipeline completes with partial result and explicit data quality warnings | `./scenarios/activate_scenario.sh lena` |
| `katrin` | Katrin Berger | Holds BahnCard 25 + Deutschland-Ticket, but neither breaks even against her actual travel volume (BC25 nets −€56.51/yr, Deutschland-Ticket −€756/yr) | **Cancel both:** drop BahnCard 25 and the Deutschland-Ticket, saving €812.51/yr — cheaper and faster, at the cost of +15 kg CO2/yr | `./scenarios/activate_scenario.sh katrin` |
| `tobias` | Tobias Wolf | Weekly Frankfurt–Munich trips clearly justify BC50 on history (~€165/yr net benefit), but a staffing mail signals long-distance travel collapses from September (project ends, local re-staffing) | **Forward-looking:** downgrade (or cancel) BC50 before the Jan renewal — the mail/forecast overrides the positive history | `./scenarios/activate_scenario.sh tobias` |
| `sofia` | Sofia Ricci | Frequent MILES car-share (~monthly, ≥€10/ride) on pay-per-use with no membership; occasional local rail on D-Ticket | **Under-subscribed (add):** add/upgrade to MILES Silber (credit offsets fee → effectively free + ~€20/yr), pick Silber over higher tiers, keep D-Ticket | `./scenarios/activate_scenario.sh sofia` |

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
