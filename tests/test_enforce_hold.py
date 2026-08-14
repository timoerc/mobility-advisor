from pathlib import Path

import pytest

from mobility_advisor import paths
from mobility_advisor.api.recommendation import finalize
from mobility_advisor.models import Alternative, ProposedAction, Recommendation

_SCENARIOS = Path(__file__).parent.parent / "mobility_advisor" / "scenarios"


def _keep():
    return Alternative(
        id="keep", name="Keep current setup", annualCostEur=1120.0,
        savingsVsCurrentEur=0.0, tradeoff="No change.", isRecommended=False, action=None,
    )


def _hold(recommended=False):
    return Alternative(
        id="hold", name="Hold pending decision", annualCostEur=1120.0,
        savingsVsCurrentEur=0.0, tradeoff="Avoids a change the move could reverse.",
        isRecommended=recommended, action=None,
    )


def _cancel(recommended=False):
    return Alternative(
        id="cancel", name="Cancel Deutschland-Ticket", annualCostEur=364.0,
        savingsVsCurrentEur=756.0, tradeoff="Lose regional rail.", isRecommended=recommended,
        action=ProposedAction(title="Cancel", description="d", consequence="c"),
    )


def _rec(alternatives):
    return Recommendation(
        verdict="Cancel Deutschland-Ticket to save €756/year",
        confidence="high",
        summaryText="Cancelling saves €63/mo.",
        metrics=[],
        reasoning=["r"],
        alternatives=alternatives,
    )


@pytest.fixture
def stefan(monkeypatch):
    monkeypatch.setattr(paths, "DATA_DIR", _SCENARIOS / "stefan")


@pytest.fixture
def maja(monkeypatch):
    monkeypatch.setattr(paths, "DATA_DIR", _SCENARIOS / "maja")


def test_promotes_hold_when_decision_pending(stefan):
    rec = _rec([_keep(), _cancel(recommended=True), _hold(recommended=False)])
    out = finalize.enforce_hold_when_decision_pending(rec)
    recommended = [a for a in out.alternatives if a.isRecommended]
    assert len(recommended) == 1
    assert recommended[0].id == "hold"
    assert out.confidence == "low"
    assert "2026-09-01" in out.verdict
    # the concrete change survives as a visible, non-recommended alternative
    assert any(a.id == "cancel" and not a.isRecommended for a in out.alternatives)


def test_no_op_without_pending_decision(maja):
    # Maja has no portfolio-resetting life event → the override must not touch the pipeline's
    # own recommendation.
    rec = _rec([_keep(), _cancel(recommended=True)])
    out = finalize.enforce_hold_when_decision_pending(rec)
    recommended = [a for a in out.alternatives if a.isRecommended]
    assert recommended[0].id == "cancel"
    assert out.confidence == "high"


def test_no_op_when_hold_already_recommended(stefan):
    rec = _rec([_keep(), _cancel(recommended=False), _hold(recommended=True)])
    before = rec.verdict
    out = finalize.enforce_hold_when_decision_pending(rec)
    assert out.verdict == before  # untouched — already correct
    assert [a for a in out.alternatives if a.isRecommended][0].id == "hold"


def test_promotes_hold_by_id_even_with_translated_name(stefan):
    # The hold row is matched on id alone (see api/recommendation/finalize.py's
    # enforce_hold_when_decision_pending),
    # not on an English name substring — so a German-language recommendation, whose alternative
    # name is not the English "Hold pending decision" string, must still be promoted correctly.
    translated_hold = Alternative(
        id="hold", name="Entscheidung zurückstellen", annualCostEur=1120.0,
        savingsVsCurrentEur=0.0, tradeoff="Vermeidet eine Änderung, die der Umzug rückgängig machen könnte.",
        isRecommended=False, action=None,
    )
    rec = _rec([_keep(), _cancel(recommended=True), translated_hold])
    out = finalize.enforce_hold_when_decision_pending(rec)
    recommended = [a for a in out.alternatives if a.isRecommended]
    assert len(recommended) == 1
    assert recommended[0].id == "hold"
    assert out.confidence == "low"


def test_does_not_promote_english_name_with_different_id(stefan):
    # Intentional narrowing (see finalize.py comment): a row that merely happens to be *named*
    # "Hold pending decision" but carries a different id must NOT be promoted. Only the
    # deterministic pending-decision id="hold" row is eligible.
    lookalike = Alternative(
        id="cancel_alt", name="Hold pending decision", annualCostEur=1120.0,
        savingsVsCurrentEur=0.0, tradeoff="t", isRecommended=False, action=None,
    )
    rec = _rec([_keep(), _cancel(recommended=True), lookalike])
    out = finalize.enforce_hold_when_decision_pending(rec)
    recommended = [a for a in out.alternatives if a.isRecommended]
    assert len(recommended) == 1
    assert recommended[0].id == "cancel"  # unchanged — the lookalike was not promoted
