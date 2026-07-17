from datetime import date
from pathlib import Path

import pytest

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


def test_deferral_signal_rides_in_optimizer_bundle(stefan):
    # The Optimizer reads this through load_optimizer_context, not a separate call.
    bundle = tools.load_optimizer_context()
    assert bundle["pending_portfolio_decision"] == tools.detect_pending_portfolio_decision()


def test_deferral_closes_once_events_are_in_the_past(stefan, monkeypatch):
    # Once today is past every qualifying event (the move has happened or been called off),
    # the gate shuts again — the setup should be re-optimized against the new reality, not held.
    monkeypatch.setattr(tools, "MOCK_TODAY", date(2026, 10, 1))
    assert tools.detect_pending_portfolio_decision()["exists"] is False


def test_deferral_not_triggered_when_decision_is_far_off(stefan, monkeypatch):
    # A reset event years away must not freeze the portfolio indefinitely.
    monkeypatch.setattr(tools, "MOCK_TODAY", date(2025, 1, 1))
    assert tools.detect_pending_portfolio_decision()["exists"] is False
