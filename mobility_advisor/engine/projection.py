"""The deterministic trip-projection pipeline's three sources (history, calendar,
car usage) and their merge into one combined ProjectedTripSet."""
import json
import logging
import time
from datetime import date, datetime

from .. import paths
from ..integrations.ors import ORS_API_KEY
from ..models import ProjectedTrip, ProjectedTripSet, RouteAlternative
from ..store.loaders import load_car_usage, load_travel_history
from .aggregates import (
    _build_commute_aggregate_trip,
    _build_intra_city_aggregate_trip,
    _build_local_aggregate_trip,
)
from .calibration import (
    _apply_rail_calibration,
    _dominant_fare_class,
    _dominant_operator_is_non_db,
    _rail_fare_calibration_ratio,
    _travel_reduction_factor,
)
from .factors import co2_kg_for_mode, estimate_duration_min, estimate_trip_price
from .geo import (
    _RAIL_DISTANCE_THRESHOLD_KM,
    _REQUEST_DELAY,
    _normalize_to_city,
    _route_key,
    compute_route_alternatives,
)

logger = logging.getLogger(__name__)

def derive_projected_trips_from_history() -> dict:
    """Analyze travel history and derive projected recurring routes with annual frequencies.

    Groups historical trips by normalized city pair (direction-independent), counts
    occurrences, extrapolates to annual frequency, and computes per-mode alternatives for
    routes with >= 2 raw observations AND an extrapolated frequency >= 2/year — both, not
    just the annualized figure: over a short data window a single observation can itself
    round up to 2/yr (e.g. 1 trip over a 5-month window annualizes to round(1*12/5) = 2),
    which used to let a genuine one-off masquerade as a recurring route. Routes below
    either bar are not simply dropped: a regional route (<= _RAIL_DISTANCE_THRESHOLD_KM)
    seen too rarely on its own to individually qualify is folded into a single synthetic
    "local/regional travel" aggregate trip (see the aggregation step below) — this is the
    demand a Deutschlandticket or regional pass actually prices against, and dropping it
    entirely made every such pass structurally incapable of showing value regardless of how
    much local travel a persona actually does. A long-distance route seen only once is
    still dropped outright, never aggregated — a real one-off trip is not recurring demand
    a subscription decision should be based on, at any distance.

    A trip whose origin and destination normalize to the SAME city (e.g. a MILES car-share
    hop between two Berlin districts) is not part of any inter-city route at all — it is
    folded into a separate "intra-city travel" aggregate (see
    _build_intra_city_aggregate_trip) instead of being discarded. Silently dropping these
    used to leave personas whose real usage is dominated by intra-city car-sharing (rides
    entirely within one city) with no car-share demand for any MILES tier's credit/discount
    to be priced against at all.

    Each route's dominant fare class (Sparpreis vs. Flexpreis) is derived from its trips'
    ticket_type text, and the projected frequency is damped when a near-term
    travel_reduction life-event signal exists (see _travel_reduction_factor()) — but only
    for long-distance routes (> _RAIL_DISTANCE_THRESHOLD_KM). A travel_reduction signal
    describes a change to inter-city travel (a project ending, a client engagement winding
    down); it says nothing about whether the persona still commutes locally or runs local
    errands, so regional/local/intra-city/commute demand is left undamped.

    Writes results to data/_projected_trips_history.json and returns a summary.
    """
    history = load_travel_history()
    trips = history["trips"]

    route_counts: dict[tuple[str, str], dict] = {}
    intra_city_trips: list[dict] = []
    for trip in trips:
        origin_city = _normalize_to_city(trip["origin"])
        dest_city = _normalize_to_city(trip["destination"])
        if origin_city.lower() == dest_city.lower():
            intra_city_trips.append(trip)
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
                "providers": [],
            }
        route_counts[key]["count"] += 1
        route_counts[key]["dates"].append(trip["date"])
        route_counts[key]["ticket_types"].append(trip.get("ticket_type"))
        route_counts[key]["providers"].append(trip.get("provider"))

    reduction_factor, reduction_warnings = _travel_reduction_factor()
    calibration_ratio, calibration_max_dist, calibration_warnings = _rail_fare_calibration_ratio()

    if not trips:
        data_window_months = 12
    else:
        all_dates = sorted(t["date"] for t in trips)
        earliest = date.fromisoformat(all_dates[0])
        latest = date.fromisoformat(all_dates[-1])
        data_window_months = max(1, round((latest - earliest).days / 30.44))

    projected: list[dict] = []
    # data_quality_warnings from load_travel_history() (null costs, empty/unknown modes —
    # see _travel_history_result) must be carried forward here, not dropped: this
    # ProjectedTripSet's warnings list is the only channel merge_projected_trip_sets()
    # aggregates from, which is in turn the only channel that reaches
    # _optimization_results.json and, from there, the Recommendation the user sees (see
    # optimize_all_categories() and main.py's Recommendation.dataQualityWarnings). Without
    # this, a persona whose history has malformed entries (e.g. Lena's null-cost/empty-mode
    # trips) got a pipeline run that silently analyzed only the clean subset with no visible
    # trace of what was excluded or why.
    warnings: list[str] = (
        list(history.get("data_quality_warnings", []))
        + list(reduction_warnings)
        + list(calibration_warnings)
    )
    # Below-threshold regional routes, collected for the aggregate step below instead of
    # being individually dropped — see the docstring.
    local_aggregate: list[dict] = []

    for key, info in route_counts.items():
        # Frequency threshold is checked on the raw historical rate — "is this actually a
        # recurring route" — before any travel_reduction damping is applied below, so a
        # damped-to-near-zero frequency never wrongly excludes a route the history clearly
        # supports.
        annual_freq = round(info["count"] * 12 / data_window_months)
        if annual_freq == 0:
            continue

        origin = info["origin"]
        dest = info["destination"]

        if ORS_API_KEY:
            time.sleep(_REQUEST_DELAY)
        result = compute_route_alternatives(origin, dest)
        if result.get("warnings"):
            warnings.extend(result["warnings"])
        hav_km = result.get("haversine_km")
        dist_km = round(hav_km * 1.3, 1) if hav_km else 0.0

        # A route only qualifies as individually recurring on BOTH the raw observation
        # count and the annualized rate — the annualized rate alone can round a single
        # observation up to 2/yr over a short data window, letting a genuine one-off pass
        # this bar (see the docstring). A regional under-qualifying route still feeds the
        # local aggregate; a long-distance one is dropped outright either way.
        if info["count"] < 2 or annual_freq < 2:
            if dist_km and dist_km <= _RAIL_DISTANCE_THRESHOLD_KM:
                local_aggregate.append({
                    "distance_km": dist_km,
                    "freq": annual_freq,
                    "ticket_types": info["ticket_types"],
                })
            continue

        # Damping only applies beyond the regional threshold — a travel_reduction signal
        # is about inter-city travel dropping off, not local/regional routes (see the
        # docstring above).
        if dist_km > _RAIL_DISTANCE_THRESHOLD_KM:
            annual_freq = round(annual_freq * reduction_factor)
        if annual_freq == 0:
            # A damped-to-zero long-distance route contributes nothing and should not
            # linger in the projected set (it previously did — merge_projected_trip_sets
            # and simulate_portfolio would carry a 0/yr "route" through the whole pipeline).
            continue

        fare_class = _dominant_fare_class(info["ticket_types"])
        non_db_operator = _dominant_operator_is_non_db(info["providers"])
        alternatives = _apply_rail_calibration(
            result.get("alternatives", []), calibration_ratio, calibration_max_dist
        )

        trip = ProjectedTrip(
            route=f"{origin} → {dest}",
            origin=origin,
            destination=dest,
            frequency_per_year=annual_freq,
            source="history",
            distance_km=dist_km,
            alternatives=alternatives,
            fare_class=fare_class,
            non_db_operator=non_db_operator,
        )
        projected.append(trip.model_dump())

    if local_aggregate:
        # Exempt from travel_reduction damping (factor=1.0) — see the docstring above and
        # _build_local_aggregate_trip's.
        agg_trip, agg_warning = _build_local_aggregate_trip(local_aggregate, 1.0)
        if agg_trip is not None:
            projected.append(agg_trip)
            warnings.append(agg_warning)

    if intra_city_trips:
        # Also exempt from damping — same-city travel, not the inter-city travel a
        # travel_reduction signal describes.
        intra_trip, intra_warning = _build_intra_city_aggregate_trip(
            intra_city_trips, data_window_months
        )
        if intra_trip is not None:
            projected.append(intra_trip)
            warnings.append(intra_warning)

    # Exempt from travel_reduction damping (factor=1.0) — see the docstring above and
    # _build_commute_aggregate_trip's.
    commute_trip, commute_warning = _build_commute_aggregate_trip(1.0)
    if commute_trip is not None:
        projected.append(commute_trip)
        warnings.append(commute_warning)

    trip_set = ProjectedTripSet(
        trips=projected,
        generated_at=datetime.now().isoformat(),
        warnings=warnings,
    )

    out_path = paths.DATA_DIR / "_projected_trips_history.json"
    paths.atomic_write_json(out_path, trip_set.model_dump())

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
    calibration_ratio, calibration_max_dist, _ = _rail_fare_calibration_ratio()
    alternatives = _apply_rail_calibration(
        result.get("alternatives", []), calibration_ratio, calibration_max_dist
    )
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

    cal_path = paths.DATA_DIR / "_projected_trips_calendar.json"
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
    paths.atomic_write_json(cal_path, trip_set.model_dump())

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
        paths.atomic_write_json(paths.DATA_DIR / "_projected_trips_car_usage.json", empty_set.model_dump())
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
    calibration_ratio, calibration_max_dist, _ = _rail_fare_calibration_ratio()
    projected: list[dict] = []
    summary_cats: list[dict] = []

    for cat in categories:
        dist = cat["distance_km"]
        # max(1, ...) guarantees every category (short/medium/long) is represented at least
        # once whenever the persona has any car usage at all — freq can therefore never be
        # below 1 here, unlike derive_projected_trips_from_history's routes (which have no
        # such floor and can legitimately round to 0/yr).
        freq = max(1, round(cat["km_share"] * km_est / dist * 12))

        alternatives: list[dict] = []
        for mode in cat["modes"]:
            if mode == "car_private" and not owns_car:
                continue
            co2_mode = mode
            rail_trip_type = None
            if mode.startswith("flight"):
                co2_mode = "flight"
            elif mode in ("rail_intercity", "rail_regional"):
                co2_mode = "rail"
                rail_trip_type = "Intercity" if mode == "rail_intercity" else "Regional"
            co2 = co2_kg_for_mode(co2_mode, dist, trip_type=rail_trip_type)
            price = estimate_trip_price(mode, dist)
            # Calibration is fitted against intercity fares only (see
            # _apply_rail_calibration's docstring) — the "short" category's rail_regional
            # alternative must not inherit a ratio derived from unrelated long-distance fares.
            if mode == "rail_intercity" and dist <= calibration_max_dist:
                price *= calibration_ratio
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
    paths.atomic_write_json(paths.DATA_DIR / "_projected_trips_car_usage.json", trip_set.model_dump())

    return {
        "status": "ok",
        "categories": summary_cats,
        "total_annual_trips": sum(c["frequency_per_year"] for c in summary_cats),
        "file": "_projected_trips_car_usage.json",
        "warnings": [],
    }


_UNCORROBORATED_CALENDAR_FREQUENCY_CAP = 12  # monthly-equivalent ceiling


def merge_projected_trip_sets() -> dict:
    """Merge all projected trip sources into a single combined trip set.

    Reads _projected_trips_history.json, _projected_trips_calendar.json, and
    _projected_trips_car_usage.json. Concatenates all trips and flags potential
    duplicates (same normalized route from different sources).

    Caps any calendar-sourced route's frequency_per_year at
    _UNCORROBORATED_CALENDAR_FREQUENCY_CAP when travel history never recorded that route
    at all — an LLM-inferred "weekly office day" from a handful of calendar entries can
    otherwise dominate the whole projected trip set (a real regression: 4 calendar entries
    read as a 48/yr commute swung a BahnCard recommendation, despite the route never
    appearing once in the persona's actual travel history). A route history DOES support,
    even at low frequency, is trusted at its full calendar-derived frequency — this only
    guards demand with zero corroboration from any other source.

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
        path = paths.DATA_DIR / filename
        if not path.exists():
            source_counts[source_name] = 0
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        trip_set = ProjectedTripSet.model_validate(raw)
        trips = [t.model_dump() for t in trip_set.trips]
        source_counts[source_name] = len(trips)
        raw_trips.extend(trips)
        warnings.extend(trip_set.warnings)

    history_route_keys = {
        _route_key(t["origin"], t["destination"])
        for t in raw_trips
        if t.get("source") == "history" and t.get("origin") != "various"
    }

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
                # Calendar wins on priority (fresher/more specific route data), but must
                # not silently discard a higher, history-corroborated frequency — a route
                # history shows happening 3x/yr is real recurring demand even when the
                # calendar (an LLM's read of a handful of events) only inferred 1x/yr for
                # the same route. Taking the max keeps calendar's route/alternative data
                # while never losing history's frequency evidence; the reverse
                # (uncorroborated calendar demand inflating a route beyond what anything
                # supports) is already bounded below by _UNCORROBORATED_CALENDAR_FREQUENCY_CAP.
                merged_freq = max(trip["frequency_per_year"], existing["frequency_per_year"])
                if merged_freq > trip["frequency_per_year"]:
                    warnings.append(
                        f"Dedup: {key[0]} ↔ {key[1]} — calendar route data used, but "
                        f"frequency kept at history's higher {merged_freq}/yr rather than "
                        f"calendar's {trip['frequency_per_year']}/yr"
                    )
                else:
                    warnings.append(
                        f"Dedup: {key[0]} ↔ {key[1]} — calendar ({trip['frequency_per_year']}/yr) replaces history ({existing['frequency_per_year']}/yr)"
                    )
                trip["frequency_per_year"] = merged_freq
                _merge_fare_class(trip, existing)
                deduped[key] = trip
            elif new_prio == existing_prio and trip["frequency_per_year"] > existing["frequency_per_year"]:
                _merge_fare_class(trip, existing)
                deduped[key] = trip
            else:
                _merge_fare_class(existing, trip)
        else:
            deduped[key] = trip

    for key, trip in deduped.items():
        if trip.get("source") != "calendar" or key in history_route_keys:
            continue
        if trip["frequency_per_year"] > _UNCORROBORATED_CALENDAR_FREQUENCY_CAP:
            warnings.append(
                f"Uncorroborated calendar demand: {trip['route']} was projected at "
                f"{trip['frequency_per_year']}/yr from calendar events alone, with no "
                f"supporting trip in travel history — capped at "
                f"{_UNCORROBORATED_CALENDAR_FREQUENCY_CAP}/yr."
            )
            trip["frequency_per_year"] = _UNCORROBORATED_CALENDAR_FREQUENCY_CAP

    all_trips = list(deduped.values()) + car_usage_trips

    merged = ProjectedTripSet(
        trips=all_trips,
        generated_at=datetime.now().isoformat(),
        warnings=warnings,
    )
    paths.atomic_write_json(paths.DATA_DIR / "_projected_trips_merged.json", merged.model_dump())

    return {
        "status": "ok",
        "total_trips": len(all_trips),
        "source_counts": source_counts,
        "total_annual_trip_instances": sum(t["frequency_per_year"] for t in all_trips),
        "duplicate_warnings": [w for w in warnings if w.startswith("Potential duplicate")],
        "file": "_projected_trips_merged.json",
    }


# ── Portfolio simulation (Branch 3) ──────────────────────────────────────────

# Enterprise (car rental) and Miles & More (flight) loyalty tiers are all €0/mo, automatic
# perks tied to usage volume rather than something a persona chooses to buy — the catalog
# still carries them (a persona's current_subscriptions.json can legitimately hold one, and
# the retrospective annual report attributes value to one already held, see
# compute_annual_report_stats), but they play no role in the FORWARD optimizer:
# apply_subscription_discount has no car_rental/flight branch, so they were priced but never
# actually cheaper than anything, and optimize_all_categories excludes them from the
# candidate surface entirely (SKIP_IDS) since there is nothing to recommend adding or
# removing about a free, automatically-assigned tier. A previous _resolve_automatic_tiers()
# helper computed which tier a projected trip volume would automatically earn, but nothing
# ever consumed that result (its only caller, load_simulation_candidates(), was itself never
# registered as a tool for any agent) — both were dead code and have been removed rather
# than left half-wired.


