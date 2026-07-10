from __future__ import annotations

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
