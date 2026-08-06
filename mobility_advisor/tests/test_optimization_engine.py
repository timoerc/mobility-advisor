"""Tests for the deterministic optimization engine added by the pipeline-foundation
merge: fare-class-aware discounting, portfolio scoring, travel-reduction damping on
projected trip frequencies, and the offline geocode fallback used when ORS_API_KEY is
unset (see tools.py's _cached_geocode/_offline_geocode and route_utils.py)."""

import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest

import main
from mobility_advisor import tools

_SCENARIOS = Path(__file__).parent.parent / "scenarios"

# BahnCard 25/50 (2nd class, standard) benefits, mirroring static/mobility_catalog.json:
# both give 25% off Sparpreis, but BC50 gives 50% off Flexpreis vs. BC25's 25% — the
# fare-class distinction only matters on Flexpreis trips.
_BC25 = {"mode": "rail", "benefits": {"discount_sparpreis_pct": 25, "discount_flexpreis_pct": 25}}
_BC50 = {"mode": "rail", "benefits": {"discount_sparpreis_pct": 25, "discount_flexpreis_pct": 50}}


# ── apply_subscription_discount: fare class ──────────────────────────────────────


def test_sparpreis_trip_bc25_and_bc50_discount_equally():
    price = 100.0
    bc25_price = tools.apply_subscription_discount("rail_intercity", price, 400, [_BC25], fare_class="spar")
    bc50_price = tools.apply_subscription_discount("rail_intercity", price, 400, [_BC50], fare_class="spar")
    assert bc25_price == bc50_price == 75.0


def test_flexpreis_trip_bc50_discounts_more_than_bc25():
    price = 100.0
    bc25_price = tools.apply_subscription_discount("rail_intercity", price, 400, [_BC25], fare_class="flex")
    bc50_price = tools.apply_subscription_discount("rail_intercity", price, 400, [_BC50], fare_class="flex")
    assert bc25_price == 75.0
    assert bc50_price == 50.0
    assert bc50_price < bc25_price


def test_fare_class_defaults_to_spar_when_unspecified():
    price = 100.0
    default_price = tools.apply_subscription_discount("rail_intercity", price, 400, [_BC50])
    spar_price = tools.apply_subscription_discount("rail_intercity", price, 400, [_BC50], fare_class="spar")
    assert default_price == spar_price


# ── apply_subscription_discount: car-share has no card-free walk-up rate ───────────


def test_car_share_no_subscription_uses_miles_basis_walkup_floor():
    # Regression guard: estimated_price_eur (the bare per-km synthetic curve from
    # estimate_trip_price, which price_factors.json's own note says excludes per-trip
    # fees) must NOT be the starting price for car_share — holding zero subscriptions
    # still costs at least a MILES Basis-equivalent walk-up fare (base rate + unlock +
    # protection), since there is no way to book a MILES ride without at least that. The
    # old behaviour (bare per-km rate, no fees) priced "no subscription" cheaper than any
    # real paid tier's walk-up cost, making every paid tier's discount structurally unable
    # to ever win.
    bare_synthetic_price = 5.0  # deliberately far below any real walk-up fare
    price = tools.apply_subscription_discount("car_share", bare_synthetic_price, 10.0, [])
    expected_floor = round(
        tools._MILES_BASIS_BASE_KM_RATE_EUR * 10.0
        + tools._MILES_BASIS_UNLOCK_FEE_EUR
        + tools._MILES_BASIS_PROTECTION_FEE_EUR,
        2,
    )
    assert price == expected_floor
    assert price > bare_synthetic_price


def test_car_share_paid_tier_still_undercuts_the_walkup_floor():
    # A paid tier with a real per-km discount or credit must still be able to win against
    # the walk-up floor — the floor raises the baseline "no subscription" price, it must
    # not also raise the price when a genuinely cheaper tier is held.
    miles_gold = {
        "mode": "car_share",
        "benefits": {
            "base_km_rate_eur": 0.79, "discount_km_pct": 15,
            "unlock_fee_eur_per_trip": 1.0, "protection_plus_eur_per_trip": 0.0,
        },
    }
    price = tools.apply_subscription_discount("car_share", 5.0, 10.0, [miles_gold])
    assert price == pytest.approx(0.79 * 0.85 * 10 + 1.0, abs=0.01)
    walkup_floor = round(
        tools._MILES_BASIS_BASE_KM_RATE_EUR * 10.0
        + tools._MILES_BASIS_UNLOCK_FEE_EUR
        + tools._MILES_BASIS_PROTECTION_FEE_EUR,
        2,
    )
    assert price < walkup_floor


def test_non_car_share_mode_still_uses_estimated_price_eur_as_floor():
    # The walk-up floor is car_share-specific — a rail/flight/bus alternative with no
    # matching subscription in the portfolio must still start from its own
    # estimated_price_eur, unaffected by this change.
    price = tools.apply_subscription_discount("rail_intercity", 42.5, 400, [])
    assert price == 42.5


# ── _dominant_fare_class ──────────────────────────────────────────────────────────


def test_dominant_fare_class_majority_flex():
    ticket_types = ["Flexpreis, 2. Klasse"] * 6 + ["Sparpreis, 2. Klasse"] * 4
    assert tools._dominant_fare_class(ticket_types) == "flex"


def test_dominant_fare_class_majority_spar():
    ticket_types = ["Sparpreis, 2. Klasse"] * 6 + ["Flexpreis, 2. Klasse"] * 4
    assert tools._dominant_fare_class(ticket_types) == "spar"


def test_dominant_fare_class_tie_defaults_to_spar():
    # A tie (or a route with no ticket_type data at all) must not accidentally grant the
    # deeper Flexpreis discount — spar is the conservative default.
    ticket_types = ["Flexpreis, 2. Klasse", "Sparpreis, 2. Klasse"]
    assert tools._dominant_fare_class(ticket_types) == "spar"
    assert tools._dominant_fare_class([None, None]) == "spar"


# ── compute_portfolio_score ────────────────────────────────────────────────────────


def _sim(cost, time_min, co2, ids=None):
    return {
        "status": "ok",
        "subscription_ids": ids or [],
        "total_annual_cost_eur": cost,
        "total_annual_time_min": time_min,
        "total_annual_co2_kg": co2,
    }


def test_compute_portfolio_score_lower_cost_wins_under_cost_weight():
    results = [_sim(1000, 500, 100, ["a"]), _sim(1200, 500, 100, ["b"])]
    scored = tools.compute_portfolio_score(
        results, {"cost_weight": 1.0, "time_weight": 0.0, "sustainability_weight": 0.0}
    )
    assert scored["status"] == "ok"
    assert scored["best"]["subscription_ids"] == ["a"]


def test_compute_portfolio_score_display_normalization_skips_small_spread():
    # norm_cost/norm_time/norm_co2 are DISPLAY-only fields (see compute_portfolio_score's
    # docstring) — they play no role in ranking. _normalize_for_display's 2% dead-band
    # should still collapse a trivial (<2%) spread to 0 for both candidates here, rather
    # than stretching a fraction-of-a-percent difference to a full 0..1 range.
    results = [
        _sim(1000, 500, 100, ["a"]),  # cost differs from b by 1% — below the 2% dead-band
        _sim(1010, 300, 100, ["b"]),
    ]
    scored = tools.compute_portfolio_score(
        results, {"cost_weight": 0.5, "time_weight": 0.5, "sustainability_weight": 0.0}
    )
    ranked = {r["subscription_ids"][0]: r for r in scored["ranked_portfolios"]}
    assert ranked["a"]["norm_cost"] == 0.0
    assert ranked["b"]["norm_cost"] == 0.0


def test_compute_portfolio_score_ranks_by_monetized_generalized_cost():
    # b costs 10 EUR/yr more than a but saves exactly 1 hour/yr; at these weights
    # (cost_weight == time_weight) value_of_time is exactly 12 EUR/hour (see
    # _generalized_cost_rates), so b's generalized cost is 1010 + 8 = 1018 against a's
    # 1000 + 20 = 1020 — an exact, precomputable EUR figure, not a set-relative 0..1 score.
    # This is the replacement for the old min-max-normalized ranking (see git history) —
    # the point of this test is that the score is a real monetized number, checkable
    # independent of whatever else happens to be in the candidate set.
    results = [_sim(1000, 100, 0, ["a"]), _sim(1010, 40, 0, ["b"])]
    scored = tools.compute_portfolio_score(
        results, {"cost_weight": 0.5, "time_weight": 0.5, "sustainability_weight": 0.0}
    )
    ranked = {r["subscription_ids"][0]: r for r in scored["ranked_portfolios"]}
    assert ranked["a"]["score"] == pytest.approx(1020.0)
    assert ranked["b"]["score"] == pytest.approx(1018.0)
    assert scored["best"]["subscription_ids"] == ["b"]


def test_compute_portfolio_score_independent_of_irrelevant_alternatives():
    # Regression guard for the set-relative min-max normalization this replaced: under the
    # old algorithm, scoring these same two real candidates (numbers drawn from an actual
    # katrin optimizer run: "BahnCard 50" vs "No subscriptions") alongside an irrelevant,
    # wildly expensive third candidate ("MILES Black", ~3x priciest option, same time/CO2
    # as the baseline) flipped a tie between the two real candidates into "No subscriptions"
    # winning outright — an unrelated candidate that could never itself win changed which
    # of the other two was better. Monetized generalized cost has no such set-relative
    # renormalization: each candidate's score depends only on its own totals and the fixed
    # value_of_time/co2_price rates, so adding or removing an irrelevant candidate must
    # leave both the winner AND the exact score of every other candidate unchanged.
    weights = {"cost_weight": 0.3, "time_weight": 0.5, "sustainability_weight": 0.2}
    low_co2 = _sim(1006, 1308.0, 188.3, ["bc50"])
    baseline = _sim(1098, 1259.4, 229.3, ["none"])
    decoy = _sim(3287, 1259.4, 229.3, ["miles_black"])

    without_decoy = tools.compute_portfolio_score([low_co2, baseline], weights)
    with_decoy = tools.compute_portfolio_score([low_co2, baseline, decoy], weights)

    assert without_decoy["best"]["subscription_ids"] == ["bc50"]
    assert with_decoy["best"]["subscription_ids"] == ["bc50"]

    scores_without = {r["subscription_ids"][0]: r["score"] for r in without_decoy["ranked_portfolios"]}
    scores_with = {r["subscription_ids"][0]: r["score"] for r in with_decoy["ranked_portfolios"]}
    assert scores_without["bc50"] == scores_with["bc50"]
    assert scores_without["none"] == scores_with["none"]


def test_compute_portfolio_score_no_valid_results_is_error():
    result = tools.compute_portfolio_score([{"status": "error"}], {})
    assert result["status"] == "error"


# ── _generalized_cost_rates ────────────────────────────────────────────────────────


def test_generalized_cost_rates_scales_with_weights():
    vot_time_heavy, co2_time_heavy = tools._generalized_cost_rates(
        {"cost_weight": 0.3, "time_weight": 0.5, "sustainability_weight": 0.2}
    )
    vot_cost_heavy, co2_cost_heavy = tools._generalized_cost_rates(
        {"cost_weight": 0.8, "time_weight": 0.1, "sustainability_weight": 0.1}
    )
    assert vot_time_heavy > vot_cost_heavy
    assert co2_time_heavy > co2_cost_heavy


def test_generalized_cost_rates_floors_zero_cost_weight():
    # A near-zero cost weight must not blow the rates up to absurd values.
    zero = tools._generalized_cost_rates(
        {"cost_weight": 0.0, "time_weight": 0.5, "sustainability_weight": 0.5}
    )
    floored = tools._generalized_cost_rates(
        {"cost_weight": 0.05, "time_weight": 0.5, "sustainability_weight": 0.5}
    )
    assert zero == floored


def test_generalized_cost_rates_none_weights_is_pure_cost():
    assert tools._generalized_cost_rates(None) == (0.0, 0.0)


# ── _mode_shares ────────────────────────────────────────────────────────────────────

_RAIL_REGIONAL_ALT = {
    "mode": "rail_regional", "distance_km": 30, "duration_min": 45,
    "co2_kg": 1.5, "estimated_price_eur": 12.0,
}
_CAR_ALT = {
    "mode": "car_share", "distance_km": 30, "duration_min": 35,
    "co2_kg": 4.5, "estimated_price_eur": 9.0,
}
_DTICKET = {"mode": "rail", "benefits": {"unlimited_regional": True, "unlimited_long_distance": False}}
_DEFAULT_WEIGHTS = {"cost_weight": 0.34, "time_weight": 0.33, "sustainability_weight": 0.33}


def test_mode_shares_sums_to_one():
    shares = tools._mode_shares([_RAIL_REGIONAL_ALT, _CAR_ALT], [], "spar", 100, _DEFAULT_WEIGHTS)
    assert sum(share for _, _, share in shares) == pytest.approx(1.0)


def test_mode_shares_single_alternative_gets_full_share():
    shares = tools._mode_shares([_RAIL_REGIONAL_ALT], [], "spar", 100, _DEFAULT_WEIGHTS)
    assert shares == [(_RAIL_REGIONAL_ALT, _RAIL_REGIONAL_ALT["estimated_price_eur"], 1.0)]


def test_mode_shares_rail_discount_raises_rail_share_on_rail_eligible_trip():
    no_sub = {
        alt["mode"]: share
        for alt, _, share in tools._mode_shares(
            [_RAIL_REGIONAL_ALT, _CAR_ALT], [], "spar", 100, _DEFAULT_WEIGHTS
        )
    }
    with_dticket = {
        alt["mode"]: share
        for alt, _, share in tools._mode_shares(
            [_RAIL_REGIONAL_ALT, _CAR_ALT], [_DTICKET], "spar", 100, _DEFAULT_WEIGHTS
        )
    }
    assert with_dticket["rail_regional"] > no_sub["rail_regional"]


# ── simulate_portfolio: mode choice must respond to the portfolio ──────────────────


def test_simulate_portfolio_time_and_co2_differ_across_portfolios(isolated_main_data_dir):
    # Regression guard for the bug this change fixes: before generalized cost + mode
    # shares, every portfolio produced byte-identical total_annual_time_min/
    # total_annual_co2_kg because mode selection ignored subscription-driven price
    # changes entirely.
    trip = {
        "route": "Home → Office", "origin": "Home", "destination": "Office",
        "frequency_per_year": 200, "source": "history", "distance_km": 30,
        "alternatives": [_RAIL_REGIONAL_ALT, _CAR_ALT], "fare_class": "spar",
    }
    _write_projected_trip_set(isolated_main_data_dir / "_projected_trips_merged.json", [trip])

    empty = tools.simulate_portfolio([], weights=_DEFAULT_WEIGHTS)
    with_dticket = tools.simulate_portfolio(["db_deutschlandticket"], weights=_DEFAULT_WEIGHTS)

    assert empty["status"] == "ok"
    assert with_dticket["status"] == "ok"
    assert empty["total_annual_time_min"] != with_dticket["total_annual_time_min"]
    assert empty["total_annual_co2_kg"] != with_dticket["total_annual_co2_kg"]


# ── _travel_reduction_factor: damping from a travel_reduction life event ─────────────


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    for f in (_SCENARIOS / "maja").glob("*.json"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setattr(tools, "_DATA", tmp_path)
    return tmp_path


def _write_life_events(data_dir, events):
    (data_dir / "life_events.json").write_text(json.dumps({"events": events}), encoding="utf-8")


def test_no_travel_reduction_signal_is_a_no_op(isolated_data_dir):
    _write_life_events(isolated_data_dir, [])
    factor, warnings = tools._travel_reduction_factor()
    assert factor == 1.0
    assert warnings == []


def test_travel_reduction_signal_prorates_by_remaining_days(isolated_data_dir):
    event_date = tools.MOCK_TODAY + timedelta(days=78)
    _write_life_events(isolated_data_dir, [{
        "category": "other",
        "summary": "Project ends, travel drops",
        "event_date": event_date.isoformat(),
        "signals": ["travel_reduction"],
        "source_mail_id": None,
        "detected_on": tools.MOCK_TODAY.isoformat(),
    }])
    factor, warnings = tools._travel_reduction_factor()
    assert factor == pytest.approx(78 / 365, abs=0.01)
    assert len(warnings) == 1
    assert event_date.isoformat() in warnings[0]


def test_travel_reduction_signal_outside_12_months_is_ignored(isolated_data_dir):
    event_date = tools.MOCK_TODAY + timedelta(days=400)
    _write_life_events(isolated_data_dir, [{
        "category": "other",
        "summary": "Far-future change",
        "event_date": event_date.isoformat(),
        "signals": ["travel_reduction"],
        "source_mail_id": None,
        "detected_on": tools.MOCK_TODAY.isoformat(),
    }])
    factor, warnings = tools._travel_reduction_factor()
    assert factor == 1.0
    assert warnings == []


def test_non_travel_reduction_signal_does_not_damp(isolated_data_dir):
    # e.g. a pure rail_card_relevance_change signal (no travel_reduction) must not damp —
    # that would double up with, or wrongly substitute for, the hold-pending-decision gate.
    _write_life_events(isolated_data_dir, [{
        "category": "subscription_change",
        "summary": "BC50 not renewed",
        "event_date": (tools.MOCK_TODAY + timedelta(days=30)).isoformat(),
        "signals": ["rail_card_relevance_change"],
        "source_mail_id": None,
        "detected_on": tools.MOCK_TODAY.isoformat(),
    }])
    factor, warnings = tools._travel_reduction_factor()
    assert factor == 1.0
    assert warnings == []


# ── Offline geocode fallback ───────────────────────────────────────────────────────


def test_offline_geocode_known_city_returns_lng_lat(monkeypatch):
    monkeypatch.setattr(tools, "_city_coords_cache", None)
    lng, lat = tools._offline_geocode("Berlin")
    # Berlin is roughly (13.4 lng, 52.5 lat) — assert order (lng first) matches
    # route_utils.geocode()'s convention, not (lat, lng).
    assert 13 < lng < 14
    assert 52 < lat < 53


def test_offline_geocode_normalizes_raw_station_strings(monkeypatch):
    monkeypatch.setattr(tools, "_city_coords_cache", None)
    result = tools._offline_geocode("Frankfurt (Main) Hbf")
    assert result is not None
    lng, lat = result
    assert 8 < lng < 9
    assert 50 < lat < 51


def test_offline_geocode_unknown_place_returns_none(monkeypatch):
    monkeypatch.setattr(tools, "_city_coords_cache", None)
    assert tools._offline_geocode("Nonexistent Fantasy City") is None


def test_cached_geocode_uses_offline_fallback_when_ors_key_absent(monkeypatch):
    monkeypatch.setattr(tools, "ORS_API_KEY", "")
    monkeypatch.setattr(tools, "_geocode_cache", {})
    monkeypatch.setattr(tools, "_city_coords_cache", None)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("geocode() must not be called when ORS_API_KEY is unset")

    monkeypatch.setattr(tools, "geocode", _fail_if_called)
    result = tools._cached_geocode("Hamburg")
    assert result is not None


# ── merge_projected_trip_sets: fare_class must survive a source dedup ─────────────


@pytest.fixture
def isolated_main_data_dir(tmp_path, monkeypatch):
    for f in (_SCENARIOS / "maja").glob("*.json"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setattr(tools, "_DATA", tmp_path)
    return tmp_path


def _write_projected_trip_set(path, trips):
    path.write_text(json.dumps({
        "trips": trips, "generated_at": "2026-06-15T00:00:00", "warnings": [],
    }), encoding="utf-8")


def test_merge_preserves_flex_fare_class_when_calendar_overrides_history(isolated_main_data_dir):
    # A route detected as Flexpreis from history must not silently revert to the "spar"
    # default just because the same route also appears on the calendar — calendar-derived
    # trips carry no fare-class signal of their own (see derive_projected_trips_from_
    # calendar), so the merge must carry the history trip's "flex" finding forward across
    # the calendar-wins-on-priority dedup, not discard it.
    history_trip = {
        "route": "Berlin → Düsseldorf", "origin": "Berlin", "destination": "Düsseldorf",
        "frequency_per_year": 10, "source": "history", "distance_km": 500,
        "alternatives": [], "fare_class": "flex",
    }
    calendar_trip = {
        "route": "Düsseldorf → Berlin", "origin": "Düsseldorf", "destination": "Berlin",
        "frequency_per_year": 12, "source": "calendar", "distance_km": 500,
        "alternatives": [], "fare_class": "spar",
    }
    _write_projected_trip_set(isolated_main_data_dir / "_projected_trips_history.json", [history_trip])
    _write_projected_trip_set(isolated_main_data_dir / "_projected_trips_calendar.json", [calendar_trip])

    result = tools.merge_projected_trip_sets()
    assert result["status"] == "ok"

    merged = json.loads((isolated_main_data_dir / "_projected_trips_merged.json").read_text(encoding="utf-8"))
    assert len(merged["trips"]) == 1
    trip = merged["trips"][0]
    assert trip["source"] == "calendar"  # calendar still wins on priority/frequency
    assert trip["fare_class"] == "flex"  # but the flex signal is carried over, not lost


# ── _clear_optimization_scratch_files: no stale cross-run/cross-persona results ────


def test_clear_optimization_scratch_files_removes_everything(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_DATA", tmp_path)
    for fname in main._OPTIMIZATION_SCRATCH_FILES:
        (tmp_path / fname).write_text("{}", encoding="utf-8")

    main._clear_optimization_scratch_files()

    for fname in main._OPTIMIZATION_SCRATCH_FILES:
        assert not (tmp_path / fname).exists()


def test_clear_optimization_scratch_files_is_a_noop_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_DATA", tmp_path)
    main._clear_optimization_scratch_files()  # must not raise when nothing exists yet


# ── simulate_portfolio: car-share credit is a portfolio-level budget, not per-trip ─────


def test_car_share_credit_never_exceeds_annual_budget_under_heavy_usage(isolated_main_data_dir):
    # Regression guard for the bug this replaces (see apply_subscription_discount's
    # docstring): a monthly credit used to be re-granted in full to every trip on a route
    # occurring under 12x/year, so N low-frequency routes could collectively disburse many
    # times the actual annual credit budget. 8 distinct routes at 6x/year each (48 trips
    # total, ~14.43 EUR gross/trip after MILES Gold's 15% km discount = ~693 EUR/yr
    # realized spend) must never draw down more than the real annual budget
    # (monthly_credit_eur * 12 = 50 * 12 = 600 EUR), even though realized spend here
    # exceeds it — the old per-trip re-granting had no such ceiling at all.
    car_share_alt = {
        "mode": "car_share", "distance_km": 20, "duration_min": 25,
        "co2_kg": 3.0, "estimated_price_eur": 15.8,
    }
    trips = [
        {
            "route": f"Route {i}", "origin": f"O{i}", "destination": f"D{i}",
            "frequency_per_year": 6, "source": "history", "distance_km": 20,
            "alternatives": [car_share_alt], "fare_class": "spar",
        }
        for i in range(8)
    ]
    _write_projected_trip_set(isolated_main_data_dir / "_projected_trips_merged.json", trips)

    sim = tools.simulate_portfolio(["miles_gold"], weights=None)
    assert sim["status"] == "ok"
    assert sim["car_share_credit_applied_eur"] == pytest.approx(50.0 * 12)


def test_car_share_credit_capped_at_realized_spend_under_light_usage(isolated_main_data_dir):
    # The other half of the same guard: with realized spend genuinely BELOW the credit
    # budget, the credit applied must equal realized spend exactly, not the full budget —
    # a persona who barely uses car-sharing shouldn't have simulate_portfolio() invent
    # savings beyond what they actually spent.
    car_share_alt = {
        "mode": "car_share", "distance_km": 20, "duration_min": 25,
        "co2_kg": 3.0, "estimated_price_eur": 15.8,
    }
    trip = {
        "route": "Route 0", "origin": "O0", "destination": "D0",
        "frequency_per_year": 2, "source": "history", "distance_km": 20,
        "alternatives": [car_share_alt], "fare_class": "spar",
    }
    _write_projected_trip_set(isolated_main_data_dir / "_projected_trips_merged.json", [trip])

    sim = tools.simulate_portfolio(["miles_gold"], weights=None)
    assert sim["status"] == "ok"
    # 2 trips/yr * (0.79 * 0.85 * 20km + 1.0 unlock) ~= 28.86 EUR/yr realized spend,
    # nowhere near the 600 EUR/yr budget.
    gross_per_trip = 0.79 * 0.85 * 20 + 1.0
    assert sim["car_share_credit_applied_eur"] == pytest.approx(gross_per_trip * 2, abs=0.05)
    assert sim["car_share_credit_applied_eur"] < 50.0 * 12


# ── derive_projected_trips_from_history: local/commute demand aggregation (C3) ─────────


def test_local_aggregate_trip_created_for_subthreshold_regional_routes():
    # katrin-shaped regression: 3 short regional routes each seen only once in the data
    # window (annual_freq == 1, below the 2/yr recurrence bar) must not be silently
    # dropped — collectively they ARE the kind of demand a Deutschlandticket prices
    # against, even though no single one of them recurs often enough to qualify alone.
    local_routes = [
        {"distance_km": 40.0, "freq": 1, "ticket_types": ["Deutschland-Ticket"]},
        {"distance_km": 37.0, "freq": 1, "ticket_types": ["Deutschland-Ticket"]},
        {"distance_km": 26.0, "freq": 1, "ticket_types": ["Deutschland-Ticket"]},
    ]
    trip, warning = tools._build_local_aggregate_trip(local_routes, reduction_factor=1.0)
    assert trip is not None
    assert trip["frequency_per_year"] == 3
    assert trip["origin"] == "various"
    modes = {a["mode"] for a in trip["alternatives"]}
    assert "rail_regional" in modes
    assert "aggregated" in warning.lower()


def test_local_aggregate_trip_none_when_damped_to_zero():
    local_routes = [{"distance_km": 40.0, "freq": 1, "ticket_types": [None]}]
    trip, warning = tools._build_local_aggregate_trip(local_routes, reduction_factor=0.0)
    assert trip is None
    assert warning == ""


def test_commute_aggregate_trip_from_office_days(isolated_data_dir):
    persona_path = isolated_data_dir / "persona.json"
    persona = json.loads(persona_path.read_text(encoding="utf-8"))
    persona["profileData"]["commute"] = {"office_days": ["mon", "tue", "wed", "thu"], "wfh_days": ["fri"]}
    persona_path.write_text(json.dumps(persona), encoding="utf-8")

    trip, warning = tools._build_commute_aggregate_trip(reduction_factor=1.0)
    assert trip is not None
    assert trip["frequency_per_year"] == 4 * tools._WORKING_WEEKS_PER_YEAR * 2
    assert trip["origin"] == "various"
    assert "rail_regional" in {a["mode"] for a in trip["alternatives"]}
    assert "office day" in warning.lower()


def test_commute_aggregate_trip_none_when_fully_remote(isolated_data_dir):
    persona_path = isolated_data_dir / "persona.json"
    persona = json.loads(persona_path.read_text(encoding="utf-8"))
    persona["profileData"]["commute"] = {"office_days": [], "wfh_days": ["mon", "tue", "wed", "thu", "fri"]}
    persona_path.write_text(json.dumps(persona), encoding="utf-8")

    trip, warning = tools._build_commute_aggregate_trip(1.0)
    assert trip is None
    assert warning == ""


# ── _build_intra_city_aggregate_trip: same-city trips (Sofia-shaped regression) ────────


def test_intra_city_aggregate_trip_created_from_car_share_trips(isolated_data_dir):
    # Sofia-shaped regression: derive_projected_trips_from_history() used to drop every
    # same-city trip outright (origin/destination normalize to the same city, so
    # _route_key groups them with nothing), leaving a car-share-heavy persona with zero
    # projected car-share demand — no MILES tier's credit/discount had anything to be
    # priced against.
    car_trips = [
        {"distance_km": 5.4, "ticket_type": "Pay-per-use", "mode": "car_share"}
        for _ in range(14)
    ]
    trip, warning = tools._build_intra_city_aggregate_trip(car_trips, data_window_months=11)
    assert trip is not None
    assert trip["origin"] == "various"
    assert trip["category"] == "intra_city_aggregate"
    modes = {a["mode"] for a in trip["alternatives"]}
    assert modes == {"car_share"}
    # No rail_regional alternative — see the function's docstring on why offering one
    # would let the simulator "solve" this demand back onto free regional transit.
    assert "rail_regional" not in modes
    assert "14 same-city car-share" in warning


def test_intra_city_aggregate_trip_excludes_non_car_modes(isolated_data_dir):
    # Same-city trips recorded as plain "rail" (ordinary Deutschlandticket-covered local
    # transit) or a malformed mode (empty string / unrecognized value — the same kind
    # load_travel_history already flags via data_quality_warnings) must not be folded in:
    # they carry no car-share-subscription signal, and a malformed mode should not silently
    # count as demand for anything.
    mixed_trips = [
        {"distance_km": 5.0, "ticket_type": None, "mode": "car_share"},
        {"distance_km": 3.0, "ticket_type": "Deutschland-Ticket", "mode": "rail"},
        {"distance_km": 4.0, "ticket_type": None, "mode": ""},
        {"distance_km": 6.0, "ticket_type": None, "mode": "hovercraft"},
    ]
    trip, warning = tools._build_intra_city_aggregate_trip(mixed_trips, data_window_months=12)
    assert trip is not None
    assert "1 same-city car-share" in warning  # only the single car_share trip counted


def test_intra_city_aggregate_trip_none_when_no_car_trips(isolated_data_dir):
    non_car_trips = [
        {"distance_km": 3.0, "ticket_type": "Deutschland-Ticket", "mode": "rail"},
        {"distance_km": 4.0, "ticket_type": None, "mode": ""},
    ]
    trip, warning = tools._build_intra_city_aggregate_trip(non_car_trips, data_window_months=12)
    assert trip is None
    assert warning == ""


def test_derive_projected_trips_from_history_folds_same_city_trips_into_intra_city_aggregate(
    isolated_data_dir, monkeypatch
):
    monkeypatch.setattr(tools, "ORS_API_KEY", "")
    monkeypatch.setattr(tools, "driving_route", lambda *a, **kw: None)
    history = {"trips": [
        {
            "date": f"2025-0{i}-01", "mode": "car_share", "origin": "Köln", "destination": "Köln",
            "cost_eur": 12.0, "distance_km": 5.0, "provider": "MILES Mobility",
            "ticket_type": "Pay-per-use",
        }
        for i in range(1, 4)
    ]}
    (isolated_data_dir / "travel_history_raw.json").write_text(json.dumps(history), encoding="utf-8")
    (isolated_data_dir / "life_events.json").write_text(json.dumps({"events": []}), encoding="utf-8")

    result = tools.derive_projected_trips_from_history()
    assert result["status"] == "ok"
    assert any("Intra-city" in r["route"] for r in result["routes"])

    written = json.loads((isolated_data_dir / "_projected_trips_history.json").read_text(encoding="utf-8"))
    intra_trip = next(t for t in written["trips"] if t.get("category") == "intra_city_aggregate")
    assert {a["mode"] for a in intra_trip["alternatives"]} == {"car_share"}


# ── derive_projected_trips_from_history: travel-reduction damping is scoped (A3/A4) ────


def test_damping_applies_to_long_distance_but_not_regional_routes(isolated_data_dir, monkeypatch):
    # A travel_reduction signal describes inter-city travel dropping off (a project
    # ending, a client engagement winding down) — it says nothing about whether the
    # persona still takes short regional trips, so only routes beyond
    # _RAIL_DISTANCE_THRESHOLD_KM (100km) may be damped.
    monkeypatch.setattr(tools, "ORS_API_KEY", "")
    monkeypatch.setattr(tools, "driving_route", lambda *a, **kw: None)
    long_distance_trips = [
        {
            "date": f"2025-0{i}-05", "mode": "rail", "origin": "Köln", "destination": "München",
            "cost_eur": 80.0, "distance_km": 570, "provider": "Deutsche Bahn",
            "ticket_type": "Sparpreis, 2. Klasse",
        }
        for i in range(1, 7)  # 6 occurrences
    ]
    regional_trips = [
        {
            "date": f"2025-0{i}-15", "mode": "rail", "origin": "Köln", "destination": "Bonn",
            "cost_eur": 8.0, "distance_km": 30, "provider": "Deutsche Bahn",
            "ticket_type": "Sparpreis, 2. Klasse",
        }
        for i in range(1, 7)  # 6 occurrences, same window
    ]
    history = {"trips": long_distance_trips + regional_trips}
    (isolated_data_dir / "travel_history_raw.json").write_text(json.dumps(history), encoding="utf-8")
    event_date = tools.MOCK_TODAY + timedelta(days=30)
    _write_life_events(isolated_data_dir, [{
        "category": "other", "summary": "Project ends, travel drops",
        "event_date": event_date.isoformat(), "signals": ["travel_reduction"],
        "source_mail_id": None, "detected_on": tools.MOCK_TODAY.isoformat(),
    }])

    result = tools.derive_projected_trips_from_history()
    written = json.loads((isolated_data_dir / "_projected_trips_history.json").read_text(encoding="utf-8"))
    # _route_key sorts alphabetically, so the Köln↔Bonn route may be written as
    # "Bonn → Köln" rather than "Köln → Bonn" — match on route name instead of a fixed
    # origin/destination order.
    long_trip = next(t for t in written["trips"] if "München" in t["route"])
    regional_trip = next(t for t in written["trips"] if "Bonn" in t["route"])

    # Undamped frequency for both would be the same (6 occurrences over the same window);
    # the long-distance route must come out damped, the regional route must not.
    assert long_trip["frequency_per_year"] < regional_trip["frequency_per_year"]


def test_damped_to_zero_long_distance_route_is_dropped(isolated_data_dir, monkeypatch):
    # A route whose damped frequency rounds to 0 must not linger in the projected set —
    # it would otherwise carry a 0/yr "route" through merge_projected_trip_sets and
    # simulate_portfolio for no reason.
    monkeypatch.setattr(tools, "ORS_API_KEY", "")
    monkeypatch.setattr(tools, "driving_route", lambda *a, **kw: None)
    history = {"trips": [
        {
            "date": f"2025-0{i}-05", "mode": "rail", "origin": "Köln", "destination": "München",
            "cost_eur": 80.0, "distance_km": 570, "provider": "Deutsche Bahn",
            "ticket_type": "Sparpreis, 2. Klasse",
        }
        for i in range(1, 3)  # 2 occurrences — annual_freq is already low pre-damping
    ]}
    (isolated_data_dir / "travel_history_raw.json").write_text(json.dumps(history), encoding="utf-8")
    # An event 5 days out damps almost everything (factor ~= 5/365).
    event_date = tools.MOCK_TODAY + timedelta(days=5)
    _write_life_events(isolated_data_dir, [{
        "category": "other", "summary": "Project ends abruptly",
        "event_date": event_date.isoformat(), "signals": ["travel_reduction"],
        "source_mail_id": None, "detected_on": tools.MOCK_TODAY.isoformat(),
    }])

    result = tools.derive_projected_trips_from_history()
    assert not any(r["route"].endswith("→ München") for r in result["routes"])
    written = json.loads((isolated_data_dir / "_projected_trips_history.json").read_text(encoding="utf-8"))
    assert not any(t["destination"] == "München" for t in written["trips"])


# ── _rail_fare_calibration_ratio: flat-rate-covered trips must not contaminate it (H2) ──


def test_rail_fare_calibration_excludes_flat_rate_and_zero_cost_trips(isolated_data_dir):
    # A persona whose history mixes real DB Sparpreis fares with Deutschlandticket-covered
    # regional legs (cost_eur == 0 by construction) must not have those 0-EUR legs drag the
    # calibration ratio down — they say nothing about what a Sparpreis/Flexpreis BahnCard
    # fare actually costs, unlike a real (if discounted) paid fare.
    history = {"trips": [
        {
            "date": "2025-01-10", "mode": "rail", "origin": "Köln Hbf", "destination": "Hamburg Hbf",
            "cost_eur": 100.0, "distance_km": 424, "provider": "Deutsche Bahn",
            "ticket_type": "Sparpreis, 2. Klasse",
        },
        {
            "date": "2025-01-12", "mode": "rail", "origin": "Hamburg Hbf", "destination": "Köln Hbf",
            "cost_eur": 95.0, "distance_km": 424, "provider": "Deutsche Bahn",
            "ticket_type": "Sparpreis, 2. Klasse",
        },
        {
            "date": "2025-02-01", "mode": "rail", "origin": "Köln Hbf", "destination": "Bonn Hbf",
            "cost_eur": 0.0, "distance_km": 25, "provider": "Deutsche Bahn",
            "ticket_type": "Deutschland-Ticket",
        },
    ]}
    (isolated_data_dir / "travel_history_raw.json").write_text(json.dumps(history), encoding="utf-8")
    (isolated_data_dir / "current_subscriptions.json").write_text(
        json.dumps({"subscriptions": []}), encoding="utf-8"
    )

    ratio, max_dist, warnings = tools._rail_fare_calibration_ratio()

    expected_synthetic = 2 * tools.estimate_trip_price("rail_intercity", 424)
    expected_ratio = (100.0 + 95.0) / expected_synthetic
    assert ratio == pytest.approx(expected_ratio, rel=1e-3)
    # max_distance_km is derived from the farthest CALIBRATED trip (424km) — the excluded
    # 25km Deutschlandticket leg must not influence it.
    assert max_dist == pytest.approx(max(424 * 2.0, 600.0))


# ── optimize_all_categories: end-to-end coherence across every persona ─────────────────

_ALL_PERSONAS = ["katrin", "lena", "maja", "sofia", "stefan", "tobias"]


@pytest.mark.parametrize("persona", _ALL_PERSONAS)
def test_optimize_all_categories_produces_a_coherent_ranking(persona, tmp_path, monkeypatch):
    # End-to-end regression guard, one per persona: the full deterministic pipeline must
    # produce a valid, internally consistent ranking — not just "runs without crashing".
    # This is what would have caught the pre-fix "cancel everything, always" failure mode
    # across every persona at once, and stays a golden-style check against future
    # objective-function regressions — the recommended candidate's generalized cost
    # (score) must be <= every other simulated candidate's, by definition of "recommended".
    for f in (_SCENARIOS / persona).glob("*.json"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setattr(tools, "_DATA", tmp_path)
    # Force the offline geocode fallback — fast and deterministic, no network dependency.
    # driving_route() (used for car_share/car_rental/car_private alternatives) isn't
    # covered by the offline geocode wrapper at all — it always hits the real ORS API — so
    # it's stubbed out directly to fall back to the heuristic distance estimate instantly.
    monkeypatch.setattr(tools, "ORS_API_KEY", "")
    monkeypatch.setattr(tools, "driving_route", lambda *a, **kw: None)

    tools.derive_projected_trips_from_history()
    tools.derive_car_usage_trips()
    tools.merge_projected_trip_sets()
    result = tools.optimize_all_categories()

    assert result["status"] == "ok"
    assert result["total_simulated"] > 0
    assert len(result["scenarios"]) >= 1

    persisted = json.loads((tmp_path / "_optimization_results.json").read_text(encoding="utf-8"))
    all_ranked = persisted["all_ranked"]
    recommended = next(e for e in all_ranked if e["is_recommended"])
    assert all(recommended["score"] <= e["score"] + 1e-6 for e in all_ranked)

    # Every candidate must be internally consistent: total cost is fee + trip cost, exactly.
    for e in all_ranked:
        assert e["total_annual_cost_eur"] == pytest.approx(
            e["total_subscription_cost_eur"] + e["total_trip_cost_eur"], abs=0.05
        )
