"""English message catalog — the source of truth. Every key here must also exist in de.py with
the same `{placeholder}` set; `test_i18n_catalog.py` enforces that.

Protected values that must NEVER be routed through this catalog (see i18n.py's docstring and
CLAUDE.md): Alternative.id, MetricDelta.direction, Recommendation.confidence,
AnalysisHistoryEntry.outcome, apply_subscription_change's status, and every catalog
product/provider/mode name from mobility_catalog.json.
"""

MESSAGES: dict[str, str] = {
    # ── _build_alternatives_from_optimization() — main.py ────────────────────────────────────
    "alt.keep.name": "Keep current setup",
    "alt.keep.tradeoff": "No change to cost or emissions",
    "alt.co2.neutral": "Neutral",
    "alt.action.replace.title": "Replace {removed} with {added}",
    "alt.action.replace.name": "Switch to {label}",
    "alt.action.replace.consequence": "Your {removed} will be cancelled and {added} will start in its place.",
    "alt.action.add.title": "Add {added}",
    "alt.action.add.name": "Add {label}",
    "alt.action.add.consequence": "{added} will be added to your portfolio.",
    "alt.action.cancel.title": "Cancel {removed}",
    "alt.action.cancel.name": "Cancel {removed}",
    "alt.action.cancel.consequence": "{removed} will be cancelled.",
    "alt.action.noChange.consequence": "No change.",
    "alt.action.description": "{title}. This changes your mobility portfolio.",
    "alt.tradeoff.moreExpensive": "€{amount} more per year",
    "alt.tradeoff.cheaper": "€{amount} cheaper per year",
    "alt.tradeoff.moreTime": "+{minutes} min travel time per year",
    "alt.tradeoff.lessTime": "{minutes} min travel time per year",
    "alt.tradeoff.moreCo2": "+{kg} kg CO₂ per year",
    "alt.tradeoff.lessCo2": "{kg} kg CO₂ per year",
    "alt.tradeoff.sameAsCurrent": "Same cost, travel time, and CO₂ as your current setup",
    "alt.breakEven.breaksEven": "breaks even",
    "alt.breakEven.netLoss": "runs a net loss",
    "alt.breakEven.line": "{label} {verb}: €{discount} discount value vs. €{fee} fee",
    "alt.co2Impact.value": "{delta:+d} kg CO₂/year",
    "alt.hold.name": "Hold pending decision",

    # ── metrics / headline tiles — main.py ───────────────────────────────────────────────────
    "metric.potentialSaving": "Potential saving",
    "metric.extraCost": "Extra cost",
    "metric.noChange": "No change",
    "metric.co2Reduction": "CO₂ reduction",
    "metric.co2Increase": "CO₂ increase",
    "metric.noCo2Change": "No CO₂ change",
    "metric.timeSaved": "Time saved",
    "metric.extraTravelTime": "Extra travel time",
    "metric.noTimeChange": "No time change",
    "metric.unit.minPerYear": "min/year",
    "metric.unit.hPerYear": "h/year",
    "metric.unit.eurPerYear": "€/year",
    "metric.unit.kgCo2PerYear": "kg CO₂/year",
    "metric.pendingDecision.revisitBy": "Revisit by",
    "metric.pendingDecision.valueOnHold": "Value on hold",
    "metric.pendingDecision.decisionPending": "Decision pending",
    "metric.pendingDecision.lifeEvent": "life event",
    "lifeEvent.category.relocation": "relocation",
    "lifeEvent.category.job_change": "job change",
    "lifeEvent.category.subscription_change": "subscription change",
    "lifeEvent.category.household_change": "household change",
    "lifeEvent.category.other": "other",

    # ── CO2 methodology assumption — main.py ─────────────────────────────────────────────────
    "assumption.co2Methodology": (
        "A subscription changes what each transport mode costs you; projected mode usage "
        "shifts in response (a gradual mode-share shift, not a hard switch), and travel "
        "time and CO2 follow. For this persona, time is valued at €{valueOfTime}/hour "
        "and CO2 at €{co2Price}/kg when weighing mode choice, derived from their "
        "stated cost/time/sustainability priorities."
    ),

    # ── pending-decision hold row — tools.py detect_pending_portfolio_decision() ─────────────
    "pending.reason": (
        "A pending {categories} is expected to take effect by {date}, which would reset the "
        "current commute-based portfolio — acting now risks a change the decision could "
        "immediately reverse."
    ),
    "verdict.holdUntilResolved": "Hold your current setup until the pending decision resolves ({revisit})",

    # ── annual report — main.py's Markdown renderers ─────────────────────────────────────────
    "mode.rail": "Rail",
    "mode.flight": "Flight",
    "mode.carRental": "Car rental",
    "mode.carShare": "Car share",
    "mode.bus": "Bus",
    "mode.unknown": "Unknown",
    "report.glance.totalSpend": "Total mobility spend",
    "report.glance.savings": "Estimated savings from subscription discounts",
    "report.glance.totalCo2": "Total CO₂ footprint (all modes)",
    "report.glance.co2Avoided": "CO₂ avoided on regional trips (rail vs. car-share)",
    "report.glance.tripsLogged": "Trips logged",
    "report.glance.header.metric": "Metric",
    "report.glance.header.value": "Value",
    "report.byMode.header.mode": "Mode",
    "report.byMode.header.trips": "Trips",
    "report.byMode.header.distance": "Distance",
    "report.byMode.header.spend": "Spend",
    "report.byMode.header.co2": "CO₂",
    "report.byMode.total": "**Total**",
    "report.subValue.paidOff": "✅ Paid off",
    "report.subValue.borderline": "⚠️ Borderline",
    "report.subValue.didNotBreakEven": "❌ Did not break even",
    "report.subValue.header.discount": " — €{monthly}/mo (€{annual}/yr)",
    "report.subValue.header.flatFee": " — €{monthly}/mo (€{annual}/yr, flat fee)",
    "report.subValue.header.loyalty": " — no monthly fee (loyalty tier)",
    "report.subValue.tripsAttributedWithMode": "- Trips attributed: {count} {provider} {mode} trips",
    "report.subValue.discountValue": "- Discount value delivered: €{amount}",
    "report.subValue.netVsFee": "- Net vs. annual fee: {sign}€{amount}",
    "report.subValue.verdict": "- Verdict: {verdict}",
    "report.subValue.tripsCoveredThisYear": "- Trips covered this year: {count}",
    "report.subValue.flatFeeNoBreakEven": "- Flat-fee unlimited-access pass — no per-trip discount to break even against.",
    "report.subValue.tripsAttributedSimple": "- Trips attributed: {count}",
    "report.subValue.activityThisYear": "- Activity this year: {count} of {threshold} needed to reach the next tier",
    "report.subValue.loyaltyNoBreakEven": "- No break-even applies — this membership has no fee to offset.",

    # ── HTTP error / status messages surfaced to the frontend — main.py ──────────────────────
    "error.pipelineRetryExhausted": (
        "The pipeline did not produce a result after {attempts} attempts (last issue: missing "
        "input {lastError}). This can happen when a stage's response comes back empty — either "
        "an oversized prompt or an intermittent backend hiccup. Please try again."
    ),
    "error.pipelineNoReport": "The recommendation pipeline failed before producing a report: {error}",
    "error.annualPipelineNoReport": "The annual report pipeline failed before producing a report: {error}",
    "error.pdfRenderingFailed": "PDF rendering failed: {error}",
    "error.jsonExtractionFailed": "JSON extraction failed: {error}",
    "error.executionAgentNoResponse": "Execution agent produced no response.",
    "error.agentNoResponse": "Agent produced no response.",
    "error.unlinkedExecutionNote": (
        "(Note: this change was applied, but could not be linked to its originating analysis — "
        "likely because a newer analysis ran in the meantime. It will not appear as revertible "
        "in your history.)"
    ),
    "error.noAnalysisHistoryEntry": "No analysis history entry '{entryId}'.",
    "error.onlyNewestCanBeResolved": "Only the newest analysis can be resolved; older analyses are read-only.",
    "error.alreadyExecutedMustRevertFirst": "This analysis was already executed; revert it before deciding again.",
    "error.onlyNewestCanBeReverted": "Only the newest analysis can be reverted.",
    "error.noExecutedChangeToRevert": "This analysis has no executed change to revert.",
    "revert.resolvedMessage": "Reverted — your previous mobility setup has been restored.",
    "revert.message": "Reverted to your previous mobility setup.",

    # ── tools.py warnings / errors ────────────────────────────────────────────────────────────
    "warn.drivingRouteFailed": "{mode}: driving route API failed, using heuristic",
    "warn.railCalibrationSkipped": (
        "Rail fare calibration skipped ({n} usable DB trip(s) with cost+distance data; need "
        ">= {minTrips}) — projected rail prices use the uncalibrated synthetic price curve, "
        "not observed fares."
    ),
    "warn.railCalibrationClamped": (
        "Rail fare calibration ratio {ratio}x (from {n} observed DB trips) looked like an "
        "outlier and was clamped to [{lo}, {hi}]."
    ),
    "warn.railCalibrationApplied": (
        "Rail prices calibrated to observed fares: synthetic price curve scaled {ratio}x from "
        "{n} observed DB Sparpreis/Flexpreis trip(s) up to {maxDist}km; routes beyond that use "
        "the uncalibrated curve."
    ),
    "warn.travelReductionDetected": (
        "Travel-reduction signal detected (event date {date}) — projected trip frequencies "
        "damped by a factor of {factor} to reflect reduced travel after this date, rather than "
        "extrapolating history unchanged."
    ),
    "route.localRegional": "Local/regional travel ({count} route(s), aggregated)",
    "route.intraCityCar": "Intra-city car travel ({count} trip(s) observed, aggregated)",
    "route.homeCommute": "Home-city commute (~{n}x/week office, ~{km}km one-way)",
    "route.carUsage": "Car usage ({name}, ~{km}km)",
    "warn.aggregatedIntraCityCar": (
        "Aggregated {count} same-city car-share/car-rental trip(s) (avg ~{avgDist}km) into "
        "one projected intra-city trip ({freq}/yr) instead of dropping them — this is the "
        "demand a car-share membership actually prices against. No rail alternative is "
        "offered for it (see this function's docstring)."
    ),
    "warn.aggregatedRegionalRoutes": (
        "Aggregated {count} regional route(s) each seen under 2x/yr individually "
        "({totalFreq}/yr combined, ~{avgDist}km avg) into one projected local-travel trip, "
        "instead of dropping them — this is the demand a Deutschlandticket or regional pass "
        "actually prices against."
    ),
    "warn.modelledCommute": (
        "Modelled {n} office day(s)/week as a recurring home-city commute at ~{km}km one-way "
        "(typical urban commute distance, not from actual data — travel history only records "
        "inter-city trips) — {freq}/yr legs. This is the demand a Deutschlandticket or regional "
        "pass is actually priced against."
    ),
    "warn.dedupCalendarWins": (
        "Dedup: {a} ↔ {b} — calendar route data used, but frequency kept at history's higher "
        "{merged}/yr rather than calendar's {calFreq}/yr"
    ),
    "warn.dedupCalendarReplaces": "Dedup: {a} ↔ {b} — calendar ({calFreq}/yr) replaces history ({histFreq}/yr)",
    "warn.uncorroboratedCalendarDemand": (
        "Uncorroborated calendar demand: {route} was projected at {freq}/yr from calendar "
        "events alone, with no supporting trip in travel history — capped at {cap}/yr."
    ),
    "data.tripExcludedNullCost": "{label}: cost_eur is null — excluded from spend totals",
    "data.tripExcludedEmptyMode": "{label}: mode is empty — excluded from CO₂ and mode aggregations",
    "data.tripExcludedUnknownMode": "{label}: unknown mode '{mode}' — excluded from CO₂ and mode aggregations",
    "catalog.noSubscriptions": "No subscriptions",
    "table.total": "Total",

    # ── annual report PDF chrome (report_pdf.py / templates/annual_report.{html,css}) ───────
    "report.pdf.title": "Your Annual Mobility Review",
    "report.pdf.mastheadLeft": "Mobility Advisor",
    "report.pdf.mastheadRight": "Annual Mobility Review",
    "report.pdf.pageLabel": "Page ",
    "report.pdf.ofLabel": " of ",

    "error.noMatchFor": "no match for '{query}'",
    "error.ambiguousMatchFor": "ambiguous match for '{query}': matched {count} entries ({matches})",

    "subscriptionChange.error.targetRequired": "target_subscription is required for action={action}",
    "subscriptionChange.error.newProductRequired": "new_product is required for action={action}",
    "subscriptionChange.error.newEntryInvalid": "new subscription entry failed validation: {error}",
    "subscriptionChange.error.resultInvalid": "resulting subscriptions failed validation: {error}",
    # ── compute_co2_impact_kg() explanations — quoted verbatim by the annual optimizer prompt,
    # so these must already be in the target language by the time the LLM sees them. ─────────
    "co2Impact.explanation.pureAdd": (
        "Neutral — 0 kg CO2/year. This adds a subscription without removing another, so it "
        "doesn't change which mode you currently use for any trip."
    ),
    "co2Impact.explanation.priceOnly": (
        "Neutral — 0 kg CO2/year. This changes price/tier only; it doesn't affect which mode "
        "of transport you use (you can still use {mode} with or without this subscription)."
    ),
    "co2Impact.explanation.stillCovered": (
        "Neutral — 0 kg CO2/year. You keep another subscription covering {mode}, so access to "
        "this mode is unaffected."
    ),
    "co2Impact.period.scoped": "in the period considered",
    "co2Impact.period.pastYear": "from the past 12 months",
    "co2Impact.explanation.saved": (
        "{delta} kg CO2/year saved. Losing your only {mode} subscription means your "
        "{tripCount} {mode} trip(s) {period} would shift to driving (at {gramsPerKm} g/km), "
        "which is actually lower emissions than those trips currently produce ({before} kg → "
        "{after} kg)."
    ),
    "co2Impact.explanation.moreEmissions": (
        "{delta} kg CO2/year more emissions. Losing your only {mode} subscription means your "
        "{tripCount} {mode} trip(s) {period} would shift to driving (at {gramsPerKm} g/km), "
        "raising emissions from {before} kg to {after} kg/year."
    ),

    "subscriptionChange.warn.replaceIsNoOp": (
        "replace target and new_product both resolved to '{product}' — this resets the renewal "
        "clock on an unchanged product, not a real swap."
    ),
}
