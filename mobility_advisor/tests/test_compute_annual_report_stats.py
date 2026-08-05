from pathlib import Path

import pytest

from mobility_advisor import tools

_SCENARIOS = Path(__file__).parent.parent / "scenarios"


@pytest.fixture
def maja(monkeypatch):
    monkeypatch.setattr(tools, "_DATA", _SCENARIOS / "maja")


@pytest.fixture
def katrin(monkeypatch):
    monkeypatch.setattr(tools, "_DATA", _SCENARIOS / "katrin")


@pytest.fixture
def sofia(monkeypatch):
    monkeypatch.setattr(tools, "_DATA", _SCENARIOS / "sofia")


@pytest.fixture
def stefan(monkeypatch):
    monkeypatch.setattr(tools, "_DATA", _SCENARIOS / "stefan")


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
    # co2_factors.csv's Rail,Null,Null was corrected from a DEFRA-derived 0.03203 kg/km to
    # 0.045 (midpoint of the German UBA/TREMOD Fernverkehr/Nahverkehr figures — see
    # load_co2_lookup's docstring), which this figure is derived from.
    assert result["rail_vs_car_saving_kg"] == pytest.approx(330.47)
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


def test_bahncard_and_deutschlandticket_trips_dont_overlap(katrin):
    # Katrin holds both a BahnCard 25 (long-distance discount) and a
    # Deutschlandticket (flat-fee unlimited regional) — both mode="rail",
    # provider="Deutsche Bahn". Before the coverage-kind split, a plain
    # (mode, provider) match attributed every rail trip to both at once.
    result = tools.compute_annual_report_stats()
    bc25 = next(s for s in result["subscriptions"] if "BahnCard" in s["product"])
    dticket = next(s for s in result["subscriptions"] if s["product"] == "Deutschland-Ticket")

    assert bc25["has_discount_value"] is True
    assert bc25["trips_attributed"] == 8  # paid long-distance legs only
    # katrin's fixture Flexpreis fares were repriced to realistic 2nd-class levels
    # (~€57-131/leg instead of ~€21-32/leg — see travel_history_raw.json), so the discount
    # value her BC25 actually earns scales up accordingly.
    assert bc25["discount_value_eur"] == pytest.approx(790.20)

    assert dticket["is_paid_subscription"] is True
    assert dticket["has_discount_value"] is False  # flat fee, no per-trip discount
    assert dticket["discount_value_eur"] is None
    assert dticket["net_eur"] is None
    assert dticket["trips_attributed"] == 1  # the one 0-cost regional leg

    # No trip is claimed by both subscriptions at once.
    assert bc25["trips_attributed"] + dticket["trips_attributed"] == 9  # total 2025 rail trips


def test_deutschlandticket_excludes_long_distance_trips_without_a_discount_card(sofia):
    # Sofia holds a Deutschlandticket but no BahnCard. Her 2 long-distance Hamburg
    # trips are real DB fares the Deutschlandticket does not cover — they must not
    # be counted as "trips covered" by a flat-fee regional-only pass.
    result = tools.compute_annual_report_stats()
    dticket = next(s for s in result["subscriptions"] if s["product"] == "Deutschland-Ticket")
    assert dticket["trips_attributed"] == 2  # only the 0-cost regional legs


def test_three_subscriptions_split_independently(stefan):
    # Stefan holds BahnCard 50, Deutschlandticket, and MILES Silber Pass at once —
    # the rail split must not affect the unrelated car_share subscription's own
    # (unrelated-mode) discount math.
    result = tools.compute_annual_report_stats()
    by_product = {s["product"]: s for s in result["subscriptions"]}
    assert by_product["BahnCard 50 (2. Klasse, Standard, Jahresabo)"]["has_discount_value"] is True
    assert by_product["Deutschland-Ticket"]["has_discount_value"] is False
    assert by_product["MILES Silber Pass"]["has_discount_value"] is True
