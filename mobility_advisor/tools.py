import json
from pathlib import Path

from .models import (
    CalendarEvents,
    CurrentSubscriptions,
    MobilityCatalog,
    TravelHistory,
    UserPreferences,
)

_DATA = Path(__file__).parent / "data"

USE_MOCK_DATA = True

def load_user_preferences() -> dict:
    """Load Maja's personal mobility preferences and constraints from the mock data store.

    Returns a dict with keys: monthly_budget_eur (float), flexibility_need (str: low/medium/high),
    sustainability_weight (float 0-1), values_time_over_money (bool), and notes (str).
    """
    raw = json.loads((_DATA / "user_preferences.json").read_text())
    return UserPreferences.model_validate(raw).model_dump()


def load_current_subscriptions() -> dict:
    """Load Maja's currently active mobility subscriptions from the mock data store.

    Returns a dict with key 'subscriptions', a list of entries each containing:
    provider (str), product (str), monthly_cost_eur (float), started (str date), notes (str).
    """
    raw = json.loads((_DATA / "current_subscriptions.json").read_text())
    return CurrentSubscriptions.model_validate(raw).model_dump()


def load_mobility_catalog() -> dict:
    """Load the market-side mobility products catalog including pricing and CO2 data.

    Returns a dict with key 'options', a list of available products each containing:
    provider (str), product (str), mode (str: rail/regional/car_share/e_scooter),
    monthly_cost_eur (float), discount_rule (str or null), co2_g_per_km (int).
    """
    raw = json.loads((_DATA / "mobility_catalog.json").read_text())
    return MobilityCatalog.model_validate(raw).model_dump()


_KNOWN_MODES = {"rail", "regional", "car_share", "e_scooter", "bus", "local_transit"}


def load_travel_history() -> dict:
    """Load Maja's 12-month travel history from the mock data store.

    Returns a dict with key 'trips', a list of past trips each containing:
    date (str), mode (str), origin (str), destination (str), distance_km (float),
    cost_eur (float or null), provider (str), booked_under (str or null).
    If any trips have data quality issues, a 'data_quality_warnings' key is included
    listing each problem so downstream agents can surface them to the user.
    """
    raw = json.loads((_DATA / "travel_history.json").read_text())
    history = TravelHistory.model_validate(raw)
    result = history.model_dump()

    warnings = []
    for trip in history.trips:
        label = f"{trip.date} {trip.origin}→{trip.destination}"
        if trip.cost_eur is None:
            warnings.append(f"{label}: cost_eur is null — excluded from spend totals")
        if not trip.mode:
            warnings.append(f"{label}: mode is empty — excluded from CO₂ and mode aggregations")
        elif trip.mode not in _KNOWN_MODES:
            warnings.append(f"{label}: unknown mode '{trip.mode}' — excluded from CO₂ and mode aggregations")

    if warnings:
        result["data_quality_warnings"] = warnings

    return result


def load_calendar_events() -> dict:
    """Load upcoming calendar events — from mock data or live Outlook API.

    Returns a dict with key 'events', a list of upcoming events each containing:
    date (str), type (str: trip/meeting/life_event), description (str),
    location (str or null), signals (list[str] — demand or life-change indicators).
    """
    if USE_MOCK_DATA:
        raw = json.loads((_DATA / "calendar_events.json").read_text())
    else:
        from .outlook_calendar import fetch_calendar_events
        raw = fetch_calendar_events()
    return CalendarEvents.model_validate(raw).model_dump()


def compute_travel_stats(
    subscription_or_provider: str | None = None,
    mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    origin_filter: str | None = None,
    destination_filter: str | None = None,
) -> dict:
    """Aggregate Maja's travel history: trip counts, total spend, and distance, with optional filters.

    Use this for ANY counting, summing, or date-range question about trips — never tally
    the travel history JSON yourself.

    Args:
        subscription_or_provider: Optional filter, e.g. "BahnCard 50" or "Deutsche Bahn".
            Matched case-insensitively as a substring against each trip's booked_under
            field OR its provider field (a match on either counts). Pass None for no filter.
        mode: Optional exact-match filter on trip mode (e.g. "rail", "car_share"). Pass None for no filter.
        date_from: Optional inclusive ISO date string ("YYYY-MM-DD"); trips before this are excluded.
        date_to: Optional inclusive ISO date string ("YYYY-MM-DD"); trips after this are excluded.
        origin_filter: Optional substring to match against the trip's origin station name
            (case-insensitive). E.g. "Frankfurt" matches "Frankfurt (Main) Hbf". Pass None for no filter.
        destination_filter: Optional substring to match against the trip's destination station
            name (case-insensitive). Pass None for no filter.

    Returns a dict with keys: trip_count (int), total_spend_eur (float, sums only trips with
    non-null cost_eur), total_distance_km (float), trips_missing_cost (int, count of matched
    trips with null cost_eur), matched_filters (dict echoing the filters applied),
    subscription_renewal (dict with next_renewal_date/billing_cycle, or null — set when
    subscription_or_provider matches an entry in current_subscriptions.json by the same
    substring rule), and data_quality_warnings (list[str], unfiltered passthrough from
    load_travel_history so data issues are never hidden by a filter).
    """
    history_data = load_travel_history()
    trips = TravelHistory.model_validate({"trips": history_data["trips"]}).trips
    needle = subscription_or_provider.lower() if subscription_or_provider else None
    origin_needle = origin_filter.lower() if origin_filter else None
    destination_needle = destination_filter.lower() if destination_filter else None

    def matches(trip) -> bool:
        if mode is not None and trip.mode != mode:
            return False
        if date_from is not None and trip.date < date_from:
            return False
        if date_to is not None and trip.date > date_to:
            return False
        if origin_needle is not None and origin_needle not in trip.origin.lower():
            return False
        if destination_needle is not None and destination_needle not in trip.destination.lower():
            return False
        if needle is not None:
            booked = (trip.booked_under or "").lower()
            if needle not in booked and needle not in trip.provider.lower():
                return False
        return True

    matched = [trip for trip in trips if matches(trip)]
    total_spend_eur = sum(trip.cost_eur for trip in matched if trip.cost_eur is not None)
    total_distance_km = sum(trip.distance_km for trip in matched)
    trips_missing_cost = sum(1 for trip in matched if trip.cost_eur is None)

    subscription_renewal = None
    if needle is not None:
        subs = load_current_subscriptions()["subscriptions"]
        for sub in subs:
            if needle in sub["product"].lower() or needle in sub["provider"].lower():
                subscription_renewal = {
                    "next_renewal_date": sub["next_renewal_date"],
                    "billing_cycle": sub["billing_cycle"],
                }
                break

    return {
        "trip_count": len(matched),
        "total_spend_eur": round(total_spend_eur, 2),
        "total_distance_km": round(total_distance_km, 2),
        "trips_missing_cost": trips_missing_cost,
        "matched_filters": {
            "subscription_or_provider": subscription_or_provider,
            "mode": mode,
            "date_from": date_from,
            "date_to": date_to,
            "origin_filter": origin_filter,
            "destination_filter": destination_filter,
        },
        "subscription_renewal": subscription_renewal,
        "data_quality_warnings": history_data.get("data_quality_warnings", []),
    }
