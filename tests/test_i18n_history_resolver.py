"""Coverage for _resolve_history_entry_language (api/routes/analysis.py) — the language-sibling
resolver that GET /api/analysis-history runs on every entry.

Two cases matter beyond the existing seeded-`_de`-only coverage in test_i18n_personas.py-style
tests: a live, `language="de"`-tagged entry with `_en` siblings must serve English to an English
request (the direction seeded fixtures never exercised), and a legacy entry with no `language`
key at all (every fixture predating this field) must still serve `_de` to a German request —
regression guard against the old `if get_language() != "de": return rec` shortcut this replaced.
"""
from mobility_advisor.api.routes.analysis import _resolve_history_entry_language
from mobility_advisor.i18n import language_scope
from mobility_advisor.models import AnalysisHistoryEntry, Alternative, MetricDelta, Recommendation


def _entry(**overrides) -> AnalysisHistoryEntry:
    rec = Recommendation(
        verdict="English verdict",
        verdict_de="German verdict",
        confidence="medium",
        summaryText="English summary",
        metrics=[MetricDelta(value=10, unit="€/year", direction="save", label="Potential saving")],
        reasoning=["English reason"],
        alternatives=[
            Alternative(
                id="keep", name="Keep current setup", annualCostEur=100,
                savingsVsCurrentEur=0, tradeoff="No change", isRecommended=False, action=None,
            ),
            Alternative(
                id="switch", name="Switch", annualCostEur=80, savingsVsCurrentEur=20,
                tradeoff="Cheaper", isRecommended=True,
                action={"title": "Switch", "description": "Switch.", "consequence": "Switched."},
            ),
        ],
    )
    defaults = dict(id="hist_test", date="2026-01-01", recommendation=rec)
    defaults.update(overrides)
    return AnalysisHistoryEntry.model_validate(defaults)


def test_legacy_entry_with_no_language_field_still_serves_de_siblings():
    # Every fixture predating AnalysisHistoryEntry.language defaults to "en" — the resolver must
    # not assume that means "there's nothing to translate".
    entry = _entry()
    assert entry.language == "en"
    with language_scope("de"):
        resolved = _resolve_history_entry_language(entry)
    assert resolved.recommendation.verdict == "German verdict"


def test_live_de_entry_serves_english_from_en_siblings():
    entry = _entry(language="de")
    entry.recommendation.verdict = "German verdict"
    entry.recommendation.verdict_de = None
    entry.recommendation.verdict_en = "English verdict"
    with language_scope("en"):
        resolved = _resolve_history_entry_language(entry)
    assert resolved.recommendation.verdict == "English verdict"


def test_matching_language_is_a_noop():
    entry = _entry(language="en")
    with language_scope("en"):
        resolved = _resolve_history_entry_language(entry)
    assert resolved.recommendation.verdict == "English verdict"


def test_metric_unit_is_localized_regardless_of_sibling_presence():
    entry = _entry()
    with language_scope("de"):
        resolved = _resolve_history_entry_language(entry)
    assert resolved.recommendation.metrics[0].unit == "€/Jahr"


def test_resolved_message_language_falls_back_correctly():
    entry = _entry(resolvedMessage="English note", resolvedMessage_de="German note")
    with language_scope("de"):
        resolved = _resolve_history_entry_language(entry)
    assert resolved.resolvedMessage == "German note"
