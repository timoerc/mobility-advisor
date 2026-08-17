"""The annual pipeline's four agents. Deliberately stays on the pre-deterministic,
single-candidate LLM design rather than following analyst_agent/forecaster_agent/
optimizer_agent onto the trip-projection/simulation engine — annual_communicator_agent's
report structure (compute_annual_report_stats() tables + a single proposed-change bullet)
is written against that single-candidate shape, and porting it is deliberate follow-up
work (see "Known limitations" in the merge plan). ADK also forbids sharing agent
instances across SequentialAgents, so these are separate objects with distinct names even
where the instruction text is shared (annual_forecaster_agent reuses the same
InstructionProvider function as no non-annual counterpart exists for it to derive from).
"""
from google.adk.agents import LlmAgent

from ..engine.stats import compute_annual_report_stats, compute_co2_impact_kg
from ..i18n import LANGUAGE_DIRECTIVE, get_language, t
from ..store.loaders import (
    load_annual_analyst_context,
    load_annual_optimizer_context,
    load_forecaster_context,
)
from .model import (
    _LONG_REPORT_TOKENS,
    _MEDIUM_REPORT_TOKENS,
    _REVIEW_YEAR,
    _SHORT_REPORT_TOKENS,
    _TODAY,
    ReadonlyContext,
    _load_home_city,
    _MODEL,
    build_content_config,
)


def _annual_forecaster_instruction(_ctx: ReadonlyContext) -> str:
    """Annual Forecaster instruction — the older, prose-summary style the annual pipeline
    still uses (forward-looking, not year-scoped, since it is describing what's ahead of
    today regardless of which past year the rest of the report covers). Kept structurally
    separate from the regular Forecaster: the annual Optimizer reads {forecast} as
    prose text, not the merged-trip-set file the deterministic Optimizer scores, so this
    agent must never call the trip-projection/merge tools.
    """
    home_city = _load_home_city()
    return f"""\
You are the Forecaster agent for your Mobility Advisor.
Today's date: {_TODAY}.

Your job: summarize forward mobility demand for the next 3–6 months from today.
The user's current home base is {home_city}.

Step 1 — call load_forecaster_context(). This returns calendar events (key 'calendar_events') and life-event signals (key 'life_events') together in one call. Do this before writing anything.

Step 2 — produce a brief forward-demand summary (3–5 bullet points):
- Expected dominant modes (rail, local transit, car-share, etc.)
- Approximate long-distance trip volume
- Life-event signals from load_forecaster_context()'s life_events field: if any events are returned, state each one's
  category and summary plus its concrete portfolio implication (e.g. a relocation signal away
  from {home_city} means the current commute-based subscription mix may no longer fit once it
  takes effect); if the events list is empty, state plainly "No life-event signals detected."
- Any notable gaps or uncertainties

Be factual and brief. Do not recommend actions — that is the Optimizer's job.

Your output is consumed by downstream agents, not displayed to the user. Write it as a clean structured report. Do not include questions, offers, follow-up prompts, or any conversational phrase at the end.
"""


annual_analyst_agent = LlmAgent(
    name="annual_analyst",
    model=_MODEL,
    description="Analyzes the user's travel history and current subscriptions to identify portfolio inefficiencies.",
    instruction=f"""\
You are the Analyst agent for your Mobility Advisor.
Today's date: {_TODAY}. This report covers only calendar year {_REVIEW_YEAR} — every figure must be scoped to {_REVIEW_YEAR} only.

You MUST call load_annual_analyst_context() first. Use ONLY the exact figures returned by the tool — do not use any outside knowledge of pricing or cashback rates. Report all numbers verbatim from the tool output.

Your job: report usage facts for each active subscription. Do not draw conclusions or make recommendations — that is another agent's job.

Step 1 — call load_annual_analyst_context(). This returns travel history scoped to {_REVIEW_YEAR} (key 'travel_history'), current subscriptions (key 'current_subscriptions'), and car usage (key 'car_usage') together in one call. Do this before writing anything.

Step 2 — for each subscription, report:
- **Subscription name** and monthly cost (verbatim from tool)
- **Trip count**: how many trips in {_REVIEW_YEAR} used this subscription (from travel history)
- **Spend figures**: total amount paid under this subscription in {_REVIEW_YEAR} (verbatim from tool data)
- **Renewal**: billing_cycle and next_renewal_date (verbatim from tool)
- **Duration/ticket type**: where a trip's duration_min and ticket_type fields are present in the travel history data, mention them alongside the trip count — this surfaces travel time, not just cost, for later steps that weigh time

Step 3 — report private car ownership from load_annual_analyst_context()'s car_usage field: if owns_car is true, state "Holds a private <type> <size> car, ~<monthly_km_estimate> km/month"; if false, state "No private car."

Keep the output concise — bullet points, no prose paragraphs. Report only what the data shows.

Your output is consumed by downstream agents, not displayed to the user. Write it as a clean structured report. Do not include questions, offers, follow-up prompts, or any conversational phrase at the end.
""",
    tools=[load_annual_analyst_context],
    # Namespaced distinctly from the regular pipeline's analyst_agent output_key="analysis"
    # — both pipelines used to write "analysis"/"forecast"/"recommendation", which is a
    # no-op collision when /api/analyze and /api/annual-report each build a fresh
    # InMemoryRunner + session, but NOT when the coordinator routes to either pipeline as
    # an AgentTool inside /api/chat's one persistent InMemorySessionService per session_id
    # (see api/deps.py's _chat_service). Ask for an optimization then an annual report in the
    # same chat, and the second run's stages would silently overwrite the first's keys —
    # or, if a stage produced empty output (the exact failure _with_pipeline_retry exists
    # to paper over on the other two entry points, which /api/chat doesn't have), the
    # downstream agent would read the PREVIOUS run's leftover value instead of failing.
    output_key="annual_analysis",
    generate_content_config=build_content_config(_MEDIUM_REPORT_TOKENS),
)

annual_forecaster_agent = LlmAgent(
    name="annual_forecaster",
    model=_MODEL,
    description="Forecasts the user's forward mobility demand for the next 3–6 months based on their calendar.",
    instruction=_annual_forecaster_instruction,
    tools=[load_forecaster_context],
    output_key="annual_forecast",  # see annual_analyst_agent's output_key comment above
    generate_content_config=build_content_config(_SHORT_REPORT_TOKENS),
    include_contents="none",
)

# Frozen instruction/description used only by annual_optimizer_agent below — the annual
# report stays on the pre-deterministic, single-candidate LLM optimizer (see Known
# limitations in the merge plan): annual_communicator_agent's Step 4 ("include the
# optimizer's proposed change as a single bullet") and the rest of the annual report are
# written against this single-candidate shape and must not receive optimizer_agent's
# multi-candidate/deterministic output.
_ANNUAL_OPTIMIZER_DESCRIPTION_BASE = "Proposes one concrete contract change based on analysis, forecast, preferences, and catalog."


async def _annual_optimizer_instruction(_ctx: ReadonlyContext) -> str:
    """Built fresh per invocation (not a module-level constant), because its Step 3 output
    labels (**Proposed change:** etc.) are looked up via t() — see i18n.py's HARD RULE against
    calling t() at module scope, which would freeze in whatever language happened to be active
    at import time.

    This agent's own instruction previously hardcoded those Step 3 labels as literal English
    text and relied on a general "write ALL prose in German" directive (appended further down
    via LANGUAGE_DIRECTIVE) to translate them — but a template explicitly framed as "output
    your recommendation in this exact structure" reads to the model as fixed structural
    markup, not prose it's free to translate, so it kept reproducing these labels verbatim in
    English even in German mode (the exact same failure mode _annual_communicator_instruction's
    section headers had, before those were moved to t() too). Since this agent's Step 3 output
    is quoted directly into annual_communicator's Section 5 ("include the optimizer's proposed
    change from {annual_recommendation}") and reaches the user near-verbatim, translating these
    labels deterministically in code — instead of hoping the LLM does it — is the only reliable
    fix, same reasoning as the report skeleton's <!-- ..._PLACEHOLDER --> labels.
    """
    proposed_change = t("report.optimizer.proposedChange")
    current_monthly_cost = t("report.optimizer.currentMonthlyCost")
    proposed_monthly_cost = t("report.optimizer.proposedMonthlyCost")
    monthly_saving = t("report.optimizer.monthlySaving")
    co2_impact = t("report.optimizer.co2Impact")
    action_deadline = t("report.optimizer.actionDeadline")
    cancel_change_before = t("report.optimizer.cancelChangeBefore", date="[next_renewal_date]")
    what_stays_and_why = t("report.optimizer.whatStaysAndWhy")
    why_this_change = t("report.optimizer.whyThisChange")

    raw_instruction = f"""\
You are the Optimizer agent for your Mobility Advisor.
Today's date: {_TODAY}.

Context from upstream agents:
- Analyst finding: {{annual_analysis}}
- Forecaster outlook: {{annual_forecast}}

Your job: propose exactly ONE concrete contract change that maximizes value for the user.
Address the user directly as "you"/"your" throughout your output — not by name.

Step 1 — call load_annual_optimizer_context(). This returns user preferences (key 'user_preferences') and the user-relevant mobility catalog (key 'relevant_mobility_catalog') together in one call. Do this before writing anything. Subscription names, costs, billing cycles, and next_renewal_date values are already in the Analyst finding above — do not re-fetch them.

Step 2 — combining the upstream findings with the user's preferences and the market catalog, identify the single highest-impact change.

PREFERENCE WEIGHTING — load_annual_optimizer_context()'s user_preferences field returns priority_weights (raw cost/time/
sustainability floats summing to ~1.0). Use these, not just values_time_over_money, to decide
WHICH change is your pick, not merely how you phrase it:
- Weigh the €-saving, time/convenience impact, and CO2 impact by these three weights before
  picking. A change that wins on the user's highest-weighted dimension can outrank one that
  only wins on a lower-weighted dimension, even with a smaller raw €-saving.
- If sustainability is the highest weight (or clearly elevated vs. the other two), prefer a
  CO2-reducing change at modest extra cost over a cheaper but CO2-neutral one.
- If values_time_over_money is true, never recommend a slower or less convenient option purely
  because it saves money.
- State explicitly in the "{why_this_change}" section which preference weight(s) drove the pick.

CRITICAL — BahnCard ROI check (do this before recommending any BahnCard change):
All rail trips in history are priced at the BahnCard 50 discount (50% off).
Therefore: full_price_per_trip = trip.cost_eur × 2

For each candidate BahnCard tier, compute:
  annual_trip_cost_at_tier = Σ(full_price_per_trip × (1 − tier_discount_rate))
    BC25 discount = 0.25  →  multiply full_price by 0.75
    BC50 discount = 0.50  →  multiply full_price by 0.50
  net_saving_at_tier = (full_price_total − annual_trip_cost_at_tier) − (tier_monthly_cost × 12)

Only recommend a BahnCard downgrade if net_saving is strictly higher at the lower tier.
Include the net_saving figures for both tiers in your output.

NAMING — always use the exact, full product name as it appears in load_annual_optimizer_context()'s
relevant_mobility_catalog field's "product" field (e.g. "BahnCard 25 (2. Klasse, Standard, Jahresabo)")
or in the Analyst finding's subscription names — never a short form like "BahnCard 25" alone. The
catalog has several same-numbered tiers (Standard, Young, Senior, Probe, 1st/2nd class) that a short
name cannot distinguish, and this name is what gets executed later — an underspecified name
cannot be applied. This applies everywhere you name a specific product: the proposed change,
cost breakdown, and "what stays" section.

Step 3 — output your recommendation in this exact structure. The bold labels below are already
given to you in the correct output language — reproduce them EXACTLY as written, do not
translate, retranslate, or reword them; only the bracketed placeholders and any sentences you
compose yourself must follow the OUTPUT LANGUAGE directive:

{proposed_change} [what to add / cancel / swap — if this is a swap/replace, explicitly
name BOTH the exact current subscription being removed AND the exact new product being
added, e.g. "Replace your BahnCard 50 (2. Klasse, Standard, Jahresabo) with a BahnCard 25
(2. Klasse, Standard, Jahresabo)" — never just "Downgrade to BahnCard 25"]

{current_monthly_cost} €X.XX/mo (list all active subscriptions and their costs)
{proposed_monthly_cost} €Y.YY/mo (list the new stack)
{monthly_saving} €Z.ZZ/mo

{co2_impact} Call compute_co2_impact_kg with this change's target_subscription/new_product
(same names as your {proposed_change} above) and date_from="{_REVIEW_YEAR}-01-01",
date_to="{_REVIEW_YEAR}-12-31" (this report is scoped to {_REVIEW_YEAR} only), then state its
"explanation" field verbatim — do NOT compute CO₂ yourself or invent a number.

{action_deadline} For any subscription being cancelled or changed, state the next_renewal_date from the Analyst finding as: "{cancel_change_before}" (substituting the real date for [next_renewal_date]). Do not hardcode the date — extract it from {{annual_analysis}}.

{what_stays_and_why}
- [subscription] — [one-line justification with the key metric]

{why_this_change}
- [bullet-point rationale referencing the analysis, forecast, and user preferences —
  including which preference weight(s) (cost/time/sustainability) drove this pick per
  PREFERENCE WEIGHTING above]

Show real numbers from the data. Do not propose more than one change.
"""
    from google.adk.utils.instructions_utils import inject_session_state
    resolved = await inject_session_state(raw_instruction, _ctx)
    return resolved + LANGUAGE_DIRECTIVE[get_language()]


annual_optimizer_agent = LlmAgent(
    name="annual_optimizer",
    model=_MODEL,
    description=_ANNUAL_OPTIMIZER_DESCRIPTION_BASE,
    # An InstructionProvider (not localized(), which only handles a static base string) —
    # unlike the regular pipeline's optimizer_agent (whose raw output is only ever read by
    # communicator_agent to pull numbers into its OWN translated prose), this agent's Step 3
    # output is quoted directly into annual_communicator's Section 5 ("include the optimizer's
    # proposed change from {annual_recommendation}"), which then reaches the user near-verbatim
    # — see _annual_optimizer_instruction's docstring for why its labels are rendered via t()
    # instead of left for the LLM to translate.
    instruction=_annual_optimizer_instruction,
    tools=[load_annual_optimizer_context, compute_co2_impact_kg],
    output_key="annual_recommendation",  # see annual_analyst_agent's output_key comment above
    generate_content_config=build_content_config(_MEDIUM_REPORT_TOKENS),
    include_contents="none",
)


async def _annual_communicator_instruction(_ctx: ReadonlyContext) -> str:
    """Built fresh per invocation (not a module-level constant) because it embeds
    compute_annual_report_stats() figures, which are persona-specific — the same
    staleness hazard _load_home_city() guards against above: a persona switch via
    POST /api/activate swaps data/*.json on disk without restarting the process, so
    a value baked in at import time would silently keep reporting the previous
    persona's numbers.

    The three headline tables (Year at a Glance, Spend & Emissions by Mode,
    Subscription Value) are NOT computed by the LLM at all — they are rendered
    verbatim in Python by api/routes/analysis.py from this same
    compute_annual_report_stats() call and swapped in for the <!-- ..._PLACEHOLDER -->
    markers below, the same mechanism the trips-table used previously. This is
    deliberate: letting the LLM re-derive spend/CO2/ROI arithmetic from free text is
    exactly what produced the contradictions in earlier reports (a "savings" figure in
    one section disagreeing with a "net loss" verdict for the same subscription in
    another). The LLM's job here is narration grounded in numbers it is handed, not
    computation.

    compute_annual_report_stats() is called here AND again independently by
    api/routes/analysis.py's /api/annual-report (to render the placeholder tables), so a
    genuinely broken dataset fails either way — this call is not guarded into a silent
    fallback. The try/except below exists only to re-raise with a clear pointer to where
    the failure actually happened: an unguarded exception here previously surfaced as an
    opaque crash inside this InstructionProvider callback (a stage with no tools of its
    own, so nothing about the failure looked related to the stats computation at all)
    before the broad except in /api/annual-report turned it into a 500 either way.

    Async, and calls inject_session_state() itself before returning: this instruction embeds
    ADK template placeholders — {{annual_recommendation}}, {{annual_analysis}},
    {{annual_forecast}} below — meant to be resolved against session state the way ADK
    resolves them for a plain-string instruction. But ADK's LlmAgent.canonical_instruction()
    sets bypass_state_injection=True for ANY callable instruction (InstructionProvider), which
    skips that resolution entirely (see google.adk.flows.llm_flows.instructions). Before this
    fix, this function returned those placeholders completely unresolved — the LLM literally
    received the text "{annual_recommendation}" instead of the optimizer's actual output — a
    silent pre-existing bug independent of i18n, only surfaced while wiring the language
    directive below through the same mechanism (see i18n.localized()'s docstring for the full
    ADK mechanics and tests/test_i18n_agent_directive.py for the regression test).
    """
    try:
        stats = compute_annual_report_stats()
    except Exception as exc:
        raise RuntimeError(
            f"annual_communicator_instruction: compute_annual_report_stats() failed "
            f"while building this stage's instruction: {exc}"
        ) from exc
    by_mode_rows = [r for r in stats["by_mode"] if r["mode"] != "Total"]
    top_emitter = max(by_mode_rows, key=lambda r: r["co2_kg"]) if by_mode_rows else None
    top_emitter_share_pct = (
        round(100 * top_emitter["co2_kg"] / stats["total_co2_kg"]) if top_emitter and stats["total_co2_kg"] else 0
    )
    warnings_text = "; ".join(stats["data_quality_warnings"]) if stats["data_quality_warnings"] else t("report.dataQualityNotesNone")

    raw_instruction = f"""\
You are the Annual Report agent for your Mobility Advisor.
Today's date: {_TODAY}.

The Optimizer has produced this recommendation:
{{annual_recommendation}}

The Analyst produced this usage report:
{{annual_analysis}}

The Forecaster produced this outlook:
{{annual_forecast}}

Authoritative figures for {_REVIEW_YEAR}, computed in code (use these exact numbers in your
prose below — never recompute, re-derive, or contradict them):
- Total trips: {stats['total_trips']}, dominant mode by trip count: {stats['dominant_mode']}
- Total CO₂ footprint, ALL modes: {stats['total_co2_kg']} kg
- Largest emission source: {top_emitter['mode'] if top_emitter else 'n/a'} ({top_emitter['co2_kg'] if top_emitter else 0} kg, ~{top_emitter_share_pct}% of the total footprint)
- CO₂ avoided on regional trips by choosing rail over a generic car-share for the same
  distance: {stats['rail_vs_car_saving_kg']} kg (rail: {stats['rail_co2_g_per_km']} g/km vs. car-share: {stats['carshare_co2_g_per_km']} g/km) — this is a secondary, rail-only figure and is NOT subtracted from the total footprint above.

Your job: produce a full annual mobility review that speaks directly to
the user as "you"/"your" throughout — not by name.

Structure your output EXACTLY as follows. The section headers and fixed labels below are
already given to you in the correct output language — reproduce them EXACTLY as written, do
not translate, retranslate, or reword them; only the sentences you compose yourself (the
narrative parts described in each section) must follow the OUTPUT LANGUAGE directive.

---
# {t("report.pdf.title")}

{t("report.periodCovered", year=_REVIEW_YEAR)}

---

## {t("report.section1")}

Output exactly this line for this section, verbatim, and nothing else — the table is inserted
automatically afterward:
<!-- GLANCE_TABLE -->

---

## {t("report.section2")}

Output exactly this line for this section, verbatim, and nothing else — the table is inserted
automatically afterward:
<!-- BY_MODE_TABLE -->

---

## {t("report.section3")}

Write 2–4 sentences of honest, plain-language narrative using ONLY the authoritative figures
given above. Explicitly name the largest emission source and its approximate share of the
total footprint — do not lead with or imply a "green year" framing if flights or another
high-emission mode dominate. You may separately mention the rail-vs-car-share saving as a
smaller, secondary positive, clearly distinguished from the total footprint.

---

## {t("report.section4")}

Output exactly this line for this section, verbatim, and nothing else — the content is inserted
automatically afterward:
<!-- SUBSCRIPTION_VALUE -->

---

## {t("report.section5")}

State plainly, as a labeled line, whether any contract changes were executed this year. If
execution is mocked/pending (the normal case), write exactly:

{t("report.actionsTakenNoneLine")}
{t("report.pendingProposalLine")}

Then include the optimizer's proposed change from {{annual_recommendation}} as a single bullet. If
{{annual_recommendation}} indicates a change was actually approved/executed, state that instead under
"{t("report.actionsTakenLabel")}" and only list remaining open proposals under
"{t("report.pendingProposalLabel")}".

---

## {t("report.section6")}

Summarise {{annual_forecast}} in 2–3 sentences: what demand signals suggest about the next quarter and whether the current portfolio still fits.

---

## {t("report.section7")}

- State that all data used is mock/synthetic, for demonstration purposes.
- State that every figure in this report is scoped to trips dated in {_REVIEW_YEAR} only —
  trips outside this year are excluded.
- State that BahnCard 50's discount value is computed only from Deutsche Bahn rail trips (fares
  already reflect the ~50% BahnCard discount, so the discount value equals the amount paid);
  other rail providers (e.g. FlixTrain) are not BahnCard fares and are excluded from that figure.
- Data quality notes: {warnings_text}

---
{t("report.footerDisclaimer")}
---
"""
    # inject_session_state resolves the {annual_recommendation}/{annual_analysis}/
    # {annual_forecast} placeholders above against real session state — see this function's
    # docstring for why that has to happen here explicitly rather than automatically. Directive
    # is appended AFTER resolution, at the end, for recency (see i18n.LANGUAGE_DIRECTIVE).
    from google.adk.utils.instructions_utils import inject_session_state
    resolved = await inject_session_state(raw_instruction, _ctx)
    return resolved + LANGUAGE_DIRECTIVE[get_language()]


annual_communicator_agent = LlmAgent(
    name="annual_communicator",
    model=_MODEL,
    description="Formats a full annual mobility review for the user from the optimizer's findings.",
    instruction=_annual_communicator_instruction,
    tools=[],
    generate_content_config=build_content_config(_LONG_REPORT_TOKENS),
    include_contents="none",
)
