"""Round-trip coverage for i18n.localize_unit() — the reverse-index lookup that translates a
raw MetricDelta.unit string (seeded fixtures, or an already-t()-generated live value) to the
active language's equivalent, without a dedicated unit_de/unit_en model field.

Regression target: a naive `{**en.MESSAGES, **de.MESSAGES}` merge collapses each shared key to
a single (German) value, silently making every English unit string un-matchable.
"""
from mobility_advisor.i18n import language_scope, localize_unit
from mobility_advisor.messages import de as _de, en as _en


def _unit_keys() -> list[str]:
    return [k for k in _en.MESSAGES if k.startswith("metric.unit.")]


def test_every_unit_value_round_trips_en_to_de():
    for key in _unit_keys():
        en_value = _en.MESSAGES[key]
        de_value = _de.MESSAGES[key]
        with language_scope("de"):
            assert localize_unit(en_value) == de_value, key


def test_every_unit_value_round_trips_de_to_en():
    for key in _unit_keys():
        en_value = _en.MESSAGES[key]
        de_value = _de.MESSAGES[key]
        with language_scope("en"):
            assert localize_unit(de_value) == en_value, key


def test_unknown_unit_is_returned_unchanged():
    with language_scope("de"):
        assert localize_unit("g/km") == "g/km"


def test_localize_unit_is_a_noop_when_already_in_active_language():
    with language_scope("de"):
        assert localize_unit("€/Jahr") == "€/Jahr"
    with language_scope("en"):
        assert localize_unit("€/year") == "€/year"
