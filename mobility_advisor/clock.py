"""The app's notion of "today" — frozen to the active persona's fixture date, not the
host machine's real clock, so mock scenarios stay reproducible.

Sourced from persona.json's "reference_date" (single source of truth, swapped in
whenever a scenario is activated) so the fixtures and the app's notion of "today" can't
drift apart.
"""
import json
from datetime import date

from . import paths

_DEFAULT_REFERENCE_DATE = date(2026, 6, 15)


def _load_reference_date() -> date:
    try:
        raw = json.loads((paths.DATA_DIR / "persona.json").read_text(encoding="utf-8"))
        return date.fromisoformat(raw["reference_date"])
    except (FileNotFoundError, KeyError, ValueError):
        return _DEFAULT_REFERENCE_DATE


MOCK_TODAY = _load_reference_date()
REVIEW_YEAR = MOCK_TODAY.year - 1  # annual report always covers the last full calendar year
