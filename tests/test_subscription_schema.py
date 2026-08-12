import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from mobility_advisor.models import (
    BusBenefits,
    CarRentalBenefits,
    CarShareBenefits,
    CatalogOption,
    CurrentSubscriptions,
    FlightBenefits,
    RailBenefits,
    Subscription,
)

_ROOT = Path(__file__).parent.parent / "mobility_advisor"
_CATALOG_PATH = _ROOT / "static" / "mobility_catalog.json"
_FIXTURE_PATHS = [
    _ROOT / "data" / "current_subscriptions.json",
    _ROOT / "scenarios" / "maja" / "current_subscriptions.json",
    _ROOT / "scenarios" / "stefan" / "current_subscriptions.json",
    _ROOT / "scenarios" / "lena" / "current_subscriptions.json",
    _ROOT / "scenarios" / "katrin" / "current_subscriptions.json",
    _ROOT / "scenarios" / "sofia" / "current_subscriptions.json",
    _ROOT / "scenarios" / "tobias" / "current_subscriptions.json",
]


def _catalog_options() -> list[dict]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))["options"]


def test_rejects_non_catalog_id():
    with pytest.raises(ValidationError):
        Subscription.model_validate(
            {"id": "not-a-real-catalog-id", "next_renewal_date": "2026-01-01", "started": "2024-01-01"}
        )


def test_tamper_resistance_real_catalog_wins():
    real = next(o for o in _catalog_options() if o["id"] == "db_bc25_2nd_annual_standard")
    spoofed = {
        "id": real["id"],
        "provider": "EVIL CORP",
        "product": "Definitely Not A BahnCard",
        "mode": "flight",
        "monthly_cost_eur": 0.01,
        "next_renewal_date": "2099-01-01",
        "started": "2020-01-01",
    }
    sub = Subscription.model_validate(spoofed)
    assert sub.provider == real["provider"]
    assert sub.product == real["product"]
    assert sub.mode == real["mode"]
    assert sub.monthly_cost_eur == real["monthly_cost_eur"]
    # Only these two fields are ever taken from the caller.
    assert sub.next_renewal_date == "2099-01-01"
    assert sub.started == "2020-01-01"


def test_extra_forbid_rejects_unexpected_key():
    entry = dict(_catalog_options()[0])
    entry["totally_bogus_field"] = "should not be accepted"
    with pytest.raises(ValidationError):
        CatalogOption.model_validate(entry)


@pytest.mark.parametrize(
    "catalog_id,expected_benefits_cls",
    [
        ("db_bc50_2nd_annual_standard", RailBenefits),
        ("miles_basis", CarShareBenefits),
        ("enterprise_silver", CarRentalBenefits),
        ("lh_miles_member", FlightBenefits),
        ("flixbus_payperuse", BusBenefits),
    ],
)
def test_typed_benefits_resolve_per_mode(catalog_id, expected_benefits_cls):
    entry = next(o for o in _catalog_options() if o["id"] == catalog_id)
    option = CatalogOption.model_validate(entry)
    assert isinstance(option.benefits, expected_benefits_cls)


@pytest.mark.parametrize("path", _FIXTURE_PATHS, ids=[str(p.relative_to(_ROOT)) for p in _FIXTURE_PATHS])
def test_live_fixture_validates(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    CurrentSubscriptions.model_validate(raw)
