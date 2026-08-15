"""End-to-end coverage for GET /api/analysis-history's translation backfill wiring — the part
test_translation_backfill.py doesn't reach: the route itself calling backfill_translations(),
persisting the result under history_lock via merge_entry_siblings(), and a second request
against the same (now-translated) file making zero LLM calls.
"""
import asyncio
import json

from fastapi.testclient import TestClient

import main as main_module
from mobility_advisor import paths
from mobility_advisor.api.recommendation import translation


def _seed_live_english_entry(tmp_path) -> None:
    entry = {
        "id": "hist_live_en",
        "date": "2026-01-01",
        "language": "en",
        "outcome": "pending",
        "recommendation": {
            "verdict": "English verdict",
            "confidence": "medium",
            "summaryText": "English summary",
            "metrics": [{"value": 10, "unit": "€/year", "direction": "save", "label": "Potential saving"}],
            "reasoning": ["English reason"],
            "assumptions": [],
            "alternatives": [
                {
                    "id": "keep", "name": "Keep current setup", "annualCostEur": 100,
                    "savingsVsCurrentEur": 0, "tradeoff": "No change", "isRecommended": False,
                    "action": None,
                },
                {
                    "id": "switch", "name": "Switch", "annualCostEur": 80,
                    "savingsVsCurrentEur": 20, "tradeoff": "Cheaper", "isRecommended": True,
                    "action": {"title": "Switch", "description": "Switch.", "consequence": "Switched."},
                },
            ],
        },
    }
    (tmp_path / "analysis_history.json").write_text(json.dumps({"entries": [entry]}), encoding="utf-8")


def test_history_route_backfills_and_persists_then_stays_quiet(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    _seed_live_english_entry(tmp_path)

    call_count = 0

    async def fake_acompletion(**kwargs):
        nonlocal call_count
        call_count += 1
        payload = json.loads(kwargs["messages"][1]["content"])
        assert "hist_live_en" in payload["entries"]
        # Every field _collect_pending asked for must come back translated — an incomplete
        # response (e.g. the model silently drops the "keep" alternative) is intentionally
        # NOT cached as "good enough": _collect_pending finds it still missing on the next
        # read and asks again, so a translation gap gets retried rather than permanently
        # accepted. This fake response is deliberately complete so this test exercises the
        # "fully cached, zero further calls" steady state instead of that retry path.
        result = {
            "entries": {
                "hist_live_en": {
                    "verdict": "Deutsches Urteil",
                    "summaryText": "Deutsche Zusammenfassung",
                    "reasoning": ["Deutscher Grund"],
                    "metrics": [{"index": 0, "label": "Mögliche Ersparnis"}],
                    "alternatives": [
                        {"id": "keep", "name": "Aktuelles Setup beibehalten", "tradeoff": "Keine Änderung"},
                        {"id": "switch", "name": "Wechseln", "tradeoff": "Günstiger",
                         "action": {"title": "Wechseln", "description": "Wechseln.", "consequence": "Gewechselt."}},
                    ],
                }
            }
        }
        return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": json.dumps(result)})()})()]})()

    monkeypatch.setattr(translation.litellm, "acompletion", fake_acompletion)

    client = TestClient(main_module.app)

    first = client.get("/api/analysis-history", headers={"X-Language": "de"})
    assert first.status_code == 200
    body = first.json()
    assert body[0]["recommendation"]["verdict"] == "Deutsches Urteil"
    assert call_count == 1

    # Persisted to disk: verdict_de survives a fresh load_history(), not just the in-memory
    # response object.
    on_disk = json.loads((tmp_path / "analysis_history.json").read_text(encoding="utf-8"))
    assert on_disk["entries"][0]["recommendation"]["verdict_de"] == "Deutsches Urteil"
    # Base (English) field must be untouched on disk.
    assert on_disk["entries"][0]["recommendation"]["verdict"] == "English verdict"

    # Second request in the same language: everything needed is now cached — no LLM call.
    second = client.get("/api/analysis-history", headers={"X-Language": "de"})
    assert second.status_code == 200
    assert second.json()[0]["recommendation"]["verdict"] == "Deutsches Urteil"
    assert call_count == 1

    # Flipping back to English serves the untouched original, still with no LLM call needed.
    third = client.get("/api/analysis-history", headers={"X-Language": "en"})
    assert third.json()[0]["recommendation"]["verdict"] == "English verdict"
    assert call_count == 1
