"""Tests for main.py's _parse_json_response()/_normalize_confidence_and_lists() — the
brace-scan JSON extraction and confidence/list normalization shared by _extract_verdict()
and _extract_recommendation_json() (see B3 in the pipeline-foundation audit)."""

import asyncio
import json
from pathlib import Path

import pytest

import main
from mobility_advisor import tools

_SCENARIOS = Path(__file__).parent.parent / "scenarios"


# ── _parse_json_response: tolerant brace-scan extraction ───────────────────────────


def test_parses_bare_json():
    assert main._parse_json_response('{"a": 1}') == {"a": 1}


def test_parses_leading_fenced_json():
    text = '```json\n{"a": 1}\n```'
    assert main._parse_json_response(text) == {"a": 1}


def test_parses_fence_with_preamble():
    # The bug this replaces: a startswith("```") check is defeated by any text before the
    # fence, which GPT-OSS-120B (a reasoning model) produces more often than not.
    text = 'Here is the JSON:\n```json\n{"a": 1}\n```'
    assert main._parse_json_response(text) == {"a": 1}


def test_parses_fence_with_trailing_commentary():
    text = '```json\n{"a": 1}\n```\nLet me know if you need anything else.'
    assert main._parse_json_response(text) == {"a": 1}


def test_parses_uppercase_json_label():
    # The old code's exact `text.startswith("json")` check (after stripping the fence)
    # missed a "JSON" or " json" label variant.
    text = '```JSON\n{"a": 1}\n```'
    assert main._parse_json_response(text) == {"a": 1}


def test_parses_object_with_nested_braces():
    text = 'prose\n{"a": {"b": 2}, "c": [1, 2]}\nmore prose'
    assert main._parse_json_response(text) == {"a": {"b": 2}, "c": [1, 2]}


def test_no_braces_raises_json_decode_error():
    with pytest.raises(json.JSONDecodeError):
        main._parse_json_response("just some plain text, no JSON at all")


# ── _normalize_confidence_and_lists ─────────────────────────────────────────────────


def test_confidence_lowercased():
    parsed = main._normalize_confidence_and_lists({"confidence": "HIGH"})
    assert parsed["confidence"] == "high"


def test_confidence_synonym_falls_back_to_medium():
    parsed = main._normalize_confidence_and_lists({"confidence": "moderate"})
    assert parsed["confidence"] == "medium"


def test_confidence_missing_defaults_to_medium():
    parsed = main._normalize_confidence_and_lists({})
    assert parsed["confidence"] == "medium"


def test_reasoning_and_assumptions_string_coerced_to_list():
    parsed = main._normalize_confidence_and_lists({
        "reasoning": "single bullet as a plain string",
        "assumptions": "single assumption as a plain string",
    })
    assert parsed["reasoning"] == ["single bullet as a plain string"]
    assert parsed["assumptions"] == ["single assumption as a plain string"]


def test_reasoning_list_left_untouched():
    parsed = main._normalize_confidence_and_lists({"reasoning": ["a", "b"]})
    assert parsed["reasoning"] == ["a", "b"]


# ── _parse_verdict_response: empty-string-vs-missing-key handling ──────────────────


def test_empty_verdict_and_summary_text_are_dropped():
    text = (
        '{"verdict": "", "confidence": "HIGH", "summaryText": "", '
        '"reasoning": ["r1"], "assumptions": []}'
    )
    result = main._parse_verdict_response(text)
    # Empty strings must not survive — verdict.get("verdict", fallback) at the call site
    # only catches a MISSING key, not "", so an empty string here would render as a blank
    # dashboard headline instead of falling back to the recommended alternative's name.
    assert "verdict" not in result
    assert "summaryText" not in result
    assert result["confidence"] == "high"


def test_non_empty_verdict_and_summary_text_survive():
    text = '{"verdict": "Switch to BC25", "summaryText": "Saves money.", "confidence": "low"}'
    result = main._parse_verdict_response(text)
    assert result["verdict"] == "Switch to BC25"
    assert result["summaryText"] == "Saves money."


# ── _extract_recommendation_json: B5's rewritten fallback prompt/parsing round-trip ─


class _FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


def test_extract_recommendation_json_round_trips_two_alternative_shape(monkeypatch):
    # B5 regression: _JSON_SYSTEM_PROMPT was rewritten against communicator_agent's actual
    # Verdict/Confidence/Summary/Reasoning/Assumptions report format, which only ever
    # describes ONE recommended option (no "Option:" blocks the old prompt assumed) — so
    # the fallback path now asks for exactly two alternatives: "recommended" (non-null
    # action) and "keep" (null action). This checks that a completion in the new shape
    # parses into a valid Recommendation end to end, through _extract_recommendation_json's
    # full pipeline (brace-scan -> normalize -> Recommendation.model_validate ->
    # _normalize_keep_current_setup -> _enforce_hold_when_decision_pending ->
    # _clamp_actionable_alternatives).
    monkeypatch.setattr(tools, "_DATA", _SCENARIOS / "maja")  # no pending decision, no-op gate
    monkeypatch.setattr(main, "_DATA", _SCENARIOS / "maja")

    fake_json = json.dumps({
        "verdict": "Switch to BahnCard 25 saves money",
        "confidence": "HIGH",  # deliberately uppercase — normalization must lowercase it
        "summaryText": "BahnCard 25 saves €249/year over your current BahnCard 50.",
        "metrics": [],
        "reasoning": "single string bullet instead of a list",  # must be coerced to a list
        "assumptions": [],
        "alternatives": [
            {
                "id": "recommended",
                "name": "Switch to BahnCard 25 (2. Klasse, Standard, Jahresabo)",
                "annualCostEur": 1162.61,
                "savingsVsCurrentEur": 249.0,
                "co2Impact": "Neutral",
                "co2ImpactKg": 0,
                "tradeoff": "Cheaper, same CO2.",
                "isRecommended": True,
                "action": {
                    "title": "Switch to BahnCard 25 (2. Klasse, Standard, Jahresabo)",
                    "description": "Cancel BahnCard 50 and start BahnCard 25 instead.",
                    "consequence": "Your BahnCard 50 (2. Klasse, Standard, Jahresabo) will "
                                    "be cancelled and BahnCard 25 (2. Klasse, Standard, "
                                    "Jahresabo) will start in its place.",
                },
            },
            {
                "id": "keep",
                "name": "Keep current setup",
                "annualCostEur": 1411.61,
                "savingsVsCurrentEur": 0,
                "co2Impact": "Neutral",
                "co2ImpactKg": 0,
                "tradeoff": "No change to cost or emissions",
                "isRecommended": False,
                "action": None,
            },
        ],
    })

    async def fake_acompletion(**kwargs):
        # Wrap in a leading-preamble + fence, exercising _parse_json_response's brace-scan
        # rather than a bare JSON string.
        return _FakeResponse(f"Here is the JSON:\n```json\n{fake_json}\n```")

    monkeypatch.setattr(main.litellm, "acompletion", fake_acompletion)

    rec = asyncio.run(main._extract_recommendation_json("some report text"))

    assert len(rec.alternatives) == 2
    assert rec.confidence == "high"
    assert isinstance(rec.reasoning, list)
    assert rec.reasoning == ["single string bullet instead of a list"]
    recommended = next(a for a in rec.alternatives if a.isRecommended)
    assert recommended.id == "recommended"
    assert recommended.action is not None
    keep = next(a for a in rec.alternatives if a.id == "keep")
    assert keep.action is None
    assert keep.isRecommended is False


# ── _finalize_recommendation: E-section, catches corruption the mutation chain misses ──


def test_finalize_recommendation_round_trip_catches_corruption_from_a_mutator(monkeypatch):
    # Recommendation has no validate_assignment=True, and two of the three post-construction
    # mutators (_normalize_keep_current_setup, _clamp_actionable_alternatives in the common
    # under-cap case) never reassign any of Recommendation's own top-level fields — they
    # only mutate nested Alternative objects' fields in place, or (for
    # _enforce_hold_when_decision_pending) return early with no reassignment at all when no
    # pending decision exists, which is the ordinary case. None of that would trigger
    # revalidation even if Recommendation DID have validate_assignment=True. This proves the
    # explicit model_dump()/model_validate() round trip in _finalize_recommendation is what
    # actually catches a corrupted invariant, not incidental reassignment side effects.
    from mobility_advisor.models import Alternative

    keep = Alternative(
        id="keep", name="Keep current setup", annualCostEur=100.0,
        savingsVsCurrentEur=0.0, tradeoff="No change.", isRecommended=False, action=None,
    )
    change = Alternative(
        id="change", name="Switch", annualCostEur=80.0, savingsVsCurrentEur=20.0,
        tradeoff="Cheaper.", isRecommended=True,
        action=main.ProposedAction(title="t", description="d", consequence="c"),
    )
    rec = main.Recommendation(
        verdict="v", confidence="medium", summaryText="s", metrics=[],
        reasoning=["r"], alternatives=[keep, change],
    )

    def _corrupt(rec):
        # Simulate a buggy mutator: mark a SECOND alternative as recommended by mutating
        # the nested object in place — exactly the kind of change
        # _normalize_keep_current_setup's own loop performs, and exactly the kind
        # validate_assignment=True on Recommendation itself would NOT catch.
        rec.alternatives[0].isRecommended = True
        return rec

    monkeypatch.setattr(main, "_normalize_keep_current_setup", _corrupt)
    monkeypatch.setattr(main, "_enforce_hold_when_decision_pending", lambda r: r)
    monkeypatch.setattr(main, "_clamp_actionable_alternatives", lambda r: r)

    with pytest.raises(Exception, match="isRecommended"):
        main._finalize_recommendation(rec)
