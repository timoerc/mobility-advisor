"""Synthetic aggregate ProjectedTrips for demand travel_history_raw.json can't represent
directly: rarely-seen regional routes, same-city car-share hops, and the home-city
commute (which never appears in travel history at all)."""
import json

from .. import paths
from ..models import ProjectedTrip, RouteAlternative
from ..store.loaders import load_car_usage
from .calibration import _dominant_fare_class
from .factors import co2_kg_for_mode, estimate_duration_min, estimate_trip_price

def _build_local_aggregate_trip(
    local_aggregate: list[dict],
    reduction_factor: float,
) -> tuple[dict | None, str]:
    """Build one synthetic "local/regional travel" ProjectedTrip from routes that were each
    seen too rarely (<2/yr) individually to qualify on their own, following the same
    origin="various" synthetic-trip convention derive_car_usage_trips() uses.

    Frequency-weights the aggregate distance across the contributing routes, then prices
    rail_regional/car_share/car_private alternatives directly at that distance — mirroring
    derive_car_usage_trips()'s per-bucket pricing — rather than trying to average distinct
    real routes' alternatives together. No calibration ratio is applied here — the ratio is
    fitted against intercity fares only and this aggregate is regional by construction (see
    _apply_rail_calibration's docstring).

    Returns (trip_dict_or_None, warning). trip is None (with an empty warning) if the
    damped total frequency rounds to 0 — a travel-reduction signal can legitimately zero
    this out just like it does every other projected route.
    """
    total_freq = sum(r["freq"] for r in local_aggregate)
    avg_dist = round(
        sum(r["distance_km"] * r["freq"] for r in local_aggregate) / total_freq, 1
    )
    ticket_types = [tt for r in local_aggregate for tt in r["ticket_types"]]
    fare_class = _dominant_fare_class(ticket_types)

    damped_freq = round(total_freq * reduction_factor)
    if damped_freq < 1:
        return None, ""

    owns_car = load_car_usage().get("owns_car", False)
    modes = ["rail_regional", "car_share"] + (["car_private"] if owns_car else [])
    alternatives: list[dict] = []
    for mode in modes:
        co2_mode = "rail" if mode.startswith("rail") else mode
        rail_trip_type = "Regional" if mode == "rail_regional" else None
        co2 = co2_kg_for_mode(co2_mode, avg_dist, trip_type=rail_trip_type)
        price = estimate_trip_price(mode, avg_dist)
        dur = estimate_duration_min(mode, avg_dist)
        alt = RouteAlternative(
            mode=mode,
            distance_km=avg_dist,
            duration_min=round(dur, 1),
            co2_kg=round(co2, 3),
            estimated_price_eur=round(price, 2),
        )
        alternatives.append(alt.model_dump())

    trip = ProjectedTrip(
        route=f"Local/regional travel ({len(local_aggregate)} route(s), aggregated)",
        origin="various",
        destination="various",
        frequency_per_year=damped_freq,
        source="history",
        category="local_aggregate",
        distance_km=avg_dist,
        alternatives=alternatives,
        fare_class=fare_class,
    )
    warning = (
        f"Aggregated {len(local_aggregate)} regional route(s) each seen under 2x/yr "
        f"individually ({total_freq}/yr combined, ~{avg_dist}km avg) into one projected "
        f"local-travel trip, instead of dropping them — this is the demand a "
        f"Deutschlandticket or regional pass actually prices against."
    )
    return trip.model_dump(), warning


_TYPICAL_URBAN_COMMUTE_KM = 8.0
_WORKING_WEEKS_PER_YEAR = 46  # 52 weeks minus ~4 weeks statutory vacation and public holidays


# Same-city trips actually booked on one of these modes are the only ones folded into the
# intra-city aggregate below. A trip recorded as plain "rail" between two stops in the same
# city is ordinary Deutschlandticket-covered local transit (already free-by-construction in
# the fixtures) and carries no signal for evaluating a car-share/rail subscription; a
# malformed entry (empty or unrecognized mode — see load_travel_history's
# data_quality_warnings) is excluded the same way it already is from every other aggregate.
_INTRA_CITY_CAR_MODES = {"car_share", "car_rental", "car_private"}


def _build_intra_city_aggregate_trip(
    intra_city_trips: list[dict],
    data_window_months: float,
) -> tuple[dict | None, str]:
    """Build one synthetic "intra-city travel" ProjectedTrip from trips whose origin and
    destination normalize to the same city (see _normalize_to_city) — most commonly
    car-share hops between districts of one city, which _route_key() has no directional
    route to key on and which derive_projected_trips_from_history() used to discard
    entirely before this existed.

    Without this, a persona whose real usage is mostly intra-city car-sharing (e.g. MILES
    rides entirely within Berlin) had zero projected car-share demand: nothing for any
    MILES tier's monthly credit or per-km discount to be priced against, making every paid
    tier look like a pure net loss regardless of how much the persona actually rides.

    Only trips booked on a mode in _INTRA_CITY_CAR_MODES are aggregated. The alternative set
    offered is deliberately car_share/car_private ONLY — no rail_regional option, unlike
    _build_local_aggregate_trip()/_build_commute_aggregate_trip(). Those two model genuinely
    substitutable local/commute demand, where offering a cheap regional-rail alternative is
    the whole point (see their docstrings). An intra-city car-share trip is different: the
    persona already had access to whatever free/cheap local transit their current
    subscriptions cover and chose to pay for a car anyway — a same-city car-share ride
    usually means carrying something, an odd-hours trip, or a route transit doesn't serve
    well. Modeling it as rail-substitutable would let the simulator "solve" it by routing
    100% of the demand onto free regional transit, which is exactly the failure this
    function exists to avoid: it reproduces the original bug (car-share demand invisible to
    every MILES tier) one layer downstream, just from an econometric artifact instead of a
    dropped trip.

    Distance is each trip's own recorded distance_km (falling back to
    _TYPICAL_URBAN_COMMUTE_KM when absent), frequency-weighted-averaged across the
    contributing trips — the same approach _build_local_aggregate_trip() uses for
    rarely-seen inter-city routes, adapted here since every contributing trip counts
    equally (there is no per-route <2/yr threshold to weight by).

    Not damped by any travel_reduction signal and not rail-fare-calibrated — this is local
    travel by construction (see _apply_rail_calibration's docstring and
    derive_projected_trips_from_history's docstring for why local demand is exempt).

    Returns (trip_dict_or_None, warning). None (with an empty warning) if there are no
    qualifying intra-city trips, or the annualized frequency rounds to 0.
    """
    car_trips = [t for t in intra_city_trips if t.get("mode") in _INTRA_CITY_CAR_MODES]
    if not car_trips:
        return None, ""

    dists = [t.get("distance_km") or _TYPICAL_URBAN_COMMUTE_KM for t in car_trips]
    avg_dist = round(sum(dists) / len(dists), 1)
    ticket_types = [t.get("ticket_type") for t in car_trips]
    fare_class = _dominant_fare_class(ticket_types)

    annual_freq = round(len(car_trips) * 12 / data_window_months)
    if annual_freq < 1:
        return None, ""

    owns_car = load_car_usage().get("owns_car", False)
    modes = ["car_share"] + (["car_private"] if owns_car else [])
    alternatives: list[dict] = []
    for mode in modes:
        co2 = co2_kg_for_mode(mode, avg_dist)
        price = estimate_trip_price(mode, avg_dist)
        dur = estimate_duration_min(mode, avg_dist)
        alt = RouteAlternative(
            mode=mode,
            distance_km=avg_dist,
            duration_min=round(dur, 1),
            co2_kg=round(co2, 3),
            estimated_price_eur=round(price, 2),
        )
        alternatives.append(alt.model_dump())

    trip = ProjectedTrip(
        route=f"Intra-city car travel ({len(car_trips)} trip(s) observed, aggregated)",
        origin="various",
        destination="various",
        frequency_per_year=annual_freq,
        source="history",
        category="intra_city_aggregate",
        distance_km=avg_dist,
        alternatives=alternatives,
        fare_class=fare_class,
    )
    warning = (
        f"Aggregated {len(car_trips)} same-city car-share/car-rental trip(s) "
        f"(avg ~{avg_dist}km) into one projected intra-city trip ({annual_freq}/yr) instead "
        f"of dropping them — this is the demand a car-share membership actually prices "
        f"against. No rail alternative is offered for it (see this function's docstring)."
    )
    return trip.model_dump(), warning


def _build_commute_aggregate_trip(reduction_factor: float) -> tuple[dict | None, str]:
    """Synthesize the recurring home-city commute as a projected local-travel trip.

    travel_history_raw.json only ever records inter-city trips — a daily commute within
    the home city never shows up there at all, so without this a Deutschlandticket (or any
    other regional pass) has no representable demand to be judged against beyond whatever
    occasional short inter-city trips history happens to contain (see
    _build_local_aggregate_trip — a real but usually much smaller signal). persona.json's
    commute.office_days gives a real per-persona office-day count; the trip distance itself
    is not in any fixture, so it is approximated at _TYPICAL_URBAN_COMMUTE_KM — the
    Mobilität in Deutschland (MiD) household travel survey puts the average one-way commute
    distance for urban regional-transit commuters at roughly 8-10km, rounded down here.
    frequency_per_year counts one-way legs (there + back per office day), matching the
    convention derive_projected_trips_from_history already uses for real routes.

    Callers should normally pass reduction_factor=1.0 — a travel_reduction life-event signal
    (see _travel_reduction_factor) describes a change to *inter-city* travel (a project
    ending, a client engagement winding down); it says nothing about whether the persona
    still goes into their home-city office, so damping the commute alongside long-distance
    routes conflated two unrelated kinds of demand. The parameter is kept so the caller
    decides explicitly rather than this function silently assuming either way. No rail-fare
    calibration ratio is applied here either — the ratio is fitted against intercity fares
    only and this is a fixed regional leg (see _apply_rail_calibration's docstring).

    tariff="local" — a home-city commute is a Verkehrsverbund/city-transit fare, not a DB
    ticket at all, so a BahnCard's percentage discount has no authority over it (see
    apply_subscription_discount's docstring). Only a genuinely local-transit-valid coverage
    benefit (Deutschlandticket's unlimited_regional) should discount this trip.

    Returns (None, "") if the persona has no office_days at all (fully remote).
    """
    persona = json.loads((paths.DATA_DIR / "persona.json").read_text(encoding="utf-8"))
    commute = persona.get("profileData", {}).get("commute", {})
    office_days = commute.get("office_days", [])
    if not office_days:
        return None, ""

    raw_freq = len(office_days) * _WORKING_WEEKS_PER_YEAR * 2  # there + back
    damped_freq = round(raw_freq * reduction_factor)
    if damped_freq < 1:
        return None, ""

    dist = _TYPICAL_URBAN_COMMUTE_KM
    owns_car = load_car_usage().get("owns_car", False)
    modes = ["rail_regional", "car_share"] + (["car_private"] if owns_car else [])
    alternatives: list[dict] = []
    for mode in modes:
        co2_mode = "rail" if mode.startswith("rail") else mode
        rail_trip_type = "Regional" if mode == "rail_regional" else None
        co2 = co2_kg_for_mode(co2_mode, dist, trip_type=rail_trip_type)
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
        route=f"Home-city commute (~{len(office_days)}x/week office, ~{dist}km one-way)",
        origin="various",
        destination="various",
        frequency_per_year=damped_freq,
        source="history",
        category="commute_aggregate",
        distance_km=dist,
        alternatives=alternatives,
        fare_class="spar",
        tariff="local",
    )
    warning = (
        f"Modelled {len(office_days)} office day(s)/week as a recurring home-city commute "
        f"at ~{dist}km one-way (typical urban commute distance, not from actual data — "
        f"travel history only records inter-city trips) — {damped_freq}/yr legs. This is "
        f"the demand a Deutschlandticket or regional pass is actually priced against."
    )
    return trip.model_dump(), warning


