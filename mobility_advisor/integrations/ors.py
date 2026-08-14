"""OpenRouteService (ORS) client: geocoding and driving directions, plus the location
string cleanup that has to run before either. The network-touching half of what used to
be route_utils.py — engine/factors.py holds the pure-math half (CO2/price/duration
lookups that need no HTTP call).
"""
import os
import re
import time

import requests
from dotenv import load_dotenv

from ..engine.factors import haversine_distance_km

load_dotenv()

ORS_API_KEY = os.getenv("ORS_API_KEY", "")
ORS_BASE = "https://api.openrouteservice.org"

REQUEST_DELAY_S = 0.6

LOCATION_PREFIXES = [
    "Enterprise Rent-A-Car",
    "MILES Station",
    "FlixTrain Station",
]

CLEANUP_PATTERNS = [
    r"\(FlixTrain\)",
    r"\(FlixBus\)",
    r"Gl\.\s*\d+[-\d]*",
    r"\bGl\b\.?\s*\d+",
    r"\([A-Z]{3}\)",
    r"\(Breisgau\)",
]

WORD_REPLACEMENTS = [
    ("Hauptbahnhof", "Hbf"),
]

# Generous lat/lng bounding box for Germany (includes a margin so a border-adjacent city
# like Basel or Freiburg doesn't misclassify on rounding). Used only to pick which single
# flight alternative (flight_domestic vs flight_short_haul) a route gets — see
# is_domestic_flight_route() — not for any pricing or CO2 decision.
_GERMANY_LAT_RANGE = (47.2, 55.15)
_GERMANY_LNG_RANGE = (5.5, 15.2)


def is_in_germany(lng: float, lat: float) -> bool:
    """Whether a (lng, lat) coordinate pair falls within Germany's bounding box."""
    lat_lo, lat_hi = _GERMANY_LAT_RANGE
    lng_lo, lng_hi = _GERMANY_LNG_RANGE
    return lat_lo <= lat <= lat_hi and lng_lo <= lng <= lng_hi


def is_domestic_flight_route(
    orig_coords: tuple[float, float], dest_coords: tuple[float, float]
) -> bool:
    """Whether both endpoints of a route lie inside Germany, i.e. this route should get a
    flight_domestic alternative rather than flight_short_haul. See
    compute_route_alternatives() — exactly one of the two flight modes is offered per
    route, never both (both were previously offered unconditionally on every route
    >=400km, which duplicated flight demand in mode-share selection — see
    _MODE_DISTANCE_FILTERS' docstring comment)."""
    return is_in_germany(*orig_coords) and is_in_germany(*dest_coords)


# ── Location cleaning ────────────────────────────────────────────────────────


def clean_location(location: str) -> str:
    """Strip provider names, platform numbers and other noise before geocoding."""
    loc = location.strip()
    for prefix in LOCATION_PREFIXES:
        if loc.startswith(prefix):
            loc = loc[len(prefix):].lstrip(" ,–-")
    for pattern in CLEANUP_PATTERNS:
        loc = re.sub(pattern, "", loc, flags=re.IGNORECASE)
    for word, replacement in WORD_REPLACEMENTS:
        loc = re.sub(rf"\b{re.escape(word)}\b", replacement, loc, flags=re.IGNORECASE)
    return loc.strip()


# ── Geocoding & routing ──────────────────────────────────────────────────────


def _ors_headers() -> dict:
    return {"Authorization": ORS_API_KEY}


def geocode(place: str) -> tuple[float, float] | None:
    """Return (lng, lat) for a place name via ORS, or None if not found."""
    resp = requests.get(
        f"{ORS_BASE}/geocode/search",
        headers=_ors_headers(),
        params={"text": place, "size": 1},
    )
    resp.raise_for_status()
    features = resp.json().get("features", [])
    if not features:
        return None
    lng, lat = features[0]["geometry"]["coordinates"]
    return lng, lat


def flight_distance_km(origin: str, destination: str) -> float | None:
    """Geocode origin and destination, return great-circle distance in km."""
    clean_origin = clean_location(origin)
    clean_dest = clean_location(destination)

    orig = geocode(clean_origin)
    if not orig:
        return None
    time.sleep(REQUEST_DELAY_S)

    dest = geocode(clean_dest)
    if not dest:
        return None

    return haversine_distance_km(orig, dest)


def driving_route(
    origin: str, destination: str
) -> tuple[float, float] | None:
    """Geocode origin and destination, return (distance_km, duration_min) via ORS driving directions."""
    clean_origin = clean_location(origin)
    clean_dest = clean_location(destination)

    orig = geocode(clean_origin)
    if not orig:
        return None
    time.sleep(REQUEST_DELAY_S)

    dest = geocode(clean_dest)
    if not dest:
        return None
    time.sleep(REQUEST_DELAY_S)

    resp = requests.get(
        f"{ORS_BASE}/v2/directions/driving-car",
        headers=_ors_headers(),
        params={
            "start": f"{orig[0]},{orig[1]}",
            "end": f"{dest[0]},{dest[1]}",
        },
    )
    resp.raise_for_status()
    features = resp.json().get("features", [])
    if not features:
        return None
    summary = features[0]["properties"]["summary"]
    distance_km = round(summary["distance"] / 1000, 1)
    duration_min = round(summary["duration"] / 60, 1)
    return distance_km, duration_min
