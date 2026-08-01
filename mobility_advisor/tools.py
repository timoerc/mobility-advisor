import calendar
import csv
import json
import logging
import os
import re
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from .models import (
    AnalysisHistory,
    CalendarEvents,
    CarUsage,
    CurrentSubscriptions,
    LifeEvents,
    MobilityCatalog,
    ProjectedTrip,
    ProjectedTripSet,
    RouteAlternative,
    Subscription,
    TravelHistory,
    UserPreferences,
)
from .route_utils import (
    ORS_API_KEY,
    clean_location,
    co2_kg_for_mode,
    driving_route,
    estimate_duration_min,
    estimate_trip_price,
    geocode,
    haversine_distance_km,
)

_DATA = Path(__file__).parent / "data"
_STATIC = Path(__file__).parent / "static"

logger = logging.getLogger(__name__)

USE_MOCK_DATA = True

# Frozen so mock scenarios stay reproducible regardless of the host machine's real date.
# Sourced from persona.json's "reference_date" (single source of truth, swapped in whenever
# a scenario is activated) so the fixtures and the app's notion of "today" can't drift apart.
_DEFAULT_REFERENCE_DATE = date(2026, 6, 15)


def _load_reference_date() -> date:
    try:
        raw = json.loads((_DATA / "persona.json").read_text(encoding="utf-8"))
        return date.fromisoformat(raw["reference_date"])
    except (FileNotFoundError, KeyError, ValueError):
        return _DEFAULT_REFERENCE_DATE


MOCK_TODAY = _load_reference_date()
REVIEW_YEAR = MOCK_TODAY.year - 1  # annual report always covers the last full calendar year

def load_user_preferences() -> dict:
    """Load the active user's mobility preferences derived from their persona profile.

    Returns a dict with keys: name (str), home_city (str), age (int or null), owns_car
    (bool), values_time_over_money (bool), notes (str), and priority_weights (dict:
    cost/time/sustainability, the raw priority floats from the frontend sliders that sum
    to ~1.0) — use priority_weights, not values_time_over_money alone, to weight which
    candidate/portfolio to recommend.
    """
    persona = json.loads((_DATA / "persona.json").read_text(encoding="utf-8"))
    car = json.loads((_DATA / "car_usage.json").read_text(encoding="utf-8"))
    pd = persona["profileData"]
    p = pd["priorities"]
    prefs = {
        "name": pd["personal"]["full_name"] or "the user",
        "home_city": pd.get("location", {}).get("home_city", ""),
        "age": pd["personal"].get("age"),
        "owns_car": car.get("owns_car", False),
        "values_time_over_money": p["time"] > p["cost"],
        "notes": pd.get("notes", ""),
        "priority_weights": {
            "cost": p["cost"],
            "time": p["time"],
            "sustainability": p["sustainability"],
        },
    }
    return UserPreferences.model_validate(prefs).model_dump()


def load_life_events() -> dict:
    """Load life-event signals distilled offline from the active user's mail.

    A life event is a relocation, job change, mobility-relevant subscription change
    (activation/cancellation/non-renewal), household change, or other notable context
    (e.g. a recurring non-mobility subscription) — never raw mail; this is always the
    small, pre-extracted fixture life_events.json.

    Returns a dict with key 'events', a list of entries each containing: category (str:
    relocation/job_change/subscription_change/household_change/other), summary (str, one
    line), event_date (str or null, ISO date the event itself takes effect), signals
    (list[str], short machine-readable tags), source_mail_id (str or null), and detected_on
    (str, ISO date the extraction ran). An empty list is a legitimate result meaning no
    life-event signal was found in the user's mail — not a loading failure.
    """
    path = _DATA / "life_events.json"
    if not path.exists():
        return {"events": []}
    raw = json.loads(path.read_text())
    return LifeEvents.model_validate(raw).model_dump()


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
    today = MOCK_TODAY
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
    categories = "/".join(sorted({event["category"] for event, _ in qualifying}))
    reason = (
        f"A pending {categories} is expected to take effect by "
        f"{revisit_after.isoformat()}, which would reset the current commute-based "
        f"portfolio — acting now risks a change the decision could immediately reverse."
    )
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


def load_car_usage() -> dict:
    """Load the active user's private car ownership/usage facts from the mock data store.

    Returns a dict with keys: owns_car (bool), mode (str, always "car_private"), type (str
    or null, e.g. Petrol/Diesel/Electric/Hybrid), size (str or null, e.g. "Medium car"), and
    monthly_km_estimate (float or null). All fields are false/null for a persona without a
    private car — that is a real "no private car" fact, not a missing-data gap.
    """
    raw = json.loads((_DATA / "car_usage.json").read_text())
    return CarUsage.model_validate(raw).model_dump()


def load_recommendation_history(limit: int = 3) -> dict:
    """Load a compact summary of the user's most recent past analysis recommendations and outcomes.

    Use this to give continuity to a new review — e.g. noting that this is the Nth review
    flagging the same subscription, and what the user decided last time — instead of
    re-analyzing cold every run.

    Returns a dict with key 'history', a list of up to the `limit` most recent entries
    (oldest first, newest last), each containing: date (str), verdict (str, that review's
    headline finding), outcome (str: pending/kept_current/executed), and recommended_action
    (str, the name of the alternative that review marked as recommended). Deliberately
    excludes full Recommendation/Alternative objects (metrics, reasoning, non-recommended
    alternatives) to keep this small. Returns an empty list if no analysis history exists yet
    (e.g. a brand-new persona) — that is a legitimate result, not a loading failure.
    """
    path = _DATA / "analysis_history.json"
    if not path.exists():
        return {"history": []}
    raw = json.loads(path.read_text())
    entries = AnalysisHistory.model_validate(raw).entries[-limit:]
    history = []
    for entry in entries:
        recommended = next(
            (alt for alt in entry.recommendation.alternatives if alt.isRecommended), None
        )
        history.append({
            "date": entry.date,
            "verdict": entry.recommendation.verdict,
            "outcome": entry.outcome,
            "recommended_action": recommended.name if recommended else "",
        })
    return {"history": history}


# ── Mode filter thresholds for route alternatives ────────────────────────────

_MODE_DISTANCE_FILTERS: dict[str, tuple[float, float]] = {
    "rail_intercity": (0, float("inf")),
    "rail_regional": (0, float("inf")),
    "car_share": (0, 100),
    "car_rental": (100, float("inf")),
    "car_private": (0, float("inf")),
    "flight_short_haul": (400, float("inf")),
    "flight_domestic": (400, float("inf")),
}

_RAIL_DISTANCE_THRESHOLD_KM = 100

_REQUEST_DELAY = 1.2

_geocode_cache: dict[str, tuple[float, float] | None] = {}
_CITY_COORDS_PATH = _STATIC / "city_coords.json"
_city_coords_cache: dict[str, tuple[float, float]] | None = None


def _load_city_coords() -> dict[str, tuple[float, float]]:
    """Load and cache the static city-name -> (lat, lng) fallback table."""
    global _city_coords_cache
    if _city_coords_cache is None:
        raw = json.loads(_CITY_COORDS_PATH.read_text(encoding="utf-8"))
        _city_coords_cache = {city: tuple(latlng) for city, latlng in raw["cities"].items()}
    return _city_coords_cache


def _offline_geocode(place: str) -> tuple[float, float] | None:
    """Static-table fallback for _cached_geocode(), returning (lng, lat) — same
    convention as route_utils.geocode() — or None if the place isn't in the table.

    Tries the raw string, then its normalized city name (_normalize_to_city()
    collapses a raw station/airport/provider string like "Frankfurt (Main) Hbf" down
    to "Frankfurt"), then a case-insensitive match against both, since callers pass
    everything from LLM-supplied plain city names to raw travel-history station text.
    """
    coords = _load_city_coords()
    for candidate in (place, _normalize_to_city(place)):
        if candidate in coords:
            lat, lng = coords[candidate]
            return (lng, lat)
    lowered = {candidate.lower() for candidate in (place, _normalize_to_city(place))}
    for city, (lat, lng) in coords.items():
        if city.lower() in lowered:
            return (lng, lat)
    return None


def _cached_geocode(place: str) -> tuple[float, float] | None:
    """Geocode with in-memory cache to avoid redundant API calls.

    Falls back to the static city-coordinate table (_offline_geocode) when
    ORS_API_KEY is unset or the live ORS call fails/errors. ORS_API_KEY is not
    configured in this deployment's .env, so the offline path is this pipeline's
    normal route, not a rare edge case — the inter-request sleep only applies to
    the live-API path, since there is no rate limit to respect offline.
    """
    if place in _geocode_cache:
        return _geocode_cache[place]
    result = None
    if ORS_API_KEY:
        time.sleep(_REQUEST_DELAY)
        try:
            result = geocode(place)
        except Exception:
            result = None
    if result is None:
        result = _offline_geocode(place)
    _geocode_cache[place] = result
    return result


def _geocode_pair(
    origin: str, destination: str
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Geocode an origin/destination pair with caching. Returns None on failure."""
    orig_clean = clean_location(origin)
    dest_clean = clean_location(destination)
    orig_coords = _cached_geocode(orig_clean)
    if not orig_coords:
        logger.warning("geocode failed for origin: %s", orig_clean)
        return None
    dest_coords = _cached_geocode(dest_clean)
    if not dest_coords:
        logger.warning("geocode failed for destination: %s", dest_clean)
        return None
    return orig_coords, dest_coords


def compute_route_alternatives(origin: str, destination: str) -> dict:
    """Compute per-mode travel alternatives for a given origin–destination pair.

    Geocodes both endpoints, computes haversine distance as a cheap pre-filter,
    then for each mode that passes the distance filter computes distance, duration,
    CO2, and estimated price.

    Args:
        origin: City or station name (e.g. "Köln" or "Köln Hbf").
        destination: City or station name.

    Returns a dict with keys: origin, destination, haversine_km, alternatives
    (list of RouteAlternative dicts), and warnings (list of strings for any
    issues encountered).
    """
    warnings: list[str] = []

    coords = _geocode_pair(origin, destination)
    if coords is None:
        return {
            "origin": origin,
            "destination": destination,
            "haversine_km": None,
            "alternatives": [],
            "warnings": ["geocoding failed — cannot compute alternatives"],
        }

    orig_coords, dest_coords = coords
    hav_km = haversine_distance_km(orig_coords, dest_coords)

    car_usage = load_car_usage()
    owns_car = car_usage.get("owns_car", False)

    alternatives: list[dict] = []

    for mode, (min_km, max_km) in _MODE_DISTANCE_FILTERS.items():
        if not (min_km <= hav_km <= max_km):
            continue

        if mode == "car_private" and not owns_car:
            continue

        if mode == "rail_regional" and hav_km > _RAIL_DISTANCE_THRESHOLD_KM:
            continue
        if mode == "rail_intercity" and hav_km <= _RAIL_DISTANCE_THRESHOLD_KM:
            continue

        if mode in ("car_share", "car_rental", "car_private"):
            try:
                route_result = driving_route(origin, destination)
                time.sleep(_REQUEST_DELAY)
            except Exception as exc:
                logger.warning("driving_route failed for %s → %s: %s", origin, destination, exc)
                route_result = None
            if route_result:
                dist_km, dur_min = route_result
            else:
                dist_km = hav_km * 1.3
                dur_min = estimate_duration_min("car", dist_km)
                warnings.append(f"{mode}: driving route API failed, using heuristic")
        elif mode.startswith("rail"):
            dist_km = round(hav_km * 1.3, 1)
            dur_min = estimate_duration_min(mode, dist_km)
        elif mode.startswith("flight"):
            dist_km = round(hav_km, 1)
            dur_min = estimate_duration_min("flight", dist_km)
        else:
            continue

        co2_mode = mode
        if mode in ("flight_short_haul", "flight_domestic"):
            co2_mode = "flight"
        elif mode in ("rail_intercity", "rail_regional"):
            co2_mode = "rail"
        co2 = co2_kg_for_mode(co2_mode, dist_km)
        price = estimate_trip_price(mode, dist_km)

        alt = RouteAlternative(
            mode=mode,
            distance_km=round(dist_km, 1),
            duration_min=round(dur_min, 1),
            co2_kg=round(co2, 3),
            estimated_price_eur=round(price, 2),
        )
        alternatives.append(alt.model_dump())

    return {
        "origin": origin,
        "destination": destination,
        "haversine_km": hav_km,
        "alternatives": alternatives,
        "warnings": warnings,
    }


# ── City normalization for route grouping ────────────────────────────────────

_STATION_CITY_MAP = {
    "basel euroairport": "Basel",
    "athens eleftherios venizelos": "Athen",
    "athens": "Athen",
}

_SUFFIX_RE = re.compile(
    r"\s+(?:Hbf|Hauptbahnhof|Messe/Deutz|EuroAirport|Eleftherios Venizelos|Airport).*$",
    re.IGNORECASE,
)

_AM_AN_RE = re.compile(r"\s+(?:am|an|im|bei)\s+\S+$", re.IGNORECASE)


def _normalize_to_city(station: str) -> str:
    """Extract the city name from a station/airport/provider-prefixed location."""
    cleaned = clean_location(station)
    lower = cleaned.lower().strip()

    for pattern, city in _STATION_CITY_MAP.items():
        if pattern in lower:
            return city

    iata = re.search(r"\(([A-Z]{3})\)", station)
    if iata:
        before_iata = station[:iata.start()].strip().rstrip(",").strip()
        if before_iata:
            return before_iata

    if "," in cleaned:
        parts = [p.strip() for p in cleaned.split(",")]
        for part in reversed(parts):
            if re.search(r"\b(?:am|an|im|bei)\b", part, re.IGNORECASE):
                city_part = _AM_AN_RE.sub("", part).strip()
                first_word = city_part.split()[0] if city_part else ""
                if len(first_word) >= 3 and first_word[0].isupper():
                    return first_word
        first_part = _SUFFIX_RE.sub("", parts[0]).strip()
        first_word = first_part.split()[0] if first_part else ""
        if len(first_word) >= 3 and first_word[0].isupper():
            return first_word

    cleaned = _SUFFIX_RE.sub("", cleaned).strip()

    first_word = cleaned.split()[0] if cleaned.split() else cleaned
    if first_word and first_word[0].isupper():
        return first_word
    return cleaned


def _route_key(origin: str, destination: str) -> tuple[str, str]:
    """Normalized, direction-independent route key."""
    a = _normalize_to_city(origin)
    b = _normalize_to_city(destination)
    return (min(a, b), max(a, b))


def _dominant_fare_class(ticket_types: list[str | None]) -> str:
    """Majority-vote a route's fare class from its contributing trips' ticket_type text.

    "flex" wins only on a strict majority (e.g. "Flexpreis, 2. Klasse" contributing >50%
    of the route's trips) — a mixed or Sparpreis-dominated route defaults to "spar", the
    conservative choice (Sparpreis discount is <= Flexpreis discount on every catalog
    BahnCard, so understating fare class never overstates a card's savings).
    """
    flex_count = sum(1 for t in ticket_types if t and "flex" in t.lower())
    return "flex" if flex_count * 2 > len(ticket_types) else "spar"


def _travel_reduction_factor() -> tuple[float, list[str]]:
    """Damping factor for projected trip frequencies from a near-term travel_reduction
    life-event signal (see load_life_events()) — e.g. a staffing/project-end mail that
    means future long-distance travel will drop sharply, which historical trip counts
    alone can't see since they only describe the past.

    Pro-rates by how much of the next 12 months precedes the event: an event 78 days out
    (out of the 365-day projection window) yields factor ~0.21, so a route projected at
    48 trips/year from history drops to ~10/year — reflecting that only ~78 days of
    business-as-usual travel remain before the reduction takes effect. Uses the nearest
    qualifying event when more than one exists. Returns (1.0, []) — no damping — when no
    travel_reduction signal falls within the next 12 months, which is the normal case.
    """
    qualifying: list[date] = []
    for event in load_life_events()["events"]:
        if "travel_reduction" not in event.get("signals", []):
            continue
        raw_date = event.get("event_date")
        if not raw_date:
            continue
        try:
            event_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        if MOCK_TODAY <= event_date <= MOCK_TODAY + timedelta(days=365):
            qualifying.append(event_date)

    if not qualifying:
        return 1.0, []

    nearest = min(qualifying)
    factor = max(0.0, min(1.0, (nearest - MOCK_TODAY).days / 365))
    warning = (
        f"Travel-reduction signal detected (event date {nearest.isoformat()}) — projected "
        f"trip frequencies damped by a factor of {round(factor, 2)} to reflect reduced "
        f"travel after this date, rather than extrapolating history unchanged."
    )
    return factor, [warning]


def derive_projected_trips_from_history() -> dict:
    """Analyze travel history and derive projected recurring routes with annual frequencies.

    Groups historical trips by normalized city pair (direction-independent), counts
    occurrences, extrapolates to annual frequency, and computes per-mode alternatives
    for routes with frequency >= 2/year. Each route's dominant fare class (Sparpreis vs.
    Flexpreis) is derived from its trips' ticket_type text, and the projected frequency is
    damped when a near-term travel_reduction life-event signal exists (see
    _travel_reduction_factor()).

    Writes results to data/_projected_trips_history.json and returns a summary.
    """
    history = load_travel_history()
    trips = history["trips"]

    route_counts: dict[tuple[str, str], dict] = {}
    for trip in trips:
        origin_city = _normalize_to_city(trip["origin"])
        dest_city = _normalize_to_city(trip["destination"])
        if origin_city.lower() == dest_city.lower():
            continue
        key = _route_key(origin_city, dest_city)

        if key not in route_counts:
            route_counts[key] = {
                "origin": key[0],
                "destination": key[1],
                "origin_city": origin_city,
                "dest_city": dest_city,
                "count": 0,
                "dates": [],
                "ticket_types": [],
            }
        route_counts[key]["count"] += 1
        route_counts[key]["dates"].append(trip["date"])
        route_counts[key]["ticket_types"].append(trip.get("ticket_type"))

    reduction_factor, reduction_warnings = _travel_reduction_factor()

    if not trips:
        data_window_months = 12
    else:
        all_dates = sorted(t["date"] for t in trips)
        earliest = date.fromisoformat(all_dates[0])
        latest = date.fromisoformat(all_dates[-1])
        data_window_months = max(1, round((latest - earliest).days / 30.44))

    projected: list[dict] = []
    warnings: list[str] = list(reduction_warnings)

    for key, info in route_counts.items():
        # Frequency threshold is checked on the raw historical rate — "is this actually a
        # recurring route" — before any travel_reduction damping is applied below, so a
        # damped-to-near-zero frequency never wrongly excludes a route the history clearly
        # supports.
        annual_freq = round(info["count"] * 12 / data_window_months)
        if annual_freq < 2:
            continue
        annual_freq = round(annual_freq * reduction_factor)

        origin = info["origin"]
        dest = info["destination"]
        fare_class = _dominant_fare_class(info["ticket_types"])

        if ORS_API_KEY:
            time.sleep(_REQUEST_DELAY)
        result = compute_route_alternatives(origin, dest)
        if result.get("warnings"):
            warnings.extend(result["warnings"])

        alternatives = result.get("alternatives", [])
        hav_km = result.get("haversine_km")
        dist_km = hav_km * 1.3 if hav_km else 0.0

        trip = ProjectedTrip(
            route=f"{origin} → {dest}",
            origin=origin,
            destination=dest,
            frequency_per_year=annual_freq,
            source="history",
            distance_km=round(dist_km, 1),
            alternatives=alternatives,
            fare_class=fare_class,
        )
        projected.append(trip.model_dump())

    trip_set = ProjectedTripSet(
        trips=projected,
        generated_at=datetime.now().isoformat(),
        warnings=warnings,
    )

    out_path = _DATA / "_projected_trips_history.json"
    _atomic_write_json(out_path, trip_set.model_dump())

    return {
        "status": "ok",
        "routes_projected": len(projected),
        "total_annual_trips": sum(t["frequency_per_year"] for t in projected),
        "routes": [
            {"route": t["route"], "frequency": t["frequency_per_year"], "alternatives_count": len(t["alternatives"])}
            for t in projected
        ],
        "file": "_projected_trips_history.json",
        "warnings": warnings,
    }


def derive_projected_trips_from_calendar(
    origin: str,
    destination: str,
    frequency_per_year: int,
) -> dict:
    """Derive a projected trip from an LLM-interpreted calendar event.

    The LLM reads calendar events, identifies recurring travel patterns
    (e.g. "Weekly Frankfurt office day"), and calls this tool with the
    origin, destination, and annual frequency it inferred.

    This tool computes route alternatives and appends the result to
    data/_projected_trips_calendar.json.

    Args:
        origin: Origin city (e.g. "Köln").
        destination: Destination city (e.g. "Frankfurt").
        frequency_per_year: How many times per year this trip occurs.

    Returns a dict with the projected trip and its alternatives.
    """
    result = compute_route_alternatives(origin, destination)
    alternatives = result.get("alternatives", [])
    hav_km = result.get("haversine_km")
    dist_km = round(hav_km * 1.3, 1) if hav_km else 0.0

    trip = ProjectedTrip(
        route=f"{origin} → {destination}",
        origin=origin,
        destination=destination,
        frequency_per_year=frequency_per_year,
        source="calendar",
        distance_km=dist_km,
        alternatives=alternatives,
    )

    cal_path = _DATA / "_projected_trips_calendar.json"
    if cal_path.exists():
        existing = json.loads(cal_path.read_text(encoding="utf-8"))
        existing_set = ProjectedTripSet.model_validate(existing)
        existing_trips = existing_set.trips
    else:
        existing_trips = []

    new_key = _route_key(origin, destination)
    duplicate_idx = None
    for i, t in enumerate(existing_trips):
        t_dict = t.model_dump() if isinstance(t, ProjectedTrip) else t
        if t_dict.get("origin") == "various":
            continue
        existing_key = _route_key(t_dict["origin"], t_dict["destination"])
        if existing_key == new_key:
            duplicate_idx = i
            break

    if duplicate_idx is not None:
        old = existing_trips[duplicate_idx]
        old_dict = old.model_dump() if isinstance(old, ProjectedTrip) else old
        old_freq = old_dict.get("frequency_per_year", 0)
        if frequency_per_year > old_freq:
            existing_trips[duplicate_idx] = trip
            logger.info("Calendar dedup: %s updated freq %d → %d", new_key, old_freq, frequency_per_year)
        else:
            logger.info("Calendar dedup: %s already exists with freq %d ≥ %d, skipping", new_key, old_freq, frequency_per_year)
    else:
        existing_trips.append(trip)

    trip_set = ProjectedTripSet(
        trips=[t.model_dump() if isinstance(t, ProjectedTrip) else t for t in existing_trips],
        generated_at=datetime.now().isoformat(),
        warnings=result.get("warnings", []),
    )
    _atomic_write_json(cal_path, trip_set.model_dump())

    return {
        "status": "ok",
        "trip": trip.model_dump(),
        "alternatives_count": len(alternatives),
        "file": "_projected_trips_calendar.json",
        "warnings": result.get("warnings", []),
        "deduplicated": duplicate_idx is not None,
    }


def derive_car_usage_trips() -> dict:
    """Derive projected trips from the user's private car usage profile.

    Uses deterministic formulas based on monthly_km_estimate from car_usage.json:
    - Short trips (20km): 40% of km budget → rail_regional, car_share alternatives
    - Medium trips (100km): 30% of km budget → rail, bus, car_share, car_rental alternatives
    - Long trips (500km): 30% of km budget → rail, bus, car_rental, flight alternatives

    Writes results to data/_projected_trips_car_usage.json and returns a summary.
    Only produces output if the user has a non-zero monthly_km_estimate.
    """
    car = load_car_usage()
    km_est = car.get("monthly_km_estimate")

    if not km_est or km_est <= 0:
        empty_set = ProjectedTripSet(
            trips=[],
            generated_at=datetime.now().isoformat(),
            warnings=["monthly_km_estimate is null or 0 — no car usage trips derived"],
        )
        _atomic_write_json(_DATA / "_projected_trips_car_usage.json", empty_set.model_dump())
        return {
            "status": "ok",
            "categories": [],
            "total_annual_trips": 0,
            "file": "_projected_trips_car_usage.json",
            "warnings": empty_set.warnings,
        }

    categories = [
        {
            "name": "short",
            "distance_km": 20,
            "km_share": 0.4,
            "modes": ["rail_regional", "car_share", "car_private"],
        },
        {
            "name": "medium",
            "distance_km": 100,
            "km_share": 0.3,
            "modes": ["rail_intercity", "car_share", "car_rental", "car_private"],
        },
        {
            "name": "long",
            "distance_km": 500,
            "km_share": 0.3,
            "modes": ["rail_intercity", "car_rental", "flight_domestic", "car_private"],
        },
    ]

    owns_car = car.get("owns_car", False)
    projected: list[dict] = []
    summary_cats: list[dict] = []

    for cat in categories:
        dist = cat["distance_km"]
        freq = max(1, round(cat["km_share"] * km_est / dist * 12))
        if freq < 1:
            continue

        alternatives: list[dict] = []
        for mode in cat["modes"]:
            if mode == "car_private" and not owns_car:
                continue
            co2_mode = mode
            if mode.startswith("flight"):
                co2_mode = "flight"
            elif mode.startswith("rail"):
                co2_mode = "rail"
            co2 = co2_kg_for_mode(co2_mode, dist)
            price = estimate_trip_price(mode, dist)
            dur = estimate_duration_min(mode, dist)

            alt = RouteAlternative(
                mode=mode,
                distance_km=dist,
                duration_min=round(dur, 1),
                co2_kg=round(co2, 3),
                estimated_price_eur=round(price, 2),
            )
            alternatives.append(alt.model_dump())

        trip = ProjectedTrip(
            route=f"Car usage ({cat['name']}, ~{dist}km)",
            origin="various",
            destination="various",
            frequency_per_year=freq,
            source="car_usage",
            category=cat["name"],
            distance_km=dist,
            alternatives=alternatives,
        )
        projected.append(trip.model_dump())
        summary_cats.append({
            "category": cat["name"],
            "distance_km": dist,
            "frequency_per_year": freq,
            "alternatives_count": len(alternatives),
        })

    trip_set = ProjectedTripSet(
        trips=projected,
        generated_at=datetime.now().isoformat(),
    )
    _atomic_write_json(_DATA / "_projected_trips_car_usage.json", trip_set.model_dump())

    return {
        "status": "ok",
        "categories": summary_cats,
        "total_annual_trips": sum(c["frequency_per_year"] for c in summary_cats),
        "file": "_projected_trips_car_usage.json",
        "warnings": [],
    }


def merge_projected_trip_sets() -> dict:
    """Merge all projected trip sources into a single combined trip set.

    Reads _projected_trips_history.json, _projected_trips_calendar.json, and
    _projected_trips_car_usage.json. Concatenates all trips and flags potential
    duplicates (same normalized route from different sources).

    Writes the merged result to data/_projected_trips_merged.json and returns a summary.
    """
    sources = [
        ("history", "_projected_trips_history.json"),
        ("calendar", "_projected_trips_calendar.json"),
        ("car_usage", "_projected_trips_car_usage.json"),
    ]

    raw_trips: list[dict] = []
    warnings: list[str] = []
    source_counts: dict[str, int] = {}

    for source_name, filename in sources:
        path = _DATA / filename
        if not path.exists():
            source_counts[source_name] = 0
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        trip_set = ProjectedTripSet.model_validate(raw)
        trips = [t.model_dump() for t in trip_set.trips]
        source_counts[source_name] = len(trips)
        raw_trips.extend(trips)
        warnings.extend(trip_set.warnings)

    _SOURCE_PRIORITY = {"calendar": 2, "history": 1}
    deduped: dict[tuple[str, str], dict] = {}
    car_usage_trips: list[dict] = []

    def _merge_fare_class(winner: dict, loser: dict) -> None:
        # Only the history source ever derives a real fare_class (from ticket_type text —
        # see _dominant_fare_class); calendar/car-usage trips always carry the model
        # default ("spar"), not an absence-of-Flexpreis finding. So when a calendar trip
        # wins a route dedup over a history trip that had detected "flex", the winner must
        # inherit it — otherwise the same physical route silently reverts to "spar" pricing
        # the moment it also appears on the calendar, undermining the whole fare-class
        # mechanism for exactly the routes a user actually keeps traveling.
        if loser.get("fare_class") == "flex":
            winner["fare_class"] = "flex"

    for trip in raw_trips:
        if trip.get("origin") == "various":
            car_usage_trips.append(trip)
            continue
        key = _route_key(trip["origin"], trip["destination"])
        if key in deduped:
            existing = deduped[key]
            existing_prio = _SOURCE_PRIORITY.get(existing["source"], 0)
            new_prio = _SOURCE_PRIORITY.get(trip["source"], 0)
            if new_prio > existing_prio:
                warnings.append(
                    f"Dedup: {key[0]} ↔ {key[1]} — calendar ({trip['frequency_per_year']}/yr) replaces history ({existing['frequency_per_year']}/yr)"
                )
                _merge_fare_class(trip, existing)
                deduped[key] = trip
            elif new_prio == existing_prio and trip["frequency_per_year"] > existing["frequency_per_year"]:
                _merge_fare_class(trip, existing)
                deduped[key] = trip
            else:
                _merge_fare_class(existing, trip)
        else:
            deduped[key] = trip

    all_trips = list(deduped.values()) + car_usage_trips

    merged = ProjectedTripSet(
        trips=all_trips,
        generated_at=datetime.now().isoformat(),
        warnings=warnings,
    )
    _atomic_write_json(_DATA / "_projected_trips_merged.json", merged.model_dump())

    return {
        "status": "ok",
        "total_trips": len(all_trips),
        "source_counts": source_counts,
        "total_annual_trip_instances": sum(t["frequency_per_year"] for t in all_trips),
        "duplicate_warnings": [w for w in warnings if w.startswith("Potential duplicate")],
        "file": "_projected_trips_merged.json",
    }


# ── Portfolio simulation (Branch 3) ──────────────────────────────────────────

# Enterprise tiers are automatic based on rental count per year.
_ENTERPRISE_TIERS = [
    (24, "enterprise_platinum"),
    (12, "enterprise_gold"),
    (6, "enterprise_silver"),
    (0, "enterprise_plus"),
]

# Miles & More tiers are automatic based on status miles per year.
# Rough heuristic: 1 intra-Europe flight ≈ 750 status miles.
_STATUS_MILES_PER_FLIGHT = 750
_MM_TIERS = [
    (600000, "lh_miles_hon_circle"),
    (100000, "lh_miles_senator"),
    (35000, "lh_miles_frequent_traveller"),
    (0, "lh_miles_member"),
]


def _resolve_automatic_tiers(
    projected_trips: list[dict], catalog: dict[str, dict]
) -> list[str]:
    """Determine automatic Enterprise and Miles & More tier IDs from projected trip volumes."""
    car_rental_trips = sum(
        t["frequency_per_year"]
        for t in projected_trips
        if any(a["mode"] == "car_rental" for a in t.get("alternatives", []))
    )
    flight_trips = sum(
        t["frequency_per_year"]
        for t in projected_trips
        if any(a["mode"].startswith("flight") for a in t.get("alternatives", []))
    )

    auto_ids: list[str] = []
    for threshold, tier_id in _ENTERPRISE_TIERS:
        if car_rental_trips >= threshold and tier_id in catalog:
            auto_ids.append(tier_id)
            break
    status_miles = flight_trips * _STATUS_MILES_PER_FLIGHT
    for threshold, tier_id in _MM_TIERS:
        if status_miles >= threshold and tier_id in catalog:
            auto_ids.append(tier_id)
            break
    return auto_ids


def apply_subscription_discount(
    mode: str,
    estimated_price_eur: float,
    distance_km: float,
    portfolio: list[dict],
    fare_class: str = "spar",
) -> float:
    """Apply subscription discounts to a single trip's estimated price.

    fare_class ("spar" or "flex") selects which catalog discount rate applies to a rail
    trip — discount_sparpreis_pct or discount_flexpreis_pct. These differ per BahnCard
    tier (e.g. BahnCard 50 gives 50% off Flexpreis but only 25% off Sparpreis), so a route
    whose historical trips were mostly booked Flexpreis (see _dominant_fare_class() in
    derive_projected_trips_from_history) must be scored against the Flexpreis rate, not
    silently assumed to be Sparpreis — otherwise every BahnCard tier looks identical on
    trips that were never actually priced that way.

    Returns the discounted price. The cheapest applicable discount wins.
    """
    best_price = estimated_price_eur

    for sub in portfolio:
        sub_mode = sub.get("mode")
        benefits = sub.get("benefits", {})

        if sub_mode == "rail" and mode in ("rail_intercity", "rail_regional"):
            if benefits.get("unlimited_regional") and mode == "rail_regional":
                best_price = min(best_price, 0.0)
            if benefits.get("unlimited_long_distance") and mode == "rail_intercity":
                best_price = min(best_price, 0.0)

            if fare_class == "flex":
                fare_pct = benefits.get("discount_flexpreis_pct")
            else:
                fare_pct = benefits.get("discount_sparpreis_pct")
            if fare_pct and not benefits.get("unlimited_long_distance"):
                discounted = estimated_price_eur * (1 - fare_pct / 100)
                best_price = min(best_price, discounted)

        elif sub_mode == "car_share" and mode == "car_share":
            base_km = benefits.get("base_km_rate_eur", 0.79)
            disc_km = benefits.get("discount_km_pct", 0)
            unlock = benefits.get("unlock_fee_eur_per_trip", 1.0)
            protection = benefits.get("protection_plus_eur_per_trip", 3.9)
            credit = benefits.get("monthly_credit_eur", 0)

            km_cost = base_km * (1 - disc_km / 100) * distance_km
            trip_cost = km_cost + unlock + protection
            if credit > 0:
                trip_cost = max(0, trip_cost - credit / 4)
            best_price = min(best_price, round(trip_cost, 2))

    return round(best_price, 2)


def simulate_portfolio(subscription_ids: list[str]) -> dict:
    """Simulate total annual cost, time, and CO2 for a given subscription portfolio.

    Loads the merged projected trip set, applies subscription discounts per trip,
    selects the cheapest mode for each trip, and sums up totals.

    Args:
        subscription_ids: List of catalog option IDs forming the portfolio
            (e.g. ["db_bc50_2nd_annual_standard", "miles_basis"]).

    Returns a dict with total_subscription_cost_eur, total_trip_cost_eur,
    total_annual_cost_eur, total_annual_time_min, total_annual_co2_kg,
    and a per-trip breakdown.
    """
    merged_path = _DATA / "_projected_trips_merged.json"
    if not merged_path.exists():
        return {"status": "error", "error": "_projected_trips_merged.json not found — run merge_projected_trip_sets first"}

    merged = json.loads(merged_path.read_text(encoding="utf-8"))
    trip_set = ProjectedTripSet.model_validate(merged)

    catalog_raw = json.loads((_STATIC / "mobility_catalog.json").read_text(encoding="utf-8"))
    catalog_by_id = {opt["id"]: opt for opt in catalog_raw["options"]}

    portfolio = []
    for sid in subscription_ids:
        opt = catalog_by_id.get(sid)
        if opt is None:
            return {"status": "error", "error": f"unknown subscription id: {sid}"}
        portfolio.append(opt)

    total_sub_cost = sum(opt["monthly_cost_eur"] * 12 for opt in portfolio)

    total_trip_cost = 0.0
    total_time = 0.0
    total_co2 = 0.0
    trip_breakdown: list[dict] = []

    for trip in trip_set.trips:
        alts = trip.alternatives
        if not alts:
            continue

        best_alt = None
        best_cost = float("inf")

        for alt in alts:
            alt_dict = alt if isinstance(alt, dict) else alt.model_dump()
            discounted = apply_subscription_discount(
                alt_dict["mode"],
                alt_dict["estimated_price_eur"],
                alt_dict["distance_km"],
                portfolio,
                fare_class=trip.fare_class,
            )
            if discounted < best_cost:
                best_cost = discounted
                best_alt = alt_dict

        if best_alt is None:
            continue

        annual_cost = best_cost * trip.frequency_per_year
        annual_time = best_alt["duration_min"] * trip.frequency_per_year
        annual_co2 = best_alt["co2_kg"] * trip.frequency_per_year

        total_trip_cost += annual_cost
        total_time += annual_time
        total_co2 += annual_co2

        trip_breakdown.append({
            "route": trip.route,
            "frequency": trip.frequency_per_year,
            "selected_mode": best_alt["mode"],
            "price_per_trip": best_cost,
            "annual_cost": round(annual_cost, 2),
            "annual_time_min": round(annual_time, 1),
            "annual_co2_kg": round(annual_co2, 3),
        })

    return {
        "status": "ok",
        "subscription_ids": subscription_ids,
        "total_subscription_cost_eur": round(total_sub_cost, 2),
        "total_trip_cost_eur": round(total_trip_cost, 2),
        "total_annual_cost_eur": round(total_sub_cost + total_trip_cost, 2),
        "total_annual_time_min": round(total_time, 1),
        "total_annual_co2_kg": round(total_co2, 3),
        "trip_breakdown": trip_breakdown,
    }


def compute_portfolio_score(
    simulation_results: list[dict],
    weights: dict,
) -> dict:
    """Score and rank multiple portfolio simulations using weighted normalization.

    Takes simulation results from multiple simulate_portfolio() calls and the
    user's priority weights. Normalizes each dimension (cost, time, CO2) to 0-1
    across all candidates, applies weights. Lower score = better.

    Args:
        simulation_results: List of dicts from simulate_portfolio().
        weights: Dict with cost_weight, time_weight, sustainability_weight (sum to 1).

    Returns a dict with ranked portfolios and their scores.
    """
    if not simulation_results:
        return {"status": "error", "error": "no simulation results to score"}

    parsed = []
    for r in simulation_results:
        if isinstance(r, str):
            try:
                r = json.loads(r)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(r, dict):
            parsed.append(r)

    valid = [r for r in parsed if r.get("status") == "ok"]
    if not valid:
        return {"status": "error", "error": "no valid simulation results"}

    if isinstance(weights, str):
        try:
            weights = json.loads(weights)
        except (json.JSONDecodeError, TypeError):
            weights = {}
    w_cost = weights.get("cost_weight", 0.34) if isinstance(weights, dict) else 0.34
    w_time = weights.get("time_weight", 0.33) if isinstance(weights, dict) else 0.33
    w_co2 = weights.get("sustainability_weight", 0.33) if isinstance(weights, dict) else 0.33

    costs = [r["total_annual_cost_eur"] for r in valid]
    times = [r["total_annual_time_min"] for r in valid]
    co2s = [r["total_annual_co2_kg"] for r in valid]

    def _normalize(values: list[float]) -> list[float]:
        lo, hi = min(values), max(values)
        if hi == lo:
            return [0.0] * len(values)
        spread_pct = (hi - lo) / max(abs(hi), abs(lo), 1)
        if spread_pct < 0.05:
            return [0.0] * len(values)
        return [(v - lo) / (hi - lo) for v in values]

    norm_cost = _normalize(costs)
    norm_time = _normalize(times)
    norm_co2 = _normalize(co2s)

    scored: list[dict] = []
    for i, r in enumerate(valid):
        score = w_cost * norm_cost[i] + w_time * norm_time[i] + w_co2 * norm_co2[i]
        scored.append({
            "subscription_ids": r["subscription_ids"],
            "score": round(score, 4),
            "total_annual_cost_eur": r["total_annual_cost_eur"],
            "total_annual_time_min": r["total_annual_time_min"],
            "total_annual_co2_kg": r["total_annual_co2_kg"],
            "norm_cost": round(norm_cost[i], 4),
            "norm_time": round(norm_time[i], 4),
            "norm_co2": round(norm_co2[i], 4),
        })

    scored.sort(key=lambda x: x["score"])

    return {
        "status": "ok",
        "weights": {"cost": w_cost, "time": w_time, "sustainability": w_co2},
        "ranked_portfolios": scored,
        "best": scored[0],
        "worst": scored[-1],
    }


def load_simulation_candidates() -> dict:
    """Load catalog options filtered for portfolio simulation.

    Pre-filters the catalog to a manageable set of chooseable subscriptions:
    1. Age-eligible options only
    2. Exclude 1st class BahnCards (simplification for v1)
    3. Exclude automatic tiers (Enterprise, Miles & More) — those are computed from trip volume
    4. Include only one MILES tier (the most relevant)

    Returns a dict with chooseable options and automatic tier info.
    """
    catalog_raw = json.loads((_STATIC / "mobility_catalog.json").read_text(encoding="utf-8"))
    catalog_options = catalog_raw["options"]
    catalog_by_id = {opt["id"]: opt for opt in catalog_options}

    persona = json.loads((_DATA / "persona.json").read_text(encoding="utf-8"))
    age = persona.get("profileData", {}).get("personal", {}).get("age")

    auto_tier_ids = {
        "enterprise_plus", "enterprise_silver", "enterprise_gold", "enterprise_platinum",
        "lh_miles_member", "lh_miles_frequent_traveller", "lh_miles_senator", "lh_miles_hon_circle",
    }
    first_class_ids = {
        "db_bc25_1st_annual_standard", "db_bc50_1st_annual_standard",
        "db_bc100_1st_annual", "db_bc100_2nd_annual",
    }
    excluded_no_sub_ids = {"flixbus_payperuse"}

    chooseable: list[dict] = []
    for opt in catalog_options:
        if opt["id"] in auto_tier_ids:
            continue
        if opt["id"] in first_class_ids:
            continue
        if opt["id"] in excluded_no_sub_ids:
            continue

        elig = opt.get("eligibility", {})
        if age is not None:
            min_age = elig.get("min_age")
            max_age = elig.get("max_age")
            if min_age is not None and age < min_age:
                continue
            if max_age is not None and age > max_age:
                continue

        chooseable.append(opt)

    merged_path = _DATA / "_projected_trips_merged.json"
    auto_tiers: list[str] = []
    if merged_path.exists():
        merged = json.loads(merged_path.read_text(encoding="utf-8"))
        trip_set = ProjectedTripSet.model_validate(merged)
        auto_tiers = _resolve_automatic_tiers(
            [t.model_dump() for t in trip_set.trips], catalog_by_id
        )

    return {
        "status": "ok",
        "chooseable_options": [
            {"id": o["id"], "product": o["product"], "mode": o["mode"], "monthly_cost_eur": o["monthly_cost_eur"]}
            for o in chooseable
        ],
        "chooseable_count": len(chooseable),
        "automatic_tiers": auto_tiers,
        "excluded_reasons": {
            "automatic_tiers": list(auto_tier_ids),
            "first_class": list(first_class_ids),
        },
    }


def optimize_all_categories() -> dict:
    """Deterministic portfolio optimization across all subscription categories.

    Systematically simulates every relevant subscription option (filtered by age,
    excluding 1st class and BC100), finds the best tier per category (rail, car-share),
    tests key combinations, and ranks all scenarios using the user's priority weights.

    Writes full results to _optimization_results.json for main.py to build
    frontend alternatives from. Returns a summary for the agent.
    """
    merged_path = _DATA / "_projected_trips_merged.json"
    if not merged_path.exists():
        return {"status": "error", "error": "Run merge_projected_trip_sets first"}

    catalog_raw = json.loads((_STATIC / "mobility_catalog.json").read_text(encoding="utf-8"))
    catalog_by_id = {opt["id"]: opt for opt in catalog_raw["options"]}

    prefs = load_user_preferences()
    age = prefs.get("age")
    # priority_weights is nested (see UserPreferences in models.py) — compute_portfolio_score
    # still takes the flat cost_weight/time_weight/sustainability_weight shape, so translate
    # here rather than changing its signature.
    pw = prefs.get("priority_weights", {})
    weights = {
        "cost_weight": pw.get("cost", 0.34),
        "time_weight": pw.get("time", 0.33),
        "sustainability_weight": pw.get("sustainability", 0.33),
    }

    current_raw = json.loads((_DATA / "current_subscriptions.json").read_text(encoding="utf-8"))
    current_ids = sorted(
        s["id"] for s in current_raw.get("subscriptions", []) if s["id"] in catalog_by_id
    )
    current_key = tuple(current_ids)

    SKIP_IDS = {
        "enterprise_plus", "enterprise_silver", "enterprise_gold", "enterprise_platinum",
        "lh_miles_member", "lh_miles_frequent_traveller", "lh_miles_senator", "lh_miles_hon_circle",
        "db_bc25_1st_annual_standard", "db_bc50_1st_annual_standard",
        "db_bc100_1st_annual", "db_bc100_2nd_annual",
        "flixbus_payperuse",
    }

    def _age_ok(opt):
        if age is None:
            return True
        elig = opt.get("eligibility", {})
        lo, hi = elig.get("min_age"), elig.get("max_age")
        return (lo is None or age >= lo) and (hi is None or age <= hi)

    chooseable = [o for o in catalog_raw["options"] if o["id"] not in SKIP_IDS and _age_ok(o)]

    rail = [o for o in chooseable if o["mode"] == "rail"]
    miles_opts = [o for o in chooseable if o["mode"] == "car_share"]
    dt_opts = [o for o in rail if o.get("benefits", {}).get("unlimited_regional")]
    bc_opts = [o for o in rail if not o.get("benefits", {}).get("unlimited_regional")]

    # --- Build candidate list: (label, category, ids) ---
    cands: list[tuple[str, str, list[str]]] = []
    cands.append(("No subscriptions", "baseline", []))

    for o in rail:
        cands.append((o["product"], "rail", [o["id"]]))
    for bc in bc_opts:
        for dt in dt_opts:
            cands.append((f"{bc['product']} + Deutschlandticket", "rail_combo", [bc["id"], dt["id"]]))
    for o in miles_opts:
        cands.append((o["product"], "car_share", [o["id"]]))

    # --- Simulate all (deduplicate by sorted ids) ---
    sim_cache: dict[tuple, dict] = {}
    entries: list[dict] = []
    seen_keys: set[tuple] = set()

    for label, cat, ids in cands:
        key = tuple(sorted(ids))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if key not in sim_cache:
            sim = simulate_portfolio(list(ids))
            if sim.get("status") != "ok":
                continue
            sim_cache[key] = sim
        sim = sim_cache[key]
        entries.append({
            "status": "ok",
            "label": label, "category": cat, "subscription_ids": list(ids),
            "total_subscription_cost_eur": sim["total_subscription_cost_eur"],
            "total_trip_cost_eur": sim["total_trip_cost_eur"],
            "total_annual_cost_eur": sim["total_annual_cost_eur"],
            "total_annual_time_min": sim["total_annual_time_min"],
            "total_annual_co2_kg": sim["total_annual_co2_kg"],
            "trip_breakdown": sim["trip_breakdown"],
        })

    # Add current portfolio if not already covered
    if current_key not in seen_keys and current_ids:
        sim = simulate_portfolio(current_ids)
        if sim.get("status") == "ok":
            sim_cache[current_key] = sim
            current_label = " + ".join(
                catalog_by_id[sid]["product"] for sid in current_ids if sid in catalog_by_id
            )
            entries.append({
                "status": "ok",
                "label": current_label, "category": "current",
                "subscription_ids": current_ids,
                "total_subscription_cost_eur": sim["total_subscription_cost_eur"],
                "total_trip_cost_eur": sim["total_trip_cost_eur"],
                "total_annual_cost_eur": sim["total_annual_cost_eur"],
                "total_annual_time_min": sim["total_annual_time_min"],
                "total_annual_co2_kg": sim["total_annual_co2_kg"],
                "trip_breakdown": sim["trip_breakdown"],
            })

    if not entries:
        return {"status": "error", "error": "No valid simulations produced"}

    # --- Find best per category, then try best-rail + best-miles combo ---
    best_rail_entry = min(
        (e for e in entries if e["category"] in ("rail", "rail_combo")),
        key=lambda e: e["total_annual_cost_eur"], default=None,
    )
    best_miles_entry = min(
        (e for e in entries if e["category"] == "car_share"),
        key=lambda e: e["total_annual_cost_eur"], default=None,
    )

    if best_rail_entry and best_miles_entry:
        combo_ids = best_rail_entry["subscription_ids"] + best_miles_entry["subscription_ids"]
        combo_key = tuple(sorted(combo_ids))
        if combo_key not in seen_keys:
            seen_keys.add(combo_key)
            sim = simulate_portfolio(combo_ids)
            if sim.get("status") == "ok":
                sim_cache[combo_key] = sim
                entries.append({
                    "status": "ok",
                    "label": f"{best_rail_entry['label']} + {best_miles_entry['label']}",
                    "category": "combo",
                    "subscription_ids": combo_ids,
                    "total_subscription_cost_eur": sim["total_subscription_cost_eur"],
                    "total_trip_cost_eur": sim["total_trip_cost_eur"],
                    "total_annual_cost_eur": sim["total_annual_cost_eur"],
                    "total_annual_time_min": sim["total_annual_time_min"],
                    "total_annual_co2_kg": sim["total_annual_co2_kg"],
                    "trip_breakdown": sim["trip_breakdown"],
                })

    # --- Score all ---
    scoring = compute_portfolio_score(entries, weights)
    rank_map = {
        tuple(sorted(r["subscription_ids"])): r["score"]
        for r in scoring["ranked_portfolios"]
    }
    for e in entries:
        e["score"] = rank_map.get(tuple(sorted(e["subscription_ids"])), 999)
    entries.sort(key=lambda e: e["score"])

    # --- Compute deltas vs recommended (#1) ---
    rec = entries[0]
    for e in entries:
        e["is_recommended"] = (e is rec)
        e["is_current"] = (tuple(sorted(e["subscription_ids"])) == current_key)
        e["delta_cost_eur"] = round(e["total_annual_cost_eur"] - rec["total_annual_cost_eur"], 2)
        e["delta_time_min"] = round(e["total_annual_time_min"] - rec["total_annual_time_min"], 1)
        e["delta_co2_kg"] = round(e["total_annual_co2_kg"] - rec["total_annual_co2_kg"], 3)

    # --- Select up to 5 scenarios to show ---
    # Guaranteed slots: recommended (#1) and current portfolio (always shown).
    shown: list[dict] = []
    shown_keys: set[tuple] = set()

    def _add(entry, force: bool = False):
        k = tuple(sorted(entry["subscription_ids"]))
        if k in shown_keys:
            return
        if not force:
            if len(shown) >= 5:
                return
            for s in shown:
                if abs(s["total_annual_cost_eur"] - entry["total_annual_cost_eur"]) < 1:
                    e_set = set(entry["subscription_ids"])
                    s_set = set(s["subscription_ids"])
                    if e_set != s_set and (e_set > s_set or e_set < s_set):
                        return
        shown.append(entry)
        shown_keys.add(k)

    _add(rec)

    current_entry = next((e for e in entries if e.get("is_current")), None)
    if current_entry and not current_entry.get("is_recommended"):
        _add(current_entry, force=True)

    best_per_cat: dict[str, dict] = {}
    for e in entries:
        best_per_cat.setdefault(e["category"], e)

    for cat in ["rail", "rail_combo", "car_share", "combo"]:
        if cat in best_per_cat:
            _add(best_per_cat[cat])

    if rec["category"] in ("rail", "rail_combo"):
        for e in entries:
            if e["category"] in ("rail", "rail_combo"):
                _add(e)

    for e in entries:
        _add(e)

    # --- Persist and return ---
    def _slim(e):
        return {k: v for k, v in e.items() if k != "trip_breakdown"}

    output = {
        "status": "ok",
        "weights": weights,
        "current_subscription_ids": current_ids,
        "scenarios": [_slim(e) for e in shown],
        "all_ranked": [_slim(e) for e in entries],
    }
    _atomic_write_json(_DATA / "_optimization_results.json", output)

    return {
        "status": "ok",
        "scenarios_count": len(shown),
        "total_simulated": len(entries),
        "weights": weights,
        "scenarios": [_slim(e) for e in shown],
    }


def load_current_subscriptions() -> dict:
    """Load the active user's currently held mobility subscriptions from the mock data store.

    Returns a dict with key 'subscriptions', a list of entries. Every entry is a full,
    exact mirror of one mobility_catalog.json product (enforced at validation time —
    a subscription can only ever reference a real catalog id), plus two
    subscription-specific fields. Every field below is always present; none are ever
    missing, and only next_renewal_date/started can be an empty string (never absent).

    id (str), provider (str), product (str), mode (str: rail/car_share/car_rental/
    flight/bus), monthly_cost_eur (float), billing_cycle (str), minimum_months (int),
    eligibility (dict: min_age/max_age, either may be null), benefits (dict, shape
    varies by mode), qualifying_threshold (dict or null, shape varies by mode),
    affiliated_airlines (list[str] or null, flight mode only), notes (str),
    next_renewal_date (str, "" if not applicable), started (str, "" if not applicable).
    """
    raw = json.loads((_DATA / "current_subscriptions.json").read_text(encoding="utf-8"))
    return CurrentSubscriptions.model_validate(raw).model_dump()


def load_mobility_catalog() -> dict:
    """Load the market-side mobility products catalog including pricing and benefits data.

    Returns a dict with key 'options', a list of available products each containing:
    id (str), provider (str), product (str), mode (str: rail/car_share/car_rental/flight/bus),
    monthly_cost_eur (float), benefits (dict), eligibility (dict), qualifying_threshold (dict or null).
    """
    raw = json.loads((_STATIC / "mobility_catalog.json").read_text(encoding="utf-8"))
    return MobilityCatalog.model_validate(raw).model_dump()


def load_relevant_mobility_catalog() -> dict:
    """Load the market catalog narrowed to options relevant to the active user.

    Same shape as load_mobility_catalog() (key 'options'), but filtered by two
    deterministic signals computed from the user's own data — not an embedding
    or relevance ranking:
      1. Mode relevance: drop a whole mode category (rail/car_share/car_rental/
         flight/bus) only if the user has never held a subscription in it nor
         taken a trip in it.
      2. Age eligibility: drop an option the user could not actually sign up
         for, per persona.json's age and the option's eligibility range.
    Each kept option also has its 'notes' field dropped — that field is
    free-text prose that duplicates numbers already present in 'benefits'/
    'monthly_cost_eur' on the same option.

    If applying the filter would remove every option (e.g. a brand-new profile
    with no subscriptions or trips yet), returns the full unfiltered catalog
    instead — with no usage signal, no filter criterion is trustworthy, and an
    empty catalog is worse than an oversized one.

    Use this (not load_mobility_catalog) when proposing or comparing contract
    options for the current user. load_mobility_catalog stays the source of
    truth for arbitrary lookups about any product regardless of relevance.
    """
    catalog = load_mobility_catalog()["options"]

    subs = load_current_subscriptions()["subscriptions"]
    trips = load_travel_history()["trips"]
    touched_modes = {s["mode"] for s in subs} | {
        t["mode"] for t in trips if t.get("mode")  # trips stay a messier data source, unchanged
    }

    persona = json.loads((_DATA / "persona.json").read_text(encoding="utf-8"))
    age = persona.get("profileData", {}).get("personal", {}).get("age")

    def eligible(option: dict) -> bool:
        if option["mode"] not in touched_modes:
            return False
        if age is None:
            return True
        elig = option["eligibility"]  # always present as a dict of {min_age, max_age}
        min_age, max_age = elig["min_age"], elig["max_age"]
        if min_age is not None and age < min_age:
            return False
        if max_age is not None and age > max_age:
            return False
        return True

    filtered = [
        {k: v for k, v in option.items() if k != "notes"}
        for option in catalog
        if eligible(option)
    ]
    return {"options": filtered or catalog}


_KNOWN_MODES = {"rail", "car_share", "car_rental", "flight", "bus"}


def _travel_history_result(trips: list) -> dict:
    """Build the load_travel_history return shape (trips + data_quality_warnings) for a given trip list."""
    warnings = []
    for trip in trips:
        label = f"{trip.date} {trip.origin}→{trip.destination}"
        if trip.cost_eur is None:
            warnings.append(f"{label}: cost_eur is null — excluded from spend totals")
        if not trip.mode:
            warnings.append(f"{label}: mode is empty — excluded from CO₂ and mode aggregations")
        elif trip.mode not in _KNOWN_MODES:
            warnings.append(f"{label}: unknown mode '{trip.mode}' — excluded from CO₂ and mode aggregations")

    result = {"trips": [t.model_dump() for t in trips]}
    if warnings:
        result["data_quality_warnings"] = warnings
    return result


def load_travel_history() -> dict:
    """Load Maja's 12-month travel history from the mock data store.

    Returns a dict with key 'trips', a list of past trips each containing:
    date (str), mode (str), origin (str), destination (str), distance_km (float),
    cost_eur (float or null), provider (str), booked_under (str or null).
    If any trips have data quality issues, a 'data_quality_warnings' key is included
    listing each problem so downstream agents can surface them to the user.
    """
    raw = json.loads((_DATA / "travel_history_raw.json").read_text(encoding="utf-8"))
    history = TravelHistory.model_validate(raw)
    return _travel_history_result(history.trips)


def load_annual_travel_history() -> dict:
    """Load travel history for the annual report, scoped to REVIEW_YEAR only.

    Same shape as load_travel_history, but trips outside REVIEW_YEAR (the last full
    calendar year) are excluded before any downstream agent sees them — the annual
    report's stated period must only ever reflect data actually filtered to that year,
    not the full unfiltered history.
    """
    raw = json.loads((_DATA / "travel_history_raw.json").read_text(encoding="utf-8"))
    history = TravelHistory.model_validate(raw)
    year_trips = [t for t in history.trips if t.date.startswith(str(REVIEW_YEAR))]
    return _travel_history_result(year_trips)


def load_calendar_events() -> dict:
    """Load upcoming calendar events — from mock data or live Outlook API.

    Returns a dict with key 'events', a list of upcoming events each containing:
    date (str), type (str: trip/meeting/life_event), description (str),
    location (str or null), signals (list[str] — demand or life-change indicators).
    """
    if USE_MOCK_DATA:
        raw = json.loads((_DATA / "calendar_events_live.json").read_text(encoding="utf-8"))
    else:
        from .outlook_calendar import fetch_calendar_events
        raw = fetch_calendar_events()
    return CalendarEvents.model_validate(raw).model_dump()


def load_annual_analyst_context() -> dict:
    """Load all fixed-context data the Annual Analyst agent needs, in one call: travel
    history scoped to REVIEW_YEAR, current subscriptions, and car usage.

    Internally calls load_annual_travel_history(), load_current_subscriptions(), and
    load_car_usage() and returns their results together under one dict. This exists
    purely to save two tool-call round-trips versus calling the three individually — it
    changes zero fields and zero values versus calling them separately. Unlike the
    regular (non-annual) Analyst, which derives projected trips deterministically
    instead of using a bundled context call like this one, the Annual Analyst stays on
    the older, LLM-narrated design (see CLAUDE.md's Four-stage pipelines section).

    Returns a dict with keys:
      - travel_history: exactly load_annual_travel_history()'s return value (key 'trips',
        list of trip dicts limited to REVIEW_YEAR; optional 'data_quality_warnings' list).
      - current_subscriptions: exactly load_current_subscriptions()'s return value.
      - car_usage: exactly load_car_usage()'s return value.
    """
    return {
        "travel_history": load_annual_travel_history(),
        "current_subscriptions": load_current_subscriptions(),
        "car_usage": load_car_usage(),
    }


def load_forecaster_context() -> dict:
    """Load all fixed-context data the Forecaster agent needs, in one call: upcoming
    calendar events and life-event signals.

    Internally calls load_calendar_events() and load_life_events() and returns their
    results together — saves one tool-call round-trip versus calling them individually;
    changes zero fields and zero values. Shared verbatim by forecaster_agent and
    annual_forecaster_agent — both need identical, forward-looking (not year-scoped) data.

    Returns a dict with keys:
      - calendar_events: exactly load_calendar_events()'s return value (key 'events').
      - life_events: exactly load_life_events()'s return value (key 'events'; an empty
        list is a legitimate result, not a loading failure).
    """
    return {
        "calendar_events": load_calendar_events(),
        "life_events": load_life_events(),
    }


def load_annual_optimizer_context() -> dict:
    """Load all fixed-context data the Annual Optimizer agent needs up front, in one
    call: user preferences and the user-relevant mobility catalog.

    Internally calls load_user_preferences() and load_relevant_mobility_catalog() and
    returns their results together — saves one tool-call round-trip versus calling them
    individually; changes zero fields and zero values.

    Deliberately excludes recommendation_history: the annual report's instruction has no
    CONTINUITY section referencing past recommendations (unlike the regular Communicator,
    which reads load_recommendation_history() directly — see CLAUDE.md's Four-stage
    pipelines section), so recent-history data stays out of this agent's tool surface,
    matching annual_optimizer_agent's existing tools=[...] scoping.

    Does NOT include compute_co2_impact_kg — that tool stays a separate, on-demand call
    invoked once per candidate action in Step 3 (with different target_subscription/
    new_product arguments each time), not once up front like the loaders bundled here.

    Returns a dict with keys:
      - user_preferences: exactly load_user_preferences()'s return value.
      - relevant_mobility_catalog: exactly load_relevant_mobility_catalog()'s return
        value (key 'options').
    """
    return {
        "user_preferences": load_user_preferences(),
        "relevant_mobility_catalog": load_relevant_mobility_catalog(),
    }


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
        sub_match, _ = _resolve_unique_match(needle, subs, ("product", "provider"))
        if sub_match is not None:
            subscription_renewal = {
                "next_renewal_date": sub_match["next_renewal_date"],
                "billing_cycle": sub_match["billing_cycle"],
            }

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


def _resolve_unique_match(
    needle: str, candidates: list[dict], fields: tuple[str, ...]
) -> tuple[dict | None, str | None]:
    """Find exactly one candidate whose given fields contain needle as a case-insensitive substring.

    Falls back to token-overlap matching (≥ 2 alphanumeric words in common) when substring
    matching yields no results, to handle language/notation variants such as "2nd class" vs
    "2. Klasse" introduced by LLM paraphrasing.

    Returns (match, None) on exactly one match. Returns (None, error_message) if zero or
    more than one candidate matches — callers must treat both as failure, never guess.
    """
    needle_lower = needle.lower()

    # Primary: case-insensitive substring
    matches = [
        c for c in candidates if any(needle_lower in str(c.get(f, "")).lower() for f in fields)
    ]

    # Fallback: token overlap — handles variants like "2nd class" vs "2. Klasse"
    if not matches:
        needle_tokens = set(re.findall(r'\w+', needle_lower))
        matches = [
            c for c in candidates
            if any(
                len(needle_tokens & set(re.findall(r'\w+', str(c.get(f, "")).lower()))) >= 2
                for f in fields
            )
        ]

    if not matches:
        return None, f"no match for '{needle}'"
    if len(matches) > 1:
        names = ", ".join(c.get("product", "?") for c in matches)
        return None, f"ambiguous match for '{needle}': matched {len(matches)} entries ({names})"
    return matches[0], None


# Only car-sharing (e.g. MILES) requires membership to use the mode at all — rail passes,
# Deutschlandticket, and car-rental loyalty tiers are discount/rewards programs layered on
# top of a mode you can already use without any subscription (full-price ticket, pay-as-you-go
# rental), so losing them changes price, not which mode is usable.
_MODE_ACCESS_GATED_MODES = {"car_share"}


def _generic_car_co2_factor_kg_per_km() -> float:
    """kg CO2e/km for driving a car with no specific type/size known — the fallback used when
    a candidate removes the user's only access to car-sharing. Car_private/Car_Sharing/
    Car_Rental all share the same 'Null,Null' average in co2_factors.csv, so it doesn't matter
    which of the three the user would actually end up driving."""
    with (_STATIC / "co2_factors.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["mode"] == "Car_Sharing" and row["type"] == "Null" and row["size"] == "Null":
                return float(row["kg_co2e_per_km"])
    raise RuntimeError("Car_Sharing,Null,Null row missing from co2_factors.csv")


def _rail_and_carshare_co2_factors() -> tuple[float, float]:
    """Return (rail, car_share) generic CO2 factors in g/km, sourced from co2_factors.csv's
    Rail/Null/Null and Car_Sharing/Null/Null rows — the same generic-average rows
    _generic_car_co2_factor_kg_per_km already reads for the optimizer, so the annual report's
    fixed CO2 formula can never disagree with the optimizer's own per-candidate CO2 math about
    what a generic rail/car-share km costs. Used to interpolate real figures into
    annual_communicator's prompt instead of a hardcoded assumption."""
    rail_kg_per_km: float | None = None
    car_share_kg_per_km: float | None = None
    with (_STATIC / "co2_factors.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["type"] != "Null" or row["size"] != "Null":
                continue
            if row["mode"] == "Rail":
                rail_kg_per_km = float(row["kg_co2e_per_km"])
            elif row["mode"] == "Car_Sharing":
                car_share_kg_per_km = float(row["kg_co2e_per_km"])
    if rail_kg_per_km is None or car_share_kg_per_km is None:
        raise RuntimeError("Rail,Null,Null or Car_Sharing,Null,Null row missing from co2_factors.csv")
    return round(rail_kg_per_km * 1000, 2), round(car_share_kg_per_km * 1000, 2)


def _rail_coverage_kind(sub: dict) -> str:
    """Classify a rail subscription's catalog benefits by how it covers trips.

    A persona can hold both a long-distance discount card (BahnCard) and a flat-fee
    regional pass (Deutschlandticket) at once — both are mode="rail", provider=
    "Deutsche Bahn", so a plain (mode, provider) match would attribute every rail
    trip to both. The catalog's benefits flags tell them apart:
      - "unlimited_all": unlimited_long_distance AND unlimited_regional (e.g.
        BahnCard 100) — every rail trip is already included, nothing to discount.
      - "unlimited_regional": unlimited_regional only (e.g. Deutschlandticket) — a
        flat monthly fee covering regional trips only.
      - "discount": neither flag set, just discount_sparpreis_pct/discount_
        flexpreis_pct (e.g. BahnCard 25/50) — a % off a fare that was still paid.
    """
    benefits = sub.get("benefits") or {}
    if benefits.get("unlimited_long_distance") and benefits.get("unlimited_regional"):
        return "unlimited_all"
    if benefits.get("unlimited_regional"):
        return "unlimited_regional"
    return "discount"


def compute_annual_report_stats() -> dict:
    """Deterministic, code-computed figures for the annual report.

    Spend, CO2, and per-subscription value are calculated here in Python rather than
    left to the LLM, so the report's headline numbers can never silently contradict
    each other the way free-text arithmetic spread across three separate agent stages
    could (e.g. a "savings" figure in one section disagreeing with a "net loss" verdict
    for the same subscription in another). annual_communicator_agent narrates around
    these figures instead of computing them itself; main.py's /api/annual-report
    endpoint substitutes the rendered tables into the report's placeholder sections.

    Trip-to-subscription attribution is done here by (mode, provider) match against
    load_annual_travel_history()'s year-scoped trips — not by the trip data's
    'booked_under' field, which is null for every mock trip and would otherwise make
    every subscription look completely unused.

    Returns a dict with keys:
      - review_year (int)
      - total_spend_eur (float): year-scoped trip costs (cost_eur present only) plus
        every active subscription's annualized fee
      - total_trips (int), trips_missing_cost (int)
      - dominant_mode (str): the mode with the most trips this year ("" if none)
      - by_mode (list[dict]): one row per mode present this year, each
        {mode, trips, distance_km, spend_eur, co2_kg}, sorted by co2_kg descending,
        followed by a final {mode: "Total", ...} row
      - total_co2_kg (float): sum of co2_emission_kg across every trip this year,
        all modes included — the honest total footprint
      - rail_vs_car_saving_kg (float): CO2 avoided by taking rail instead of a generic
        car-share for the same distance, computed over rail trips only. This is a
        secondary "smart regional choice" figure — it is NOT subtracted from
        total_co2_kg, which already reflects what was actually emitted.
      - rail_co2_g_per_km / carshare_co2_g_per_km (float): the factors behind the
        figure above, for the report's methodology section
      - subscriptions (list[dict]): one per active subscription, each
        {product, provider, mode, monthly_cost_eur, billing_cycle, annual_fee_eur,
         is_paid_subscription, has_discount_value, trips_attributed,
         discount_value_eur, net_eur, qualifying_activity}. discount_value_eur/
        net_eur are populated only when has_discount_value is True — False (and
        both fields None) for €0 loyalty tiers (no fee to break even against) and
        for paid flat-fee unlimited-access rail passes like Deutschlandticket or
        BahnCard 100 (no discrete per-trip fare to discount; see
        _rail_coverage_kind). qualifying_activity is None unless the subscription
        carries a usage threshold (e.g. Enterprise Silver's rentals_per_year).
      - data_quality_warnings (list[str])
    """
    history = load_annual_travel_history()
    trips = history["trips"]
    warnings = list(history.get("data_quality_warnings", []))

    total_trips = len(trips)
    trips_missing_cost = sum(1 for t in trips if t["cost_eur"] is None)

    by_mode_acc: dict[str, dict] = {}
    for t in trips:
        mode = t["mode"] or "unknown"
        row = by_mode_acc.setdefault(
            mode, {"mode": mode, "trips": 0, "distance_km": 0.0, "spend_eur": 0.0, "co2_kg": 0.0}
        )
        row["trips"] += 1
        row["distance_km"] += t["distance_km"] or 0.0
        row["spend_eur"] += t["cost_eur"] or 0.0
        row["co2_kg"] += t["co2_emission_kg"] or 0.0

    by_mode = sorted(by_mode_acc.values(), key=lambda r: r["co2_kg"], reverse=True)
    for row in by_mode:
        row["distance_km"] = round(row["distance_km"], 1)
        row["spend_eur"] = round(row["spend_eur"], 2)
        row["co2_kg"] = round(row["co2_kg"], 2)

    total_co2_kg = round(sum(r["co2_kg"] for r in by_mode), 2)
    trip_spend_eur = round(sum(r["spend_eur"] for r in by_mode), 2)
    dominant_mode = max(by_mode_acc.values(), key=lambda r: r["trips"])["mode"] if by_mode_acc else ""

    by_mode_with_total = by_mode + [{
        "mode": "Total",
        "trips": total_trips,
        "distance_km": round(sum(r["distance_km"] for r in by_mode), 1),
        "spend_eur": trip_spend_eur,
        "co2_kg": total_co2_kg,
    }]

    rail_g_per_km, carshare_g_per_km = _rail_and_carshare_co2_factors()
    rail_km = sum(t["distance_km"] or 0.0 for t in trips if t["mode"] == "rail")
    rail_vs_car_saving_kg = round(rail_km * (carshare_g_per_km - rail_g_per_km) / 1000, 2)

    subscriptions_raw = load_current_subscriptions()["subscriptions"]
    subscriptions = []
    for sub in subscriptions_raw:
        matched = [
            t for t in trips
            if t["mode"] == sub["mode"] and sub["provider"].lower() in (t["provider"] or "").lower()
        ]

        is_paid = sub["monthly_cost_eur"] > 0
        has_discount_value = is_paid

        if sub["mode"] == "rail":
            coverage_kind = _rail_coverage_kind(sub)
            if coverage_kind == "unlimited_regional":
                # A flat monthly fee for unlimited *regional* travel (e.g.
                # Deutschlandticket) only covers trips priced at 0 in this mock data
                # — there's no separate per-trip charge once you hold the pass. A
                # long-distance trip on the same provider is a different product
                # (e.g. BahnCard) and must not be claimed here too, or a persona
                # holding both ends up with every rail trip double-attributed.
                matched = [t for t in matched if (t["cost_eur"] or 0) == 0]
                has_discount_value = False
            elif coverage_kind == "unlimited_all":
                # e.g. BahnCard 100 — every rail trip is already included, so there's
                # no discrete "amount paid" to treat as a discount either.
                has_discount_value = False
            else:  # "discount" (e.g. BahnCard 25/50) — a % off a fare you still paid
                matched = [t for t in matched if t["cost_eur"] not in (None, 0)]

        trips_attributed = len(matched)
        annual_fee_eur = round(sub["monthly_cost_eur"] * 12, 2)

        discount_value_eur = None
        net_eur = None
        if has_discount_value:
            discount_value_eur = round(
                sum(t["cost_eur"] for t in matched if t["cost_eur"] is not None), 2
            )
            net_eur = round(discount_value_eur - annual_fee_eur, 2)

        qualifying_activity = None
        threshold = sub.get("qualifying_threshold")
        if threshold and threshold.get("rentals_per_year") is not None:
            qualifying_activity = {"count": trips_attributed, "threshold": threshold["rentals_per_year"]}

        subscriptions.append({
            "product": sub["product"],
            "provider": sub["provider"],
            "mode": sub["mode"],
            "monthly_cost_eur": sub["monthly_cost_eur"],
            "billing_cycle": sub["billing_cycle"],
            "annual_fee_eur": annual_fee_eur,
            "is_paid_subscription": is_paid,
            "has_discount_value": has_discount_value,
            "trips_attributed": trips_attributed,
            "discount_value_eur": discount_value_eur,
            "net_eur": net_eur,
            "qualifying_activity": qualifying_activity,
        })

    total_spend_eur = round(trip_spend_eur + sum(s["annual_fee_eur"] for s in subscriptions), 2)

    return {
        "review_year": REVIEW_YEAR,
        "total_spend_eur": total_spend_eur,
        "total_trips": total_trips,
        "trips_missing_cost": trips_missing_cost,
        "dominant_mode": dominant_mode,
        "by_mode": by_mode_with_total,
        "total_co2_kg": total_co2_kg,
        "rail_vs_car_saving_kg": rail_vs_car_saving_kg,
        "rail_co2_g_per_km": rail_g_per_km,
        "carshare_co2_g_per_km": carshare_g_per_km,
        "subscriptions": subscriptions,
        "data_quality_warnings": warnings,
    }


def compute_co2_impact_kg(
    target_subscription: str | None = None,
    new_product: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Compute the CO2 delta (kg/year) of one candidate portfolio change vs. the current portfolio.

    Grounded in real per-trip co2_emission_kg data (already computed offline from
    co2_factors.csv) — never invents or estimates a distance/emissions figure. Call this for
    EVERY candidate action before writing its CO2 impact line; do not compute CO2 yourself.

    Same add/remove/replace argument shape as apply_subscription_change: target_subscription
    is the current subscription being removed (None for a pure add), new_product is the
    catalog product being added (None for a pure cancel). Matched the same way
    apply_subscription_change matches them (case-insensitive substring against
    product/provider, falling back to token overlap) — must resolve to exactly one entry
    each; zero or multiple matches return an error rather than guessing.

    Most candidates are CO2-neutral by design: a subscription only changes emissions if
    removing it takes away the user's *last* remaining way to use a given transport mode at
    all. In the current catalog that is true only for car-sharing (membership-gated); rail
    cards, Deutschlandticket, and car-rental loyalty tiers are discount/rewards programs on
    top of a mode usable without any subscription, so changing/cancelling them is always
    neutral (0 kg) — e.g. downgrading BahnCard 50 to BahnCard 25 never affects CO2, only price.

    Args:
        target_subscription: Substring/name of the current subscription being removed or
            replaced, matched against current_subscriptions.json. None for a pure "add".
        new_product: Substring/name of the catalog product being added, matched against
            mobility_catalog.json. None for a pure "cancel".
        date_from: Optional inclusive ISO date ("YYYY-MM-DD") — same filter semantics as
            compute_travel_stats. Pass this (with date_to) when evaluating the ANNUAL report
            so affected trips are scoped to REVIEW_YEAR only, not the full travel history.
            Leave both None for the regular (non-annual) review, which uses all available trips.
        date_to: Optional inclusive ISO date ("YYYY-MM-DD"); see date_from.

    Returns a dict with: status ("ok" or "error"), mode_access_changed (bool, whether this
    candidate actually removes the user's last access to a gated mode), delta_kg (float,
    signed — positive means the candidate SAVES this many kg CO2/year vs. the current
    portfolio, negative means it emits this many kg MORE; always 0.0 when
    mode_access_changed is False), co2_before_kg / co2_after_kg (float, only meaningful when
    mode_access_changed is True), trips_affected (int), explanation (str, a ready-to-quote
    one-line sentence stating the signed number plainly — quote this verbatim as the CO2
    impact line, do not paraphrase or recompute it), and error (str or None).
    """

    def _result(
        *,
        mode_access_changed: bool = False,
        delta_kg: float = 0.0,
        co2_before_kg: float = 0.0,
        co2_after_kg: float = 0.0,
        trips_affected: int = 0,
        explanation: str,
        error: str | None = None,
    ) -> dict:
        return {
            "status": "error" if error else "ok",
            "mode_access_changed": mode_access_changed,
            "delta_kg": round(delta_kg, 2),
            "co2_before_kg": round(co2_before_kg, 2),
            "co2_after_kg": round(co2_after_kg, 2),
            "trips_affected": trips_affected,
            "explanation": explanation,
            "error": error,
        }

    if not target_subscription and not new_product:
        return _result(
            explanation="",
            error="at least one of target_subscription or new_product is required",
        )

    subs = load_current_subscriptions()["subscriptions"]
    target_match = None
    if target_subscription:
        target_match, error = _resolve_unique_match(target_subscription, subs, ("product", "provider"))
        if error:
            return _result(explanation="", error=error)

    catalog_match = None
    if new_product:
        catalog_options = load_mobility_catalog()["options"]
        catalog_match, error = _resolve_unique_match(new_product, catalog_options, ("product", "provider"))
        if error:
            return _result(explanation="", error=error)

    # Pure add: no historical trips can be attributed to a mode the user is only now gaining
    # (or a second subscription for a mode they already have) — stated honestly rather than guessed.
    if target_match is None:
        return _result(
            explanation=(
                "Neutral — 0 kg CO2/year. This adds a subscription without removing another, "
                "so it doesn't change which mode you currently use for any trip."
            )
        )

    changed_mode = target_match["mode"]
    if changed_mode not in _MODE_ACCESS_GATED_MODES:
        return _result(
            explanation=(
                "Neutral — 0 kg CO2/year. This changes price/tier only; it doesn't affect "
                f"which mode of transport you use (you can still use {changed_mode} with or "
                "without this subscription)."
            )
        )

    still_covered = (catalog_match is not None and catalog_match["mode"] == changed_mode) or any(
        s["mode"] == changed_mode and s is not target_match for s in subs
    )
    if still_covered:
        return _result(
            explanation=(
                "Neutral — 0 kg CO2/year. You keep another subscription covering "
                f"{changed_mode}, so access to this mode is unaffected."
            )
        )

    trips = load_travel_history()["trips"]
    affected = [
        t
        for t in trips
        if t.get("mode") == changed_mode
        and (date_from is None or t.get("date", "") >= date_from)
        and (date_to is None or t.get("date", "") <= date_to)
    ]
    co2_before_kg = sum(
        t["co2_emission_kg"] for t in affected if t.get("co2_emission_kg") is not None
    )
    generic_factor = _generic_car_co2_factor_kg_per_km()
    co2_after_kg = sum(
        t["distance_km"] * generic_factor for t in affected if t.get("distance_km") is not None
    )
    delta_kg = co2_before_kg - co2_after_kg
    period = "in the period considered" if (date_from or date_to) else "from the past 12 months"

    if delta_kg >= 0:
        explanation = (
            f"{delta_kg:.1f} kg CO2/year saved. Losing your only {changed_mode} subscription "
            f"means your {len(affected)} {changed_mode} trip(s) {period} would "
            f"shift to driving (at {generic_factor * 1000:.0f} g/km), which is actually lower "
            f"emissions than those trips currently produce ({co2_before_kg:.1f} kg → "
            f"{co2_after_kg:.1f} kg)."
        )
    else:
        explanation = (
            f"{abs(delta_kg):.1f} kg CO2/year more emissions. Losing your only {changed_mode} "
            f"subscription means your {len(affected)} {changed_mode} trip(s) {period} "
            f"would shift to driving (at {generic_factor * 1000:.0f} g/km), raising "
            f"emissions from {co2_before_kg:.1f} kg to {co2_after_kg:.1f} kg/year."
        )

    return _result(
        mode_access_changed=True,
        delta_kg=delta_kg,
        co2_before_kg=co2_before_kg,
        co2_after_kg=co2_after_kg,
        trips_affected=len(affected),
        explanation=explanation,
    )


def _add_months(d: date, months: int) -> date:
    """Add a number of months to a date, clamping the day to the target month's last valid day."""
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _compute_next_renewal_date(as_of: date, billing_cycle: str) -> str:
    """Compute the next renewal date as an ISO string from an as-of date and billing cycle."""
    if billing_cycle == "annual":
        return _add_months(as_of, 12).isoformat()
    if billing_cycle == "monthly":
        return _add_months(as_of, 1).isoformat()
    raise ValueError(f"unknown billing_cycle: {billing_cycle!r}")


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write data as JSON to path atomically (temp file + os.replace); never leaves a partial file."""
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def apply_subscription_change(
    action: Literal["add", "remove", "replace"],
    target_subscription: str | None = None,
    new_product: str | None = None,
    as_of: date | None = None,
) -> dict:
    """Apply one confirmed change to Maja's active subscriptions. The sole writer of current_subscriptions.json.

    Only call this after the user has explicitly instructed a specific change — never to
    evaluate whether a change is a good idea. mobility_catalog.json and every other
    fixture stay read-only; only current_subscriptions.json is ever written, and only on
    full success. No write of any kind happens on any error path.

    Args:
        action: "add" a new subscription, "remove" an existing one, or "replace" (remove
            the matched target and add the matched new_product in a single atomic write).
        target_subscription: Required for "remove"/"replace". Matched case-insensitively
            as a substring against each current subscription's product or provider field.
            Must resolve to exactly one subscription — zero or multiple matches both return
            an error with no write, rather than guessing which one was meant.
        new_product: Required for "add"/"replace". Matched the same way against
            mobility_catalog.json's options. Must resolve to exactly one catalog option —
            zero or multiple matches both return an error with no write.
        as_of: The date to treat as "today" when computing the new entry's started date
            and next_renewal_date. Defaults to MOCK_TODAY when omitted. Exists only for
            deterministic testing — leave unset in normal use.

    Returns a dict with: status ("applied" or "error"), action, removed (list of removed
    subscription dicts, empty if none), added (list of added subscription dicts, empty if
    none), before_count (int), after_count (int), file ("current_subscriptions.json"),
    warnings (list[str], e.g. noting a same-product replace), and error (str message, or
    None on success).
    """
    as_of = as_of or MOCK_TODAY
    warnings: list[str] = []

    def _error(message: str, before_count: int = 0) -> dict:
        return {
            "status": "error",
            "action": action,
            "removed": [],
            "added": [],
            "before_count": before_count,
            "after_count": before_count,
            "file": "current_subscriptions.json",
            "warnings": warnings,
            "error": message,
        }

    if action in ("remove", "replace") and not target_subscription:
        return _error(f"target_subscription is required for action={action!r}")
    if action in ("add", "replace") and not new_product:
        return _error(f"new_product is required for action={action!r}")

    # Load raw dicts to preserve all fields beyond the Pydantic model.
    raw_file = json.loads((_DATA / "current_subscriptions.json").read_text(encoding="utf-8"))
    subs_list = raw_file["subscriptions"]
    before_count = len(subs_list)

    target_match = None
    if action in ("remove", "replace"):
        target_match, error = _resolve_unique_match(
            target_subscription, subs_list, ("product", "provider")
        )
        if error:
            return _error(error, before_count)

    catalog_match = None
    if action in ("add", "replace"):
        catalog_options = load_mobility_catalog()["options"]
        catalog_match, error = _resolve_unique_match(
            new_product, catalog_options, ("product", "provider")
        )
        if error:
            return _error(error, before_count)

    new_sub = None
    if catalog_match is not None:
        try:
            next_renewal_date = _compute_next_renewal_date(as_of, catalog_match["billing_cycle"])
        except ValueError as exc:
            return _error(str(exc), before_count)
        new_sub = {
            **catalog_match,
            "next_renewal_date": next_renewal_date,
            "started": as_of.isoformat(),
        }
        try:
            Subscription.model_validate(new_sub)
        except (ValueError, ValidationError) as exc:
            return _error(f"new subscription entry failed validation: {exc}", before_count)

    if (
        action == "replace"
        and target_match is not None
        and catalog_match is not None
        and target_match["product"] == catalog_match["product"]
    ):
        warnings.append(
            f"replace target and new_product both resolved to '{catalog_match['product']}' — "
            "this resets the renewal clock on an unchanged product, not a real swap."
        )

    removed = [target_match] if target_match is not None else []
    added = [new_sub] if new_sub is not None else []
    new_subs_list = [s for s in subs_list if s is not target_match]
    if new_sub is not None:
        new_subs_list.append(new_sub)
    after_count = len(new_subs_list)

    try:
        CurrentSubscriptions.model_validate({"subscriptions": new_subs_list})
    except (ValueError, ValidationError) as exc:
        return _error(f"resulting subscriptions failed validation: {exc}", before_count)

    # Write raw dicts (not model_dump) to preserve all fields beyond the pipeline schema.
    _atomic_write_json(_DATA / "current_subscriptions.json", {"subscriptions": new_subs_list})

    return {
        "status": "applied",
        "action": action,
        "removed": removed,
        "added": added,
        "before_count": before_count,
        "after_count": after_count,
        "file": "current_subscriptions.json",
        "warnings": warnings,
        "error": None,
    }
