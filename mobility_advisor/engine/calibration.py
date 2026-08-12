"""Fare-class/operator majority-voting for a route's contributing historical trips, rail
fare calibration against what the persona actually paid, and travel-reduction damping
from a near-term life-event signal."""
from datetime import date, timedelta

from .. import clock
from ..store.loaders import load_current_subscriptions, load_life_events, load_travel_history
from .factors import estimate_trip_price
from .geo import _RAIL_DISTANCE_THRESHOLD_KM

def _dominant_fare_class(ticket_types: list[str | None]) -> str:
    """Majority-vote a route's fare class from its contributing trips' ticket_type text.

    "flex" wins only on a strict majority (e.g. "Flexpreis, 2. Klasse" contributing >50%
    of the route's trips) — a mixed or Sparpreis-dominated route defaults to "spar", the
    conservative choice (Sparpreis discount is <= Flexpreis discount on every catalog
    BahnCard, so understating fare class never overstates a card's savings).
    """
    flex_count = sum(1 for t in ticket_types if t and "flex" in t.lower())
    return "flex" if flex_count * 2 > len(ticket_types) else "spar"


def _dominant_operator_is_non_db(providers: list[str | None]) -> bool:
    """Majority-vote whether a route's contributing historical trips ran on a non-DB
    operator (e.g. FlixTrain) rather than Deutsche Bahn.

    True only on a strict majority of non-DB-provider trips — a mixed or DB-dominated
    route defaults to False (DB-eligible), matching _dominant_fare_class's majority-vote
    convention. A BahnCard's discount and a Deutschlandticket's coverage are both DB-only
    benefits (see apply_subscription_discount's docstring) — without this check, a route
    actually run by FlixTrain got re-projected as a generic rail_intercity alternative and
    discounted by a BahnCard exactly as if it were a real DB ticket, which FlixTrain does
    not honour.
    """
    non_db_count = sum(1 for p in providers if p and "deutsche bahn" not in p.lower())
    return non_db_count * 2 > len(providers)


_RAIL_FARE_CALIBRATION_MIN_TRIPS = 2
# Tightened from (0.3, 3.0): now that the ratio is only ever applied to rail_intercity
# alternatives (see _apply_rail_calibration), a 3x swing has no regional trip to hide
# behind — it would scale a persona's entire long-distance rail pricing by 3x off as few as
# _RAIL_FARE_CALIBRATION_MIN_TRIPS=2 observed fares. No real Sparpreis/Flexpreis spread on
# the same route class plausibly exceeds ~2.5x.
_RAIL_FARE_CALIBRATION_CLAMP = (0.5, 2.5)
# How far beyond the farthest calibrated trip the ratio is still trusted to extrapolate.
# A ratio fitted on 300-450km domestic Sparpreis fares says nothing about a 2000km+ route
# (no realistic single-ticket DB fare exists at that distance) — applying it there has
# flipped mode selection from flight to a implausibly cheap "rail_intercity" in testing.
# Beyond this bound, calibration is skipped and the trip falls back to the uncalibrated
# synthetic curve rather than extrapolating a domestic-fare ratio onto a route class it
# was never fitted on.
_RAIL_FARE_CALIBRATION_MAX_DISTANCE_MULTIPLIER = 2.0
_RAIL_FARE_CALIBRATION_MIN_MAX_DISTANCE_KM = 600.0


def _rail_fare_calibration_ratio() -> tuple[float, float, list[str]]:
    """Calibrate the synthetic rail price curve (estimate_trip_price) against fares the
    persona actually paid, so a BahnCard's ROI is judged against real spend rather than
    a generic exponential curve that can systematically over- or understate every card's
    payoff regardless of usage.

    Grosses each DB-provider historical rail trip's paid fare back up to its full-price
    equivalent using the discount rate of whichever BahnCard the persona currently holds
    (0% if none — the fare is already full price), matched to the fare class ("flex" vs
    "spar") the trip's own ticket_type text shows — not assumed uniform across trips.
    Compares the average full-price-equivalent EUR/trip against what estimate_trip_price()
    would have synthesized for the same distances, and returns (ratio, max_distance_km,
    warnings) — max_distance_km is how far the ratio may be extrapolated (see
    _RAIL_FARE_CALIBRATION_MAX_DISTANCE_MULTIPLIER); callers must not apply the ratio to
    an alternative beyond it.

    FlixTrain and other non-DB providers are excluded — they are not BahnCard fares (same
    distinction _rail_coverage_kind() draws for the annual report). Trips already covered
    by a flat-rate pass (Deutschlandticket, BahnCard 100 — ticket_type names one, or
    cost_eur is 0) are excluded too: their "fare" is €0 by construction, which has nothing
    to do with what a Sparpreis/Flexpreis BahnCard trip would have cost, and previously
    dragged the ratio down (a persona with a few flat-rate-covered regional legs got a
    systematically cheaper calibrated price on every other route). Trips at or under
    _RAIL_DISTANCE_THRESHOLD_KM are excluded too — the ratio is applied only to
    rail_intercity alternatives (see _apply_rail_calibration's docstring for why regional
    fares are exempt), so a regional trip in the fitting sample would calibrate the ratio
    against a fare structure it is never actually used to scale. Falls back to
    (1.0, 0.0, [warning]) — the unscaled synthetic curve, applied nowhere — when fewer
    than _RAIL_FARE_CALIBRATION_MIN_TRIPS priced DB Sparpreis/Flexpreis intercity trips
    with a usable distance exist.
    """
    trips = load_travel_history()["trips"]

    current = load_current_subscriptions()["subscriptions"]
    rail_card = next(
        (
            s for s in current
            if s.get("mode") == "rail" and not s.get("benefits", {}).get("unlimited_regional")
            and not s.get("benefits", {}).get("unlimited_long_distance")
        ),
        None,
    )
    benefits = (rail_card or {}).get("benefits", {})
    spar_pct = benefits.get("discount_sparpreis_pct") or 0
    flex_pct = benefits.get("discount_flexpreis_pct") or 0

    full_price_total = 0.0
    synthetic_total = 0.0
    max_dist = 0.0
    n = 0
    for t in trips:
        if t.get("mode") != "rail":
            continue
        if "deutsche bahn" not in (t.get("provider") or "").lower():
            continue
        cost = t.get("cost_eur")
        dist = t.get("distance_km")
        if cost is None or not dist or dist <= 0:
            continue
        if dist <= _RAIL_DISTANCE_THRESHOLD_KM:
            # The ratio is only ever applied to rail_intercity alternatives (see
            # _apply_rail_calibration) — a regional-distance fare here would fit the ratio
            # against a fare structure it never actually scales.
            continue
        ticket_type_lower = (t.get("ticket_type") or "").lower()
        if cost == 0 or "deutschland-ticket" in ticket_type_lower or "bahncard 100" in ticket_type_lower:
            continue
        fare_class = "flex" if "flex" in ticket_type_lower else "spar"
        pct = flex_pct if fare_class == "flex" else spar_pct
        full_price = cost / (1 - pct / 100) if pct else cost
        synthetic = estimate_trip_price("rail_intercity", dist)
        if synthetic <= 0:
            continue
        full_price_total += full_price
        synthetic_total += synthetic
        max_dist = max(max_dist, dist)
        n += 1

    if n < _RAIL_FARE_CALIBRATION_MIN_TRIPS or synthetic_total <= 0:
        return 1.0, 0.0, [
            f"Rail fare calibration skipped ({n} usable DB trip(s) with cost+distance data; "
            f"need >= {_RAIL_FARE_CALIBRATION_MIN_TRIPS}) — projected rail prices use the "
            f"uncalibrated synthetic price curve, not observed fares."
        ]

    ratio = full_price_total / synthetic_total
    max_distance_km = max(
        max_dist * _RAIL_FARE_CALIBRATION_MAX_DISTANCE_MULTIPLIER,
        _RAIL_FARE_CALIBRATION_MIN_MAX_DISTANCE_KM,
    )
    lo, hi = _RAIL_FARE_CALIBRATION_CLAMP
    if ratio < lo or ratio > hi:
        warning = (
            f"Rail fare calibration ratio {round(ratio, 2)}x (from {n} observed DB trips) "
            f"looked like an outlier and was clamped to [{lo}, {hi}]."
        )
        ratio = max(lo, min(hi, ratio))
    else:
        warning = (
            f"Rail prices calibrated to observed fares: synthetic price curve scaled "
            f"{round(ratio, 2)}x from {n} observed DB Sparpreis/Flexpreis trip(s) up to "
            f"{round(max_distance_km)}km; routes beyond that use the uncalibrated curve."
        )
    return ratio, max_distance_km, [warning]


def _apply_rail_calibration(
    alternatives: list[dict], ratio: float, max_distance_km: float
) -> list[dict]:
    """Scale a route's rail_intercity alternatives' estimated_price_eur by the calibration
    ratio from _rail_fare_calibration_ratio(), for alternatives at or under max_distance_km
    only — see that function's docstring for why calibration must not extrapolate past the
    distance range it was fitted on.

    rail_regional is deliberately excluded, not just distance-guarded: the ratio is fitted
    exclusively against DB Sparpreis/Flexpreis intercity fares (_rail_fare_calibration_ratio
    filters to those), which say nothing about a regional/short-hop fare structure. Applying
    it to rail_regional used to inflate the synthetic home-city commute — a fixed ~8km leg
    that dominates >90% of every persona's projected trips (see
    _build_commute_aggregate_trip) — by whatever ratio an unrelated set of long-distance
    fares happened to produce (observed up to 2.6x in one persona), which then decided the
    whole portfolio ranking. Non-rail alternatives (car_rental, flight, ...) are untouched
    either way — the calibration is derived from, and only validated against, observed rail
    fares.
    """
    if ratio == 1.0:
        return alternatives
    for alt in alternatives:
        if alt.get("mode") == "rail_intercity" and alt.get("distance_km", 0) <= max_distance_km:
            alt["estimated_price_eur"] = round(alt["estimated_price_eur"] * ratio, 2)
    return alternatives


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
        if clock.MOCK_TODAY <= event_date <= clock.MOCK_TODAY + timedelta(days=365):
            qualifying.append(event_date)

    if not qualifying:
        return 1.0, []

    nearest = min(qualifying)
    factor = max(0.0, min(1.0, (nearest - clock.MOCK_TODAY).days / 365))
    warning = (
        f"Travel-reduction signal detected (event date {nearest.isoformat()}) — projected "
        f"trip frequencies damped by a factor of {round(factor, 2)} to reflect reduced "
        f"travel after this date, rather than extrapolating history unchanged."
    )
    return factor, [warning]


