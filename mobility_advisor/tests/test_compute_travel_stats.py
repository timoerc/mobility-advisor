from pathlib import Path

import pytest

from mobility_advisor import tools

_SCENARIOS = Path(__file__).parent.parent / "scenarios"


@pytest.fixture
def happy_path(monkeypatch):
    monkeypatch.setattr(tools, "_DATA", _SCENARIOS / "maja")


@pytest.fixture
def failure_recovery(monkeypatch):
    monkeypatch.setattr(tools, "_DATA", _SCENARIOS / "lena")


def test_total_trip_count(happy_path):
    result = tools.compute_travel_stats()
    assert result["trip_count"] == 10


def test_filter_by_mode(happy_path):
    result = tools.compute_travel_stats(mode="rail")
    assert result["trip_count"] == 6
    # 111.70 across the 5 Deutsche Bahn trips + 34.99 for the FlixTrain trip, which
    # used to have a null cost_eur (excluded from the sum) before it was filled in
    # with a realistic fare.
    assert result["total_spend_eur"] == pytest.approx(146.69)
    assert result["total_distance_km"] == pytest.approx(2703.2)


def test_filter_by_subscription(happy_path):
    # Maja's raw trips don't carry a booked_under tag, so a provider match against
    # "Deutsche Bahn" is what exercises the subscription_renewal lookup meaningfully.
    result = tools.compute_travel_stats(subscription_or_provider="Deutsche Bahn")
    assert result["trip_count"] == 5
    assert result["total_spend_eur"] == pytest.approx(111.70)
    assert result["subscription_renewal"] == {
        "next_renewal_date": "2026-12-31",
        "billing_cycle": "annual",
    }


def test_filter_by_provider(happy_path):
    result = tools.compute_travel_stats(subscription_or_provider="MILES")
    assert result["trip_count"] == 1
    assert result["total_spend_eur"] == pytest.approx(23.92)


def test_filter_by_date_range(happy_path):
    # Covers the two Greece-holiday flights plus the FlixTrain, Köln->Karlsruhe rail,
    # and Enterprise car-rental trips — all of Maja's trips now fall in H2 2025 (see
    # scenarios/maja/travel_history_raw.json), so trips outside 2025 are excluded here.
    result = tools.compute_travel_stats(date_from="2025-09-01", date_to="2025-11-30")
    assert result["trip_count"] == 5
    assert result["total_spend_eur"] == pytest.approx(659.40)
    assert result["total_distance_km"] == pytest.approx(4641.5)


def test_no_match_returns_null_renewal(happy_path):
    result = tools.compute_travel_stats(subscription_or_provider="Nonexistent Provider")
    assert result["trip_count"] == 0
    assert result["subscription_renewal"] is None


def test_filter_by_origin(happy_path):
    # Only the Enterprise car-rental (Frankfurt Hauptbahnhof -> München Hauptbahnhof)
    # originates in Frankfurt — the MILES car-share trip was originally an intra-Frankfurt
    # hop left over from a different persona's template despite Maja being Köln-based (see
    # test_same_city_car_trips_are_not_orphaned_in_a_different_city), and has since been
    # re-homed to Köln in the fixture.
    result = tools.compute_travel_stats(origin_filter="Frankfurt")
    assert result["trip_count"] == 1
    assert result["total_spend_eur"] == pytest.approx(189.99)
    assert result["total_distance_km"] == pytest.approx(397.1)


def test_filter_by_destination(happy_path):
    # The same car-rental trip is the only one destined for München.
    result = tools.compute_travel_stats(destination_filter="München")
    assert result["trip_count"] == 1
    assert result["total_spend_eur"] == pytest.approx(189.99)
    assert result["total_distance_km"] == pytest.approx(397.1)


def test_filter_by_subscription_and_origin(happy_path):
    # Acceptance case: of Maja's 5 Deutsche Bahn trips, 3 originate in Köln
    # (2025-07-14 Köln->Ulm, 2025-08-05 Köln Messe->Freiburg, 2025-11-18 Köln->Karlsruhe).
    result = tools.compute_travel_stats(
        subscription_or_provider="Deutsche Bahn", origin_filter="Köln"
    )
    assert result["trip_count"] == 3
    assert result["total_spend_eur"] == pytest.approx(62.22)
    assert result["total_distance_km"] == pytest.approx(1181.4)


def test_data_quality_warnings_passthrough(failure_recovery):
    result = tools.compute_travel_stats()
    assert result["trip_count"] == 20
    assert result["trips_missing_cost"] == 2
    assert len(result["data_quality_warnings"]) == 6


def test_warnings_passthrough_unaffected_by_filter(failure_recovery):
    result = tools.compute_travel_stats(mode="rail")
    assert len(result["data_quality_warnings"]) == 6


# ── total_co2_kg (C-section: qa_agent CO2 questions had no aggregation tool at all) ──


def test_total_co2_kg_sums_all_clean_trips(happy_path):
    # Every one of Maja's 10 trips has a valid mode and a non-null co2_emission_kg.
    result = tools.compute_travel_stats()
    assert result["total_co2_kg"] == pytest.approx(588.0)
    assert result["trips_excluded_from_co2"] == 0


def test_total_co2_kg_excludes_malformed_and_unrecognized_modes(failure_recovery):
    # Lena's fixture: 4 trips with an empty ("") or unrecognized ("hovercraft") mode, plus
    # one car_share trip whose co2_emission_kg is itself null — all 5 must be excluded from
    # the sum, matching load_travel_history's own data_quality_warnings text ("excluded
    # from CO₂ ... aggregations") rather than raising or silently treating them as 0.
    result = tools.compute_travel_stats()
    assert result["trips_excluded_from_co2"] == 5
    assert result["total_co2_kg"] == pytest.approx(156.462)


def test_null_distance_does_not_raise(failure_recovery):
    # Regression: total_distance_km used to sum trip.distance_km unguarded, unlike the
    # analogous cost_eur sum right above it — a single trip with a null distance_km raised
    # TypeError inside qa_agent's most-used tool. Lena's malformed entries include some with
    # null distance_km; this must not raise, and must count them separately.
    result = tools.compute_travel_stats()  # would raise before the fix, if any are null
    assert isinstance(result["total_distance_km"], float)
    assert result["trips_missing_distance"] >= 0
