# Scenario Testing Framework

Each subdirectory is a self-contained set of fixture files that replaces `data/` for a specific demo or evaluation run. Scenarios are fully isolated — every directory contains all five required JSON files so that no shared state exists between scenarios.

Use `activate_scenario.sh` to switch scenarios. The script creates a timestamped backup of `data/` before overwriting it, so the previous state is always recoverable.

---

## Scenarios

Scenario folder names match the frontend persona IDs. Selecting a persona in the UI automatically activates its scenario on the backend.

| Scenario | Persona | Key Signal | Expected Outcome | Activate Command |
|---|---|---|---|---|
| `maja` | Maja Hoffmann | BC50 savings (€36) far below card cost (€244); no upcoming long-distance travel | Unambiguous recommendation to cancel BC50 | `./scenarios/activate_scenario.sh maja` |
| `stefan` | Stefan Kurz | Car owner; no active subscriptions; high ownership costs vs. carsharing; time priority conflicts with cost savings | Hedged conditional recommendation — no single dominant action | `./scenarios/activate_scenario.sh stefan` |
| `lena` | Lena Brandt | 6 of 20 travel history entries are semantically malformed (null costs, empty mode, unknown mode value) | Pipeline completes with partial result and explicit data quality warnings | `./scenarios/activate_scenario.sh lena` |

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

- Each scenario folder also contains a `persona.json` file with the full persona profile (name, display metadata, onboarding preferences). This is served by `GET /api/personas` and used by the frontend to load persona data from a single authoritative source.
- `mobility_catalog.json` is identical across all three scenarios. It is copied into each directory (not symlinked) so each scenario remains fully self-contained.
- All JSON files are valid and pass `python -m json.tool`. In scenario `lena`, the breakage in `travel_history.json` is **semantic** (null values, unrecognized mode strings), not syntactic.
- Do not modify files directly inside `scenarios/` subdirectories during a demo run — activate the scenario first, then let the agent read from `data/`.
- The `activate_scenario.sh` script always creates a timestamped backup before switching, so switching between scenarios is non-destructive.
