"""Coverage for backfill_translations() (api/recommendation/translation.py) — the lazy
translator that fills in a history entry's missing `_en`/`_de` sibling fields the first time
it's read in a language other than the one it was generated in.

Same fake-litellm pattern as test_json_extraction_parsing.py: monkeypatch
translation.litellm.acompletion so no real network/model call happens.
"""
import asyncio
import json

from mobility_advisor.api.recommendation import translation
from mobility_advisor.models import AnalysisHistoryEntry, Alternative, MetricDelta, Recommendation


class _FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


def _live_entry(entry_id: str = "hist_live") -> AnalysisHistoryEntry:
    rec = Recommendation(
        verdict="English verdict",
        confidence="medium",
        summaryText="English summary",
        metrics=[MetricDelta(value=10, unit="€/year", direction="save", label="Potential saving")],
        reasoning=["English reason"],
        alternatives=[
            Alternative(
                id="keep", name="Keep current setup", annualCostEur=100,
                savingsVsCurrentEur=0, tradeoff="No change", isRecommended=False, action=None,
            ),
            Alternative(
                id="switch", name="Switch", annualCostEur=80, savingsVsCurrentEur=20,
                tradeoff="Cheaper", isRecommended=True,
                action={"title": "Switch", "description": "Switch.", "consequence": "Switched."},
            ),
        ],
    )
    return AnalysisHistoryEntry.model_validate(
        {"id": entry_id, "date": "2026-01-01", "recommendation": rec, "language": "en"}
    )


def test_backfill_populates_missing_de_siblings(monkeypatch):
    entry = _live_entry()

    async def fake_acompletion(**kwargs):
        payload = json.loads(kwargs["messages"][1]["content"])
        assert "hist_live" in payload["entries"]
        result = {
            "entries": {
                "hist_live": {
                    "verdict": "Deutsches Urteil",
                    "summaryText": "Deutsche Zusammenfassung",
                    "reasoning": ["Deutscher Grund"],
                    "metrics": [{"index": 0, "label": "Mögliche Ersparnis"}],
                    "alternatives": [
                        {"id": "switch", "name": "Wechseln", "tradeoff": "Günstiger",
                         "action": {"title": "Wechseln", "description": "Wechseln.", "consequence": "Gewechselt."}},
                    ],
                }
            }
        }
        return _FakeResponse(json.dumps(result))

    monkeypatch.setattr(translation.litellm, "acompletion", fake_acompletion)

    changed = asyncio.run(translation.backfill_translations([entry], "de"))

    assert changed is True
    assert entry.recommendation.verdict_de == "Deutsches Urteil"
    assert entry.recommendation.verdict == "English verdict"  # base field untouched
    assert entry.recommendation.metrics[0].label_de == "Mögliche Ersparnis"
    switch = next(a for a in entry.recommendation.alternatives if a.id == "switch")
    assert switch.name_de == "Wechseln"
    assert switch.action.title_de == "Wechseln"
    # "keep" had nothing requiring translation beyond what a full round trip would ask for in
    # this fake response — untouched fields must not error.
    keep = next(a for a in entry.recommendation.alternatives if a.id == "keep")
    assert keep.name_de is None


def test_backfill_is_a_noop_when_nothing_pending(monkeypatch):
    entry = _live_entry()
    entry.recommendation.verdict_de = "already there"

    called = False

    async def fake_acompletion(**kwargs):
        nonlocal called
        called = True
        return _FakeResponse("{}")

    monkeypatch.setattr(translation.litellm, "acompletion", fake_acompletion)

    # Populate every other pending field too, so _collect_pending returns nothing at all.
    entry.recommendation.summaryText_de = "x"
    entry.recommendation.reasoning_de = ["x"]
    entry.recommendation.metrics[0].label_de = "x"
    for alt in entry.recommendation.alternatives:
        alt.name_de = "x"
        alt.tradeoff_de = "x"
        if alt.action is not None:
            alt.action.title_de = "x"
            alt.action.description_de = "x"
            alt.action.consequence_de = "x"

    changed = asyncio.run(translation.backfill_translations([entry], "de"))

    assert changed is False
    assert called is False


def test_backfill_never_raises_on_llm_failure(monkeypatch):
    entry = _live_entry()

    async def fake_acompletion(**kwargs):
        raise RuntimeError("simulated LLM outage")

    monkeypatch.setattr(translation.litellm, "acompletion", fake_acompletion)

    changed = asyncio.run(translation.backfill_translations([entry], "de"))

    assert changed is False
    assert entry.recommendation.verdict_de is None
    assert entry.recommendation.verdict == "English verdict"


def test_backfill_never_raises_on_malformed_llm_response(monkeypatch):
    entry = _live_entry()

    async def fake_acompletion(**kwargs):
        return _FakeResponse("not json at all")

    monkeypatch.setattr(translation.litellm, "acompletion", fake_acompletion)

    changed = asyncio.run(translation.backfill_translations([entry], "de"))

    assert changed is False
    assert entry.recommendation.verdict_de is None


def test_backfill_skips_entries_already_in_the_target_language():
    entry = _live_entry()
    entry.language = "de"

    changed = asyncio.run(translation.backfill_translations([entry], "de"))

    assert changed is False


def test_merge_entry_siblings_fills_only_missing_fields():
    dst = _live_entry("hist_a")
    src = _live_entry("hist_a")
    src.recommendation.verdict_de = "Deutsches Urteil"
    src.recommendation.metrics[0].label_de = "Mögliche Ersparnis"
    dst.recommendation.verdict_de = "already set, must survive"

    translation.merge_entry_siblings(dst, src, "de")

    assert dst.recommendation.verdict_de == "already set, must survive"
    assert dst.recommendation.metrics[0].label_de == "Mögliche Ersparnis"
