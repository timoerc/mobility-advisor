import json
import time
from pathlib import Path

import requests

from .mail_processor import _enrich_rail_trips
from .route_utils import (
    REQUEST_DELAY_S,
    clean_location,
    driving_route,
    flight_distance_km,
    geocode,
    load_co2_lookup,
    lookup_co2_emission_kg,
)
from .tools import load_current_subscriptions

_DATA = Path(__file__).parent / "data"
_RAW_OUTPUT = _DATA / "travel_history_raw.json"

ROUTABLE_MODES = {"rail", "bus", "car_share", "car_rental"}
CAR_MODES = {"car_share", "car_rental"}


def _load_subscriptions() -> list[dict]:
    return load_current_subscriptions()["subscriptions"]


def _provider_matches(trip_provider: str, sub_provider: str) -> bool:
    tp = trip_provider.lower()
    sp = sub_provider.lower()
    return tp in sp or sp in tp


def _date_in_range(trip_date: str, started: str | None, next_renewal: str | None) -> bool:
    if not started:
        return True
    if trip_date < started:
        return False
    if next_renewal and trip_date > next_renewal:
        return False
    return True


def _enrich_booked_under(trips: list[dict]) -> int:
    subs = _load_subscriptions()
    if not subs:
        return 0

    updated = 0
    for trip in trips:
        trip_mode = trip.get("mode", "")
        trip_provider = trip.get("provider", "")
        trip_date = trip.get("date", "")
        trip_type = trip.get("type", "")

        matched_id = None

        if trip_mode == "rail" and _provider_matches(trip_provider, "Deutsche Bahn"):
            rail_subs = [s for s in subs if s["mode"] == "rail"
                         and _provider_matches(trip_provider, s["provider"])
                         and _date_in_range(trip_date, s["started"], s["next_renewal_date"])]

            bc100 = next((s for s in rail_subs if s["id"].startswith("db_bc100")), None)
            bahncard = next((s for s in rail_subs if s["id"].startswith("db_bc") and not s["id"].startswith("db_bc100")), None)
            dt = next((s for s in rail_subs if s["id"] == "db_deutschlandticket"), None)

            if bc100:
                matched_id = bc100["id"]
            elif trip_type == "Intercity":
                if bahncard:
                    matched_id = bahncard["id"]
            elif trip_type == "Regional":
                if dt:
                    matched_id = dt["id"]
                elif bahncard:
                    matched_id = bahncard["id"]

        elif trip_mode == "flight":
            for s in subs:
                if s["mode"] != "flight":
                    continue
                if not _date_in_range(trip_date, s["started"], s["next_renewal_date"]):
                    continue
                affiliated = s.get("affiliated_airlines") or []
                if any(_provider_matches(trip_provider, airline) for airline in affiliated):
                    matched_id = s["id"]
                    break

        else:
            for s in subs:
                if s["mode"] != trip_mode:
                    continue
                if not _provider_matches(trip_provider, s["provider"]):
                    continue
                if not _date_in_range(trip_date, s["started"], s["next_renewal_date"]):
                    continue
                matched_id = s["id"]
                break

        if matched_id and trip.get("booked_under") != matched_id:
            trip["booked_under"] = matched_id
            updated += 1

    return updated


def enrich() -> None:
    """Fill distance_km, co2_emission_kg, and booked_under for all trips."""
    co2_lookup = load_co2_lookup()
    raw = json.loads(_RAW_OUTPUT.read_text(encoding="utf-8"))
    trips = raw["trips"]
    dist_updated = 0
    co2_updated = 0
    duration_updated = 0

    for trip in trips:
        mode = trip.get("mode")
        if mode not in ROUTABLE_MODES and mode != "flight":
            continue

        needs_distance = trip.get("distance_km") is None
        needs_duration = mode in CAR_MODES and trip.get("real_travel_duration_min") is None
        if not needs_distance and not needs_duration:
            continue

        origin = trip.get("origin", "")
        destination = trip.get("destination", "")
        print(f"[{trip['date']}] {origin} → {destination}")
        try:
            if mode == "flight":
                dist = flight_distance_km(origin, destination)
                if dist is not None and needs_distance:
                    trip["distance_km"] = dist
                    print(f"    → {dist} km")
                    dist_updated += 1
                elif dist is None:
                    print(f"    → Could not compute distance")
            else:
                result = driving_route(origin, destination)
                if result is not None:
                    dist, duration = result
                    if needs_distance:
                        trip["distance_km"] = dist
                        print(f"    → {dist} km")
                        dist_updated += 1
                    if needs_duration:
                        trip["real_travel_duration_min"] = duration
                        print(f"    → {duration} min real travel time")
                        duration_updated += 1
                else:
                    print(f"    → Could not compute distance/duration")
        except requests.HTTPError as e:
            print(f"    → HTTP error: {e}")
        except Exception as e:
            print(f"    → Error: {e}")

    trips = _enrich_rail_trips(trips)

    for trip in trips:
        if trip.get("co2_emission_kg") is not None:
            continue
        co2 = lookup_co2_emission_kg(
            co2_lookup,
            trip.get("mode", ""),
            trip.get("distance_km"),
            trip.get("type"),
            trip.get("size"),
        )
        if co2 is not None:
            trip["co2_emission_kg"] = co2
            co2_updated += 1

    for trip in trips:
        if trip.get("mode") not in CAR_MODES and trip.get("real_travel_duration_min") is None:
            trip["real_travel_duration_min"] = trip.get("duration_min")
            duration_updated += 1

    booked_updated = _enrich_booked_under(trips)

    raw["trips"] = trips
    _RAW_OUTPUT.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"\nDone — {dist_updated} distance(s), {duration_updated} real travel duration(s), "
        f"{co2_updated} CO₂ emission(s), and {booked_updated} booked_under assignment(s) filled."
    )


if __name__ == "__main__":
    enrich()
