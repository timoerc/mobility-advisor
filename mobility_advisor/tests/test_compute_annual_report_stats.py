from pathlib import Path

import pytest

from mobility_advisor import tools

_SCENARIOS = Path(__file__).parent.parent / "scenarios"


@pytest.fixture
def maja(monkeypatch):
    monkeypatch.setattr(tools, "_DATA", _SCENARIOS / "maja")


def test_totals(maja):
    # Sanity totals for the annual report's "Year at a Glance" section — trip costs
    # (all modes) plus every active subscription's annualized fee.
    result = tools.compute_annual_report_stats()
    assert result["review_year"] == 2025
    assert result["total_trips"] == 10
    assert result["trips_missing_cost"] == 0
    assert result["total_spend_eur"] == pytest.approx(1026.24)
    assert result["dominant_mode"] == "rail"


def test_co2_footprint_includes_all_modes(maja):
    # The bug this guards against: an earlier report version only counted rail CO2,
    # silently hiding the two flights that actually dominate the footprint.
    result = tools.compute_annual_report_stats()
    assert result["total_co2_kg"] == pytest.approx(587.99)

    by_mode = {row["mode"]: row for row in result["by_mode"] if row["mode"] != "Total"}
    assert set(by_mode) == {"rail", "flight", "car_rental", "car_share"}
    assert by_mode["flight"]["co2_kg"] == pytest.approx(422.46)
    assert by_mode["flight"]["co2_kg"] > by_mode["rail"]["co2_kg"]

    total_row = next(row for row in result["by_mode"] if row["mode"] == "Total")
    assert total_row["trips"] == 10
    assert total_row["co2_kg"] == pytest.approx(result["total_co2_kg"])


def test_rail_vs_car_saving_is_secondary_not_subtracted(maja):
    result = tools.compute_annual_report_stats()
    assert result["rail_vs_car_saving_kg"] == pytest.approx(365.53)
    # The secondary rail-only saving must never be netted against the real total.
    assert result["rail_vs_car_saving_kg"] < result["total_co2_kg"]


def test_bahncard_50_attribution_and_verdict(maja):
    # Attribution is by (mode, provider) match, not the trip data's always-null
    # booked_under field — this is what fixes the old "0 trips attributed" bug.
    result = tools.compute_annual_report_stats()
    bc50 = next(s for s in result["subscriptions"] if s["provider"] == "Deutsche Bahn")
    assert bc50["is_paid_subscription"] is True
    assert bc50["trips_attributed"] == 5  # the 5 DB rail trips; FlixTrain excluded
    assert bc50["annual_fee_eur"] == pytest.approx(243.96)
    assert bc50["discount_value_eur"] == pytest.approx(111.70)
    assert bc50["net_eur"] == pytest.approx(-132.26)


def test_enterprise_silver_has_no_break_even_verdict(maja):
    # A 0-EUR loyalty tier has no fee to break even against — discount_value_eur/
    # net_eur must stay None rather than produce a nonsensical "Paid off"/"€0 net
    # cost" verdict for a program with no cost at all.
    result = tools.compute_annual_report_stats()
    enterprise = next(s for s in result["subscriptions"] if s["provider"] == "Enterprise")
    assert enterprise["is_paid_subscription"] is False
    assert enterprise["discount_value_eur"] is None
    assert enterprise["net_eur"] is None
    assert enterprise["qualifying_activity"] == {"count": 1, "threshold": 6}


def test_no_data_quality_warnings(maja):
    # Maja's one previously-null-cost trip (FlixTrain) now carries a real fare.
    result = tools.compute_annual_report_stats()
    assert result["data_quality_warnings"] == []
