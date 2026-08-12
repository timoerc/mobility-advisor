"""Reads and writes of analysis_history.json — the log of past pipeline runs and what
the user decided about each one."""
import json

from pydantic import ValidationError

from .. import paths
from ..models import AnalysisHistory


def load_recommendation_history(limit: int = 3) -> dict:
    """Load a compact summary of the user's most recent past analysis recommendations and outcomes.

    Use this to give continuity to a new review — e.g. noting that this is the Nth review
    flagging the same subscription, and what the user decided last time — instead of
    re-analyzing cold every run.

    Returns a dict with key 'history', a list of up to the `limit` most recent entries
    (oldest first, newest last), each containing: date (str), verdict (str, that review's
    headline finding), outcome (str: pending/kept_current/executed), and recommended_action
    (str, the name of the alternative that review marked as recommended). Deliberately
    excludes full Recommendation/Alternative objects (metrics, reasoning, non-recommended
    alternatives) to keep this small. Returns an empty list if no analysis history exists yet
    (e.g. a brand-new persona) — that is a legitimate result, not a loading failure.
    """
    path = paths.DATA_DIR / "analysis_history.json"
    if not path.exists():
        return {"history": []}
    raw = json.loads(path.read_text())
    entries = AnalysisHistory.model_validate(raw).entries[-limit:]
    history = []
    for entry in entries:
        recommended = next(
            (alt for alt in entry.recommendation.alternatives if alt.isRecommended), None
        )
        history.append({
            "date": entry.date,
            "verdict": entry.recommendation.verdict,
            "outcome": entry.outcome,
            "recommended_action": recommended.name if recommended else "",
        })
    return {"history": history}


def load_history() -> AnalysisHistory:
    """Load the full analysis history as typed AnalysisHistoryEntry objects (unlike
    load_recommendation_history's compact summary dict) — used by the API layer to
    append/resolve/revert entries."""
    path = paths.DATA_DIR / "analysis_history.json"
    if not path.exists():
        return AnalysisHistory(entries=[])
    try:
        return AnalysisHistory.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError):
        return AnalysisHistory(entries=[])


def save_history(hist: AnalysisHistory) -> None:
    paths.atomic_write_json(paths.DATA_DIR / "analysis_history.json", hist.model_dump())
