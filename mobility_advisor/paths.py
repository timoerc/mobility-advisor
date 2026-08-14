"""Single source of truth for every filesystem location and file-list the app touches.

Previously `_DATA`/`_STATIC` were independently defined in tools.py, main.py, and
sub_agents.py (as `_DATA_DIR`), so a test isolating a run had to monkeypatch two or three
module-level names for what is really one path. Every reader of these paths must access
them through this module at call time (`from . import paths` ... `paths.DATA_DIR / ...`),
never via `from .paths import DATA_DIR` — a bound import can't be monkeypatched and
breaks both test isolation and scenario switching.
"""
import json
import os
import tempfile
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parent

DATA_DIR = PACKAGE_ROOT / "data"
STATIC_DIR = PACKAGE_ROOT / "static"
SCENARIOS_DIR = PACKAGE_ROOT / "scenarios"
TEMPLATES_DIR = PACKAGE_ROOT / "reporting" / "templates"

# The full set of fixture files a scenario/profile activation copies into DATA_DIR.
SCENARIO_FILES = [
    "persona.json",
    "current_subscriptions.json",
    "travel_history_raw.json",
    "mail_raw.json",
    "calendar_events_live.json",
    "car_usage.json",
    "analysis_history.json",
    "life_events.json",
]

# Scratch files the deterministic trip-projection/optimization engine (engine/) writes
# during a pipeline run and api/recommendation/builder.py reads back. Regenerated on every
# analysis run — never fixture data, never meant to be committed (see .gitignore).
SCRATCH_FILES = [
    "_projected_trips_history.json",
    "_projected_trips_calendar.json",
    "_projected_trips_car_usage.json",
    "_projected_trips_merged.json",
    "_optimization_results.json",
]


def known_personas() -> frozenset[str]:
    """The set of pre-built scenario personas, derived from scenarios/ subdirectories
    rather than a hardcoded literal that has to be kept in sync with them by hand."""
    return frozenset(
        p.name for p in SCENARIOS_DIR.iterdir() if p.is_dir() and (p / "persona.json").exists()
    )


def clear_scratch_files() -> None:
    """Delete this run's scratch files before the pipeline executes.

    Without this, a stale _optimization_results.json from a previous run (a different
    persona, or an earlier request in the same persona) stays on disk untouched by
    persona activation (store.scenarios.activate_scenario only copies scenario JSON in,
    never clears these) and by a failed run (engine.optimizer.optimize_all_categories()'s
    error paths return before writing the file). The alternatives-builder would then
    silently read that stale file — with no freshness check — and serve a previous run's
    (possibly a different persona's) alternatives as if they were this run's. Deleting
    first makes "file absent" mean exactly what it should: this run's Optimizer agent
    did not (yet, or at all) call optimize_all_categories(), which correctly triggers the
    LLM-extraction fallback instead of serving contaminated data.
    """
    for fname in SCRATCH_FILES:
        (DATA_DIR / fname).unlink(missing_ok=True)


def atomic_write_json(path: Path, data: dict) -> None:
    """Write data as JSON to path atomically (temp file + os.replace); never leaves a
    partial file on disk if the write is interrupted."""
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
