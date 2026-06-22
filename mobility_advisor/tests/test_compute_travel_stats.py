from pathlib import Path

import pytest

from mobility_advisor import tools

_SCENARIOS = Path(__file__).parent.parent / "scenarios"


@pytest.fixture
def happy_path(monkeypatch):
    monkeypatch.setattr(tools, "_DATA", _SCENARIOS / "01_happy_path")


@pytest.fixture
def failure_recovery(monkeypatch):
    monkeypatch.setattr(tools, "_DATA", _SCENARIOS / "03_failure_recovery")


def test_total_trip_count(happy_path):
    result = tools.compute_travel_stats()
    assert result["trip_count"] == 5


def test_filter_by_mode(happy_path):
    result = tools.compute_travel_stats(mode="rail")
    assert result["trip_count"] == 3
    assert result["total_spend_eur"] == pytest.approx(36.00)
    assert result["total_distance_km"] == pytest.approx(240.0)


def test_filter_by_subscription(happy_path):
    result = tools.compute_travel_stats(subscription_or_provider="BahnCard 50")
    assert result["trip_count"] == 3
    assert result["total_spend_eur"] == pytest.approx(36.00)
    assert result["subscription_renewal"] == {
        "next_renewal_date": "2027-01-15",
        "billing_cycle": "annual",
    }


def test_filter_by_provider(happy_path):
    result = tools.compute_travel_stats(subscription_or_provider="MILES")
    assert result["trip_count"] == 2
    assert result["total_spend_eur"] == pytest.approx(23.30)


def test_filter_by_date_range(happy_path):
    result = tools.compute_travel_stats(date_from="2025-04-01", date_to="2025-12-31")
    assert result["trip_count"] == 3
    assert result["total_spend_eur"] == pytest.approx(37.80)
    assert result["total_distance_km"] == pytest.approx(165.2)


def test_no_match_returns_null_renewal(happy_path):
    result = tools.compute_travel_stats(subscription_or_provider="Nonexistent Provider")
    assert result["trip_count"] == 0
    assert result["subscription_renewal"] is None


def test_filter_by_origin(happy_path):
    result = tools.compute_travel_stats(origin_filter="Frankfurt")
    assert result["trip_count"] == 4


def test_filter_by_destination(happy_path):
    result = tools.compute_travel_stats(destination_filter="Frankfurt")
    assert result["trip_count"] == 3


def test_filter_by_subscription_and_origin(happy_path):
    # Acceptance case: of 3 BahnCard 50 trips, 2 originate in Frankfurt
    # (2025-05-14 and 2025-02-10); the third (2025-05-16) originates in Mannheim.
    result = tools.compute_travel_stats(
        subscription_or_provider="BahnCard 50", origin_filter="Frankfurt"
    )
    assert result["trip_count"] == 2


def test_data_quality_warnings_passthrough(failure_recovery):
    result = tools.compute_travel_stats()
    assert result["trip_count"] == 20
    assert result["trips_missing_cost"] == 2
    assert len(result["data_quality_warnings"]) == 6


def test_warnings_passthrough_unaffected_by_filter(failure_recovery):
    result = tools.compute_travel_stats(mode="rail")
    assert len(result["data_quality_warnings"]) == 6
