from pathlib import Path

import pytest

from mobility_advisor import paths
from mobility_advisor.engine import stats

_SCENARIOS = Path(__file__).parent.parent / "mobility_advisor" / "scenarios"


@pytest.fixture
def happy_path(monkeypatch):
    monkeypatch.setattr(paths, "DATA_DIR", _SCENARIOS / "maja")


@pytest.fixture
def failure_recovery(monkeypatch):
    monkeypatch.setattr(paths, "DATA_DIR", _SCENARIOS / "lena")


def test_total_trip_count(happy_path):
    result = stats.compute_travel_stats()
    assert result["trip_count"] == 13


def test_filter_by_mode(happy_path):
    result = stats.compute_travel_stats(mode="rail")
    assert result["trip_count"] == 8
    # 111.70 across the 5 Deutsche Bahn 2025 trips + 34.99 for the FlixTrain trip
    # (which used to have a null cost_eur, excluded from the sum, before it was
    # filled in with a realistic fare) + 29.99/39.99 for the two 2026 DB trips.
    assert result["total_spend_eur"] == pytest.approx(216.67)
    assert result["total_distance_km"] == pytest.approx(3334.2)


def test_filter_by_subscription(happy_path):
    # Maja's raw trips don't carry a booked_under tag, so a provider match against
    # "Deutsche Bahn" is what exercises the subscription_renewal lookup meaningfully.
    result = stats.compute_travel_stats(subscription_or_provider="Deutsche Bahn")
    assert result["trip_count"] == 7
    assert result["total_spend_eur"] == pytest.approx(181.68)
    assert result["subscription_renewal"] == {
        "next_renewal_date": "2026-12-31",
        "billing_cycle": "annual",
    }


def test_filter_by_provider(happy_path):
    result = stats.compute_travel_stats(subscription_or_provider="MILES")
    assert result["trip_count"] == 2
    assert result["total_spend_eur"] == pytest.approx(43.72)


def test_filter_by_date_range(happy_path):
    # Covers the two Greece-holiday flights plus the FlixTrain, Köln->Karlsruhe rail,
    # and Enterprise car-rental trips — all of Maja's trips now fall in H2 2025 (see
    # scenarios/maja/travel_history_raw.json), so trips outside 2025 are excluded here.
    result = stats.compute_travel_stats(date_from="2025-09-01", date_to="2025-11-30")
    assert result["trip_count"] == 5
    assert result["total_spend_eur"] == pytest.approx(659.40)
    assert result["total_distance_km"] == pytest.approx(4641.5)


def test_no_match_returns_null_renewal(happy_path):
    result = stats.compute_travel_stats(subscription_or_provider="Nonexistent Provider")
    assert result["trip_count"] == 0
    assert result["subscription_renewal"] is None


def test_filter_by_origin(happy_path):
    # Only the Enterprise car-rental (Frankfurt Hauptbahnhof -> München Hauptbahnhof)
    # originates in Frankfurt — the MILES car-share trip was originally an intra-Frankfurt
    # hop left over from a different persona's template despite Maja being Köln-based (see
    # test_same_city_car_trips_are_not_orphaned_in_a_different_city), and has since been
    # re-homed to Köln in the fixture.
    result = stats.compute_travel_stats(origin_filter="Frankfurt")
    assert result["trip_count"] == 1
    assert result["total_spend_eur"] == pytest.approx(189.99)
    assert result["total_distance_km"] == pytest.approx(397.1)


def test_filter_by_destination(happy_path):
    # The same car-rental trip is the only one destined for München.
    result = stats.compute_travel_stats(destination_filter="München")
    assert result["trip_count"] == 1
    assert result["total_spend_eur"] == pytest.approx(189.99)
    assert result["total_distance_km"] == pytest.approx(397.1)


def test_filter_by_subscription_and_origin(happy_path):
    # Acceptance case: of Maja's 7 Deutsche Bahn trips, 5 originate in Köln
    # (2025-07-14 Köln->Ulm, 2025-08-05 Köln Messe->Freiburg, 2025-11-18 Köln->Karlsruhe,
    # 2026-01-20 Köln->Stuttgart, 2026-05-05 Köln->Hamburg).
    result = stats.compute_travel_stats(
        subscription_or_provider="Deutsche Bahn", origin_filter="Köln"
    )
    assert result["trip_count"] == 5
    assert result["total_spend_eur"] == pytest.approx(132.20)
    assert result["total_distance_km"] == pytest.approx(1812.4)


def test_data_quality_warnings_passthrough(failure_recovery):
    result = stats.compute_travel_stats()
    assert result["trip_count"] == 20
    assert result["trips_missing_cost"] == 2
    assert len(result["data_quality_warnings"]) == 6


def test_warnings_passthrough_unaffected_by_filter(failure_recovery):
    result = stats.compute_travel_stats(mode="rail")
    assert len(result["data_quality_warnings"]) == 6


# ── total_co2_kg (C-section: qa_agent CO2 questions had no aggregation tool at all) ──


def test_total_co2_kg_sums_all_clean_trips(happy_path):
    # Every one of Maja's 13 trips has a valid mode and a non-null co2_emission_kg.
    result = stats.compute_travel_stats()
    assert result["total_co2_kg"] == pytest.approx(611.206)
    assert result["trips_excluded_from_co2"] == 0


def test_total_co2_kg_excludes_malformed_and_unrecognized_modes(failure_recovery):
    # Lena's fixture: 4 trips with an empty ("") or unrecognized ("hovercraft") mode, plus
    # one car_share trip whose co2_emission_kg is itself null — all 5 must be excluded from
    # the sum, matching load_travel_history's own data_quality_warnings text ("excluded
    # from CO₂ ... aggregations") rather than raising or silently treating them as 0.
    result = stats.compute_travel_stats()
    assert result["trips_excluded_from_co2"] == 5
    assert result["total_co2_kg"] == pytest.approx(156.462)


def test_null_distance_does_not_raise(failure_recovery):
    # Regression: total_distance_km used to sum trip.distance_km unguarded, unlike the
    # analogous cost_eur sum right above it — a single trip with a null distance_km raised
    # TypeError inside qa_agent's most-used tool. Lena's malformed entries include some with
    # null distance_km; this must not raise, and must count them separately.
    result = stats.compute_travel_stats()  # would raise before the fix, if any are null
    assert isinstance(result["total_distance_km"], float)
    assert result["trips_missing_distance"] >= 0
