import pytest
from pydantic import ValidationError

from mobility_advisor.models import Alternative, ProposedAction, Recommendation

_KEEP = Alternative(
    id="keep",
    name="Keep current setup",
    annualCostEur=1120.0,
    savingsVsCurrentEur=0.0,
    tradeoff="No change.",
    isRecommended=False,
    action=None,
)


def _rec(alternatives):
    return Recommendation(
        verdict="v",
        confidence="low",
        summaryText="s",
        metrics=[],
        reasoning=["r"],
        alternatives=alternatives,
    )


def test_recommended_hold_no_op_is_accepted():
    # A deliberate "Hold pending decision" recommendation is itself a no-op: it carries a null
    # action and sits alongside the Keep baseline (two no-action rows). This must validate.
    hold = Alternative(
        id="hold",
        name="Hold pending decision",
        annualCostEur=1120.0,
        savingsVsCurrentEur=0.0,
        tradeoff="Avoids a change the pending move could reverse.",
        isRecommended=True,
        action=None,
    )
    cancel = Alternative(
        id="cancel_dticket",
        name="Cancel Deutschland-Ticket",
        annualCostEur=364.0,
        savingsVsCurrentEur=756.0,
        tradeoff="Lose unlimited regional rail.",
        isRecommended=False,
        action=ProposedAction(title="Cancel", description="d", consequence="c"),
    )
    rec = _rec([_KEEP, hold, cancel])
    assert next(a for a in rec.alternatives if a.isRecommended).id == "hold"


def test_ordinary_null_action_recommendation_still_rejected():
    # The normal case has exactly one no-action row (keep). A recommended alternative with a
    # null action there is an extraction bug, not a hold — it must stay rejected.
    broken = Alternative(
        id="cancel_dticket",
        name="Cancel Deutschland-Ticket",
        annualCostEur=364.0,
        savingsVsCurrentEur=756.0,
        tradeoff="Lose unlimited regional rail.",
        isRecommended=True,
        action=None,  # a real change with its action dropped
    )
    with pytest.raises(ValidationError, match="non-null action"):
        _rec([_KEEP, broken])


def test_recommended_change_with_action_still_valid():
    cancel = Alternative(
        id="cancel_dticket",
        name="Cancel Deutschland-Ticket",
        annualCostEur=364.0,
        savingsVsCurrentEur=756.0,
        tradeoff="Lose unlimited regional rail.",
        isRecommended=True,
        action=ProposedAction(title="Cancel", description="d", consequence="c"),
    )
    rec = _rec([_KEEP, cancel])
    assert next(a for a in rec.alternatives if a.isRecommended).id == "cancel_dticket"
