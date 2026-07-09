#!/usr/bin/env python3
"""Rebuild scenario persona.json & current_subscriptions.json from persona_full.json.

Usage:
    python scripts/rebuild_mock_scenarios.py

Reads (per scenario):
    mobility_advisor/scenarios/{id}/persona_full.json   – single source of truth
    mobility_advisor/data/mobility_catalog_new.json     – catalog to merge by subscription id

Writes (per scenario):
    mobility_advisor/scenarios/{id}/persona.json              – profile without subscriptions
    mobility_advisor/scenarios/{id}/current_subscriptions.json – subscriptions merged with catalog
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "mobility_advisor" / "data" / "mobility_catalog_new.json"
SCENARIOS_DIR = ROOT / "mobility_advisor" / "scenarios"


def _load_catalog_lookup() -> dict[str, dict]:
    if not CATALOG_PATH.exists():
        print(f"WARNING: catalog not found at {CATALOG_PATH}", file=sys.stderr)
        return {}
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {opt["id"]: opt for opt in catalog.get("options", [])}


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    catalog = _load_catalog_lookup()
    written = 0

    for full_path in sorted(SCENARIOS_DIR.glob("*/persona_full.json")):
        full = json.loads(full_path.read_text(encoding="utf-8"))
        pid = full["id"]
        scenario_dir = full_path.parent

        # --- persona.json: everything except subscriptions ---
        persona = json.loads(json.dumps(full))
        persona["profileData"].pop("subscriptions", None)
        _write_json(scenario_dir / "persona.json", persona)

        # --- current_subscriptions.json: merge with catalog ---
        subs = []
        for s in full["profileData"].get("subscriptions", []):
            entry = {
                "id": s["id"],
                "next_renewal_date": s["next_renewal_date"],
                "started": s["started"],
            }
            if s["id"] in catalog:
                entry.update(catalog[s["id"]])
            else:
                print(f"  WARNING: '{s['id']}' not found in catalog, skipping enrichment", file=sys.stderr)
            subs.append(entry)

        _write_json(scenario_dir / "current_subscriptions.json", {"subscriptions": subs})

        print(f"  {pid}: persona.json + current_subscriptions.json ({len(subs)} subs)")
        written += 1

    if written == 0:
        print("No persona_full.json files found in scenarios/", file=sys.stderr)
        sys.exit(1)

    print(f"\nDone — rebuilt {written} scenarios.")


if __name__ == "__main__":
    main()
