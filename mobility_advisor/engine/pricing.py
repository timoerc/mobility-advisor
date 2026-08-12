"""Per-trip subscription discounting — the cheapest applicable rate a held subscription
grants on a single trip."""

# MILES Basis catalog defaults (mobility_catalog.json's miles_basis benefits) — the floor
# every car-share ride costs even with NO subscription held. Named here so the walk-up
# floor below and the existing per-tier .get(..., default) fallbacks stay in sync.
_MILES_BASIS_BASE_KM_RATE_EUR = 0.79
_MILES_BASIS_UNLOCK_FEE_EUR = 1.0
_MILES_BASIS_PROTECTION_FEE_EUR = 3.9
# MILES's published Basis tariff is a per-km AND per-minute rate combined, not per-km
# alone — every catalog car-share tier's discount_time_pct benefit exists specifically to
# discount this second component. Without a base rate to discount, discount_time_pct was
# dead: every tier's "X% off Zeittarif" was worth exactly €0 regardless of how much it
# should have reduced a car-share trip's cost. €0.19/min is MILES's publicly listed Basis
# per-minute rate (the low end of its published per-vehicle-class range) — an anchor in
# the same spirit as _BASE_VALUE_OF_TIME_EUR_PER_HOUR below, not a precisely-metered figure.
# The fixtures don't record an actual rental duration for a car-share trip, only distance —
# duration_min here is estimate_duration_min()'s driving-time heuristic, which understates
# real MILES usage (park, run an errand, drive back) whenever a ride isn't pure transit
# time, so this remains an approximation like every other synthetic price curve in this
# module, not a claim of precisely reconstructed billing.
_MILES_BASIS_BASE_TIME_RATE_EUR_PER_MIN = 0.19


def apply_subscription_discount(
    mode: str,
    estimated_price_eur: float,
    distance_km: float,
    portfolio: list[dict],
    fare_class: str = "spar",
    local_tariff: bool = False,
    non_db_operator: bool = False,
    duration_min: float = 0.0,
) -> float:
    """Apply subscription discounts to a single trip's estimated (marginal) price.

    fare_class ("spar" or "flex") selects which catalog discount rate applies to a rail
    trip — discount_sparpreis_pct or discount_flexpreis_pct. These differ per BahnCard
    tier (e.g. BahnCard 50 gives 50% off Flexpreis but only 25% off Sparpreis), so a route
    whose historical trips were mostly booked Flexpreis (see _dominant_fare_class() in
    derive_projected_trips_from_history) must be scored against the Flexpreis rate, not
    silently assumed to be Sparpreis — otherwise every BahnCard tier looks identical on
    trips that were never actually priced that way.

    local_tariff=True marks a trip priced under a Verkehrsverbund/city-transit fare (see
    ProjectedTrip.tariff — currently only the synthesized home-city commute) rather than a
    real DB ticket. A BahnCard has no authority over a city-transit fare at all, so its
    percentage discount and its unlimited_long_distance/unlimited_regional flags must not
    apply — only a benefit that is genuinely valid on local transit
    (Deutschlandticket's unlimited_regional specifically) may discount it. Without this, a
    BahnCard's Sparpreis/Flexpreis discount rate was applied to the commute exactly as if
    it were a real long-distance-rail-tariff Nahverkehr ticket, inflating that BahnCard's
    reported "discount value" by whatever the commute's own price contributes — for a
    persona whose projected trips are dominated by the commute (as most personas' are),
    this was the single largest input to the reported figure.

    non_db_operator=True marks a trip whose contributing historical trips were run by a
    non-DB rail operator (e.g. FlixTrain — see ProjectedTrip.non_db_operator /
    _dominant_operator_is_non_db()). Neither a BahnCard's discount nor a Deutschlandticket's
    coverage apply — both are benefits DB grants on DB-ticketed travel, and a non-DB
    operator honours neither. Without this, a route actually run by FlixTrain was
    re-projected as a generic rail_intercity alternative and discounted by a BahnCard
    exactly as if it were a real DB fare.

    Car-share pricing here is the gross per-km/unlock/protection price with NO monthly
    credit applied — the credit is a portfolio-level annual budget, not a per-trip
    entitlement, and it is deducted exactly once, at the portfolio level, in
    simulate_portfolio() against total realized car-share spend across every trip. Pricing
    it in here per-trip (against a single route's own frequency) let a route occurring
    fewer than 12x/year claim the FULL monthly credit on every one of its trips — an €600/yr
    credit budget could be disbursed several times over across a handful of low-frequency
    routes. This does mean mode-share selection (see _mode_shares) sees the marginal,
    uncredited car-share price rather than a credit-aware one — a deliberate
    simplification, since correctly allocating a single shared credit across many
    competing routes to influence which mode each one picks would require solving one
    joint allocation across the whole trip set, not pricing routes independently.

    For car_share specifically, the starting best_price is NOT estimated_price_eur (the
    bare per-km curve from estimate_trip_price, which price_factors.json's own note says
    excludes per-trip unlock/protection fees "applied separately … in
    apply_subscription_discount"). Car-sharing has no truly card-free walk-up rate — using a
    service like MILES at all requires at least the free Basis-tier membership, which
    itself carries those fees (see _MILES_BASIS_* above). Starting from the bare per-km rate
    instead priced "no subscription" cheaper than every paid tier's actual walk-up cost,
    which made a paid tier's credit or per-km discount structurally unable to ever win
    regardless of how much car-share the persona actually uses. duration_min adds MILES's
    per-minute component (see _MILES_BASIS_BASE_TIME_RATE_EUR_PER_MIN) on top of the per-km
    rate — every catalog car-share tier's discount_time_pct benefit exists to discount
    exactly this, and was otherwise applied to nothing at all. Ignored for every other mode.

    Returns the discounted price. The cheapest applicable discount wins.
    """
    if mode == "car_share":
        best_price = round(
            _MILES_BASIS_BASE_KM_RATE_EUR * distance_km
            + _MILES_BASIS_BASE_TIME_RATE_EUR_PER_MIN * duration_min
            + _MILES_BASIS_UNLOCK_FEE_EUR
            + _MILES_BASIS_PROTECTION_FEE_EUR,
            2,
        )
    else:
        best_price = estimated_price_eur

    for sub in portfolio:
        sub_mode = sub.get("mode")
        benefits = sub.get("benefits", {})

        if sub_mode == "rail" and mode in ("rail_intercity", "rail_regional"):
            if non_db_operator:
                # A BahnCard's discount and a Deutschlandticket's coverage are both DB-only
                # benefits — a non-DB operator (e.g. FlixTrain) honours neither.
                continue

            if benefits.get("unlimited_regional") and mode == "rail_regional":
                best_price = min(best_price, 0.0)

            if local_tariff:
                # A city-transit fare has no BahnCard-eligible ticket to discount and no
                # long-distance leg to cover — only the unlimited_regional check above
                # (Deutschlandticket) applies here.
                continue

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
            base_km = benefits.get("base_km_rate_eur", _MILES_BASIS_BASE_KM_RATE_EUR)
            disc_km = benefits.get("discount_km_pct", 0)
            disc_time = benefits.get("discount_time_pct", 0)
            unlock = benefits.get("unlock_fee_eur_per_trip", _MILES_BASIS_UNLOCK_FEE_EUR)
            protection = benefits.get("protection_plus_eur_per_trip", _MILES_BASIS_PROTECTION_FEE_EUR)

            km_cost = base_km * (1 - disc_km / 100) * distance_km
            time_cost = (
                _MILES_BASIS_BASE_TIME_RATE_EUR_PER_MIN * (1 - disc_time / 100) * duration_min
            )
            trip_cost = km_cost + time_cost + unlock + protection
            best_price = min(best_price, round(trip_cost, 2))

    return round(best_price, 2)
