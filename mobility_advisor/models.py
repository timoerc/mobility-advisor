from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator

_CATALOG_PATH = Path(__file__).parent / "static" / "mobility_catalog.json"


def catalog_lookup() -> dict[str, dict]:
    raw = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    return {opt["id"]: opt for opt in raw.get("options", [])}


class PriorityWeights(BaseModel):
    cost: float = 1 / 3
    time: float = 1 / 3
    sustainability: float = 1 / 3


class UserPreferences(BaseModel):
    name: str
    home_city: str
    age: int | None = None
    owns_car: bool = False
    values_time_over_money: bool
    notes: str = ""
    # The three priority-slider weights, nested (not flat cost_weight/time_weight/
    # sustainability_weight) — this is the one representation every reader (prompt text
    # and compute_portfolio_score()) is normalized onto; see PriorityWeights above.
    priority_weights: PriorityWeights = PriorityWeights()


class Eligibility(BaseModel):
    model_config = {"extra": "forbid"}
    min_age: int | None = None
    max_age: int | None = None


class RailBenefits(BaseModel):
    model_config = {"extra": "forbid"}
    discount_sparpreis_pct: float | None
    discount_flexpreis_pct: float | None
    unlimited_long_distance: bool
    unlimited_regional: bool


class CarShareBenefits(BaseModel):
    model_config = {"extra": "forbid"}
    base_km_rate_eur: float
    monthly_credit_eur: float
    discount_km_pct: float
    discount_time_pct: float
    unlock_fee_eur_per_trip: float
    protection_plus_eur_per_trip: float


class CarRentalBenefits(BaseModel):
    model_config = {"extra": "forbid"}
    bonus_points_pct: float
    point_value_eur: float


class FlightBenefits(BaseModel):
    model_config = {"extra": "forbid"}
    bonus_miles_pct: float
    mile_value_eur: float


class BusBenefits(BaseModel):
    model_config = {"extra": "forbid"}  # flixbus_payperuse's benefits is genuinely {}


class CarRentalThreshold(BaseModel):
    model_config = {"extra": "forbid"}
    rentals_per_year: int
    rental_days_per_year: int | None


class FlightThreshold(BaseModel):
    model_config = {"extra": "forbid"}
    status_miles_per_year: int
    flights_per_year: int | None


_BENEFITS_BY_MODE = {
    "rail": RailBenefits,
    "car_share": CarShareBenefits,
    "car_rental": CarRentalBenefits,
    "flight": FlightBenefits,
    "bus": BusBenefits,
}
_THRESHOLD_BY_MODE = {"car_rental": CarRentalThreshold, "flight": FlightThreshold}


def _typed_benefits(mode: str, raw: dict) -> BaseModel:
    cls = _BENEFITS_BY_MODE.get(mode)
    if cls is None:
        raise ValueError(f"no benefits schema registered for mode {mode!r}")
    return cls.model_validate(raw)


def _typed_qualifying_threshold(mode: str, raw: dict | None) -> BaseModel | None:
    if raw is None:
        return None
    cls = _THRESHOLD_BY_MODE.get(mode)
    if cls is None:
        raise ValueError(f"mode {mode!r} does not support a qualifying_threshold")
    return cls.model_validate(raw)


class _CatalogFields(BaseModel):
    """Fields shared verbatim between a market catalog option and a subscription
    entry mirroring one — kept in one place so the two schemas can't drift."""
    model_config = {"extra": "forbid"}
    provider: str
    product: str
    mode: Literal["rail", "car_share", "car_rental", "flight", "bus"]
    monthly_cost_eur: float
    billing_cycle: str = "monthly"
    minimum_months: int = 0
    eligibility: Eligibility
    benefits: RailBenefits | CarShareBenefits | CarRentalBenefits | FlightBenefits | BusBenefits
    qualifying_threshold: CarRentalThreshold | FlightThreshold | None = None
    affiliated_airlines: list[str] | None = None
    notes: str = ""

    @model_validator(mode="before")
    @classmethod
    def _dispatch_by_mode(cls, values: dict) -> dict:
        mode = values.get("mode")
        if isinstance(values.get("benefits"), dict):
            values["benefits"] = _typed_benefits(mode, values["benefits"])
        if isinstance(values.get("qualifying_threshold"), dict):
            values["qualifying_threshold"] = _typed_qualifying_threshold(mode, values["qualifying_threshold"])
        return values


class CatalogOption(_CatalogFields):
    id: str


class Subscription(_CatalogFields):
    id: str
    next_renewal_date: str = ""
    started: str = ""

    @model_validator(mode="before")
    @classmethod
    def _resolve_from_catalog(cls, values: dict) -> dict:
        """current_subscriptions.json may only reference products that exist in
        mobility_catalog.json. Every catalog-owned field (provider, product, mode,
        pricing, benefits, ...) is always derived from the catalog by id — never
        trusted from the caller — so the two files can never drift apart. Only
        next_renewal_date/started/detected are subscription-specific and pulled
        from the caller; a null value there (e.g. a usage-threshold loyalty tier
        with no signup date) is left absent so the field default ("") applies."""
        catalog_entry = catalog_lookup().get(values.get("id"))
        if catalog_entry is None:
            raise ValueError(f"subscription id {values.get('id')!r} is not in mobility_catalog.json")
        resolved = dict(catalog_entry)
        for key in ("next_renewal_date", "started", "detected"):
            if values.get(key) is not None:
                resolved[key] = values[key]
        return resolved


class CurrentSubscriptions(BaseModel):
    subscriptions: list[Subscription]


class MobilityCatalog(BaseModel):
    options: list[CatalogOption]


class Trip(BaseModel):
    date: str
    mode: str
    origin: str
    destination: str
    departure_time: str | None = None
    arrival_time: str | None = None
    duration_min: int | None = None
    real_travel_duration_min: float | None = None
    cost_eur: float | None = None
    provider: str
    ticket_type: str | None = None
    type: str | None = None
    size: str | None = None
    distance_km: float | None = None
    co2_emission_kg: float | None = None
    booked_under: str | None = None
    source_mail_id: str | None = None


class TravelHistory(BaseModel):
    trips: list[Trip]


class CalendarEvent(BaseModel):
    start_date: str = ""
    end_date: str = ""
    time_start: str | None = None
    time_end: str | None = None
    type: str
    description: str
    # German sibling of `description`, read by tools.py's i18n.pick() when the request
    # language is "de". Optional and unmodeled-extra-safe: without this field, a scenario's
    # description_de would silently validate away and never reach any consumer — see
    # CLAUDE.md's note on Pydantic dropping unmodeled extra fields.
    description_de: str | None = None
    location: str | None = None
    signals: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_date(cls, values: dict) -> dict:
        if "date" in values and not values.get("start_date"):
            values["start_date"] = values.pop("date")
            values.setdefault("end_date", values["start_date"])
        return values


class CalendarEvents(BaseModel):
    events: list[CalendarEvent]


class CarUsage(BaseModel):
    owns_car: bool = False
    mode: str = "car_private"
    type: str | None = None
    size: str | None = None
    monthly_km_estimate: float | None = None


class LifeEvent(BaseModel):
    category: Literal[
        "relocation", "job_change", "subscription_change", "household_change", "other"
    ]
    summary: str
    # See CalendarEvent.description_de above — same pattern.
    summary_de: str | None = None
    event_date: str | None = None
    signals: list[str] = []
    source_mail_id: str | None = None
    detected_on: str


class LifeEvents(BaseModel):
    events: list[LifeEvent]


# ── Projected trip models (used by the redesigned pipeline) ───────────────────


class RouteAlternative(BaseModel):
    mode: str
    distance_km: float
    duration_min: float
    co2_kg: float
    estimated_price_eur: float


class ProjectedTrip(BaseModel):
    route: str
    origin: str
    destination: str
    frequency_per_year: int
    source: Literal["history", "calendar", "car_usage"]
    category: str | None = None
    distance_km: float
    alternatives: list[RouteAlternative]
    # Dominant historical fare class for this route ("flex" if a majority of the
    # contributing trips' ticket_type mentions Flexpreis, else "spar"). Lets
    # apply_subscription_discount() pick discount_flexpreis_pct vs.
    # discount_sparpreis_pct instead of assuming every trip is Sparpreis.
    fare_class: Literal["spar", "flex"] = "spar"
    # "national" (default): a real DB-ticketed trip (Fernverkehr or Nahverkehr single
    # ticket), which a BahnCard's percentage discount or an unlimited pass legitimately
    # applies to. "local": a Verkehrsverbund/city-transit fare (e.g. the synthesized
    # home-city commute) that a BahnCard has no authority over at all — only a coverage
    # benefit that is genuinely valid on local transit (Deutschlandticket's
    # unlimited_regional) should discount it. See apply_subscription_discount().
    tariff: Literal["national", "local"] = "national"
    # Majority-vote (see _dominant_operator_is_non_db()) whether this route's contributing
    # historical trips ran on a non-DB rail operator (e.g. FlixTrain) rather than Deutsche
    # Bahn. False (the default) means DB-eligible — the default for every source without a
    # real provider signal (calendar, car_usage), matching prior behavior for those. A
    # BahnCard's discount and a Deutschlandticket's coverage are both DB-only benefits (see
    # apply_subscription_discount()) and must not apply when this is True.
    non_db_operator: bool = False


class ProjectedTripSet(BaseModel):
    trips: list[ProjectedTrip]
    generated_at: str
    warnings: list[str] = []


# ── Pipeline output / API response schemas ──────────────────────────────────────
# Field names are camelCase (unlike the snake_case data-loading schemas above)
# because these models ARE the wire contract with frontend/src/types/recommendation.ts —
# main.py serializes them directly as the /api/analyze response body.

class MetricDelta(BaseModel):
    # Usually the numeric delta a tile is built from; a headline tile can instead carry a
    # date or a word (e.g. a pending-decision tile showing "2026-09-01" or "relocation").
    value: float | str
    unit: str
    direction: Literal["save", "extra_cost", "reduce", "increase", "neutral"]
    label: str
    # German sibling for seeded scenario analysis_history.json entries — see
    # CalendarEvent.description_de. Live runs never populate this (their MetricDelta.label
    # values are already built in the request's language via t()/main.py's metric builders).
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
    # CalendarEvent.description_de for why these must be declared, not left as extras.
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
    # CalendarEvent.description_de) — a live /api/analyze run never sets these; its LLM output
    # already comes back in the request's language via the agent-prompt directive.
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
    # selects it — see /api/execute in main.py.
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
    # CalendarEvent.description_de. Live runs never populate these (see Alternative.name_de).
    verdict_de: str | None = None
    summaryText_de: str | None = None
    reasoning_de: list[str] | None = None
    assumptions_de: list[str] | None = None
    # Deterministic warnings from the trip-projection engine (tools.py) — malformed travel
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
    # German sibling for seeded scenario entries — see CalendarEvent.description_de.
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
