"""CLI wrapper over store.scenarios.activate_scenario — the one implementation of
"copy a persona's fixture files into data/ and clear stale scratch files", shared with
the API's /api/activate and /api/profile endpoints.

Usage: uv run python -m mobility_advisor.scenarios.activate <scenario_name>

Backs up the current data/ directory to a timestamped folder before overwriting it,
same as the old shell script.
"""
import shutil
import sys
from datetime import datetime

from .. import paths
from ..store.scenarios import activate_scenario


def main(argv: list[str]) -> int:
    available = sorted(paths.known_personas())
    if len(argv) != 2:
        print(f"Usage: {argv[0] if argv else 'activate.py'} <scenario_name>")
        print("\nAvailable scenarios:")
        for name in available:
            print(f"  {name}")
        return 1

    scenario_name = argv[1]
    scenario_dir = paths.SCENARIOS_DIR / scenario_name
    if not scenario_dir.is_dir():
        print(f"Error: scenario not found: {scenario_dir}")
        print("\nAvailable scenarios:")
        for name in available:
            print(f"  {name}")
        return 1

    if not paths.DATA_DIR.is_dir():
        print(f"Error: data directory not found: {paths.DATA_DIR}")
        return 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = paths.PACKAGE_ROOT / f"data_backup_{timestamp}"
    print(f"Backing up {paths.DATA_DIR} -> {backup_dir}")
    shutil.copytree(paths.DATA_DIR, backup_dir)

    print(f"Activating scenario: {scenario_name}")
    activate_scenario(scenario_name)

    print()
    print(f"Active scenario : {scenario_name}")
    print(f"Data directory  : {paths.DATA_DIR}")
    print(f"Backup saved to : {backup_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
