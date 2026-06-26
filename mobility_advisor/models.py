from __future__ import annotations

from pydantic import BaseModel


class UserPreferences(BaseModel):
    name: str
    flexibility_need: str
    sustainability_weight: float
    values_time_over_money: bool
    notes: str


class Subscription(BaseModel):
    provider: str
    product: str
    monthly_cost_eur: float
    billing_cycle: str
    next_renewal_date: str
    started: str
    notes: str


class CurrentSubscriptions(BaseModel):
    subscriptions: list[Subscription]


class CatalogOption(BaseModel):
    provider: str
    product: str
    mode: str
    monthly_cost_eur: float
    billing_cycle: str = "monthly"
    discount_rule: str | None = None
    co2_g_per_km: int


class MobilityCatalog(BaseModel):
    options: list[CatalogOption]


class Trip(BaseModel):
    date: str
    mode: str
    origin: str
    destination: str
    distance_km: float
    cost_eur: float | None = None
    provider: str
    booked_under: str | None = None


class TravelHistory(BaseModel):
    trips: list[Trip]


class CalendarEvent(BaseModel):
    date: str
    type: str
    description: str
    location: str | None = None
    signals: list[str] = []


class CalendarEvents(BaseModel):
    events: list[CalendarEvent]
