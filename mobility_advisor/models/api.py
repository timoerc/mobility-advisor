"""Pipeline output / API response schemas.

Field names are camelCase (unlike the snake_case data-loading schemas in fixtures.py)
because these models ARE the wire contract with frontend/src/types/recommendation.ts —
api/routes/analysis.py serializes them directly as the /api/analyze response body.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator


class MetricDelta(BaseModel):
    # Usually the numeric delta a tile is built from; a headline tile can instead carry a
    # date or a word (e.g. a pending-decision tile showing "2026-09-01" or "relocation").
    value: float | str
    unit: str
    direction: Literal["save", "extra_cost", "reduce", "increase", "neutral"]
    label: str
    # German sibling for seeded scenario analysis_history.json entries — see
    # CalendarEvent.description_de in models/fixtures.py. Live runs never populate this (their
    # MetricDelta.label values are already built in the request's language via t()/main.py's
    # metric builders).
    label_de: str | None = None
    # Some seeded entries' `value` is itself a short English word rather than a number (e.g.
    # a pending-decision tile's "relocation") — this is that value's German counterpart, kept
    # separate from label_de since value and label are independent fields.
    value_de: str | None = None


class ProposedAction(BaseModel):
    title: str
    description: str
    consequence: str
    # German siblings for seeded analysis_history.json entries — see
    # CalendarEvent.description_de in models/fixtures.py for why these must be declared, not
    # left as extras.
    title_de: str | None = None
    description_de: str | None = None
    consequence_de: str | None = None


class DeltaVsCurrent(BaseModel):
    """This alternative's projected impact vs. the user's current portfolio, on all three
    preference dimensions. Single sign convention across all three: negative = better than
    current (cheaper / faster / less CO2), so the fields read the same way."""
    costEur: float = 0.0
    timeMin: float = 0.0
    co2Kg: float = 0.0


class Alternative(BaseModel):
    id: str
    name: str
    # German siblings, populated only on seeded scenario analysis_history.json entries (see
    # CalendarEvent.description_de in models/fixtures.py) — a live /api/analyze run never sets
    # these; its LLM output already comes back in the request's language via the agent-prompt
    # directive.
    name_de: str | None = None
    tradeoff_de: str | None = None
    annualCostEur: float
    savingsVsCurrentEur: float
    co2Impact: str = "Neutral"
    # Signed kg CO2/year, same convention as savingsVsCurrentEur: positive = this
    # alternative saves CO2 vs. the current portfolio, negative = it emits more.
    co2ImpactKg: float = 0.0
    tradeoff: str
    isRecommended: bool
    # Deltas vs. the recommended portfolio (0 for the recommended itself).
    deltaCostVsRecommendedEur: float = 0.0
    deltaTimeVsRecommendedMin: float = 0.0
    deltaCo2VsRecommendedKg: float = 0.0
    # Deltas vs. the user's CURRENT setup, on all three dimensions — what the presentation
    # layer drives its "vs. your current setup" strip from. Optional so seeded
    # analysis_history.json entries predating this field still validate.
    deltaVsCurrent: DeltaVsCurrent | None = None
    # None only for the always-present "Keep current setup" row. Every other
    # alternative must carry its own action so it can be executed if the user
    # selects it — see /api/execute in api/routes/execution.py.
    action: ProposedAction | None = None
    # Structured product-name lists behind `name`/`action.title`, so the frontend can render
    # cancel vs. add as distinct chips instead of parsing an opaque sentence. Empty for rows
    # with no change (e.g. "Keep current setup").
    addedProducts: list[str] = []
    removedProducts: list[str] = []


class Recommendation(BaseModel):
    verdict: str
    confidence: Literal["high", "medium", "low"]
    summaryText: str
    metrics: list[MetricDelta]
    reasoning: list[str]
    assumptions: list[str] = []
    alternatives: list[Alternative]
    # German siblings for seeded scenario analysis_history.json entries — see
    # CalendarEvent.description_de in models/fixtures.py. Live runs never populate these (see
    # Alternative.name_de).
    verdict_de: str | None = None
    summaryText_de: str | None = None
    reasoning_de: list[str] | None = None
    assumptions_de: list[str] | None = None
    # Deterministic warnings from the trip-projection engine (engine/) — malformed travel
    # history entries (null costs, empty/unknown modes), travel-reduction damping applied,
    # rail-fare calibration notes, uncorroborated calendar demand caps, etc. Populated from
    # optimize_all_categories()'s persisted `warnings` list, not from the LLM narration, so a
    # persona whose history has data-quality issues (e.g. Lena's) always surfaces them
    # regardless of what the communicator's prose happens to mention.
    dataQualityWarnings: list[str] = []

    @model_validator(mode="after")
    def _validate_alternatives_shape(self) -> "Recommendation":
        ids = [a.id for a in self.alternatives]
        if len(ids) != len(set(ids)):
            raise ValueError(f"alternatives ids must be unique, got {ids}")
        recommended = [a for a in self.alternatives if a.isRecommended]
        if len(recommended) != 1:
            raise ValueError(
                f"expected exactly one isRecommended alternative, got {len(recommended)}"
            )
        no_action_rows = [a for a in self.alternatives if a.action is None]
        if not no_action_rows:
            raise ValueError(
                "expected at least one 'Keep current setup' alternative (action: null)"
            )
        # The recommended alternative normally must be executable (non-null action). The one
        # exception is a deliberate "Hold pending decision" recommendation, which is itself a
        # no-op: holding costs exactly the same as the status-quo baseline. So a null-action
        # recommendation is allowed only when another no-action row (the "Keep current setup"
        # baseline) carries the same annualCostEur. A null action on a row whose cost differs
        # from baseline means a real change lost its action (an extraction bug) — stays rejected.
        rec_alt = recommended[0]
        if rec_alt.action is None:
            is_deliberate_hold = any(
                abs(a.annualCostEur - rec_alt.annualCostEur) < 0.01
                for a in no_action_rows
                if a is not rec_alt
            )
            if not is_deliberate_hold:
                raise ValueError("the recommended alternative must have a non-null action")
        return self


class AnalysisRunResult(BaseModel):
    """/api/analyze's response wrapper — carries the history entry id created for
    this run alongside the Recommendation itself, so the frontend can later report
    back what the user decided (see AnalysisHistoryEntry)."""
    id: str
    recommendation: Recommendation


class AnalysisHistoryEntry(BaseModel):
    id: str
    date: str
    recommendation: Recommendation
    outcome: Literal["pending", "kept_current", "executed"] = "pending"
    resolvedAlternativeId: str | None = None
    resolvedMessage: str | None = None
    # German sibling for seeded scenario entries — see CalendarEvent.description_de in
    # models/fixtures.py.
    resolvedMessage_de: str | None = None
    resolvedAt: str | None = None
    # The language this entry's recommendation prose was generated/seeded in. Lets the
    # frontend and the Communicator's continuity read (load_recommendation_history()) tell a
    # German live analysis apart from an older English one instead of assuming everything in
    # history matches the currently selected language.
    language: Literal["en", "de"] = "en"
    # Subscription stack captured just before an executed change, kept so the newest executed entry
    # can be reverted (restored) as a true undo. Present only while outcome == "executed"; cleared on
    # revert. Shape: a CurrentSubscriptions dump ({"subscriptions": [...]}).
    revertSnapshot: dict | None = None


class AnalysisHistory(BaseModel):
    entries: list[AnalysisHistoryEntry]
