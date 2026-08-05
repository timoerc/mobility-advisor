"""Reusable routing, geocoding, CO2 lookup, and price estimation utilities.

Extracted from distance_enricher.py so both the batch enrichment pipeline and
the agent tools can share the same core functions without circular imports.
"""

import csv
import json
import math
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ORS_API_KEY = os.getenv("ORS_API_KEY", "")
ORS_BASE = "https://api.openrouteservice.org"

_STATIC = Path(__file__).parent / "static"
_CO2_CSV = _STATIC / "co2_factors.csv"
_PRICE_FACTORS = _STATIC / "price_factors.json"

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

MODE_CO2_MAP = {
    "rail": "Rail",
    "bus": "Bus",
    "car_share": "Car_Sharing",
    "car_rental": "Car_Rental",
    "car_private": "Car_private",
    "flight": "flight",
}

# Speed heuristics for duration estimation (km/h)
MODE_SPEED_KMH = {
    "rail_intercity": 160,
    "rail_regional": 60,
    "bus": 65,
    "car": 80,
    "flight": 700,
}

FLIGHT_OVERHEAD_MIN = 120  # check-in, security, boarding, taxi


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


def haversine_distance_km(
    orig: tuple[float, float], dest: tuple[float, float]
) -> float:
    """Great-circle distance between two (lng, lat) points in km."""
    R = 6371.0
    lng1, lat1 = math.radians(orig[0]), math.radians(orig[1])
    lng2, lat2 = math.radians(dest[0]), math.radians(dest[1])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    return round(R * 2 * math.asin(math.sqrt(a)), 1)


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


def estimate_duration_min(mode: str, distance_km: float) -> float:
    """Estimate travel duration from distance using speed heuristics."""
    if mode == "flight" or mode.startswith("flight_"):
        cruise_min = distance_km / MODE_SPEED_KMH["flight"] * 60
        return round(cruise_min + FLIGHT_OVERHEAD_MIN, 1)
    speed = MODE_SPEED_KMH.get(mode, MODE_SPEED_KMH["car"])
    return round(distance_km / speed * 60, 1)


# ── CO2 lookup ───────────────────────────────────────────────────────────────


def load_co2_lookup() -> dict[tuple[str, str, str], float]:
    """Load co2_factors.csv into a dict keyed by (mode, type, size) → kg CO2e/km.

    Most rows (Car_*, Bus, flight) are UK DEFRA/BEIS-style per-km conversion factors, used
    as reasonable order-of-magnitude proxies since no German-specific per-vehicle-class
    breakdown is wired into the fixtures. The two Rail rows are the exception: Rail,
    Intercity (0.03546) and Rail, Regional (0.054) are set to the German UBA/TREMOD
    figures for Fernverkehr (~32g/pkm) and Nahverkehr (~54g/pkm) respectively — DEFRA's
    own "national rail" (~35g) and "light rail and tram" (~29g) figures materially
    understate German regional rail's per-passenger emissions (more stops, lower average
    occupancy than long-distance ICE/IC). Rail, Null, Null (0.045) is a simple midpoint of
    the two, used only where a caller doesn't distinguish intercity from regional.
    """
    lookup: dict[tuple[str, str, str], float] = {}
    with _CO2_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["mode"], row["type"], row["size"])
            lookup[key] = float(row["kg_co2e_per_km"])
    return lookup


def lookup_co2_emission_kg(
    lookup: dict,
    mode: str,
    distance_km: float,
    trip_type: str | None = None,
    size: str | None = None,
) -> float | None:
    """Return total CO2 emission in kg for a trip, or None if not computable."""
    csv_mode = MODE_CO2_MAP.get(mode)
    if csv_mode is None:
        return None
    csv_type = trip_type if trip_type is not None else "Null"
    csv_size = size if size is not None else "Null"
    kg_per_km = lookup.get((csv_mode, csv_type, csv_size))
    if kg_per_km is None:
        return None
    return round(kg_per_km * distance_km, 3)


def co2_kg_for_mode(mode: str, distance_km: float, trip_type: str | None = None) -> float:
    """Quick CO2 estimate for a mode using generic (Null,Null) factors by default.

    trip_type lets a caller that already knows the rail sub-mode ("Intercity" vs
    "Regional") get the correctly differentiated factor instead of the generic Rail/Null/
    Null blend — see load_co2_lookup's docstring for why that split matters for German
    rail specifically. None (the default) preserves the old generic-only behavior.
    """
    lookup = load_co2_lookup()
    result = lookup_co2_emission_kg(lookup, mode, distance_km, trip_type=trip_type)
    return result if result is not None else 0.0


# ── Price estimation ─────────────────────────────────────────────────────────


def _load_price_factors() -> dict:
    """Load the exponential price factor config."""
    return json.loads(_PRICE_FACTORS.read_text(encoding="utf-8"))


def estimate_trip_price(mode: str, distance_km: float) -> float:
    """Estimate the full (undiscounted) price for a trip using an exponential formula.

    price = base_rate × distance_km ^ exponent

    The exponent < 1 for most modes, making the per-km cost decrease with
    distance (economies of scale). Car modes use exponent=1.0 (linear).
    """
    factors = _load_price_factors()
    entry = factors.get(mode)
    if entry is None:
        return 0.0
    base_rate = entry["base_rate"]
    exponent = entry["exponent"]
    if distance_km <= 0:
        return 0.0
    return round(base_rate * (distance_km ** exponent), 2)
