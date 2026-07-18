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
    result = tools.compute_travel_stats(origin_filter="Frankfurt")
    assert result["trip_count"] == 2
    assert result["total_spend_eur"] == pytest.approx(213.91)
    assert result["total_distance_km"] == pytest.approx(403.3)


def test_filter_by_destination(happy_path):
    result = tools.compute_travel_stats(destination_filter="Frankfurt")
    assert result["trip_count"] == 1
    assert result["total_spend_eur"] == pytest.approx(23.92)
    assert result["total_distance_km"] == pytest.approx(6.2)


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
