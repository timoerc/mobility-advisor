"""Deterministic gate for the pipeline's "hold pending a decision" recommendation —
whether an unresolved, near-term portfolio-resetting life event exists."""
from datetime import date, timedelta

from .. import clock
from ..i18n import t
from .loaders import load_life_events

# Signals whose arrival would, on their own, invalidate the current commute-based
# portfolio if it takes effect — a home relocation or a change of work pattern resets
# which subscriptions make sense at all. Lower-impact signals (income_change,
# d_ticket_relevance_change, rail_card_relevance_change, non_mobility_spend, ...)
# deliberately do NOT gate deferral: they refine an existing setup rather than reset it,
# so the normal optimize-now path still applies. This narrow set is what keeps the
# "hold pending a decision" recommendation from ever firing spuriously (e.g. for Lena,
# whose only signals are ticket-relevance/spend changes, or Maja, who has none).
_PORTFOLIO_RESET_SIGNALS = frozenset({"home_base_change", "work_pattern_change"})

# How far ahead an unresolved reset event may sit and still justify holding. A move a
# couple of months out is worth waiting for; one years away should not freeze the
# portfolio indefinitely, so beyond this horizon the normal optimize-now path resumes.
_DECISION_HORIZON_DAYS = 275  # ~9 months


def detect_pending_portfolio_decision() -> dict:
    """Detect whether an unresolved, near-term life event would reset the portfolio.

    This is the deterministic gate for the Optimizer's "hold / defer pending a decision"
    recommendation: the pipeline may only propose holding subscriptions instead of acting
    now when this returns exists=True. It fires only for a genuine portfolio-resetting
    change — a relocation or work-pattern change (a life event whose signals include
    home_base_change or work_pattern_change) that is still upcoming (event_date on/after
    today) and lands within ~9 months. A persona with no life events (e.g. Maja), or only
    lower-impact signals such as a ticket-relevance or non-mobility-spend change (e.g.
    Lena), returns exists=False, so their reviews behave exactly as before. Once every
    qualifying event's date has passed (the move has happened or been called off), it
    returns exists=False again — the setup should then be re-optimized against the new
    reality, not held indefinitely.

    Returns a dict with keys:
      - exists (bool): whether a deferral-worthy pending decision was found.
      - reason (str): one-line explanation of the pending decision; "" when exists is False.
      - revisit_after (str | None): ISO date the last qualifying event takes effect — the
        point by which the uncertainty is certainly resolved and the review should be
        re-run; None when exists is False.
      - events (list[dict]): the qualifying life events (category, summary, event_date,
        signals), empty when exists is False.
    """
    today = clock.MOCK_TODAY
    horizon_end = today + timedelta(days=_DECISION_HORIZON_DAYS)
    qualifying: list[tuple[dict, date]] = []
    for event in load_life_events()["events"]:
        if not (_PORTFOLIO_RESET_SIGNALS & set(event.get("signals", []))):
            continue
        raw_date = event.get("event_date")
        if not raw_date:
            continue  # undated reset signal: can't confirm it's near-term or unresolved
        try:
            event_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        if today <= event_date <= horizon_end:
            qualifying.append((event, event_date))

    if not qualifying:
        return {"exists": False, "reason": "", "revisit_after": None, "events": []}

    revisit_after = max(event_date for _, event_date in qualifying)
    categories = "/".join(
        t(f"lifeEvent.category.{c}") for c in sorted({event["category"] for event, _ in qualifying})
    )
    reason = t("pending.reason", categories=categories, date=revisit_after.isoformat())
    return {
        "exists": True,
        "reason": reason,
        "revisit_after": revisit_after.isoformat(),
        "events": [
            {
                "category": event["category"],
                "summary": event["summary"],
                "event_date": event.get("event_date"),
                "signals": event.get("signals", []),
            }
            for event, _ in qualifying
        ],
    }

