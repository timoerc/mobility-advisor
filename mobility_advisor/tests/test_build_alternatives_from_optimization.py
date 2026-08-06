"""Tests for main.py's _build_alternatives_from_optimization() and the deterministic
warnings pipeline it feeds into Recommendation.dataQualityWarnings — see CLAUDE.md's
"Four-stage pipelines" section and the has_keep fix in _build_alternatives_from_optimization.
"""

import json
from pathlib import Path

import main
from mobility_advisor import tools

_SCENARIOS = Path(__file__).parent.parent / "scenarios"


def _write_opt_results(tmp_path, opt_results):
    (tmp_path / "_optimization_results.json").write_text(
        json.dumps(opt_results), encoding="utf-8"
    )


def _base_scenario(**overrides):
    scenario = {
        "status": "ok", "label": "Current", "category": "current",
        "subscription_ids": ["db_bc50_2nd_annual_standard"],
        "total_annual_cost_eur": 900.0, "total_annual_time_min": 1000.0,
        "total_annual_co2_kg": 200.0, "is_current": True, "is_recommended": True,
        "delta_cost_eur": 0.0, "delta_time_min": 0.0, "delta_co2_kg": 0.0,
    }
    scenario.update(overrides)
    return scenario


def test_current_also_recommended_produces_two_distinct_no_action_rows(tmp_path, monkeypatch):
    # Regression for the "current setup is already optimal" 500: when a single scenario is
    # both is_current and is_recommended, the old has_keep guard counted that row as
    # satisfying "there is a keep row" and never appended a separate baseline — leaving
    # Recommendation with one null-action recommended row and nothing else with action=None,
    # which failed the "deliberate hold" validator exception and turned into an HTTP 500 on
    # exactly the case the coordinator's own instructions advertise as valid ("no change
    # improves on the current setup").
    monkeypatch.setattr(main, "_DATA", tmp_path)
    # _build_alternatives_from_optimization() calls detect_pending_portfolio_decision(),
    # which reads tools._DATA/life_events.json directly (not main._DATA) — without this,
    # these tests were implicitly reading whatever life_events.json the REAL repo's
    # mobility_advisor/data/ happened to contain at test time (e.g. a persona left active
    # from manual/live-server testing), rather than being isolated in tmp_path. tmp_path has
    # no life_events.json, so load_life_events() correctly defaults to no events/no gate.
    monkeypatch.setattr(tools, "_DATA", tmp_path)
    current_ids = ["db_bc50_2nd_annual_standard"]
    opt_results = {
        "status": "ok",
        "current_subscription_ids": current_ids,
        "scenarios": [_base_scenario(subscription_ids=current_ids)],
        "all_ranked": [_base_scenario(subscription_ids=current_ids)],
        "break_even": [],
        "warnings": [],
    }
    _write_opt_results(tmp_path, opt_results)

    alts = main._build_alternatives_from_optimization()
    assert alts is not None
    no_action_ids = {a.id for a in alts if a.action is None}
    # Two distinct no-action rows: the recommended "keep" row and a non-recommended
    # baseline — a duplicate id would fail Recommendation's unique-ids validator below.
    assert len(no_action_ids) == 2
    assert sum(a.isRecommended for a in alts) == 1

    # Must actually construct a valid Recommendation — this is what raised 500 before the fix.
    rec = main.Recommendation(
        verdict="Keep your current setup", confidence="high", summaryText="s",
        metrics=[], reasoning=["r"], alternatives=alts,
    )
    assert rec.alternatives  # constructed without raising


def test_current_also_recommended_no_action_rows_have_matching_cost(tmp_path, monkeypatch):
    # The appended baseline row's annualCostEur must match the recommended row's (both are
    # "the current setup"), which is what lets Recommendation's is_deliberate_hold check
    # accept the null-action recommended row.
    monkeypatch.setattr(main, "_DATA", tmp_path)
    # _build_alternatives_from_optimization() calls detect_pending_portfolio_decision(),
    # which reads tools._DATA/life_events.json directly (not main._DATA) — without this,
    # these tests were implicitly reading whatever life_events.json the REAL repo's
    # mobility_advisor/data/ happened to contain at test time (e.g. a persona left active
    # from manual/live-server testing), rather than being isolated in tmp_path. tmp_path has
    # no life_events.json, so load_life_events() correctly defaults to no events/no gate.
    monkeypatch.setattr(tools, "_DATA", tmp_path)
    current_ids = ["db_bc50_2nd_annual_standard"]
    opt_results = {
        "status": "ok",
        "current_subscription_ids": current_ids,
        "scenarios": [_base_scenario(subscription_ids=current_ids, total_annual_cost_eur=750.0)],
        "all_ranked": [_base_scenario(subscription_ids=current_ids, total_annual_cost_eur=750.0)],
        "break_even": [],
        "warnings": [],
    }
    _write_opt_results(tmp_path, opt_results)

    alts = main._build_alternatives_from_optimization()
    no_action_rows = [a for a in alts if a.action is None]
    assert len(no_action_rows) == 2
    assert no_action_rows[0].annualCostEur == no_action_rows[1].annualCostEur == 750.0


def test_normal_case_still_has_one_keep_row(tmp_path, monkeypatch):
    # Sanity check the fix didn't regress the ordinary case: current != recommended still
    # produces exactly one no-action ("keep") row, not two.
    monkeypatch.setattr(main, "_DATA", tmp_path)
    # _build_alternatives_from_optimization() calls detect_pending_portfolio_decision(),
    # which reads tools._DATA/life_events.json directly (not main._DATA) — without this,
    # these tests were implicitly reading whatever life_events.json the REAL repo's
    # mobility_advisor/data/ happened to contain at test time (e.g. a persona left active
    # from manual/live-server testing), rather than being isolated in tmp_path. tmp_path has
    # no life_events.json, so load_life_events() correctly defaults to no events/no gate.
    monkeypatch.setattr(tools, "_DATA", tmp_path)
    current_ids = ["db_bc50_2nd_annual_standard"]
    rec_ids = ["db_bc25_2nd_annual_standard"]
    opt_results = {
        "status": "ok",
        "current_subscription_ids": current_ids,
        "scenarios": [
            _base_scenario(subscription_ids=current_ids, is_recommended=False, label="Current"),
            _base_scenario(
                subscription_ids=rec_ids, is_current=False, is_recommended=True,
                total_annual_cost_eur=700.0, label="BahnCard 25",
            ),
        ],
        "all_ranked": [
            _base_scenario(subscription_ids=current_ids, is_recommended=False, label="Current"),
            _base_scenario(
                subscription_ids=rec_ids, is_current=False, is_recommended=True,
                total_annual_cost_eur=700.0, label="BahnCard 25",
            ),
        ],
        "break_even": [],
        "warnings": [],
    }
    _write_opt_results(tmp_path, opt_results)

    alts = main._build_alternatives_from_optimization()
    no_action_rows = [a for a in alts if a.action is None]
    assert len(no_action_rows) == 1
    assert no_action_rows[0].id == "keep"


def test_optimize_all_categories_persists_merged_warnings(tmp_path, monkeypatch):
    # B4/A5: data_quality_warnings from load_travel_history() and the trip-projection
    # engine's own notices (travel-reduction damping, rail-fare calibration, aggregation)
    # must reach _optimization_results.json's "warnings" key — this is the one channel
    # main._load_optimization_warnings() reads to populate
    # Recommendation.dataQualityWarnings, so a persona like Lena (malformed history
    # entries) actually surfaces them to the user instead of the pipeline silently
    # analyzing only the clean subset.
    for f in (_SCENARIOS / "lena").glob("*.json"):
        (tmp_path / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(tools, "_DATA", tmp_path)
    monkeypatch.setattr(tools, "ORS_API_KEY", "")
    monkeypatch.setattr(tools, "driving_route", lambda *a, **kw: None)

    tools.derive_projected_trips_from_history()
    tools.derive_car_usage_trips()
    tools.merge_projected_trip_sets()
    result = tools.optimize_all_categories()

    assert result["status"] == "ok"
    assert any("cost_eur is null" in w for w in result["warnings"])
    assert any("mode is empty" in w or "unknown mode" in w for w in result["warnings"])

    persisted = json.loads((tmp_path / "_optimization_results.json").read_text(encoding="utf-8"))
    assert persisted["warnings"] == result["warnings"]

    monkeypatch.setattr(main, "_DATA", tmp_path)
    # _build_alternatives_from_optimization() calls detect_pending_portfolio_decision(),
    # which reads tools._DATA/life_events.json directly (not main._DATA) — without this,
    # these tests were implicitly reading whatever life_events.json the REAL repo's
    # mobility_advisor/data/ happened to contain at test time (e.g. a persona left active
    # from manual/live-server testing), rather than being isolated in tmp_path. tmp_path has
    # no life_events.json, so load_life_events() correctly defaults to no events/no gate.
    monkeypatch.setattr(tools, "_DATA", tmp_path)
    assert main._load_optimization_warnings() == result["warnings"]


def test_activate_from_scenario_clears_stale_scratch_files(tmp_path, monkeypatch):
    # B2 regression: switching personas via _activate_from_scenario() (used by both
    # /api/activate and /api/profile) must not leave a PREVIOUS persona's derived
    # trip-projection/optimization files sitting in data/ — main.py's
    # _build_alternatives_from_optimization() has no freshness check and would otherwise
    # serve them as if they belonged to the newly activated persona.
    monkeypatch.setattr(main, "_DATA", tmp_path)
    # _build_alternatives_from_optimization() calls detect_pending_portfolio_decision(),
    # which reads tools._DATA/life_events.json directly (not main._DATA) — without this,
    # these tests were implicitly reading whatever life_events.json the REAL repo's
    # mobility_advisor/data/ happened to contain at test time (e.g. a persona left active
    # from manual/live-server testing), rather than being isolated in tmp_path. tmp_path has
    # no life_events.json, so load_life_events() correctly defaults to no events/no gate.
    monkeypatch.setattr(tools, "_DATA", tmp_path)
    for fname in main._OPTIMIZATION_SCRATCH_FILES:
        (tmp_path / fname).write_text("{}", encoding="utf-8")

    ok = main._activate_from_scenario("maja")

    assert ok is True
    for fname in main._OPTIMIZATION_SCRATCH_FILES:
        assert not (tmp_path / fname).exists(), f"{fname} should have been cleared"
    # The real scenario fixtures must still have been copied in.
    assert (tmp_path / "persona.json").exists()


def test_co2_impact_string_sign_distinguishes_more_from_less_emissions(tmp_path, monkeypatch):
    # B6 regression: co2Impact (the human-readable string) used to be wrapped in abs(...),
    # so an option emitting 40 kg MORE than current and one emitting 40 kg LESS rendered as
    # the identical string. co2ImpactKg (the signed number, positive = saves) already got
    # this right; the string must show the opposite-convention raw delta with its own sign.
    monkeypatch.setattr(main, "_DATA", tmp_path)
    # _build_alternatives_from_optimization() calls detect_pending_portfolio_decision(),
    # which reads tools._DATA/life_events.json directly (not main._DATA) — without this,
    # these tests were implicitly reading whatever life_events.json the REAL repo's
    # mobility_advisor/data/ happened to contain at test time (e.g. a persona left active
    # from manual/live-server testing), rather than being isolated in tmp_path. tmp_path has
    # no life_events.json, so load_life_events() correctly defaults to no events/no gate.
    monkeypatch.setattr(tools, "_DATA", tmp_path)
    current_ids = ["db_bc50_2nd_annual_standard"]
    dirtier_ids = ["db_bc25_2nd_annual_standard"]
    cleaner_ids = ["db_deutschlandticket"]
    opt_results = {
        "status": "ok",
        "current_subscription_ids": current_ids,
        "scenarios": [
            _base_scenario(subscription_ids=current_ids, is_recommended=False, label="Current"),
            _base_scenario(
                subscription_ids=dirtier_ids, is_current=False, is_recommended=True,
                total_annual_co2_kg=240.0, label="Dirtier",
            ),
            _base_scenario(
                subscription_ids=cleaner_ids, is_current=False, is_recommended=False,
                total_annual_co2_kg=160.0, label="Cleaner",
            ),
        ],
        "all_ranked": [
            _base_scenario(subscription_ids=current_ids, is_recommended=False, label="Current"),
            _base_scenario(
                subscription_ids=dirtier_ids, is_current=False, is_recommended=True,
                total_annual_co2_kg=240.0, label="Dirtier",
            ),
            _base_scenario(
                subscription_ids=cleaner_ids, is_current=False, is_recommended=False,
                total_annual_co2_kg=160.0, label="Cleaner",
            ),
        ],
        "break_even": [],
        "warnings": [],
    }
    _write_opt_results(tmp_path, opt_results)

    alts = main._build_alternatives_from_optimization()
    dirtier = next(a for a in alts if "dirtier" in a.name.lower() or a.id.startswith("db_bc25"))
    cleaner = next(a for a in alts if "cleaner" in a.name.lower() or a.id.startswith("db_deutschlandticket"))

    # Dirtier: +40 kg vs current -> co2ImpactKg negative (does NOT save), string shows "+40".
    assert dirtier.co2ImpactKg == -40.0
    assert dirtier.co2Impact == "+40 kg CO₂/year"
    # Cleaner: -40 kg vs current -> co2ImpactKg positive (saves), string shows "-40".
    assert cleaner.co2ImpactKg == 40.0
    assert cleaner.co2Impact == "-40 kg CO₂/year"
    # The two must never render identically despite being opposite outcomes.
    assert dirtier.co2Impact != cleaner.co2Impact
