#!/bin/bash
# Usage: ./scenarios/activate_scenario.sh <scenario_name>
# Example: ./scenarios/activate_scenario.sh maja
#
# Backs up the current data/ directory, then copies the chosen scenario's
# JSON fixtures into data/, making it the active scenario.
# Available scenarios: maja, stefan, lena, katrin, tobias, sofia

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $(basename "$0") <scenario_name>"
    echo ""
    echo "Available scenarios:"
    SCRIPT_DIR_TEMP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    for d in "$SCRIPT_DIR_TEMP"/*/; do
        [[ -d "$d" ]] && basename "$d"
    done
    exit 1
fi

SCENARIO_NAME="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIO_DIR="$SCRIPT_DIR/$SCENARIO_NAME"
DATA_DIR="$(dirname "$SCRIPT_DIR")/data"

if [[ ! -d "$SCENARIO_DIR" ]]; then
    echo "Error: scenario not found: $SCENARIO_DIR"
    echo ""
    echo "Available scenarios:"
    for d in "$SCRIPT_DIR"/*/; do
        [[ -d "$d" ]] && basename "$d"
    done
    exit 1
fi

if [[ ! -d "$DATA_DIR" ]]; then
    echo "Error: data directory not found: $DATA_DIR"
    exit 1
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$(dirname "$SCRIPT_DIR")/data_backup_$TIMESTAMP"

echo "Backing up $DATA_DIR -> $BACKUP_DIR"
cp -r "$DATA_DIR" "$BACKUP_DIR"

echo "Activating scenario: $SCENARIO_NAME"
cp "$SCENARIO_DIR"/*.json "$DATA_DIR/"

echo ""
echo "Active scenario : $SCENARIO_NAME"
echo "Data directory  : $DATA_DIR"
echo "Backup saved to : $BACKUP_DIR"
