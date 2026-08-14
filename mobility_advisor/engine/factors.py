"""Pure-math reference-data lookups over static/: CO2 factors, price curves, and
duration/distance heuristics. No network calls — see integrations/ors.py for the
geocoding/routing half this was split from (formerly one route_utils.py)."""
import csv
import json
import math

from .. import paths

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
    with (paths.STATIC_DIR / "co2_factors.csv").open(encoding="utf-8") as f:
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
    return json.loads((paths.STATIC_DIR / "price_factors.json").read_text(encoding="utf-8"))


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
