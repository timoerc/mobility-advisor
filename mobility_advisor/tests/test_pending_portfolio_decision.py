import json
import shutil
from datetime import date
from pathlib import Path

import pytest

import main
from mobility_advisor import tools

_SCENARIOS = Path(__file__).parent.parent / "scenarios"


@pytest.fixture
def maja(monkeypatch):
    monkeypatch.setattr(tools, "_DATA", _SCENARIOS / "maja")


@pytest.fixture
def stefan(monkeypatch):
    monkeypatch.setattr(tools, "_DATA", _SCENARIOS / "stefan")


@pytest.fixture
def lena(monkeypatch):
    monkeypatch.setattr(tools, "_DATA", _SCENARIOS / "lena")


def test_no_life_events_no_deferral(maja):
    # Maja has no life events at all — the gate must stay shut.
    result = tools.detect_pending_portfolio_decision()
    assert result == {"exists": False, "reason": "", "revisit_after": None, "events": []}


def test_non_reset_signals_no_deferral(lena):
    # Lena's only signals are ticket-relevance / non-mobility-spend changes — real life
    # events, but none reset the portfolio, so deferral must NOT fire. This is the guard
    # against spurious "hold pending a decision" output.
    result = tools.detect_pending_portfolio_decision()
    assert result["exists"] is False
    assert result["events"] == []


def test_pending_relocation_triggers_deferral(stefan):
    # Stefan has an upcoming relocation + job change (home_base_change / work_pattern_change),
    # both within the horizon of MOCK_TODAY (2026-06-15).
    result = tools.detect_pending_portfolio_decision()
    assert result["exists"] is True
    # revisit_after is the LAST qualifying event to take effect (job start 2026-09-01).
    assert result["revisit_after"] == "2026-09-01"
    assert len(result["events"]) == 2
    categories = {e["category"] for e in result["events"]}
    assert categories == {"relocation", "job_change"}
    assert "2026-09-01" in result["reason"]


def test_hold_row_injected_and_promoted_for_stefan(tmp_path, monkeypatch):
    # The regular (deterministic) pipeline no longer routes the pending-decision signal
    # through an LLM context bundle (load_optimizer_context, which this test used to
    # exercise, was removed with the deterministic optimizer) — the gate is now
    # deterministic post-processing in main.py: _build_alternatives_from_optimization()
    # injects a "Hold pending decision" row whenever detect_pending_portfolio_decision()
    # fires, and _enforce_hold_when_decision_pending() promotes it over whatever
    # optimize_all_categories() actually ranked #1. This seeds a synthetic
    # _optimization_results.json (standing in for a real optimize_all_categories() run)
    # against stefan's fixtures, whose life_events.json is known to trigger the gate
    # (see test_pending_relocation_triggers_deferral above).
    for f in (_SCENARIOS / "stefan").glob("*.json"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setattr(tools, "_DATA", tmp_path)
    monkeypatch.setattr(main, "_DATA", tmp_path)

    current_ids = ["db_bc50_2nd_annual_standard", "db_deutschlandticket", "miles_silber"]
    opt_results = {
        "status": "ok",
        "current_subscription_ids": current_ids,
        "scenarios": [
            {
                "status": "ok", "label": "Current", "category": "current",
                "subscription_ids": current_ids,
                "total_annual_cost_eur": 900.0, "total_annual_time_min": 1000.0,
                "total_annual_co2_kg": 200.0, "is_current": True, "is_recommended": False,
                "delta_cost_eur": 100.0, "delta_time_min": 0.0, "delta_co2_kg": 0.0,
            },
            {
                "status": "ok", "label": "BahnCard 25 (2. Klasse, Standard, Jahresabo)",
                "category": "rail", "subscription_ids": ["db_bc25_2nd_annual_standard"],
                "total_annual_cost_eur": 800.0, "total_annual_time_min": 1000.0,
                "total_annual_co2_kg": 200.0, "is_current": False, "is_recommended": True,
                "delta_cost_eur": 0.0, "delta_time_min": 0.0, "delta_co2_kg": 0.0,
            },
        ],
    }
    (tmp_path / "_optimization_results.json").write_text(json.dumps(opt_results), encoding="utf-8")

    alts = main._build_alternatives_from_optimization()
    hold_rows = [a for a in alts if a.id == "hold"]
    assert len(hold_rows) == 1, "gate is active for stefan — a Hold row must be injected"
    assert hold_rows[0].action is None
    assert not hold_rows[0].isRecommended  # not promoted yet — that's the next step's job

    rec = main.Recommendation(
        verdict="placeholder", confidence="medium", summaryText="", metrics=[],
        reasoning=[], alternatives=alts,
    )
    rec = main._enforce_hold_when_decision_pending(rec)

    hold = next(a for a in rec.alternatives if a.id == "hold")
    assert hold.isRecommended is True
    assert sum(a.isRecommended for a in rec.alternatives) == 1
    bc25 = next(a for a in rec.alternatives if a.id != "hold" and a.action is not None)
    assert bc25.isRecommended is False


def test_deferral_closes_once_events_are_in_the_past(stefan, monkeypatch):
    # Once today is past every qualifying event (the move has happened or been called off),
    # the gate shuts again — the setup should be re-optimized against the new reality, not held.
    monkeypatch.setattr(tools, "MOCK_TODAY", date(2026, 10, 1))
    assert tools.detect_pending_portfolio_decision()["exists"] is False


def test_deferral_not_triggered_when_decision_is_far_off(stefan, monkeypatch):
    # A reset event years away must not freeze the portfolio indefinitely.
    monkeypatch.setattr(tools, "MOCK_TODAY", date(2025, 1, 1))
    assert tools.detect_pending_portfolio_decision()["exists"] is False
