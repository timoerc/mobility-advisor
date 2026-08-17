"""Product-name localization: mobility_catalog.json's `product` field is German-only and
doubles as the identity/matching key (see models/fixtures.py's _CatalogFields docstring), so
every option carries a `product_en` display sibling. The plain loaders
(load_mobility_catalog/load_current_subscriptions) always return the canonical German
`product` — engine/stats.py and engine/calibration.py match subscriptions against the catalog
and travel history by that exact string, so localizing it there would silently break those
joins in English-mode requests. The `_display` variants (load_mobility_catalog_display/
load_current_subscriptions_display), used by qa_agent, resolve `product` to the active
language instead — see store/loaders._localize_entries and i18n.pick_lang(). This is the fix
for the reported bug: an English-mode execution receipt still showing German product names
("BahnCard 50 (2. Klasse, Standard, Jahresabo)") — apply_subscription_change applies the same
_localize_entries treatment to its own removed/added lists (see test_apply_subscription_change.py)."""
import json
import shutil
from pathlib import Path

import pytest

from mobility_advisor import paths
from mobility_advisor.i18n import language_scope
from mobility_advisor.store.loaders import (
    load_current_subscriptions,
    load_current_subscriptions_display,
    load_mobility_catalog,
    load_mobility_catalog_display,
)

_SCENARIOS = Path(__file__).parent.parent / "mobility_advisor" / "scenarios"
_STATIC_CATALOG = Path(__file__).parent.parent / "mobility_advisor" / "static" / "mobility_catalog.json"

_BC50_ID = "db_bc50_2nd_annual_standard"
_BC50_DE = "BahnCard 50 (2. Klasse, Standard, Jahresabo)"
_BC50_EN = "BahnCard 50 (2nd class, standard, annual)"


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    for f in (_SCENARIOS / "maja").glob("*.json"):
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    return tmp_path


def test_every_catalog_option_has_a_nonempty_product_en():
    raw = json.loads(_STATIC_CATALOG.read_text(encoding="utf-8"))
    missing = [o["id"] for o in raw["options"] if not o.get("product_en")]
    assert not missing, f"catalog options missing product_en: {missing}"


def test_plain_loaders_always_return_canonical_german_product():
    # load_mobility_catalog/load_current_subscriptions back internal engine matching (see
    # engine/stats.py, engine/calibration.py) — must stay in the canonical form regardless
    # of the active request language, or those joins silently break in English mode.
    with language_scope("en"):
        catalog = {o["id"]: o for o in load_mobility_catalog()["options"]}
    assert catalog[_BC50_ID]["product"] == _BC50_DE
    assert catalog[_BC50_ID]["product_en"] == _BC50_EN


def test_display_catalog_resolves_product_by_language():
    with language_scope("de"):
        de_catalog = {o["id"]: o for o in load_mobility_catalog_display()["options"]}
    with language_scope("en"):
        en_catalog = {o["id"]: o for o in load_mobility_catalog_display()["options"]}

    assert de_catalog[_BC50_ID]["product"] == _BC50_DE
    assert en_catalog[_BC50_ID]["product"] == _BC50_EN

    # Neither localized payload leaks the raw sibling or the German-only notes prose.
    for catalog in (de_catalog.values(), en_catalog.values()):
        for option in catalog:
            assert "product_en" not in option
            assert "notes" not in option


def test_display_subscriptions_resolves_product_by_language(isolated_data_dir):
    with language_scope("de"):
        de_subs = {s["id"]: s for s in load_current_subscriptions_display()["subscriptions"]}
    with language_scope("en"):
        en_subs = {s["id"]: s for s in load_current_subscriptions_display()["subscriptions"]}

    assert de_subs[_BC50_ID]["product"] == _BC50_DE
    assert en_subs[_BC50_ID]["product"] == _BC50_EN

    for subs in (de_subs.values(), en_subs.values()):
        for sub in subs:
            assert "product_en" not in sub
            assert "notes" not in sub


def test_plain_subscriptions_loader_unaffected_by_language(isolated_data_dir):
    # The non-display loader must never vary by request language — this is what
    # engine/stats.py's internal subscription/catalog/travel-history joins depend on.
    with language_scope("de"):
        de_subs = {s["id"]: s for s in load_current_subscriptions()["subscriptions"]}
    with language_scope("en"):
        en_subs = {s["id"]: s for s in load_current_subscriptions()["subscriptions"]}
    assert de_subs[_BC50_ID]["product"] == en_subs[_BC50_ID]["product"] == _BC50_DE


def test_brand_only_product_names_are_unchanged_across_languages():
    # Deutschland-Ticket has no German qualifier to translate — product_en mirrors product.
    with language_scope("de"):
        de_catalog = {o["id"]: o for o in load_mobility_catalog_display()["options"]}
    with language_scope("en"):
        en_catalog = {o["id"]: o for o in load_mobility_catalog_display()["options"]}
    assert de_catalog["db_deutschlandticket"]["product"] == "Deutschland-Ticket"
    assert en_catalog["db_deutschlandticket"]["product"] == "Deutschland-Ticket"
