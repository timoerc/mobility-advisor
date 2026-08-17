#!/bin/bash
# Usage: ./scenarios/activate_scenario.sh <scenario_name>
# Example: ./scenarios/activate_scenario.sh maja
#
# Thin wrapper over the scenarios.activate CLI (mobility_advisor/scenarios/activate.py),
# which backs up the current data/ directory, then copies the chosen scenario's JSON
# fixtures into data/, making it the active scenario.
# Available scenarios: maja, stefan, lena, katrin, tobias, sofia

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$REPO_ROOT"
exec uv run python -m mobility_advisor.scenarios.activate "$@"
