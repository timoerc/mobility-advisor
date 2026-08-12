"""Post-construction mutation chain every Recommendation passes through, on both the
deterministic path (builder.py) and the LLM-extraction fallback (extraction.py): headline
metric tiles, the pending-decision hold override, cost/CO2 normalization, and the
actionable-alternatives cap."""
from ...engine.simulation import _generalized_cost_rates
from ...models import Alternative, DeltaVsCurrent, MetricDelta, Recommendation
from ...store.decisions import detect_pending_portfolio_decision
from .builder import load_optimization_context, load_optimization_weights


def clamp_actionable_alternatives(
    rec: Recommendation, max_actionable: int = 5
) -> Recommendation:
    """Defensively enforce the product cap of `max_actionable` actionable alternatives.

    On the deterministic path (builder.build_alternatives_from_optimization), optimize_all_
    categories() can surface up to 5 scenarios, so the default cap here matches that. On
    the LLM-extraction fallback path (extraction.extract_recommendation_json),
    _JSON_SYSTEM_PROMPT only ever asks for one actionable alternative (the report itself
    only ever describes one recommended option — see that prompt's own docstring-
    equivalent comment), so this is normally a no-op there; it exists as a hard backstop
    regardless of what either path actually returns. Keeps the recommended alternative,
    then earlier non-recommended actionable alternatives up to the cap (in original
    order), then all keep-current-setup row(s) (action is None) unchanged.
    """
    actionable = [a for a in rec.alternatives if a.action is not None]
    if len(actionable) <= max_actionable:
        return rec
    keep_rows = [a for a in rec.alternatives if a.action is None]
    recommended = [a for a in actionable if a.isRecommended]
    others = [a for a in actionable if not a.isRecommended]
    rec.alternatives = (recommended + others)[:max_actionable] + keep_rows
    return rec


def _co2_methodology_assumption(weights: dict | None) -> str:
    """A subscription changes what each transport mode costs you; projected usage of each
    mode shifts in response (a logit mode share over generalized cost, not an all-or-
    nothing pick — see _mode_shares() in engine/simulation.py), and CO2 and travel time
    follow from that shift. This replaces the old "CO2 is 0 unless a mode becomes newly
    (un)available" methodology, which was only true because mode choice used to ignore
    price entirely.
    """
    value_of_time, co2_price = _generalized_cost_rates(weights)
    return (
        "A subscription changes what each transport mode costs you; projected mode usage "
        "shifts in response (a gradual mode-share shift, not a hard switch), and travel "
        f"time and CO2 follow. For this persona, time is valued at €{value_of_time:.2f}/hour "
        f"and CO2 at €{co2_price:.3f}/kg when weighing mode choice, derived from their "
        "stated cost/time/sustainability priorities."
    )


def normalize_keep_current_setup(rec: Recommendation) -> Recommendation:
    """Deterministically guarantee cost/CO2 deltas can never contradict the cost figures they're
    derived from, regardless of what the LLM extraction step produced.

    savingsVsCurrentEur is defined as "vs. the current setup" — i.e. vs. the status-quo
    'Keep current setup' row's own annualCostEur — so it is recomputed here as exactly that
    difference for every alternative, never trusted as an independently-extracted number. This
    also covers alternatives whose action reconfirms/renews something unchanged (annualCostEur
    equal to the keep row's), which must show a €0 delta by the same logic, not a stray figure
    like a "vs. cancelling" saving that answers a different question.

    Separately, the keep row itself (action is None) is the baseline by definition, so it also
    always shows Neutral/0 CO2 regardless of extraction. Also records the CO2 methodology as an
    assumption so it's visible to the user rather than silently applied.
    """
    keep_rows = [alt for alt in rec.alternatives if alt.action is None]
    if keep_rows:
        keep_cost = keep_rows[0].annualCostEur
        for alt in rec.alternatives:
            alt.savingsVsCurrentEur = round(keep_cost - alt.annualCostEur, 2)
    for alt in rec.alternatives:
        if alt.action is None:
            alt.co2Impact = "Neutral"
            alt.co2ImpactKg = 0.0
    assumption = _co2_methodology_assumption(load_optimization_weights())
    if assumption not in rec.assumptions:
        rec.assumptions.append(assumption)
    return rec


_HEADLINE_DROP_THRESHOLDS = {"cost": 1.0, "co2": 1.0, "time": 15.0}


def _format_time_headline(abs_time_min: float) -> tuple[float, str]:
    """Minutes below 90 render as whole minutes; above that, hours to 1 decimal — same
    breakpoint AlternativeRow uses for the vs-current strip."""
    if abs_time_min < 90:
        return round(abs_time_min), "min/year"
    return round(abs_time_min / 60, 1), "h/year"


def build_pending_decision_metrics(alts: list[Alternative], decision: dict) -> list[MetricDelta]:
    """Decision-framed headline tiles for when a portfolio-resetting life event is pending:
    the date the uncertainty resolves, the value being left on the table by holding instead
    of taking the best deferred alternative, and what kind of decision is pending."""
    best_deferred = max(
        (a for a in alts if a.action is not None),
        key=lambda a: a.savingsVsCurrentEur,
        default=None,
    )
    value_on_hold = best_deferred.savingsVsCurrentEur if best_deferred else 0.0
    category = decision["events"][0]["category"] if decision.get("events") else "life event"
    return [
        MetricDelta(value=decision["revisit_after"], unit="", direction="neutral", label="Revisit by"),
        MetricDelta(
            # max(0, ...), not abs(...) — savingsVsCurrentEur is negative when even the best
            # deferred alternative is WORSE than the status quo (no candidate improves on
            # holding), and abs() flipped that into a positive "Value on hold €X" figure,
            # implying value is being left on the table when there is none.
            value=max(0, round(value_on_hold)),
            unit="€/year",
            direction="neutral",
            label="Value on hold",
        ),
        MetricDelta(
            value=category.replace("_", " "), unit="", direction="neutral", label="Decision pending"
        ),
    ]


def build_headline_metrics(alts: list[Alternative], decision: dict) -> list[MetricDelta]:
    """Headline tiles for the top of the recommendation.

    Normal case: up to three tiles built from the recommended alternative's deltaVsCurrent —
    one per dimension. A dimension whose |delta| is below its drop threshold
    (_HEADLINE_DROP_THRESHOLDS) is omitted, except cost, which always survives so the row is
    never empty. Tiles are ordered by strikingness = |delta| / |current total| * the
    persona's own weight for that dimension, so the most persona-relevant, largest-magnitude
    change leads.

    Pending-decision case: when decision["exists"], the normal tiles would show a change the
    Hold recommendation deliberately isn't making (its deltaVsCurrent is all zeros) — build
    decision-framed tiles instead (see build_pending_decision_metrics).
    """
    if decision["exists"]:
        return build_pending_decision_metrics(alts, decision)

    rec_alt = next((a for a in alts if a.isRecommended), alts[0])
    delta = rec_alt.deltaVsCurrent or DeltaVsCurrent()
    keep_cost, keep_time, keep_co2, weights = load_optimization_context()
    w = weights or {}
    w_cost = w.get("cost_weight", 0.34)
    w_time = w.get("time_weight", 0.33)
    w_co2 = w.get("sustainability_weight", 0.33)

    def strikingness(value: float, total: float | None, weight: float) -> float:
        if not total:
            return 0.0
        return abs(value) / abs(total) * weight

    cost_metric = MetricDelta(
        value=abs(round(delta.costEur)),
        unit="€/year",
        direction="save" if delta.costEur < 0 else ("extra_cost" if delta.costEur > 0 else "neutral"),
        label="Potential saving" if delta.costEur < 0 else ("Extra cost" if delta.costEur > 0 else "No change"),
    )
    co2_metric = MetricDelta(
        value=abs(round(delta.co2Kg, 1)),
        unit="kg CO₂/year",
        direction="reduce" if delta.co2Kg < 0 else ("increase" if delta.co2Kg > 0 else "neutral"),
        label="CO₂ reduction" if delta.co2Kg < 0 else ("CO₂ increase" if delta.co2Kg > 0 else "No CO₂ change"),
    )
    time_value, time_unit = _format_time_headline(abs(delta.timeMin))
    time_metric = MetricDelta(
        value=time_value,
        unit=time_unit,
        direction="reduce" if delta.timeMin < 0 else ("increase" if delta.timeMin > 0 else "neutral"),
        label="Time saved" if delta.timeMin < 0 else ("Extra travel time" if delta.timeMin > 0 else "No time change"),
    )

    ranked = sorted(
        [
            ("cost", delta.costEur, strikingness(delta.costEur, keep_cost, w_cost), cost_metric),
            ("co2", delta.co2Kg, strikingness(delta.co2Kg, keep_co2, w_co2), co2_metric),
            ("time", delta.timeMin, strikingness(delta.timeMin, keep_time, w_time), time_metric),
        ],
        key=lambda c: c[2],
        reverse=True,
    )

    metrics = []
    for dim, value, _score, metric in ranked:
        if dim != "cost" and abs(value) < _HEADLINE_DROP_THRESHOLDS[dim]:
            continue
        metrics.append(metric)
    return metrics


def enforce_hold_when_decision_pending(rec: Recommendation) -> Recommendation:
    """When a portfolio-resetting life decision is pending, make the deliberate "Hold pending
    decision" alternative the recommended one — deterministically, not at the LLM's discretion.

    detect_pending_portfolio_decision() is a strict gate: it fires ONLY for a genuine, near-term
    relocation / work-pattern change (see its docstring), so this override never touches an
    ordinary review — for every persona without such a signal it is a no-op and the pipeline's
    own pick stands. When the gate IS active, holding until the decision resolves is the correct
    conservative call (acting now bets on a decision that isn't settled), but the optimizer LLM
    does not reliably choose it — so if it recommended a concrete change instead, re-point the
    recommendation at the Hold row here and rewrite the headline fields to match, keeping the
    concrete change visible as the non-recommended option the user is deferring.
    """
    decision = detect_pending_portfolio_decision()
    if not decision["exists"]:
        return rec
    hold = next(
        (
            a
            for a in rec.alternatives
            if a.action is None
            and (a.id == "hold" or "hold pending" in a.name.lower())
        ),
        None,
    )
    if hold is None or hold.isRecommended:
        # No hold candidate to promote (optimizer omitted it), or it is already the pick.
        return rec
    for alt in rec.alternatives:
        alt.isRecommended = alt is hold
    revisit = decision["revisit_after"]
    rec.verdict = f"Hold your current setup until the pending decision resolves ({revisit})"
    rec.summaryText = decision["reason"]
    rec.confidence = "low"
    rec.metrics = build_pending_decision_metrics(rec.alternatives, decision)
    return rec


def finalize_recommendation(rec: Recommendation) -> Recommendation:
    """Run the standard post-construction mutation chain, then re-validate the result as a
    whole — the one place both /api/analyze's deterministic path and
    extraction.extract_recommendation_json's LLM-extraction fallback path finish building a
    Recommendation, so both get the same guarantee.

    Recommendation has no validate_assignment=True, so normalize_keep_current_setup,
    enforce_hold_when_decision_pending, and clamp_actionable_alternatives each mutate an
    already-validated model without _validate_alternatives_shape (the model_validator
    enforcing unique ids / exactly one recommended / at least one keep row) ever running
    again. Turning validate_assignment on would not reliably fix this either: two of the
    three functions mutate nested Alternative objects' own fields in place (never
    reassigning any of Recommendation's own top-level fields), and the ONE reassignment
    enforce_hold_when_decision_pending performs only happens on the rare pending-decision
    path — the ordinary case (no pending decision, alternatives at or under the cap) would
    still trigger zero revalidation. Round-tripping through model_dump()/model_validate()
    here instead re-runs every validator unconditionally against the mutation chain's final
    state, regardless of which functions did or didn't reassign anything.
    """
    rec = normalize_keep_current_setup(rec)
    rec = enforce_hold_when_decision_pending(rec)
    rec = clamp_actionable_alternatives(rec)
    return Recommendation.model_validate(rec.model_dump())
