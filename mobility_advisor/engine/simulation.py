"""Portfolio simulation: per-trip mode-share pricing over generalized cost, aggregation
into total annual cost/time/CO2 for a candidate subscription set, and ranking/break-even
across multiple simulated candidates."""
import json
import math

from .. import paths
from ..models import ProjectedTripSet
from .pricing import apply_subscription_discount

# Value of travel time and CO2, used to express duration and emissions in euros so a
# subscription's price effect can actually change which mode is economical.
# Anchors: ~€12/h is a mid-range German value of travel-time savings for non-work travel;
# €0.20/kg is the UBA climate cost rate (~€200/t CO2). Both are scaled by the persona's
# own priority weights relative to their cost weight.
_BASE_VALUE_OF_TIME_EUR_PER_HOUR = 12.0
_BASE_CO2_PRICE_EUR_PER_KG = 0.20

# Logit "temperature" for _mode_shares' softmax over generalized cost, as a fraction of the
# mean generalized cost across a trip's alternatives (see _mode_shares' docstring for the
# formula). Not fitted against any observed German mode-choice data — no revealed-preference
# dataset is wired into this project — so treat it as a judgment call, not a calibrated
# constant, and read it by its effect rather than its value: at 0.08, two alternatives whose
# generalized cost differs by ~8% of the mean split roughly 70/30; a ~25% gap is needed
# before the cheaper option takes essentially the whole share (>95%). That is deliberately
# soft — it's what makes a subscription's effect on mode choice gradual (see _mode_shares'
# docstring for why a hard argmin was rejected) — rather than a knife-edge switch on a
# fraction-of-a-euro price change. A lower value sharpens the split toward a hard argmin: at
# theta->0, this degenerates to the pre-mode-share hard cheapest-alternative pick. A higher
# value flattens it toward splitting demand near-evenly regardless of cost.
_MODE_SHARE_THETA_FRACTION = 0.08


def _generalized_cost_rates(weights: dict | None) -> tuple[float, float]:
    """(value_of_time_eur_per_hour, co2_price_eur_per_kg) for these priority weights.

    Scales the base anchors by how much a persona weighs time/sustainability relative to
    cost, so a time-obsessed persona's generalized cost reacts more to a slow mode than a
    cost-obsessed persona's does. weights=None returns (0.0, 0.0) — pure-cost selection,
    preserving the pre-generalized-cost default.
    """
    if weights is None:
        return 0.0, 0.0
    w_cost = max(weights.get("cost_weight", 1.0), 0.05)
    w_time = weights.get("time_weight", 0.0)
    w_co2 = weights.get("sustainability_weight", 0.0)
    value_of_time = _BASE_VALUE_OF_TIME_EUR_PER_HOUR * (w_time / w_cost)
    co2_price = _BASE_CO2_PRICE_EUR_PER_KG * (w_co2 / w_cost)
    return value_of_time, co2_price


def _mode_shares(
    alts: list,
    portfolio: list[dict],
    fare_class: str,
    frequency_per_year: float,
    weights: dict | None,
    local_tariff: bool = False,
    non_db_operator: bool = False,
) -> list[tuple[dict, float, float]]:
    """Split a trip's frequency across its mode alternatives by a logit mode share over
    generalized cost, instead of an all-or-nothing pick. Without this, a persona's time
    and sustainability priority_weights never influenced which MODE gets used for any
    individual trip — every portfolio ended up with identical total_annual_time_min/
    total_annual_co2_kg, silently making those two weights inert.

    Generalized cost per alternative: gc = discounted_price + (duration_min / 60) *
    value_of_time + co2_kg * co2_price (see _generalized_cost_rates). Share is a softmax
    over -gc / theta, theta = _MODE_SHARE_THETA_FRACTION * mean(gc), which makes theta
    scale-free across a 20 km hop and an 800 km trip. min(gc) is subtracted before exp for
    numerical safety.

    Shares are used instead of a hard argmin because a hard pick lets a fraction-of-a-euro
    fare margin swing every trip on a route at once; shares make the response gradual and
    directly express that holding a subscription shifts how much a mode gets used, not a
    binary switch of every trip.

    frequency_per_year is kept in the signature (this route's own annual frequency, used by
    callers to annualize the returned per-trip prices) but is no longer forwarded into
    apply_subscription_discount() — car-share pricing there is now the marginal, uncredited
    price; the monthly credit is applied once at the portfolio level in simulate_portfolio()
    against total realized car-share spend, not per route (see apply_subscription_discount's
    docstring for why).

    local_tariff and non_db_operator are forwarded to apply_subscription_discount
    unchanged — see that function's docstring (a city-transit fare, currently only the
    synthesized commute, that a BahnCard has no authority over; and a non-DB rail operator
    such as FlixTrain, which honours neither a BahnCard nor a Deutschlandticket). Each
    alternative's own duration_min is forwarded too, so a car_share alternative's per-minute
    tariff component (and its tier-specific discount_time_pct) is priced correctly.

    Returns a list of (alt_dict, discounted_price, share) tuples, shares summing to 1.0.
    """
    priced: list[tuple[dict, float]] = []
    for alt in alts:
        alt_dict = alt if isinstance(alt, dict) else alt.model_dump()
        discounted = apply_subscription_discount(
            alt_dict["mode"], alt_dict["estimated_price_eur"], alt_dict["distance_km"],
            portfolio, fare_class=fare_class, local_tariff=local_tariff,
            non_db_operator=non_db_operator, duration_min=alt_dict.get("duration_min", 0.0),
        )
        priced.append((alt_dict, discounted))

    if len(priced) == 1:
        return [(priced[0][0], priced[0][1], 1.0)]

    value_of_time, co2_price = _generalized_cost_rates(weights)
    gcs = [
        price + (alt["duration_min"] / 60) * value_of_time + alt["co2_kg"] * co2_price
        for alt, price in priced
    ]

    mean_gc = sum(gcs) / len(gcs)
    theta = _MODE_SHARE_THETA_FRACTION * mean_gc
    if theta <= 0:
        best_idx = min(range(len(gcs)), key=lambda i: gcs[i])
        return [
            (alt, price, 1.0 if i == best_idx else 0.0)
            for i, (alt, price) in enumerate(priced)
        ]

    min_gc = min(gcs)
    weights_exp = [math.exp(-(gc - min_gc) / theta) for gc in gcs]
    total = sum(weights_exp)
    shares = [w / total for w in weights_exp]

    return [(alt, price, share) for (alt, price), share in zip(priced, shares)]


def _select_best_alternative(
    alts: list,
    portfolio: list[dict],
    fare_class: str,
    frequency_per_year: float,
    weights: dict | None,
) -> tuple[dict, float]:
    """Thin wrapper over _mode_shares() returning the highest-share (alt, discounted_price)
    entry. Kept for explainability and any future use; simulate_portfolio() itself
    accumulates over all shares rather than calling this.
    """
    shares = _mode_shares(alts, portfolio, fare_class, frequency_per_year, weights)
    alt, price, _ = max(shares, key=lambda s: s[2])
    return alt, price


def simulate_portfolio(subscription_ids: list[str], weights: dict | None = None) -> dict:
    """Simulate total annual cost, time, and CO2 for a given subscription portfolio.

    Loads the merged projected trip set, applies subscription discounts per trip, and
    splits each trip's frequency across its mode alternatives by a logit mode share over
    generalized cost (see _mode_shares — weights=None means pure cost, same as before this
    parameter existed). Per-trip totals are accumulated as share-weighted sums, so a
    subscription that shifts generalized cost enough to make a mode more attractive shows
    up as a gradual shift in projected mode usage rather than an all-or-nothing flip.

    Args:
        subscription_ids: List of catalog option IDs forming the portfolio
            (e.g. ["db_bc50_2nd_annual_standard", "miles_basis"]).
        weights: Optional dict with cost_weight/time_weight/sustainability_weight
            (see compute_portfolio_score). None selects the cheapest mode per trip only.

    A held car-share subscription's monthly_credit_eur is a portfolio-level annual budget
    (credit * 12), not a per-trip entitlement — it is deducted here exactly once, capped at
    whatever car-share spend was actually realized across every trip in the projected set,
    never per route (see apply_subscription_discount's docstring for the bug this replaces:
    a route occurring under 12x/year used to claim the full monthly credit on every one of
    its trips, disbursing many times the annual budget). car_share_credit_applied_eur in
    the return value is that one-time deduction, so total_trip_cost_eur = (sum of
    trip_breakdown's per-trip annual_cost, which are gross/uncredited for car-share trips)
    minus car_share_credit_applied_eur — the two won't sum to the same total by design.

    Returns a dict with total_subscription_cost_eur, total_trip_cost_eur,
    total_annual_cost_eur, total_annual_time_min, total_annual_co2_kg,
    car_share_credit_applied_eur, and a per-trip breakdown (dominant-share selected_mode
    plus a mode_shares dict).
    """
    merged_path = paths.DATA_DIR / "_projected_trips_merged.json"
    if not merged_path.exists():
        return {"status": "error", "error": "_projected_trips_merged.json not found — run merge_projected_trip_sets first"}

    merged = json.loads(merged_path.read_text(encoding="utf-8"))
    trip_set = ProjectedTripSet.model_validate(merged)

    catalog_raw = json.loads((paths.STATIC_DIR / "mobility_catalog.json").read_text(encoding="utf-8"))
    catalog_by_id = {opt["id"]: opt for opt in catalog_raw["options"]}

    portfolio = []
    for sid in subscription_ids:
        opt = catalog_by_id.get(sid)
        if opt is None:
            return {"status": "error", "error": f"unknown subscription id: {sid}"}
        portfolio.append(opt)

    total_sub_cost = sum(opt["monthly_cost_eur"] * 12 for opt in portfolio)

    total_trip_cost = 0.0
    total_time = 0.0
    total_co2 = 0.0
    total_car_share_spend = 0.0
    trip_breakdown: list[dict] = []

    for trip in trip_set.trips:
        alts = trip.alternatives
        if not alts:
            continue

        shares = _mode_shares(
            alts, portfolio, trip.fare_class, trip.frequency_per_year, weights,
            local_tariff=(trip.tariff == "local"),
            non_db_operator=trip.non_db_operator,
        )

        annual_cost = sum(price * share for _, price, share in shares) * trip.frequency_per_year
        annual_time = sum(alt["duration_min"] * share for alt, _, share in shares) * trip.frequency_per_year
        annual_co2 = sum(alt["co2_kg"] * share for alt, _, share in shares) * trip.frequency_per_year
        annual_car_share_cost = sum(
            price * share for alt, price, share in shares if alt["mode"] == "car_share"
        ) * trip.frequency_per_year

        total_trip_cost += annual_cost
        total_time += annual_time
        total_co2 += annual_co2
        total_car_share_spend += annual_car_share_cost

        dominant_alt, dominant_price, _ = max(shares, key=lambda s: s[2])
        mode_shares = {alt["mode"]: round(share, 4) for alt, _, share in shares}

        trip_breakdown.append({
            "route": trip.route,
            "frequency": trip.frequency_per_year,
            "selected_mode": dominant_alt["mode"],
            "mode_shares": mode_shares,
            "price_per_trip": dominant_price,
            "annual_cost": round(annual_cost, 2),
            "annual_time_min": round(annual_time, 1),
            "annual_co2_kg": round(annual_co2, 3),
        })

    annual_car_share_credit = sum(
        opt.get("benefits", {}).get("monthly_credit_eur", 0) * 12
        for opt in portfolio if opt.get("mode") == "car_share"
    )
    car_share_credit_applied = min(annual_car_share_credit, total_car_share_spend)
    total_trip_cost -= car_share_credit_applied

    return {
        "status": "ok",
        "subscription_ids": subscription_ids,
        "total_subscription_cost_eur": round(total_sub_cost, 2),
        "total_trip_cost_eur": round(total_trip_cost, 2),
        "car_share_credit_applied_eur": round(car_share_credit_applied, 2),
        "total_annual_cost_eur": round(total_sub_cost + total_trip_cost, 2),
        "total_annual_time_min": round(total_time, 1),
        "total_annual_co2_kg": round(total_co2, 3),
        "trip_breakdown": trip_breakdown,
    }


def _normalize_for_display(values: list[float]) -> list[float]:
    """Min-max normalize a dimension to 0-1 across a candidate set, for DISPLAY only.

    A 2% dead-band collapses a trivial spread to 0 for all candidates, rather than letting
    a fraction-of-a-percent difference blow up to a full 0..1 range once it's the only
    variation left. Not used for ranking (see compute_portfolio_score) — set-relative
    normalization mixes units that aren't comparable (a EUR spread and a minutes spread are
    not the same "distance"), which is exactly why ranking uses a monetized generalized
    cost instead. This is kept only so callers can still show "how does this candidate
    compare on cost alone" as a 0..1 bar.
    """
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0] * len(values)
    spread_pct = (hi - lo) / max(abs(hi), abs(lo), 1)
    if spread_pct < 0.02:
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def compute_portfolio_score(
    simulation_results: list[dict],
    weights: dict,
) -> dict:
    """Score and rank multiple portfolio simulations by monetized generalized annual cost.

    Takes simulation results from multiple simulate_portfolio() calls and the user's
    priority weights, and ranks candidates on:

        generalized_eur = total_annual_cost_eur
                         + (total_annual_time_min / 60) * value_of_time
                         + total_annual_co2_kg * co2_price

    using the same value_of_time/co2_price rates _mode_shares() already uses to pick mode
    shares (see _generalized_cost_rates) — so the portfolio ranking and the per-trip mode
    choice share one objective instead of disagreeing about what "better" means. Lower
    score = better.

    This replaces the previous set-relative min-max normalization, which mixed
    incommensurable units (a EUR spread and a minutes spread both mapped to 0..1) and broke
    independence of irrelevant alternatives: adding or removing an irrelevant candidate
    changed every other candidate's normalized position and could reorder the ranking. A
    monetized cost has none of that — every candidate is measured against a fixed EUR/hour
    and EUR/kg rate, not against whatever else happens to be in the candidate set, so
    dropping or adding a candidate can never change the relative order of the others.

    Args:
        simulation_results: List of dicts from simulate_portfolio().
        weights: Dict with cost_weight, time_weight, sustainability_weight (sum to 1).

    Returns a dict with ranked portfolios and their scores. Each ranked entry also carries
    norm_cost/norm_time/norm_co2 — set-relative 0..1 positions per dimension, for display
    only (e.g. a per-dimension bar). They play no role in the ranking itself.
    """
    if not simulation_results:
        return {"status": "error", "error": "no simulation results to score"}

    parsed = []
    for r in simulation_results:
        if isinstance(r, str):
            try:
                r = json.loads(r)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(r, dict):
            parsed.append(r)

    valid = [r for r in parsed if r.get("status") == "ok"]
    if not valid:
        return {"status": "error", "error": "no valid simulation results"}

    if isinstance(weights, str):
        try:
            weights = json.loads(weights)
        except (json.JSONDecodeError, TypeError):
            weights = {}
    w_cost = weights.get("cost_weight", 0.34) if isinstance(weights, dict) else 0.34
    w_time = weights.get("time_weight", 0.33) if isinstance(weights, dict) else 0.33
    w_co2 = weights.get("sustainability_weight", 0.33) if isinstance(weights, dict) else 0.33

    value_of_time, co2_price = _generalized_cost_rates(
        {"cost_weight": w_cost, "time_weight": w_time, "sustainability_weight": w_co2}
    )

    costs = [r["total_annual_cost_eur"] for r in valid]
    times = [r["total_annual_time_min"] for r in valid]
    co2s = [r["total_annual_co2_kg"] for r in valid]
    norm_cost = _normalize_for_display(costs)
    norm_time = _normalize_for_display(times)
    norm_co2 = _normalize_for_display(co2s)

    scored: list[dict] = []
    for i, r in enumerate(valid):
        generalized_eur = (
            r["total_annual_cost_eur"]
            + (r["total_annual_time_min"] / 60) * value_of_time
            + r["total_annual_co2_kg"] * co2_price
        )
        scored.append({
            "subscription_ids": r["subscription_ids"],
            "score": round(generalized_eur, 2),
            "generalized_annual_cost_eur": round(generalized_eur, 2),
            "total_annual_cost_eur": r["total_annual_cost_eur"],
            "total_annual_time_min": r["total_annual_time_min"],
            "total_annual_co2_kg": r["total_annual_co2_kg"],
            "norm_cost": round(norm_cost[i], 4),
            "norm_time": round(norm_time[i], 4),
            "norm_co2": round(norm_co2[i], 4),
        })

    scored.sort(key=lambda x: x["score"])

    return {
        "status": "ok",
        "weights": {"cost": w_cost, "time": w_time, "sustainability": w_co2},
        "value_of_time_eur_per_hour": round(value_of_time, 2),
        "co2_price_eur_per_kg": round(co2_price, 3),
        "ranked_portfolios": scored,
        "best": scored[0],
        "worst": scored[-1],
    }


def _compute_break_even(entries: list[dict]) -> list[dict]:
    """Forward-looking break-even for every non-baseline candidate — a single BahnCard tier
    or Deutschlandticket, a single car-share membership, a BahnCard+Deutschlandticket
    combo, a rail+car-share combo, or the user's current portfolio — against the "no
    subscriptions" baseline. Covers every candidate optimize_all_categories() simulates,
    not just single-subscription rail/car-share picks: a combo's fee and discount value are
    exactly as answerable a "does this pay for itself" question as a single card's, and
    restricting break-even to singles meant the current portfolio and every multi-
    subscription candidate had no break-even line at all.

    This is the forward-looking counterpart to compute_annual_report_stats()'s
    discount_value_eur/net_eur — that function attributes discount value retrospectively
    by matching (mode, provider) against last year's actual trips; this one reads it off
    the already-simulated forward-projected trip set, so it automatically reflects
    calibrated fares, cost-based mode selection, and every projected route (not just
    literal past trips). discount_value_eur is simply how much cheaper the projected
    year's trip costs become with this candidate held vs. holding nothing — a definition
    that works uniformly across rail percentage-discount cards, flat-fee unlimited rail
    passes, car-share membership credits/km-discounts, and any combination of them, unlike
    the retrospective version which has to special-case each kind (see
    _rail_coverage_kind()). Note this mixes fare-discount value with any mode-share shift
    the candidate induces (see _mode_shares) — it answers "how much cheaper do my trips get
    with this", not narrowly "how much discount did I receive". For a persona with no
    projected trips in that mode (e.g. no car-share usage), discount_value_eur is
    correctly 0 — the membership fee is a pure net loss, which is itself the useful
    finding for a "why would I want this" question.

    Requires a "baseline" category entry (the "No subscriptions" candidate) in `entries`;
    returns [] if absent (should not happen — optimize_all_categories() always adds it).
    """
    baseline = next((e for e in entries if e["category"] == "baseline"), None)
    if baseline is None:
        return []
    baseline_trip_cost = baseline["total_trip_cost_eur"]

    result = []
    for e in entries:
        if e["category"] == "baseline":
            continue
        annual_fee_eur = e["total_subscription_cost_eur"]
        discount_value_eur = round(baseline_trip_cost - e["total_trip_cost_eur"], 2)
        net_eur = round(discount_value_eur - annual_fee_eur, 2)
        result.append({
            "label": e["label"],
            "subscription_ids": e["subscription_ids"],
            "annual_fee_eur": annual_fee_eur,
            "discount_value_eur": discount_value_eur,
            "net_eur": net_eur,
            "breaks_even": net_eur >= 0,
        })
    return result



