"""Deterministic portfolio optimization: builds the exhaustive candidate surface from the
market catalog, simulates and ranks every candidate, and persists the results the API
layer reads back to build the user-facing Recommendation."""
import json

from .. import paths
from ..i18n import t
from ..store.loaders import load_user_preferences
from .simulation import _compute_break_even, compute_portfolio_score, simulate_portfolio

def optimize_all_categories() -> dict:
    """Deterministic portfolio optimization across all subscription categories.

    Systematically simulates every relevant subscription option (filtered by age,
    excluding 1st class and BC100), finds the best tier per category (rail, car-share),
    tests key combinations, and ranks all scenarios using the user's priority weights.

    Writes full results to _optimization_results.json for main.py to build
    frontend alternatives from. Returns a summary for the agent.
    """
    merged_path = paths.DATA_DIR / "_projected_trips_merged.json"
    if not merged_path.exists():
        return {"status": "error", "error": "Run merge_projected_trip_sets first"}

    # merge_projected_trip_sets() already aggregates every upstream warning (history's
    # data_quality_warnings, travel_reduction/calibration notices, local/commute/intra-city
    # aggregation notes, calendar dedup/uncorroborated-demand caps) into one list — carried
    # through here into _optimization_results.json since that file (not any of the
    # `_projected_trips_*` scratch files) is what main.py reads to build the Recommendation
    # the user actually sees. Without this, e.g. Lena's malformed-trip warnings were
    # generated correctly but had no path to the user-facing report at all.
    warnings = json.loads(merged_path.read_text(encoding="utf-8")).get("warnings", [])

    catalog_raw = json.loads((paths.STATIC_DIR / "mobility_catalog.json").read_text(encoding="utf-8"))
    catalog_by_id = {opt["id"]: opt for opt in catalog_raw["options"]}

    prefs = load_user_preferences()
    age = prefs.get("age")
    # priority_weights is nested (see UserPreferences in models.py) — compute_portfolio_score
    # still takes the flat cost_weight/time_weight/sustainability_weight shape, so translate
    # here rather than changing its signature.
    pw = prefs.get("priority_weights", {})
    weights = {
        "cost_weight": pw.get("cost", 0.34),
        "time_weight": pw.get("time", 0.33),
        "sustainability_weight": pw.get("sustainability", 0.33),
    }

    SKIP_IDS = {
        "enterprise_plus", "enterprise_silver", "enterprise_gold", "enterprise_platinum",
        "lh_miles_member", "lh_miles_frequent_traveller", "lh_miles_senator", "lh_miles_hon_circle",
        "db_bc25_1st_annual_standard", "db_bc50_1st_annual_standard",
        "db_bc100_1st_annual", "db_bc100_2nd_annual",
        "flixbus_payperuse",
    }

    def _age_ok(opt):
        if age is None:
            return True
        elig = opt.get("eligibility", {})
        lo, hi = elig.get("min_age"), elig.get("max_age")
        return (lo is None or age >= lo) and (hi is None or age <= hi)

    chooseable = [o for o in catalog_raw["options"] if o["id"] not in SKIP_IDS and _age_ok(o)]
    chooseable_ids = {o["id"] for o in chooseable}

    current_raw = json.loads((paths.DATA_DIR / "current_subscriptions.json").read_text(encoding="utf-8"))
    current_ids = sorted(
        s["id"] for s in current_raw.get("subscriptions", []) if s["id"] in catalog_by_id
    )
    # The matching key used to dedup the current portfolio against the generated candidate
    # surface (cands below, which never contains a SKIP_IDS id) is NOT simply current_ids —
    # a currently-held free automatic tier that's excluded from the candidate surface for
    # having nothing to decide about (e.g. Enterprise Silver, a €0/mo loyalty perk — see
    # SKIP_IDS' own comment) would otherwise never match any generated candidate's key, so
    # the current portfolio got appended as a SEPARATE, category="current" entry sitting
    # right alongside its own twin (e.g. "BahnCard 50" and "BahnCard 50 + Enterprise
    # Silver") with an identical simulated cost/time/CO2 — a tie the stable sort resolved
    # in favor of the twin lacking category="current", so a recommendation could point at a
    # non-current row whose diff-vs-current computation (main.py's added/removed sets) then
    # found nothing to add or remove, rendering as an actionable "recommended" alternative
    # whose consequence text is literally "No change." A held id that carries a real
    # nonzero cost (e.g. a 1st-class BahnCard) is kept in the key regardless of whether the
    # candidate surface offers it — dropping a real cost from the matching identity would
    # misrepresent what the user actually pays, not just relabel it.
    def _match_key(ids: list[str]) -> tuple:
        """Same filtering current_key applies, for comparing ANY entry's subscription_ids
        against current_key on equal terms — every entry built from `cands` already
        consists only of chooseable ids, so this is a no-op for them; it only ever changes
        the current-portfolio entry's own ids (see current_key's comment above)."""
        return tuple(sorted(
            sid for sid in ids
            if sid in chooseable_ids
            or catalog_by_id.get(sid, {}).get("monthly_cost_eur", 0) > 0
        ))

    current_key = _match_key(current_ids)

    rail = [o for o in chooseable if o["mode"] == "rail"]
    miles_opts = [o for o in chooseable if o["mode"] == "car_share"]
    dt_opts = [o for o in rail if o.get("benefits", {}).get("unlimited_regional")]
    bc_opts = [o for o in rail if not o.get("benefits", {}).get("unlimited_regional")]

    # --- Build the full candidate list as the cross product of every rail choice (none, a
    # single BahnCard/Deutschlandticket, or a BahnCard+Deutschlandticket combo) and every
    # car-share choice (none, or a single MILES tier) — exhaustive rather than picking one
    # best-rail/best-car-share pair by raw cost and simulating only that one combo. With
    # ~10 rail options and ~5 car-share tiers this is at most a few dozen simulate_portfolio()
    # calls, all cached below, so exhaustive is cheap. This also means every candidate is
    # judged by the same one ranking pass (compute_portfolio_score on ALL of them) instead
    # of the combo step separately picking its rail/car-share halves by raw annual cost —
    # a persona weighting time or CO2 heavily could have its best combo built from
    # components that aren't individually cheapest, which the old greedy selection could
    # never construct.
    rail_choices: list[tuple[str, list[str]]] = [("", [])]
    rail_choices += [(o["product"], [o["id"]]) for o in rail]
    rail_choices += [
        # dt["product"], not a hardcoded "Deutschlandticket" — the catalog's actual product
        # name ("Deutschland-Ticket", with a hyphen) is what this label reaches the user as
        # (main.py's "Switch to {label}"/break_even text), and product names are otherwise
        # always required to be copied verbatim from the catalog.
        (f"{bc['product']} + {dt['product']}", [bc["id"], dt["id"]])
        for bc in bc_opts for dt in dt_opts
    ]
    car_share_choices: list[tuple[str, list[str]]] = [("", [])]
    car_share_choices += [(o["product"], [o["id"]]) for o in miles_opts]

    cands: list[tuple[str, str, list[str]]] = []
    for rail_label, rail_ids in rail_choices:
        for cs_label, cs_ids in car_share_choices:
            ids = rail_ids + cs_ids
            if not ids:
                cands.append((t("catalog.noSubscriptions"), "baseline", ids))
            elif rail_ids and cs_ids:
                cands.append((f"{rail_label} + {cs_label}", "combo", ids))
            elif rail_ids:
                cat = "rail_combo" if len(rail_ids) == 2 else "rail"
                cands.append((rail_label, cat, ids))
            else:
                cands.append((cs_label, "car_share", ids))

    # --- Simulate all (deduplicate by sorted ids) ---
    sim_cache: dict[tuple, dict] = {}
    entries: list[dict] = []
    seen_keys: set[tuple] = set()

    for label, cat, ids in cands:
        key = tuple(sorted(ids))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if key not in sim_cache:
            sim = simulate_portfolio(list(ids), weights)
            if sim.get("status") != "ok":
                continue
            sim_cache[key] = sim
        sim = sim_cache[key]
        entries.append({
            "status": "ok",
            "label": label, "category": cat, "subscription_ids": list(ids),
            "total_subscription_cost_eur": sim["total_subscription_cost_eur"],
            "total_trip_cost_eur": sim["total_trip_cost_eur"],
            "total_annual_cost_eur": sim["total_annual_cost_eur"],
            "total_annual_time_min": sim["total_annual_time_min"],
            "total_annual_co2_kg": sim["total_annual_co2_kg"],
            "trip_breakdown": sim["trip_breakdown"],
        })

    # Add current portfolio if not already covered
    if current_key not in seen_keys and current_ids:
        sim = simulate_portfolio(current_ids, weights)
        if sim.get("status") == "ok":
            sim_cache[current_key] = sim
            current_label = " + ".join(
                catalog_by_id[sid]["product"] for sid in current_ids if sid in catalog_by_id
            )
            entries.append({
                "status": "ok",
                "label": current_label, "category": "current",
                "subscription_ids": current_ids,
                "total_subscription_cost_eur": sim["total_subscription_cost_eur"],
                "total_trip_cost_eur": sim["total_trip_cost_eur"],
                "total_annual_cost_eur": sim["total_annual_cost_eur"],
                "total_annual_time_min": sim["total_annual_time_min"],
                "total_annual_co2_kg": sim["total_annual_co2_kg"],
                "trip_breakdown": sim["trip_breakdown"],
            })

    if not entries:
        return {"status": "error", "error": "No valid simulations produced"}

    # --- Score all ---
    scoring = compute_portfolio_score(entries, weights)
    rank_map = {
        tuple(sorted(r["subscription_ids"])): r["score"]
        for r in scoring["ranked_portfolios"]
    }
    for e in entries:
        # A missing rank_map entry should never happen (every entry here came from the same
        # simulation pass compute_portfolio_score just scored) — float("inf") makes that
        # failure mode sort LAST if it ever did occur, instead of a low sentinel like 999
        # (well within real generalized-cost scores) sorting an un-scored entry FIRST and
        # silently becoming the recommendation.
        e["score"] = rank_map.get(tuple(sorted(e["subscription_ids"])), float("inf"))
    entries.sort(key=lambda e: e["score"])

    # --- Compute deltas vs recommended (#1) and vs the user's current setup ---
    # Two distinct baselines, deliberately kept as separate fields rather than one the
    # caller has to reinterpret per row: delta_*_eur/min/kg is "this row minus the
    # recommended row" (zero on the recommended row itself, so it says nothing about how
    # the recommendation compares to today). delta_*_vs_current_* is "this row minus the
    # user's current portfolio" (zero on the current row itself) — this is the one to use
    # for "vs. your current setup" language, on every row including the recommended one,
    # with no sign flip required. Same convention as frontend Alternative.deltaVsCurrent:
    # negative = better than current (cheaper / faster / less CO2).
    rec = entries[0]
    current_ref = next(
        (e for e in entries if _match_key(e["subscription_ids"]) == current_key), None
    )
    for e in entries:
        e["is_recommended"] = (e is rec)
        e["is_current"] = (_match_key(e["subscription_ids"]) == current_key)
        e["delta_cost_eur"] = round(e["total_annual_cost_eur"] - rec["total_annual_cost_eur"], 2)
        e["delta_time_min"] = round(e["total_annual_time_min"] - rec["total_annual_time_min"], 1)
        e["delta_co2_kg"] = round(e["total_annual_co2_kg"] - rec["total_annual_co2_kg"], 3)
        if current_ref is not None:
            e["delta_cost_vs_current_eur"] = round(
                e["total_annual_cost_eur"] - current_ref["total_annual_cost_eur"], 2
            )
            e["delta_time_vs_current_min"] = round(
                e["total_annual_time_min"] - current_ref["total_annual_time_min"], 1
            )
            e["delta_co2_vs_current_kg"] = round(
                e["total_annual_co2_kg"] - current_ref["total_annual_co2_kg"], 3
            )
        else:
            e["delta_cost_vs_current_eur"] = None
            e["delta_time_vs_current_min"] = None
            e["delta_co2_vs_current_kg"] = None

    # --- Select up to 5 scenarios to show ---
    # Guaranteed slots: recommended (#1) and current portfolio (always shown).
    shown: list[dict] = []
    shown_keys: set[tuple] = set()

    def _add(entry, force: bool = False):
        k = tuple(sorted(entry["subscription_ids"]))
        if k in shown_keys:
            return
        if not force:
            if len(shown) >= 5:
                return
            for s in shown:
                if abs(s["total_annual_cost_eur"] - entry["total_annual_cost_eur"]) < 1:
                    e_set = set(entry["subscription_ids"])
                    s_set = set(s["subscription_ids"])
                    if e_set != s_set and (e_set > s_set or e_set < s_set):
                        return
        shown.append(entry)
        shown_keys.add(k)

    _add(rec)

    current_entry = next((e for e in entries if e.get("is_current")), None)
    if current_entry and not current_entry.get("is_recommended"):
        _add(current_entry, force=True)

    best_per_cat: dict[str, dict] = {}
    for e in entries:
        best_per_cat.setdefault(e["category"], e)

    # "baseline" ("No subscriptions") goes first so it wins the near-duplicate-suppression
    # check below against any paid tier that simulates identically (e.g. MILES Basis, a
    # €0/mo pay-per-use tier with no route ever cheap enough to trigger its discount,
    # scores byte-identical to holding nothing) — without a guaranteed slot, "No
    # subscriptions" only ever reaches the catch-all pass at the bottom of this function,
    # by which point its zero-cost duplicate has usually already filled the 5-slot cap,
    # leaving the real "cancel everything" option unshown while its mislabeled twin
    # ("Switch to MILES Basis") occupies a slot instead.
    for cat in ["baseline", "rail", "rail_combo", "car_share", "combo"]:
        if cat in best_per_cat:
            _add(best_per_cat[cat])

    if rec["category"] in ("rail", "rail_combo"):
        for e in entries:
            if e["category"] in ("rail", "rail_combo"):
                _add(e)

    for e in entries:
        _add(e)

    # --- Persist and return ---
    def _slim(e):
        return {k: v for k, v in e.items() if k != "trip_breakdown"}

    break_even = _compute_break_even(entries)

    output = {
        "status": "ok",
        "weights": weights,
        "current_subscription_ids": current_ids,
        "scenarios": [_slim(e) for e in shown],
        "all_ranked": [_slim(e) for e in entries],
        "break_even": break_even,
        "warnings": warnings,
    }
    paths.atomic_write_json(paths.DATA_DIR / "_optimization_results.json", output)

    return {
        "status": "ok",
        "scenarios_count": len(shown),
        "total_simulated": len(entries),
        "weights": weights,
        "scenarios": [_slim(e) for e in shown],
        "break_even": break_even,
        "warnings": warnings,
    }


