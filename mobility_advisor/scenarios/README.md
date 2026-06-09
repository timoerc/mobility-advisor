# Scenario Testing Framework

Each subdirectory is a self-contained set of fixture files that replaces `data/` for a specific demo or evaluation run. Scenarios are fully isolated — every directory contains all five required JSON files so that no shared state exists between scenarios.

Use `activate_scenario.sh` to switch scenarios. The script creates a timestamped backup of `data/` before overwriting it, so the previous state is always recoverable.

---

## Scenarios

| Scenario | Key Signal | Expected Outcome | Activate Command |
|---|---|---|---|
| `01_happy_path` | BC50 savings (€36) far below card cost (€244); no upcoming long-distance travel | Unambiguous recommendation to cancel BC50 | `./scenarios/activate_scenario.sh 01_happy_path` |
| `02_edge_case` | Erratic usage; BC50 borderline break-even (±€5); possible Hamburg relocation; conflicting user goals | Hedged conditional recommendation — no single dominant action | `./scenarios/activate_scenario.sh 02_edge_case` |
| `03_failure_recovery` | 6 of 20 travel history entries are semantically malformed (null costs, empty mode, unknown mode value) | Pipeline completes with partial result and explicit data quality warnings | `./scenarios/activate_scenario.sh 03_failure_recovery` |

---

## Usage

Run from the `mobility_advisor/` directory:

```bash
./scenarios/activate_scenario.sh 01_happy_path
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

- `mobility_catalog.json` is identical in scenarios `01_happy_path` and `02_edge_case`. It is copied into each directory (not symlinked) so each scenario remains fully self-contained.
- All JSON files are valid and pass `python -m json.tool`. In scenario `03_failure_recovery`, the breakage in `travel_history.json` is **semantic** (null values, unrecognized mode strings), not syntactic.
- Do not modify files directly inside `scenarios/` subdirectories during a demo run — activate the scenario first, then let the agent read from `data/`.
- The `activate_scenario.sh` script always creates a timestamped backup before switching, so switching between scenarios is non-destructive.
