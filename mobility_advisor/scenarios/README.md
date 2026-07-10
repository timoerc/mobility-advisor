# Scenario Testing Framework

Each subdirectory is a self-contained set of fixture files that replaces `data/` for a specific demo or evaluation run. Scenarios are fully isolated — every directory contains all six required JSON files (`persona.json`, `current_subscriptions.json`, `travel_history_raw.json`, `mail_raw.json`, `calendar_events_live.json`, `car_usage.json`) so that no shared state exists between scenarios. The mobility catalog is not part of this set — it's a single shared file at `mobility_advisor/static/mobility_catalog.json`, identical for every persona.

Use `activate_scenario.sh` to switch scenarios. The script creates a timestamped backup of `data/` before overwriting it, so the previous state is always recoverable.

---

## Scenarios

Scenario folder names match the frontend persona IDs. Selecting a persona in the UI automatically activates its scenario on the backend.

| Scenario | Persona | Key Signal | Expected Outcome | Activate Command |
|---|---|---|---|---|
| `maja` | Maja Hoffmann | BC50 savings (€36) far below card cost (€244); no upcoming long-distance travel | Unambiguous recommendation to cancel BC50 | `./scenarios/activate_scenario.sh maja` |
| `stefan` | Stefan Kurz | Car owner who also holds a full rail/carsharing stack (BC50 + D-Ticket + MILES) he uses irregularly; BC50 near breakeven; Hamburg relocation uncertainty affects all three subscriptions at once; time priority conflicts with cost savings | Hedged conditional recommendation — no single dominant action | `./scenarios/activate_scenario.sh stefan` |
| `lena` | Lena Brandt | Several of 20 travel history entries are semantically malformed (null costs, empty mode, unknown mode value) | Pipeline completes with partial result and explicit data quality warnings | `./scenarios/activate_scenario.sh lena` |

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
- `mobility_advisor/static/mobility_catalog.json` is shared by all three scenarios — it is not part of any scenario directory and is never copied by activation.
- All JSON files are valid and pass `python -m json.tool`. In scenario `lena`, the breakage in `travel_history_raw.json` is **semantic** (null values, unrecognized mode strings), not syntactic.
- Do not modify files directly inside `scenarios/` subdirectories during a demo run — activate the scenario first, then let the agent read from `data/`.
- The `activate_scenario.sh` script always creates a timestamped backup before switching, so switching between scenarios is non-destructive.
