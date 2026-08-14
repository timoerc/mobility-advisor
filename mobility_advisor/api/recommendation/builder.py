"""Builds Alternative objects deterministically from _optimization_results.json — the
primary path api/routes/analysis.py's /api/analyze takes, ahead of the LLM-extraction
fallback in extraction.py."""
import json

from ... import paths
from ...i18n import t
from ...models import Alternative, DeltaVsCurrent, ProposedAction
from ...store.decisions import detect_pending_portfolio_decision


def load_optimization_weights() -> dict | None:
    """The flat cost_weight/time_weight/sustainability_weight dict optimize_all_categories()
    persisted for this run, or None if no deterministic run has happened yet (LLM-extraction
    fallback path)."""
    opt_path = paths.DATA_DIR / "_optimization_results.json"
    if not opt_path.exists():
        return None
    return json.loads(opt_path.read_text(encoding="utf-8")).get("weights")


def _dedupe_warnings(warnings: list[str]) -> list[str]:
    """Collapse exact-duplicate warning strings into a single "(×N)" line, preserving
    first-seen order. Upstream (engine/), the same warning — e.g. "car_share: driving route
    API failed, using heuristic" — is appended once per affected historical route rather than
    once per mode, so an API outage or missing ORS_API_KEY can otherwise repeat an identical
    line many times in the Data quality notes panel."""
    counts: dict[str, int] = {}
    order: list[str] = []
    for w in warnings:
        if w not in counts:
            order.append(w)
        counts[w] = counts.get(w, 0) + 1
    return [f"{w} (×{counts[w]})" if counts[w] > 1 else w for w in order]


def load_optimization_warnings() -> list[str]:
    """Deterministic warnings optimize_all_categories() persisted for this run — malformed
    travel-history entries, travel-reduction damping, rail-fare calibration notes, etc. (see
    engine/projection.py's derive_projected_trips_from_history/merge_projected_trip_sets).
    Empty list when no deterministic run has happened yet (LLM-extraction fallback path),
    matching Recommendation.dataQualityWarnings's default."""
    opt_path = paths.DATA_DIR / "_optimization_results.json"
    if not opt_path.exists():
        return []
    warnings = json.loads(opt_path.read_text(encoding="utf-8")).get("warnings", [])
    return _dedupe_warnings(warnings)


def load_optimization_context() -> tuple[float | None, float | None, float | None, dict | None]:
    """(keep_cost, keep_time, keep_co2, weights) for the current run's status-quo baseline
    and persona priority weights, or all-None if no deterministic optimization has run yet."""
    opt_path = paths.DATA_DIR / "_optimization_results.json"
    if not opt_path.exists():
        return None, None, None, None
    opt = json.loads(opt_path.read_text(encoding="utf-8"))
    weights = opt.get("weights")
    all_ranked = opt.get("all_ranked", opt.get("scenarios", []))
    current_ids = set(opt.get("current_subscription_ids", []))
    for s in all_ranked:
        if s.get("is_current") or (not s["subscription_ids"] and not current_ids):
            return (
                s["total_annual_cost_eur"],
                s["total_annual_time_min"],
                s["total_annual_co2_kg"],
                weights,
            )
    return None, None, None, weights


def build_alternatives_from_optimization() -> list[Alternative] | None:
    """Build Alternative objects deterministically from _optimization_results.json.

    Returns None if the file doesn't exist (fallback to LLM extraction).
    """
    opt_path = paths.DATA_DIR / "_optimization_results.json"
    if not opt_path.exists():
        return None

    opt = json.loads(opt_path.read_text(encoding="utf-8"))
    scenarios = opt.get("scenarios", [])
    if not scenarios:
        return None

    catalog_raw = json.loads((paths.STATIC_DIR / "mobility_catalog.json").read_text(encoding="utf-8"))
    catalog_by_id = {o["id"]: o for o in catalog_raw["options"]}
    current_ids = set(opt.get("current_subscription_ids", []))
    break_even_by_ids = {
        tuple(sorted(b["subscription_ids"])): b for b in opt.get("break_even", [])
    }

    # Search all_ranked (every simulated candidate), not the possibly-truncated `scenarios`
    # display subset — "No subscriptions" and the current portfolio are always present in
    # all_ranked (optimize_all_categories() guarantees both), so this should never actually
    # fall through to the `max(...)` fallback below in practice.
    all_ranked = opt.get("all_ranked", scenarios)

    # Find the baseline (no subs or current) cost/time/co2 for savingsVsCurrentEur and for
    # the recommended row's own tradeoff (see below).
    keep_cost = keep_time = keep_co2 = None
    for s in all_ranked:
        if s.get("is_current") or (not s["subscription_ids"] and not current_ids):
            keep_cost = s["total_annual_cost_eur"]
            keep_time = s["total_annual_time_min"]
            keep_co2 = s["total_annual_co2_kg"]
            break
    if keep_cost is None:
        # Should not happen — optimize_all_categories() always simulates both the current
        # portfolio and "No subscriptions". Fall back to the worst candidate rather than
        # crashing the whole recommendation, but flag it loudly: silently treating the
        # priciest scenario as "the status quo" would make every savingsVsCurrentEur look
        # artificially large.
        print("Warning: build_alternatives_from_optimization found no current/baseline "
              "scenario — falling back to the most expensive candidate as the status quo baseline.")
        worst = max(all_ranked, key=lambda s: s["total_annual_cost_eur"])
        keep_cost = worst["total_annual_cost_eur"]
        keep_time = worst["total_annual_time_min"]
        keep_co2 = worst["total_annual_co2_kg"]

    alts: list[Alternative] = []
    for s in scenarios:
        ids = set(s["subscription_ids"])
        is_keep = s.get("is_current") or (not ids and not current_ids)

        if is_keep:
            alts.append(Alternative(
                id="keep",
                name=t("alt.keep.name"),
                annualCostEur=s["total_annual_cost_eur"],
                savingsVsCurrentEur=0,
                co2Impact=t("alt.co2.neutral"),
                co2ImpactKg=0.0,
                tradeoff=t("alt.keep.tradeoff"),
                isRecommended=s.get("is_recommended", False),
                action=None,
                deltaCostVsRecommendedEur=s.get("delta_cost_eur", 0),
                deltaTimeVsRecommendedMin=s.get("delta_time_min", 0),
                deltaCo2VsRecommendedKg=s.get("delta_co2_kg", 0),
                deltaVsCurrent=DeltaVsCurrent(),
            ))
            continue

        # Build action from diff vs current portfolio. Free tiers (Enterprise Silver, Miles
        # & More, etc. — monthly_cost_eur == 0) are excluded from both sides of the diff:
        # they're automatic loyalty tiers the optimizer never proposes adding or removing
        # (see SKIP_IDS in optimize_all_categories()), so surfacing one as "Cancel
        # Enterprise Silver" alongside a real BahnCard swap is just confusing — there is
        # nothing to decide about a €0/mo tier the user isn't being asked to give up.
        added = {
            sid for sid in (ids - current_ids)
            if catalog_by_id.get(sid, {}).get("monthly_cost_eur", 0) > 0
        }
        removed = {
            sid for sid in (current_ids - ids)
            if catalog_by_id.get(sid, {}).get("monthly_cost_eur", 0) > 0
        }

        added_names = [catalog_by_id[sid]["product"] for sid in sorted(added) if sid in catalog_by_id]
        removed_names = [catalog_by_id[sid]["product"] for sid in sorted(removed) if sid in catalog_by_id]
        # " + " everywhere a card joins multiple product names — matches the separator
        # optimize_all_categories() already uses for its combo labels (engine/optimizer.py),
        # so a two-product cancel/add reads the same as a two-product portfolio label
        # instead of switching between ", " and " + " depending on which code path built
        # the string.
        added_joined = " + ".join(added_names)
        removed_joined = " + ".join(removed_names)

        if added_names and removed_names:
            action_title = t("alt.action.replace.title", removed=removed_joined, added=added_joined)
            name = t("alt.action.replace.name", label=s["label"])
            consequence = t("alt.action.replace.consequence", removed=removed_joined, added=added_joined)
        elif added_names:
            action_title = t("alt.action.add.title", added=added_joined)
            name = t("alt.action.add.name", label=s["label"])
            consequence = t("alt.action.add.consequence", added=added_joined)
        elif removed_names:
            action_title = t("alt.action.cancel.title", removed=removed_joined)
            name = t("alt.action.cancel.name", removed=removed_joined)
            consequence = t("alt.action.cancel.consequence", removed=removed_joined)
        else:
            action_title = s["label"]
            name = s["label"]
            consequence = t("alt.action.noChange.consequence")

        # Generate tradeoff string from deltas vs. the user's CURRENT setup — every row's
        # own card states what the user is being asked to give up or gain relative to what
        # they hold today, the recommended row included.
        d_cost = s["total_annual_cost_eur"] - keep_cost
        d_time = s["total_annual_time_min"] - keep_time if keep_time is not None else 0
        d_co2 = s["total_annual_co2_kg"] - keep_co2 if keep_co2 is not None else 0
        tradeoff_parts = []
        if abs(d_cost) >= 1:
            if d_cost > 0:
                tradeoff_parts.append(t("alt.tradeoff.moreExpensive", amount=round(d_cost)))
            else:
                tradeoff_parts.append(t("alt.tradeoff.cheaper", amount=round(abs(d_cost))))
        if abs(d_time) >= 10:
            if d_time > 0:
                tradeoff_parts.append(t("alt.tradeoff.moreTime", minutes=round(d_time)))
            else:
                tradeoff_parts.append(t("alt.tradeoff.lessTime", minutes=round(d_time)))
        if abs(d_co2) >= 1:
            if d_co2 > 0:
                tradeoff_parts.append(t("alt.tradeoff.moreCo2", kg=round(d_co2)))
            else:
                tradeoff_parts.append(t("alt.tradeoff.lessCo2", kg=round(d_co2)))

        # Break-even for this row's resulting portfolio as a whole, not for its added/removed
        # subscriptions scored independently. optimize_all_categories() now computes
        # break-even for every non-baseline candidate it simulates (see _compute_break_even),
        # not just single-subscription ones, so the row's own subscription_ids usually has a
        # direct match — showing that one combined figure instead of one line per added/
        # removed id avoids double-counting: two cards' discount_value_eur are each computed
        # independently against the "no subscriptions" baseline, so summing both lines (e.g.
        # for "Add BahnCard 25 + Deutschlandticket") overstates what holding both together
        # actually saves, since they compete for the same trips. Falls back to the
        # per-added/removed-id lookup only for a row with no whole-portfolio match (should
        # not normally happen, since `s` is itself one of optimize_all_categories()'s
        # simulated candidates).
        break_even_parts = []
        row_break_even = break_even_by_ids.get(tuple(sorted(ids)))
        if row_break_even is not None:
            verb = t("alt.breakEven.breaksEven") if row_break_even["breaks_even"] else t("alt.breakEven.netLoss")
            break_even_parts.append(t(
                "alt.breakEven.line",
                label=s["label"], verb=verb,
                discount=f"{row_break_even['discount_value_eur']:.0f}",
                fee=f"{row_break_even['annual_fee_eur']:.0f}",
            ))
        else:
            for sid in sorted(added | removed):
                break_even = break_even_by_ids.get((sid,))
                if break_even is None:
                    continue
                verb = t("alt.breakEven.breaksEven") if break_even["breaks_even"] else t("alt.breakEven.netLoss")
                product = catalog_by_id.get(sid, {}).get("product", break_even["label"])
                break_even_parts.append(t(
                    "alt.breakEven.line",
                    label=product, verb=verb,
                    discount=f"{break_even['discount_value_eur']:.0f}",
                    fee=f"{break_even['annual_fee_eur']:.0f}",
                ))
        if break_even_parts:
            tradeoff_parts.append("; ".join(break_even_parts))

        if tradeoff_parts:
            tradeoff = "; ".join(tradeoff_parts)
        else:
            tradeoff = t("alt.tradeoff.sameAsCurrent")

        # CO2 impact vs. current setup (positive = saves CO2), consistent with
        # savingsVsCurrentEur's baseline.
        co2_impact_kg = round(-d_co2, 1)
        # The human-readable string uses the opposite sign convention from co2ImpactKg —
        # it shows the raw emissions delta (d_co2: negative = fewer emissions = greener),
        # matching the tradeoff text's own "+X kg CO₂ per year"/"-X kg CO₂ per year"
        # phrasing above. Previously wrapped in abs(...), which made an option emitting 40
        # kg MORE than current render identically to one saving 40 kg — the same string for
        # opposite outcomes, on a field that's part of the wire contract (persisted into
        # analysis_history.json) even though today's frontend doesn't render it.
        d_co2_rounded = round(d_co2)
        co2_impact_str = t("alt.co2Impact.value", delta=d_co2_rounded) if d_co2_rounded != 0 else t("alt.co2.neutral")

        slug = "_".join(s["subscription_ids"]) if s["subscription_ids"] else "none"

        alts.append(Alternative(
            id=slug,
            name=name,
            annualCostEur=s["total_annual_cost_eur"],
            savingsVsCurrentEur=round(keep_cost - s["total_annual_cost_eur"], 2),
            co2ImpactKg=co2_impact_kg,
            co2Impact=co2_impact_str,
            tradeoff=tradeoff,
            isRecommended=s.get("is_recommended", False),
            action=ProposedAction(
                title=action_title,
                description=t("alt.action.description", title=action_title),
                consequence=consequence,
            ),
            deltaCostVsRecommendedEur=s.get("delta_cost_eur", 0),
            deltaTimeVsRecommendedMin=s.get("delta_time_min", 0),
            deltaCo2VsRecommendedKg=s.get("delta_co2_kg", 0),
            deltaVsCurrent=DeltaVsCurrent(
                costEur=round(d_cost, 2),
                timeMin=round(d_time, 1),
                co2Kg=round(d_co2, 2),
            ),
            addedProducts=added_names,
            removedProducts=removed_names,
        ))

    # Deterministic "hold pending decision" row — detect_pending_portfolio_decision() is a
    # strict gate that only fires for a genuine, near-term relocation/work-pattern change
    # (see its docstring in store/decisions.py), so this is a no-op for every persona
    # without one. When it does fire, the row is added here as a candidate but NOT marked
    # recommended yet — finalize.enforce_hold_when_decision_pending() (called by
    # /api/analyze after this function returns) is what promotes it over whatever scored
    # best, same as it already does on the LLM-extraction fallback path. Cost is pinned to
    # keep_cost (same convention as "Keep current setup") so Recommendation's deliberate-
    # hold validator exception accepts it.
    decision = detect_pending_portfolio_decision()
    if decision["exists"]:
        alts.append(Alternative(
            id="hold",
            name=t("alt.hold.name"),
            annualCostEur=keep_cost,
            savingsVsCurrentEur=0,
            co2Impact=t("alt.co2.neutral"),
            co2ImpactKg=0.0,
            tradeoff=decision["reason"],
            isRecommended=False,
            action=None,
            deltaVsCurrent=DeltaVsCurrent(),
        ))

    # Ensure exactly one recommended and one keep row
    has_recommended = any(a.isRecommended for a in alts)
    # Deliberately excludes the recommended row itself: when the current/baseline portfolio
    # is ALSO the top-ranked candidate, the loop above emits a single row with id="keep",
    # action=None, isRecommended=True — that row satisfies `a.action is None` but is not a
    # separate baseline to compare against. Without the `and not a.isRecommended` exclusion,
    # has_keep was True here even though no non-recommended no-action row exists, so the
    # append below never ran — leaving Recommendation with a null-action recommended row and
    # no other no-action row for its validator's "deliberate hold" exception to match against
    # (see models/api.py's _validate_alternatives_shape), which raised ValueError and turned
    # into an HTTP 500 on every "current setup is already optimal" result — exactly the "Do
    # Nothing" case the coordinator's own instructions advertise as a valid outcome.
    has_keep = any(a.action is None and not a.isRecommended for a in alts)

    if not has_recommended and alts:
        alts[0].isRecommended = True
    if not has_keep:
        # The recommended row may itself already use id="keep" (the is_keep branch above,
        # when the current portfolio is also the top-ranked candidate) — this baseline row
        # must not collide with it, or Recommendation's unique-ids validator rejects the
        # whole result.
        existing_ids = {a.id for a in alts}
        baseline_id = "keep_baseline" if "keep" in existing_ids else "keep"
        alts.append(Alternative(
            id=baseline_id,
            name=t("alt.keep.name"),
            annualCostEur=keep_cost,
            savingsVsCurrentEur=0,
            tradeoff=t("alt.keep.tradeoff"),
            isRecommended=False,
            action=None,
            deltaVsCurrent=DeltaVsCurrent(),
        ))

    # Sort: recommended first, then by cost, keep-current last
    def _sort_key(a):
        if a.isRecommended:
            return (0,)
        if a.action is None:
            return (2,)
        return (1, a.annualCostEur)
    alts.sort(key=_sort_key)

    return alts
