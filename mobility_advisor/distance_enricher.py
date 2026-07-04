import csv
import json
import math
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from .mail_processor import _enrich_rail_trips

load_dotenv()

ORS_API_KEY = os.getenv("ORS_API_KEY", "")
ORS_BASE = "https://api.openrouteservice.org"

_DATA = Path(__file__).parent / "data"
_STATIC = Path(__file__).parent / "static"
_RAW_OUTPUT = _DATA / "travel_history_raw.json"
_CO2_CSV = _STATIC / "co2_factors.csv"

ROUTABLE_MODES = {"rail", "bus", "car_share", "car_rental"}

# Map JSON mode values → mode column in co2_factors.csv
_MODE_MAP = {
    "rail": "Rail",
    "bus": "Bus",
    "car_share": "Car_Sharing",
    "car_rental": "Car_Rental",
    "flight": "flight",
}

_REQUEST_DELAY_S = 0.6  # stay within ORS free-tier rate limit (40 req/min)

# Prefixes to strip before geocoding (provider names that precede the actual location)
_LOCATION_PREFIXES = [
    "Enterprise Rent-A-Car",
    "MILES Station",
    "FlixTrain Station",
]

# Regex patterns to remove from location strings before geocoding
import re
_CLEANUP_PATTERNS = [
    r"\(FlixTrain\)",       # "(FlixTrain)"
    r"\(FlixBus\)",         # "(FlixBus)"
    r"Gl\.\s*\d+[-\d]*",   # "Gl.11-12", "Gl. 3"
    r"\bGl\b\.?\s*\d+",    # variations
    r"\([A-Z]{3}\)",        # airport codes like "(ATH)", "(ZRH)"
    r"\(Breisgau\)",        # "Freiburg(Breisgau) Hbf" → "Freiburg Hbf"
]

_WORD_REPLACEMENTS = [
    ("Hauptbahnhof", "Hbf"),    # ORS resolves "Hbf" reliably; "Hauptbahnhof" often picks wrong city
]


def _clean_location(location: str) -> str:
    """Strip provider names, platform numbers and other noise before geocoding."""
    loc = location.strip()
    for prefix in _LOCATION_PREFIXES:
        if loc.startswith(prefix):
            loc = loc[len(prefix):].lstrip(" ,–-")
    for pattern in _CLEANUP_PATTERNS:
        loc = re.sub(pattern, "", loc, flags=re.IGNORECASE)
    for word, replacement in _WORD_REPLACEMENTS:
        loc = re.sub(rf"\b{re.escape(word)}\b", replacement, loc, flags=re.IGNORECASE)
    return loc.strip()


def _load_co2_lookup() -> dict[tuple[str, str, str], float]:
    """Load co2_factors.csv into a dict keyed by (mode, type, size) → kg CO2e/km."""
    lookup = {}
    with _CO2_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["mode"], row["type"], row["size"])
            lookup[key] = float(row["kg_co2e_per_km"])
    return lookup


def _lookup_co2_emission_kg(
    lookup: dict,
    mode: str,
    trip_type: str | None,
    size: str | None,
    distance_km: float | None,
) -> float | None:
    """Return total CO2 emission in grams for a trip, or None if not computable."""
    if distance_km is None:
        return None
    csv_mode = _MODE_MAP.get(mode)
    if csv_mode is None:
        return None
    csv_type = trip_type if trip_type is not None else "Null"
    csv_size = size if size is not None else "Null"
    kg_per_km = lookup.get((csv_mode, csv_type, csv_size))
    if kg_per_km is None:
        return None
    return round(kg_per_km * distance_km, 3)


def _headers() -> dict:
    return {"Authorization": ORS_API_KEY}


def _geocode(place: str) -> tuple[float, float] | None:
    """Return (lng, lat) for a place name, or None if not found."""
    resp = requests.get(
        f"{ORS_BASE}/geocode/search",
        headers=_headers(),
        params={"text": place, "size": 1},
    )
    resp.raise_for_status()
    features = resp.json().get("features", [])
    if not features:
        return None
    lng, lat = features[0]["geometry"]["coordinates"]
    return lng, lat


def _haversine_distance_km(
    orig: tuple[float, float], dest: tuple[float, float]
) -> float:
    """Great-circle distance between two (lng, lat) points in km."""
    R = 6371.0
    lng1, lat1 = math.radians(orig[0]), math.radians(orig[1])
    lng2, lat2 = math.radians(dest[0]), math.radians(dest[1])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return round(R * 2 * math.asin(math.sqrt(a)), 1)


def _flight_distance_km(origin: str, destination: str) -> float | None:
    """Geocode origin and destination airports, then return great-circle distance in km."""
    clean_origin = _clean_location(origin)
    clean_dest = _clean_location(destination)
    print(f"    Geocoding: '{clean_origin}' → '{clean_dest}'")

    orig = _geocode(clean_origin)
    if not orig:
        print(f"    Geocoding failed: {clean_origin}")
        return None
    time.sleep(_REQUEST_DELAY_S)

    dest = _geocode(clean_dest)
    if not dest:
        print(f"    Geocoding failed: {clean_dest}")
        return None

    return _haversine_distance_km(orig, dest)


def _driving_distance_km(origin: str, destination: str) -> float | None:
    """Geocode origin and destination, then return driving distance in km."""
    clean_origin = _clean_location(origin)
    clean_dest = _clean_location(destination)
    print(f"    Geocoding: '{clean_origin}' → '{clean_dest}'")

    orig = _geocode(clean_origin)
    if not orig:
        print(f"    Geocoding failed: {clean_origin}")
        return None
    time.sleep(_REQUEST_DELAY_S)

    dest = _geocode(clean_dest)
    if not dest:
        print(f"    Geocoding failed: {clean_dest}")
        return None
    time.sleep(_REQUEST_DELAY_S)

    resp = requests.get(
        f"{ORS_BASE}/v2/directions/driving-car",
        headers=_headers(),
        params={
            "start": f"{orig[0]},{orig[1]}",
            "end": f"{dest[0]},{dest[1]}",
        },
    )
    resp.raise_for_status()
    features = resp.json().get("features", [])
    if not features:
        return None
    distance_m = features[0]["properties"]["summary"]["distance"]
    return round(distance_m / 1000, 1)


def enrich() -> None:
    """Fill distance_km and co2_emission_kg for all trips missing those values."""
    lookup = _load_co2_lookup()
    raw = json.loads(_RAW_OUTPUT.read_text(encoding="utf-8"))
    trips = raw["trips"]
    dist_updated = 0
    co2_updated = 0

    # Pass 1 — fill distance_km for all modes that support it
    for trip in trips:
        mode = trip.get("mode")
        if trip.get("distance_km") is not None:
            continue
        if mode not in ROUTABLE_MODES and mode != "flight":
            continue

        origin = trip.get("origin", "")
        destination = trip.get("destination", "")
        print(f"[{trip['date']}] {origin} → {destination}")
        try:
            if mode == "flight":
                dist = _flight_distance_km(origin, destination)
            else:
                dist = _driving_distance_km(origin, destination)

            if dist is not None:
                trip["distance_km"] = dist
                print(f"    → {dist} km")
                dist_updated += 1
            else:
                print(f"    → Could not compute distance")
        except requests.HTTPError as e:
            print(f"    → HTTP error: {e}")
        except Exception as e:
            print(f"    → Error: {e}")

    # Pass 2 — set rail type based on fresh distance_km values
    trips = _enrich_rail_trips(trips)

    # Pass 3 — fill co2_emission_kg using (mode, type, size, distance_km)
    for trip in trips:
        if trip.get("co2_emission_kg") is not None:
            continue
        co2 = _lookup_co2_emission_kg(
            lookup,
            trip.get("mode", ""),
            trip.get("type"),
            trip.get("size"),
            trip.get("distance_km"),
        )
        if co2 is not None:
            trip["co2_emission_kg"] = co2
            co2_updated += 1

    raw["trips"] = trips
    _RAW_OUTPUT.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone — {dist_updated} distance(s) and {co2_updated} CO₂ emission(s) filled.")


if __name__ == "__main__":
    enrich()
