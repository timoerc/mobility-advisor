"""Aggregation and lookup helpers over travel history and subscriptions: the QA agent's
compute_travel_stats tool, the fuzzy-match resolver shared by execution and CO2-impact
lookups, and the annual report's deterministic figures."""
import csv
import re

from .. import clock, paths
from ..i18n import t
from ..models import TravelHistory
from ..store.loaders import (
    _KNOWN_MODES,
    load_annual_travel_history,
    load_current_subscriptions,
    load_mobility_catalog,
    load_travel_history,
)

def compute_travel_stats(
    subscription_or_provider: str | None = None,
    mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    origin_filter: str | None = None,
    destination_filter: str | None = None,
) -> dict:
    """Aggregate the active persona's travel history: trip counts, total spend, distance,
    and CO2, with optional filters.

    Use this for ANY counting, summing, or date-range question about trips — never tally
    the travel history JSON yourself, and never use outside knowledge of CO2 factors for a
    "what's my footprint" question — this is the one aggregation tool that has one.

    Args:
        subscription_or_provider: Optional filter, e.g. "BahnCard 50" or "Deutsche Bahn".
            Matched case-insensitively as a substring against each trip's booked_under
            field OR its provider field (a match on either counts). Pass None for no filter.
        mode: Optional exact-match filter on trip mode (e.g. "rail", "car_share"). Pass None for no filter.
        date_from: Optional inclusive ISO date string ("YYYY-MM-DD"); trips before this are excluded.
        date_to: Optional inclusive ISO date string ("YYYY-MM-DD"); trips after this are excluded.
        origin_filter: Optional substring to match against the trip's origin station name
            (case-insensitive). E.g. "Frankfurt" matches "Frankfurt (Main) Hbf". Pass None for no filter.
        destination_filter: Optional substring to match against the trip's destination station
            name (case-insensitive). Pass None for no filter.

    Returns a dict with keys: trip_count (int), total_spend_eur (float, sums only trips with
    non-null cost_eur), total_distance_km (float, sums only trips with non-null distance_km),
    total_co2_kg (float, sums only trips with non-null co2_emission_kg AND a recognized mode
    — an empty/unknown mode is excluded here the same way load_travel_history's own
    data_quality_warnings already say it is), trips_missing_cost/trips_missing_distance (int,
    count of matched trips excluded from the respective sum for a null value),
    trips_excluded_from_co2 (int, count excluded from total_co2_kg for either a null value or
    an empty/unrecognized mode), matched_filters (dict echoing the filters applied),
    subscription_renewal (dict with next_renewal_date/billing_cycle, or null — set when
    subscription_or_provider matches an entry in current_subscriptions.json by the same
    substring rule), and data_quality_warnings (list[str], unfiltered passthrough from
    load_travel_history so data issues are never hidden by a filter).
    """
    history_data = load_travel_history()
    trips = TravelHistory.model_validate({"trips": history_data["trips"]}).trips
    needle = subscription_or_provider.lower() if subscription_or_provider else None
    origin_needle = origin_filter.lower() if origin_filter else None
    destination_needle = destination_filter.lower() if destination_filter else None

    def matches(trip) -> bool:
        if mode is not None and trip.mode != mode:
            return False
        if date_from is not None and trip.date < date_from:
            return False
        if date_to is not None and trip.date > date_to:
            return False
        if origin_needle is not None and origin_needle not in trip.origin.lower():
            return False
        if destination_needle is not None and destination_needle not in trip.destination.lower():
            return False
        if needle is not None:
            booked = (trip.booked_under or "").lower()
            if needle not in booked and needle not in trip.provider.lower():
                return False
        return True

    matched = [trip for trip in trips if matches(trip)]
    total_spend_eur = sum(trip.cost_eur for trip in matched if trip.cost_eur is not None)
    # distance_km is float | None on the Trip model (a null value is possible, e.g. one of
    # Lena's malformed history entries) — unguarded, a single such trip raised TypeError
    # here even though the analogous cost_eur sum right above was always guarded.
    total_distance_km = sum(trip.distance_km for trip in matched if trip.distance_km is not None)
    trips_missing_cost = sum(1 for trip in matched if trip.cost_eur is None)
    trips_missing_distance = sum(1 for trip in matched if trip.distance_km is None)
    total_co2_kg = sum(
        trip.co2_emission_kg for trip in matched
        if trip.co2_emission_kg is not None and trip.mode in _KNOWN_MODES
    )
    trips_excluded_from_co2 = sum(
        1 for trip in matched
        if trip.co2_emission_kg is None or trip.mode not in _KNOWN_MODES
    )

    subscription_renewal = None
    if needle is not None:
        subs = load_current_subscriptions()["subscriptions"]
        sub_match, _ = _resolve_unique_match(needle, subs, ("product", "provider"))
        if sub_match is not None:
            subscription_renewal = {
                "next_renewal_date": sub_match["next_renewal_date"],
                "billing_cycle": sub_match["billing_cycle"],
            }

    return {
        "trip_count": len(matched),
        "total_spend_eur": round(total_spend_eur, 2),
        "total_distance_km": round(total_distance_km, 2),
        "total_co2_kg": round(total_co2_kg, 3),
        "trips_missing_cost": trips_missing_cost,
        "trips_missing_distance": trips_missing_distance,
        "trips_excluded_from_co2": trips_excluded_from_co2,
        "matched_filters": {
            "subscription_or_provider": subscription_or_provider,
            "mode": mode,
            "date_from": date_from,
            "date_to": date_to,
            "origin_filter": origin_filter,
            "destination_filter": destination_filter,
        },
        "subscription_renewal": subscription_renewal,
        "data_quality_warnings": history_data.get("data_quality_warnings", []),
    }


def _resolve_unique_match(
    needle: str, candidates: list[dict], fields: tuple[str, ...]
) -> tuple[dict | None, str | None]:
    """Find exactly one candidate whose given fields contain needle as a case-insensitive substring.

    Falls back to token-overlap matching (≥ 2 alphanumeric words in common) when substring
    matching yields no results, to handle language/notation variants such as "2nd class" vs
    "2. Klasse" introduced by LLM paraphrasing.

    Returns (match, None) on exactly one match. Returns (None, error_message) if zero or
    more than one candidate matches — callers must treat both as failure, never guess.
    """
    needle_lower = needle.lower()

    # Primary: case-insensitive substring
    matches = [
        c for c in candidates if any(needle_lower in str(c.get(f, "")).lower() for f in fields)
    ]

    # Fallback: token overlap — handles variants like "2nd class" vs "2. Klasse"
    if not matches:
        needle_tokens = set(re.findall(r'\w+', needle_lower))
        matches = [
            c for c in candidates
            if any(
                len(needle_tokens & set(re.findall(r'\w+', str(c.get(f, "")).lower()))) >= 2
                for f in fields
            )
        ]

    if not matches:
        return None, t("error.noMatchFor", query=needle)
    if len(matches) > 1:
        names = ", ".join(c.get("product", "?") for c in matches)
        return None, t("error.ambiguousMatchFor", query=needle, count=len(matches), matches=names)
    return matches[0], None


# Only car-sharing (e.g. MILES) requires membership to use the mode at all — rail passes,
# Deutschlandticket, and car-rental loyalty tiers are discount/rewards programs layered on
# top of a mode you can already use without any subscription (full-price ticket, pay-as-you-go
# rental), so losing them changes price, not which mode is usable.
_MODE_ACCESS_GATED_MODES = {"car_share"}


def _generic_car_co2_factor_kg_per_km() -> float:
    """kg CO2e/km for driving a car with no specific type/size known — the fallback used when
    a candidate removes the user's only access to car-sharing. Car_private/Car_Sharing/
    Car_Rental all share the same 'Null,Null' average in co2_factors.csv, so it doesn't matter
    which of the three the user would actually end up driving."""
    with (paths.STATIC_DIR / "co2_factors.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["mode"] == "Car_Sharing" and row["type"] == "Null" and row["size"] == "Null":
                return float(row["kg_co2e_per_km"])
    raise RuntimeError("Car_Sharing,Null,Null row missing from co2_factors.csv")


def _rail_and_carshare_co2_factors() -> tuple[float, float]:
    """Return (rail, car_share) generic CO2 factors in g/km, sourced from co2_factors.csv's
    Rail/Null/Null and Car_Sharing/Null/Null rows — the same generic-average rows
    _generic_car_co2_factor_kg_per_km already reads for the optimizer, so the annual report's
    fixed CO2 formula can never disagree with the optimizer's own per-candidate CO2 math about
    what a generic rail/car-share km costs. Used to interpolate real figures into
    annual_communicator's prompt instead of a hardcoded assumption."""
    rail_kg_per_km: float | None = None
    car_share_kg_per_km: float | None = None
    with (paths.STATIC_DIR / "co2_factors.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["type"] != "Null" or row["size"] != "Null":
                continue
            if row["mode"] == "Rail":
                rail_kg_per_km = float(row["kg_co2e_per_km"])
            elif row["mode"] == "Car_Sharing":
                car_share_kg_per_km = float(row["kg_co2e_per_km"])
    if rail_kg_per_km is None or car_share_kg_per_km is None:
        raise RuntimeError("Rail,Null,Null or Car_Sharing,Null,Null row missing from co2_factors.csv")
    return round(rail_kg_per_km * 1000, 2), round(car_share_kg_per_km * 1000, 2)


def _rail_coverage_kind(sub: dict) -> str:
    """Classify a rail subscription's catalog benefits by how it covers trips.

    A persona can hold both a long-distance discount card (BahnCard) and a flat-fee
    regional pass (Deutschlandticket) at once — both are mode="rail", provider=
    "Deutsche Bahn", so a plain (mode, provider) match would attribute every rail
    trip to both. The catalog's benefits flags tell them apart:
      - "unlimited_all": unlimited_long_distance AND unlimited_regional (e.g.
        BahnCard 100) — every rail trip is already included, nothing to discount.
      - "unlimited_regional": unlimited_regional only (e.g. Deutschlandticket) — a
        flat monthly fee covering regional trips only.
      - "discount": neither flag set, just discount_sparpreis_pct/discount_
        flexpreis_pct (e.g. BahnCard 25/50) — a % off a fare that was still paid.
    """
    benefits = sub.get("benefits") or {}
    if benefits.get("unlimited_long_distance") and benefits.get("unlimited_regional"):
        return "unlimited_all"
    if benefits.get("unlimited_regional"):
        return "unlimited_regional"
    return "discount"


def compute_annual_report_stats() -> dict:
    """Deterministic, code-computed figures for the annual report.

    Spend, CO2, and per-subscription value are calculated here in Python rather than
    left to the LLM, so the report's headline numbers can never silently contradict
    each other the way free-text arithmetic spread across three separate agent stages
    could (e.g. a "savings" figure in one section disagreeing with a "net loss" verdict
    for the same subscription in another). annual_communicator_agent narrates around
    these figures instead of computing them itself; main.py's /api/annual-report
    endpoint substitutes the rendered tables into the report's placeholder sections.

    Trip-to-subscription attribution is done here by (mode, provider) match against
    load_annual_travel_history()'s year-scoped trips — not by the trip data's
    'booked_under' field, which is null for every mock trip and would otherwise make
    every subscription look completely unused.

    Returns a dict with keys:
      - review_year (int)
      - total_spend_eur (float): year-scoped trip costs (cost_eur present only) plus
        every active subscription's annualized fee
      - total_trips (int), trips_missing_cost (int)
      - dominant_mode (str): the mode with the most trips this year ("" if none)
      - by_mode (list[dict]): one row per mode present this year, each
        {mode, trips, distance_km, spend_eur, co2_kg}, sorted by co2_kg descending,
        followed by a final {mode: "Total", ...} row
      - total_co2_kg (float): sum of co2_emission_kg across every trip this year,
        all modes included — the honest total footprint
      - rail_vs_car_saving_kg (float): CO2 avoided by taking rail instead of a generic
        car-share for the same distance, computed over rail trips only. This is a
        secondary "smart regional choice" figure — it is NOT subtracted from
        total_co2_kg, which already reflects what was actually emitted.
      - rail_co2_g_per_km / carshare_co2_g_per_km (float): the factors behind the
        figure above, for the report's methodology section
      - subscriptions (list[dict]): one per active subscription, each
        {product, provider, mode, monthly_cost_eur, billing_cycle, annual_fee_eur,
         is_paid_subscription, has_discount_value, trips_attributed,
         discount_value_eur, net_eur, qualifying_activity}. discount_value_eur/
        net_eur are populated only when has_discount_value is True — False (and
        both fields None) for €0 loyalty tiers (no fee to break even against) and
        for paid flat-fee unlimited-access rail passes like Deutschlandticket or
        BahnCard 100 (no discrete per-trip fare to discount; see
        _rail_coverage_kind). qualifying_activity is None unless the subscription
        carries a usage threshold (e.g. Enterprise Silver's rentals_per_year).
      - data_quality_warnings (list[str])
    """
    history = load_annual_travel_history()
    trips = history["trips"]
    warnings = list(history.get("data_quality_warnings", []))

    total_trips = len(trips)
    trips_missing_cost = sum(1 for t in trips if t["cost_eur"] is None)

    by_mode_acc: dict[str, dict] = {}
    # `trip`, not `t` — see the identical note in _rail_fare_calibration_ratio() in
    # engine/calibration.py; this function doesn't call the t() translator today, but a bare
    # `for t in ...:` here would silently break the first one anyone adds.
    for trip in trips:
        mode = trip["mode"] or "unknown"
        row = by_mode_acc.setdefault(
            mode, {"mode": mode, "trips": 0, "distance_km": 0.0, "spend_eur": 0.0, "co2_kg": 0.0}
        )
        row["trips"] += 1
        row["distance_km"] += trip["distance_km"] or 0.0
        row["spend_eur"] += trip["cost_eur"] or 0.0
        row["co2_kg"] += trip["co2_emission_kg"] or 0.0

    by_mode = sorted(by_mode_acc.values(), key=lambda r: r["co2_kg"], reverse=True)
    for row in by_mode:
        row["distance_km"] = round(row["distance_km"], 1)
        row["spend_eur"] = round(row["spend_eur"], 2)
        row["co2_kg"] = round(row["co2_kg"], 2)

    total_co2_kg = round(sum(r["co2_kg"] for r in by_mode), 2)
    trip_spend_eur = round(sum(r["spend_eur"] for r in by_mode), 2)
    dominant_mode = max(by_mode_acc.values(), key=lambda r: r["trips"])["mode"] if by_mode_acc else ""

    by_mode_with_total = by_mode + [{
        "mode": "Total",
        "trips": total_trips,
        "distance_km": round(sum(r["distance_km"] for r in by_mode), 1),
        "spend_eur": trip_spend_eur,
        "co2_kg": total_co2_kg,
    }]

    rail_g_per_km, carshare_g_per_km = _rail_and_carshare_co2_factors()
    rail_km = sum(t["distance_km"] or 0.0 for t in trips if t["mode"] == "rail")
    rail_vs_car_saving_kg = round(rail_km * (carshare_g_per_km - rail_g_per_km) / 1000, 2)

    subscriptions_raw = load_current_subscriptions()["subscriptions"]
    subscriptions = []
    for sub in subscriptions_raw:
        matched = [
            t for t in trips
            if t["mode"] == sub["mode"] and sub["provider"].lower() in (t["provider"] or "").lower()
        ]

        is_paid = sub["monthly_cost_eur"] > 0
        has_discount_value = is_paid

        if sub["mode"] == "rail":
            coverage_kind = _rail_coverage_kind(sub)
            if coverage_kind == "unlimited_regional":
                # A flat monthly fee for unlimited *regional* travel (e.g.
                # Deutschlandticket) only covers trips priced at 0 in this mock data
                # — there's no separate per-trip charge once you hold the pass. A
                # long-distance trip on the same provider is a different product
                # (e.g. BahnCard) and must not be claimed here too, or a persona
                # holding both ends up with every rail trip double-attributed.
                matched = [t for t in matched if (t["cost_eur"] or 0) == 0]
                has_discount_value = False
            elif coverage_kind == "unlimited_all":
                # e.g. BahnCard 100 — every rail trip is already included, so there's
                # no discrete "amount paid" to treat as a discount either.
                has_discount_value = False
            else:  # "discount" (e.g. BahnCard 25/50) — a % off a fare you still paid
                matched = [t for t in matched if t["cost_eur"] not in (None, 0)]

        trips_attributed = len(matched)
        annual_fee_eur = round(sub["monthly_cost_eur"] * 12, 2)

        discount_value_eur = None
        net_eur = None
        if has_discount_value:
            discount_value_eur = round(
                sum(t["cost_eur"] for t in matched if t["cost_eur"] is not None), 2
            )
            net_eur = round(discount_value_eur - annual_fee_eur, 2)

        qualifying_activity = None
        threshold = sub.get("qualifying_threshold")
        if threshold and threshold.get("rentals_per_year") is not None:
            qualifying_activity = {"count": trips_attributed, "threshold": threshold["rentals_per_year"]}

        subscriptions.append({
            "product": sub["product"],
            "provider": sub["provider"],
            "mode": sub["mode"],
            "monthly_cost_eur": sub["monthly_cost_eur"],
            "billing_cycle": sub["billing_cycle"],
            "annual_fee_eur": annual_fee_eur,
            "is_paid_subscription": is_paid,
            "has_discount_value": has_discount_value,
            "trips_attributed": trips_attributed,
            "discount_value_eur": discount_value_eur,
            "net_eur": net_eur,
            "qualifying_activity": qualifying_activity,
        })

    total_spend_eur = round(trip_spend_eur + sum(s["annual_fee_eur"] for s in subscriptions), 2)

    return {
        "review_year": clock.REVIEW_YEAR,
        "total_spend_eur": total_spend_eur,
        "total_trips": total_trips,
        "trips_missing_cost": trips_missing_cost,
        "dominant_mode": dominant_mode,
        "by_mode": by_mode_with_total,
        "total_co2_kg": total_co2_kg,
        "rail_vs_car_saving_kg": rail_vs_car_saving_kg,
        "rail_co2_g_per_km": rail_g_per_km,
        "carshare_co2_g_per_km": carshare_g_per_km,
        "subscriptions": subscriptions,
        "data_quality_warnings": warnings,
    }


def compute_co2_impact_kg(
    target_subscription: str | None = None,
    new_product: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Compute the CO2 delta (kg/year) of one candidate portfolio change vs. the current portfolio.

    Grounded in real per-trip co2_emission_kg data (already computed offline from
    co2_factors.csv) — never invents or estimates a distance/emissions figure. Call this for
    EVERY candidate action before writing its CO2 impact line; do not compute CO2 yourself.

    Same add/remove/replace argument shape as apply_subscription_change: target_subscription
    is the current subscription being removed (None for a pure add), new_product is the
    catalog product being added (None for a pure cancel). Matched the same way
    apply_subscription_change matches them (case-insensitive substring against
    product/provider, falling back to token overlap) — must resolve to exactly one entry
    each; zero or multiple matches return an error rather than guessing.

    Most candidates are CO2-neutral by design: a subscription only changes emissions if
    removing it takes away the user's *last* remaining way to use a given transport mode at
    all. In the current catalog that is true only for car-sharing (membership-gated); rail
    cards, Deutschlandticket, and car-rental loyalty tiers are discount/rewards programs on
    top of a mode usable without any subscription, so changing/cancelling them is always
    neutral (0 kg) — e.g. downgrading BahnCard 50 to BahnCard 25 never affects CO2, only price.

    Args:
        target_subscription: Substring/name of the current subscription being removed or
            replaced, matched against current_subscriptions.json. None for a pure "add".
        new_product: Substring/name of the catalog product being added, matched against
            mobility_catalog.json. None for a pure "cancel".
        date_from: Optional inclusive ISO date ("YYYY-MM-DD") — same filter semantics as
            compute_travel_stats. Pass this (with date_to) when evaluating the ANNUAL report
            so affected trips are scoped to clock.REVIEW_YEAR only, not the full travel history.
            Leave both None for the regular (non-annual) review, which uses all available trips.
        date_to: Optional inclusive ISO date ("YYYY-MM-DD"); see date_from.

    Returns a dict with: status ("ok" or "error"), mode_access_changed (bool, whether this
    candidate actually removes the user's last access to a gated mode), delta_kg (float,
    signed — positive means the candidate SAVES this many kg CO2/year vs. the current
    portfolio, negative means it emits this many kg MORE; always 0.0 when
    mode_access_changed is False), co2_before_kg / co2_after_kg (float, only meaningful when
    mode_access_changed is True), trips_affected (int), explanation (str, a ready-to-quote
    one-line sentence stating the signed number plainly — quote this verbatim as the CO2
    impact line, do not paraphrase or recompute it), and error (str or None).
    """

    def _result(
        *,
        mode_access_changed: bool = False,
        delta_kg: float = 0.0,
        co2_before_kg: float = 0.0,
        co2_after_kg: float = 0.0,
        trips_affected: int = 0,
        explanation: str,
        error: str | None = None,
    ) -> dict:
        return {
            "status": "error" if error else "ok",
            "mode_access_changed": mode_access_changed,
            "delta_kg": round(delta_kg, 2),
            "co2_before_kg": round(co2_before_kg, 2),
            "co2_after_kg": round(co2_after_kg, 2),
            "trips_affected": trips_affected,
            "explanation": explanation,
            "error": error,
        }

    if not target_subscription and not new_product:
        return _result(
            explanation="",
            error="at least one of target_subscription or new_product is required",
        )

    subs = load_current_subscriptions()["subscriptions"]
    target_match = None
    if target_subscription:
        target_match, error = _resolve_unique_match(target_subscription, subs, ("product", "provider"))
        if error:
            return _result(explanation="", error=error)

    catalog_match = None
    if new_product:
        catalog_options = load_mobility_catalog()["options"]
        catalog_match, error = _resolve_unique_match(new_product, catalog_options, ("product", "provider"))
        if error:
            return _result(explanation="", error=error)

    # Pure add: no historical trips can be attributed to a mode the user is only now gaining
    # (or a second subscription for a mode they already have) — stated honestly rather than guessed.
    if target_match is None:
        return _result(explanation=t("co2Impact.explanation.pureAdd"))

    changed_mode = target_match["mode"]
    if changed_mode not in _MODE_ACCESS_GATED_MODES:
        return _result(explanation=t("co2Impact.explanation.priceOnly", mode=changed_mode))

    still_covered = (catalog_match is not None and catalog_match["mode"] == changed_mode) or any(
        s["mode"] == changed_mode and s is not target_match for s in subs
    )
    if still_covered:
        return _result(explanation=t("co2Impact.explanation.stillCovered", mode=changed_mode))

    trips = load_travel_history()["trips"]
    affected = [
        t
        for t in trips
        if t.get("mode") == changed_mode
        and (date_from is None or t.get("date", "") >= date_from)
        and (date_to is None or t.get("date", "") <= date_to)
    ]
    co2_before_kg = sum(
        t["co2_emission_kg"] for t in affected if t.get("co2_emission_kg") is not None
    )
    generic_factor = _generic_car_co2_factor_kg_per_km()
    co2_after_kg = sum(
        t["distance_km"] * generic_factor for t in affected if t.get("distance_km") is not None
    )
    delta_kg = co2_before_kg - co2_after_kg
    period = t("co2Impact.period.scoped") if (date_from or date_to) else t("co2Impact.period.pastYear")

    if delta_kg >= 0:
        explanation = t(
            "co2Impact.explanation.saved",
            delta=f"{delta_kg:.1f}", mode=changed_mode, tripCount=len(affected), period=period,
            gramsPerKm=f"{generic_factor * 1000:.0f}",
            before=f"{co2_before_kg:.1f}", after=f"{co2_after_kg:.1f}",
        )
    else:
        explanation = t(
            "co2Impact.explanation.moreEmissions",
            delta=f"{abs(delta_kg):.1f}", mode=changed_mode, tripCount=len(affected), period=period,
            gramsPerKm=f"{generic_factor * 1000:.0f}",
            before=f"{co2_before_kg:.1f}", after=f"{co2_after_kg:.1f}",
        )

    return _result(
        mode_access_changed=True,
        delta_kg=delta_kg,
        co2_before_kg=co2_before_kg,
        co2_after_kg=co2_after_kg,
        trips_affected=len(affected),
        explanation=explanation,
    )


