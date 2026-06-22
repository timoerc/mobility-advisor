import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from mobility_advisor import tools

_SCENARIOS = Path(__file__).parent.parent / "scenarios"


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    for f in (_SCENARIOS / "01_happy_path").glob("*.json"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setattr(tools, "_DATA", tmp_path)
    return tmp_path


def _read_subscriptions(data_dir):
    return json.loads((data_dir / "current_subscriptions.json").read_text())["subscriptions"]


def _read_catalog_bytes(data_dir):
    return (data_dir / "mobility_catalog.json").read_bytes()


def test_remove_existing_subscription(isolated_data_dir):
    result = tools.apply_subscription_change(action="remove", target_subscription="MILES+ Abo")
    assert result["status"] == "applied"
    assert result["before_count"] == 3
    assert result["after_count"] == 2
    assert result["removed"][0]["product"] == "MILES+ Abo"
    assert result["added"] == []
    subs = _read_subscriptions(isolated_data_dir)
    assert len(subs) == 2
    assert all(s["product"] != "MILES+ Abo" for s in subs)


def test_add_from_catalog_computes_renewal_date(isolated_data_dir):
    result = tools.apply_subscription_change(
        action="add", new_product="BahnCard 25", as_of=date(2026, 3, 10)
    )
    assert result["status"] == "applied"
    added = result["added"][0]
    assert added["product"] == "BahnCard 25 (2. Klasse)"
    assert added["billing_cycle"] == "annual"
    assert added["started"] == "2026-03-10"
    assert added["next_renewal_date"] == "2027-03-10"
    subs = _read_subscriptions(isolated_data_dir)
    assert len(subs) == 4
    assert any(s["product"] == "BahnCard 25 (2. Klasse)" for s in subs)


def test_add_monthly_product_renewal_date_clamps_month_end(isolated_data_dir):
    result = tools.apply_subscription_change(
        action="add", new_product="MILES Basis", as_of=date(2026, 1, 31)
    )
    assert result["status"] == "applied"
    added = result["added"][0]
    assert added["billing_cycle"] == "monthly"
    assert added["next_renewal_date"] == "2026-02-28"


def test_replace_swaps_in_one_pass(isolated_data_dir):
    result = tools.apply_subscription_change(
        action="replace",
        target_subscription="BahnCard 50",
        new_product="BahnCard 25",
        as_of=date(2026, 6, 22),
    )
    assert result["status"] == "applied"
    assert result["removed"][0]["product"] == "BahnCard 50 (2. Klasse)"
    assert result["added"][0]["product"] == "BahnCard 25 (2. Klasse)"
    assert result["before_count"] == 3
    assert result["after_count"] == 3
    subs = _read_subscriptions(isolated_data_dir)
    rail_subs = [s for s in subs if "BahnCard" in s["product"]]
    assert len(rail_subs) == 1
    assert rail_subs[0]["product"] == "BahnCard 25 (2. Klasse)"


def test_remove_nonexistent_target_is_error_no_write(isolated_data_dir):
    before = (isolated_data_dir / "current_subscriptions.json").read_bytes()
    result = tools.apply_subscription_change(action="remove", target_subscription="Nonexistent")
    assert result["status"] == "error"
    assert "no match" in result["error"]
    assert result["backup_path"] is None
    after = (isolated_data_dir / "current_subscriptions.json").read_bytes()
    assert before == after


def test_ambiguous_new_product_is_error_no_write(isolated_data_dir):
    before = (isolated_data_dir / "current_subscriptions.json").read_bytes()
    result = tools.apply_subscription_change(action="add", new_product="MILES")
    assert result["status"] == "error"
    assert "ambiguous" in result["error"]
    after = (isolated_data_dir / "current_subscriptions.json").read_bytes()
    assert before == after


def test_add_nonexistent_product_is_error_no_write(isolated_data_dir):
    before = (isolated_data_dir / "current_subscriptions.json").read_bytes()
    result = tools.apply_subscription_change(action="add", new_product="Nonexistent Product")
    assert result["status"] == "error"
    assert "no match" in result["error"]
    after = (isolated_data_dir / "current_subscriptions.json").read_bytes()
    assert before == after


def test_missing_required_param_is_error_no_backup(isolated_data_dir):
    result = tools.apply_subscription_change(action="remove")
    assert result["status"] == "error"
    assert "target_subscription is required" in result["error"]
    assert not list(isolated_data_dir.glob("current_subscriptions.json.bak_*"))


@pytest.mark.parametrize(
    "action,kwargs",
    [
        ("remove", {"target_subscription": "MILES+ Abo"}),
        ("add", {"new_product": "BahnCard 25"}),
        ("replace", {"target_subscription": "BahnCard 50", "new_product": "BahnCard 25"}),
    ],
)
def test_catalog_file_untouched_after_every_operation(isolated_data_dir, action, kwargs):
    before = _read_catalog_bytes(isolated_data_dir)
    result = tools.apply_subscription_change(action=action, **kwargs)
    assert result["status"] == "applied"
    after = _read_catalog_bytes(isolated_data_dir)
    assert before == after


def test_backup_file_created_on_successful_write(isolated_data_dir):
    original = (isolated_data_dir / "current_subscriptions.json").read_bytes()
    result = tools.apply_subscription_change(action="remove", target_subscription="MILES+ Abo")
    backups = list(isolated_data_dir.glob("current_subscriptions.json.bak_*"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == original
    assert result["backup_path"] == str(backups[0])


def test_no_stray_temp_file_after_success_or_error(isolated_data_dir):
    tools.apply_subscription_change(action="remove", target_subscription="MILES+ Abo")
    tools.apply_subscription_change(action="remove", target_subscription="Nonexistent")
    assert not list(isolated_data_dir.glob("*.tmp"))
