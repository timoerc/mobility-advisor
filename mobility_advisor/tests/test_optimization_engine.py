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


def test_compute_portfolio_score_skips_normalization_under_small_spread():
    # Two candidates whose cost differs by well under 5% of the larger value: the
    # normalization-skip guard should treat them as tied on cost (score contribution 0),
    # not let a trivial gap dominate the ranking versus a real difference in another
    # dimension.
    results = [
        _sim(1000, 500, 100, ["a"]),  # cost differs from b by 1% — below the 5% threshold
        _sim(1010, 300, 100, ["b"]),  # meaningfully less time
    ]
    scored = tools.compute_portfolio_score(
        results, {"cost_weight": 0.5, "time_weight": 0.5, "sustainability_weight": 0.0}
    )
    ranked = {r["subscription_ids"][0]: r for r in scored["ranked_portfolios"]}
    assert ranked["a"]["norm_cost"] == 0.0
    assert ranked["b"]["norm_cost"] == 0.0
    # Time has a real (>5%) spread, so it still discriminates — b wins on time.
    assert scored["best"]["subscription_ids"] == ["b"]


def test_compute_portfolio_score_no_valid_results_is_error():
    result = tools.compute_portfolio_score([{"status": "error"}], {})
    assert result["status"] == "error"


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
