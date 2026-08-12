"""Pydantic models for the snake_case mock data store: market catalog, current
subscriptions, travel history, calendar events, car usage, and life events."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator

_CATALOG_PATH = Path(__file__).parent.parent / "static" / "mobility_catalog.json"


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
    event_date: str | None = None
    signals: list[str] = []
    source_mail_id: str | None = None
    detected_on: str


class LifeEvents(BaseModel):
    events: list[LifeEvent]
