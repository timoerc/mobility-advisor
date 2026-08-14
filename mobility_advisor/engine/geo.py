"""Geocoding, per-mode route alternative computation, and route/city normalization for
grouping historical trips into recurring routes."""
import json
import logging
import re
import time

from .. import paths
from ..i18n import t
from ..integrations.ors import (
    ORS_API_KEY,
    clean_location,
    driving_route,
    geocode,
    is_domestic_flight_route,
)
from ..models import RouteAlternative
from ..store.loaders import load_car_usage
from .factors import co2_kg_for_mode, estimate_duration_min, estimate_trip_price, haversine_distance_km

logger = logging.getLogger(__name__)

# ── Mode filter thresholds for route alternatives ────────────────────────────

_MODE_DISTANCE_FILTERS: dict[str, tuple[float, float]] = {
    # rail_intercity's upper bound matters more than it looks: with cost-only mode
    # selection an unbounded "rail" alternative was harmless (a synthetic domestic IC/ICE
    # price curve extrapolated to 2000km+ never beat a flight's raw price, so it was never
    # picked). Once selection weighs time/CO2 too (see _select_best_alternative), a route
    # like Athens->Zurich (2100km, no realistic direct rail journey) can get "picked" for
    # its CO2 score despite being physically nonsensical as a single rail trip. 1500km
    # covers real single-day intra-European IC/ICE/EC corridors (Hamburg-Milan, Berlin-
    # Barcelona-ish) while excluding transcontinental distances no through-rail product
    # actually serves.
    "rail_intercity": (0, 1500),
    "rail_regional": (0, float("inf")),
    "car_share": (0, 100),
    "car_rental": (100, float("inf")),
    "car_private": (0, float("inf")),
    # flight_short_haul and flight_domestic share the same distance band on purpose — which
    # one a given route actually offers is decided in compute_route_alternatives() by
    # is_domestic_flight_route(), not by distance. Never both: two flight alternatives with
    # near-identical price/duration/CO2 (both map to the same "flight" CO2 factor) would
    # double-count flight demand in _mode_shares()'s softmax.
    "flight_short_haul": (400, float("inf")),
    "flight_domestic": (400, float("inf")),
}

_RAIL_DISTANCE_THRESHOLD_KM = 100

_REQUEST_DELAY = 1.2

_geocode_cache: dict[str, tuple[float, float] | None] = {}
_CITY_COORDS_PATH = paths.STATIC_DIR / "city_coords.json"
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
    CO2, and estimated price. Exactly one flight alternative is offered per route
    (flight_domestic if both endpoints are in Germany, else flight_short_haul — see
    is_domestic_flight_route()), never both.

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

    # Which single flight mode this route may offer — never both flight_domestic and
    # flight_short_haul (see _MODE_DISTANCE_FILTERS' comment on why offering both
    # double-counts flight demand in _mode_shares()'s softmax).
    domestic_route = is_domestic_flight_route(orig_coords, dest_coords)

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

        if mode == "flight_domestic" and not domestic_route:
            continue
        if mode == "flight_short_haul" and domestic_route:
            continue

        if mode in ("car_share", "car_rental", "car_private"):
            try:
                route_result = driving_route(origin, destination)
                # Only the live-API path has a rate limit to respect (see _cached_geocode's
                # docstring for the same convention) — sleeping here unconditionally added a
                # full _REQUEST_DELAY per car-mode alternative even when ORS_API_KEY is unset
                # and driving_route() never left this process at all.
                if ORS_API_KEY:
                    time.sleep(_REQUEST_DELAY)
            except Exception as exc:
                logger.warning("driving_route failed for %s → %s: %s", origin, destination, exc)
                route_result = None
            if route_result:
                dist_km, dur_min = route_result
            else:
                dist_km = hav_km * 1.3
                dur_min = estimate_duration_min("car", dist_km)
                warnings.append(t("warn.drivingRouteFailed", mode=mode))
        elif mode.startswith("rail"):
            dist_km = round(hav_km * 1.3, 1)
            dur_min = estimate_duration_min(mode, dist_km)
        elif mode.startswith("flight"):
            dist_km = round(hav_km, 1)
            dur_min = estimate_duration_min("flight", dist_km)
        else:
            continue

        co2_mode = mode
        rail_trip_type = None
        if mode in ("flight_short_haul", "flight_domestic"):
            co2_mode = "flight"
        elif mode in ("rail_intercity", "rail_regional"):
            co2_mode = "rail"
            rail_trip_type = "Intercity" if mode == "rail_intercity" else "Regional"
        co2 = co2_kg_for_mode(co2_mode, dist_km, trip_type=rail_trip_type)
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


