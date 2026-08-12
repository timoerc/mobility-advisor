"""Scenario/profile activation — the one implementation of "copy a persona's fixture
files into data/ and clear stale scratch files", shared by the API's /api/activate and
/api/profile endpoints and by scenarios/activate.py's standalone CLI (which used to
duplicate this logic in shell)."""
import shutil

from .. import paths


def activate_scenario(persona_id: str) -> bool:
    """Copy all pipeline JSON files from scenarios/{persona_id}/ into data/.

    Also clears the derived _projected_trips_*/_optimization_results.json scratch files
    (see paths.clear_scratch_files) — without this, switching personas left the PREVIOUS
    persona's projected trips and optimization results sitting in data/, readable by the
    alternatives-builder with no freshness check, until something happened to regenerate
    them. A stale file "looking valid" is worse than one that's simply absent, since
    absence correctly triggers the LLM-extraction fallback instead of silently serving a
    different persona's numbers.

    Returns False (no write performed) if persona_id has no scenarios/ directory.
    """
    scenario_dir = paths.SCENARIOS_DIR / persona_id
    if not scenario_dir.is_dir():
        return False
    for fname in paths.SCENARIO_FILES:
        src = scenario_dir / fname
        if src.exists():
            shutil.copy2(src, paths.DATA_DIR / fname)
    paths.clear_scratch_files()
    return True
