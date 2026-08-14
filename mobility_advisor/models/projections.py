"""Projected trip models used by the deterministic trip-projection/optimization
pipeline (engine/projection.py)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


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
