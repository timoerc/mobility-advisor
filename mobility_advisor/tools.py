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

USE_MOCK_DATA = False

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
