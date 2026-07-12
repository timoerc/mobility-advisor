from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator


class UserPreferences(BaseModel):
    name: str
    flexibility_need: str
    sustainability_weight: float
    values_time_over_money: bool
    notes: str


class Subscription(BaseModel):
    model_config = {"extra": "allow"}
    id: str
    provider: str
    product: str
    mode: str
    monthly_cost_eur: float = 0.0
    billing_cycle: str = "monthly"
    minimum_months: int = 0
    eligibility: dict | None = None
    benefits: dict | None = None
    qualifying_threshold: dict | None = None
    affiliated_airlines: list[str] | None = None
    next_renewal_date: str = ""
    started: str = ""
    notes: str = ""

    @model_validator(mode="before")
    @classmethod
    def _null_dates_to_empty(cls, values: dict) -> dict:
        # Threshold/status-based benefits (e.g. a car-rental loyalty tier reached by
        # usage volume, not signed up on a date) legitimately have no start/renewal
        # date and are stored as null in the mock data.
        for key in ("next_renewal_date", "started"):
            if values.get(key) is None:
                values[key] = ""
        return values


class CurrentSubscriptions(BaseModel):
    subscriptions: list[Subscription]


class CatalogOption(BaseModel):
    model_config = {"extra": "allow"}
    id: str
    provider: str
    product: str
    mode: str
    monthly_cost_eur: float
    billing_cycle: str = "monthly"
    minimum_months: int = 0
    eligibility: dict | None = None
    benefits: dict | None = None
    qualifying_threshold: dict | None = None
    affiliated_airlines: list[str] | None = None
    notes: str = ""


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


# ── Pipeline output / API response schemas ──────────────────────────────────────
# Field names are camelCase (unlike the snake_case data-loading schemas above)
# because these models ARE the wire contract with frontend/src/types/recommendation.ts —
# main.py serializes them directly as the /api/analyze response body.

class MetricDelta(BaseModel):
    value: float
    unit: str
    direction: Literal["save", "extra_cost", "reduce", "increase", "neutral"]
    label: str


class ProposedAction(BaseModel):
    title: str
    description: str
    consequence: str


class Alternative(BaseModel):
    id: str
    name: str
    annualCostEur: float
    savingsVsCurrentEur: float
    co2Impact: str = "Neutral"
    # Signed kg CO2/year, same convention as savingsVsCurrentEur: positive = this
    # alternative saves CO2 vs. the current portfolio, negative = it emits more.
    co2ImpactKg: float = 0.0
    tradeoff: str
    isRecommended: bool
    # None only for the always-present "Keep current setup" row. Every other
    # alternative must carry its own action so it can be executed if the user
    # selects it — see /api/execute in main.py.
    action: ProposedAction | None = None


class Recommendation(BaseModel):
    verdict: str
    confidence: Literal["high", "medium", "low"]
    summaryText: str
    metrics: list[MetricDelta]
    reasoning: list[str]
    assumptions: list[str] = []
    alternatives: list[Alternative]

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
        if recommended[0].action is None:
            raise ValueError("the recommended alternative must have a non-null action")
        if not any(a.action is None for a in self.alternatives):
            raise ValueError(
                "expected at least one 'Keep current setup' alternative (action: null)"
            )
        return self
