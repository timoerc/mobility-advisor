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
    assert result["total_spend_eur"] == pytest.approx(111.70)
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
    result = tools.compute_travel_stats(date_from="2026-04-01", date_to="2026-06-30")
    assert result["trip_count"] == 5
    assert result["total_spend_eur"] == pytest.approx(276.13)
    assert result["total_distance_km"] == pytest.approx(1606.3)


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
    # (2026-04-22 Köln->Ulm, 2026-05-07 Köln Messe->Freiburg, 2026-06-03 Köln->Karlsruhe).
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
