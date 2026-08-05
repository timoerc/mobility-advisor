import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("KICONNECT_API_KEY", ""))
os.environ.setdefault("OPENAI_API_BASE", "https://chat.kiconnect.nrw/api/v1")

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from .tools import (
    MOCK_TODAY,
    REVIEW_YEAR,
    compute_annual_report_stats,
    compute_co2_impact_kg,
    derive_car_usage_trips,
    derive_projected_trips_from_calendar,
    derive_projected_trips_from_history,
    load_annual_analyst_context,
    load_annual_optimizer_context,
    load_calendar_events,
    load_car_usage,
    load_forecaster_context,
    load_life_events,
    load_recommendation_history,
    load_travel_history,
    merge_projected_trip_sets,
    optimize_all_categories,
)

_MODEL = LiteLlm(model="openai/OpenAI GPT OSS 120b KI:Inferenz.nrw")  # options: "openai/OpenAI GPT OSS 120b KI:Inferenz.nrw", "openai/Mistral Small 4 119B 2603", "openai/Mistral Small 3-2-24b Instruct KI:Inferenz.nrw"


def build_model() -> LiteLlm:
    """Return the shared LiteLlm singleton used by all pipeline agents."""
    return _MODEL


# Output-length tiers for the pipeline agents below (see build_content_config).
_SHORT_REPORT_TOKENS = 4096   # analyst / annual forecaster: trip projection / forecast summaries.
# Bumped from an earlier 1024/2048 budget — GPT-OSS-120B's internal reasoning tokens count
# against max_output_tokens, so a tight budget across several sequential tool calls could
# exhaust it before any visible text was written, producing an empty response — confirmed
# empirically against Stefan's larger dataset (3 subscriptions).
_MEDIUM_REPORT_TOKENS = 4096  # forecaster / communicator / annual agents: structured output
# with a scoring or recommendation breakdown.
_OPTIMIZER_TOKENS = 8192      # optimizer: simulation results + scoring analysis over every
# candidate scenario optimize_all_categories() returns — the largest structured payload
# any agent in this pipeline handles.
_LONG_REPORT_TOKENS = 4096    # annual_communicator: full multi-section annual review


def build_content_config(max_output_tokens: int) -> types.GenerateContentConfig:
    """Deterministic generation config shared by the pipeline agents.

    temperature=0.0: analyst/forecaster/optimizer/communicator perform exact
    arithmetic and verbatim transcription from tool output (BahnCard ROI
    comparison, CO2-emission formulas, cost sums) rather than creative
    composition, and this report may be re-run and compared — reproducibility
    matters more here than sampling diversity.
    """
    return types.GenerateContentConfig(
        temperature=0.0, max_output_tokens=max_output_tokens
    )


_TODAY = MOCK_TODAY.isoformat()
_REVIEW_YEAR = REVIEW_YEAR
_DATA_DIR = Path(__file__).parent / "data"


def _load_home_city() -> str:
    """Read the active persona's home city fresh from disk on every call.

    Unlike a module-level constant (evaluated once, at process start), this must be
    read per-invocation: switching personas via POST /api/activate swaps data/persona.json
    on disk without restarting the backend process, so any value cached at import time goes
    stale the moment a second persona is activated in the same running server — exactly the
    scenario the demo personas exist to exercise live.
    """
    prefs = json.loads((_DATA_DIR / "persona.json").read_text())
    return prefs.get("profileData", {}).get("location", {}).get("home_city", "")


def _forecaster_instruction(_ctx: ReadonlyContext) -> str:
    """Regular (non-annual) Forecaster instruction — derives projected trips from
    calendar events, car usage, and life events, then merges them with the Analyst's
    history-derived trips into the single file the deterministic Optimizer scores.

    Built fresh per invocation (an InstructionProvider, not a plain string) so the home
    city — used as the origin for every derived calendar trip — can never go stale after
    a persona switch; see _load_home_city() above.
    """
    home_city = _load_home_city()
    return f"""\
You are the Forecaster agent for your Mobility Advisor.
Today's date: {_TODAY}.

Your job: derive projected trips from calendar events, car usage, and life events,
then merge all trip sources into a single projected trip set.

The Analyst has already derived projected trips from travel history.

Step 1 — call load_calendar_events() to see the user's upcoming events over the next 12 months.

Step 2 — for each calendar event that implies a trip to a DIFFERENT city,
call derive_projected_trips_from_calendar(origin, destination, frequency_per_year).
The user's home city is {home_city} — always use "{home_city}" as the origin parameter.
Estimate frequency: a weekly recurring meeting = 48/yr, a monthly event = 12/yr, a one-off trip = 1/yr.
Skip events that are local (location is {home_city} or same city), virtual/online,
or life events without a concrete travel destination.

Step 3 — call load_car_usage() to check if the user has car usage data. If monthly_km_estimate > 0,
call derive_car_usage_trips() to generate car-based projected trips.

Step 4 — call load_life_events() to check for life-event signals (relocation, job change,
subscription-relevance change, etc.) distilled from the user's mail. These are not merged into
the trip set directly (merge_projected_trip_sets combines history/calendar/car-usage trips
only) — a travel_reduction signal is instead applied by derive_projected_trips_from_history
upstream, damping the affected routes' frequency before you ever see them here. Your job with
this data is purely to report it in your summary below.

Step 5 — call merge_projected_trip_sets() to combine all sources (history, calendar, car usage)
into a single merged trip set. This tool also flags duplicate routes across sources.

Step 6 — output a summary:
- How many trips from each source (history, calendar, car usage)
- Total merged trips and annual instances
- Any duplicate warnings
- Life-event signals from load_life_events(): if any events are returned, state each one's
  category and summary plus its concrete portfolio implication; if the list is empty, state
  plainly "No life-event signals detected."

Keep the output concise — bullet points, no prose. Your output is consumed by downstream agents.
Do not include questions, offers, or conversational phrases at the end.
"""


def _annual_forecaster_instruction(_ctx: ReadonlyContext) -> str:
    """Annual Forecaster instruction — the older, prose-summary style the annual pipeline
    still uses (forward-looking, not year-scoped, since it is describing what's ahead of
    today regardless of which past year the rest of the report covers). Kept structurally
    separate from the regular Forecaster above: the annual Optimizer reads {forecast} as
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


analyst_agent = LlmAgent(
    name="analyst",
    model=_MODEL,
    description="Derives projected trips from the user's travel history.",
    instruction=f"""\
You are the Analyst agent for your Mobility Advisor.
Today's date: {_TODAY}.

Your job: derive projected recurring trips from historical travel patterns.

Step 1 — call load_travel_history() to examine the user's travel history.

Step 2 — call derive_projected_trips_from_history(). This tool:
- Groups historical trips by route (direction-independent)
- Extrapolates to annual frequency
- Computes per-mode alternatives (rail, car_share, car_rental, flight) with cost/time/CO2
- Derives each route's dominant fare class (Sparpreis vs. Flexpreis) from ticket_type
- Damps any route affected by a near-term travel_reduction life-event signal
- Writes the result to _projected_trips_history.json

Step 3 — output a summary of what was projected:
- How many recurring routes were found
- Total projected annual trips
- For each route: route name, annual frequency, fare class, and number of mode alternatives
- Any warnings from the tool, including any travel_reduction damping applied

Keep the output concise — bullet points, no prose. Your output is consumed by downstream agents.
Do not include questions, offers, or conversational phrases at the end.
""",
    tools=[load_travel_history, derive_projected_trips_from_history],
    output_key="analysis",
    generate_content_config=build_content_config(_SHORT_REPORT_TOKENS),
)

forecaster_agent = LlmAgent(
    name="forecaster",
    model=_MODEL,
    description="Derives projected trips from the user's calendar, car usage, and life events, then merges all trip sources.",
    instruction=_forecaster_instruction,
    tools=[
        load_calendar_events,
        derive_projected_trips_from_calendar,
        derive_car_usage_trips,
        load_car_usage,
        load_life_events,
        merge_projected_trip_sets,
    ],
    output_key="forecast",
    generate_content_config=build_content_config(_MEDIUM_REPORT_TOKENS),
    include_contents="none",
)

# Frozen instruction/description used only by annual_optimizer_agent below — the annual
# report stays on the pre-deterministic, single-candidate LLM optimizer (see Known
# limitations in the merge plan): annual_communicator_agent's Step 4 ("include the
# optimizer's proposed change as a single bullet") and the rest of the annual report are
# written against this single-candidate shape and must not receive optimizer_agent's
# multi-candidate/deterministic output.
_ANNUAL_OPTIMIZER_DESCRIPTION_BASE = "Proposes one concrete contract change based on analysis, forecast, preferences, and catalog."
_ANNUAL_OPTIMIZER_INSTRUCTION_BASE = f"""\
You are the Optimizer agent for your Mobility Advisor.
Today's date: {_TODAY}.

Context from upstream agents:
- Analyst finding: {{analysis}}
- Forecaster outlook: {{forecast}}

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
- State explicitly in "Why this change" which preference weight(s) drove the pick.

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

Step 3 — output your recommendation in this exact structure:

**Proposed change:** [what to add / cancel / swap — if this is a swap/replace, explicitly
name BOTH the exact current subscription being removed AND the exact new product being
added, e.g. "Replace your BahnCard 50 (2. Klasse, Standard, Jahresabo) with a BahnCard 25
(2. Klasse, Standard, Jahresabo)" — never just "Downgrade to BahnCard 25"]

**Current monthly cost:** €X.XX/mo (list all active subscriptions and their costs)
**Proposed monthly cost:** €Y.YY/mo (list the new stack)
**Monthly saving:** €Z.ZZ/mo

**CO₂ impact:** Call compute_co2_impact_kg with this change's target_subscription/new_product
(same names as your Proposed change above) and date_from="{_REVIEW_YEAR}-01-01",
date_to="{_REVIEW_YEAR}-12-31" (this report is scoped to {_REVIEW_YEAR} only), then state its
"explanation" field verbatim — do NOT compute CO₂ yourself or invent a number.

**Action deadline:** For any subscription being cancelled or changed, state the next_renewal_date from the Analyst finding: "Cancel/change before [next_renewal_date] to avoid auto-renewal." Do not hardcode the date — extract it from {{analysis}}.

**What stays and why:**
- [subscription] — [one-line justification with the key metric]

**Why this change:**
- [bullet-point rationale referencing the analysis, forecast, and user preferences —
  including which preference weight(s) (cost/time/sustainability) drove this pick per
  PREFERENCE WEIGHTING above]

Show real numbers from the data. Do not propose more than one change.
"""

optimizer_agent = LlmAgent(
    name="optimizer",
    model=_MODEL,
    description="Runs deterministic portfolio optimization across all subscription categories.",
    instruction=f"""\
You are the Optimizer agent for your Mobility Advisor.
Today's date: {_TODAY}.

Context from upstream agents:
- Analyst finding: {{analysis}}
- Forecaster outlook: {{forecast}}

Your job: call optimize_all_categories() — it deterministically simulates every relevant
subscription option (rail, car-share), finds the best per category, tests combinations,
and returns a ranked comparison with scores and deltas vs. the recommended portfolio.

Step 1 — call optimize_all_categories(). This is the ONLY tool you need to call.

Step 2 — output the full result verbatim as structured data. Do not summarize or omit
scenarios. Include all fields: label, subscription_ids, score, total_annual_cost_eur,
total_annual_time_min, total_annual_co2_kg, delta_cost_eur, delta_time_min, delta_co2_kg,
delta_cost_vs_current_eur, delta_time_vs_current_min, delta_co2_vs_current_kg,
is_recommended, is_current.

Note the two different delta families — do not mix them up: delta_cost_eur/delta_time_min/
delta_co2_kg are each row MINUS THE RECOMMENDED ROW (zero on the recommended row itself).
delta_*_vs_current_* fields are each row MINUS THE USER'S CURRENT SETUP (zero on the current
row itself) — these are the ones that describe "vs. your current setup", already correctly
signed on every row including the recommended one. Negative = better than current (cheaper /
faster / less CO2); positive = worse than current.

Step 3 — also output the result's break_even list verbatim (one entry per single-subscription
candidate — a BahnCard tier, the Deutschlandticket, or a car-share membership, each held
alone): label, annual_fee_eur, discount_value_eur, net_eur, breaks_even. This is the
forward-looking answer to "does this subscription pay for itself" — annual_fee_eur is what it
costs, discount_value_eur is how much cheaper the projected year's trips (rail fares or
car-share rides, whichever mode the candidate applies to) become by holding it, and net_eur is
the difference (negative means it's a net loss at this usage level, regardless of how it ranks
against other candidates). A candidate with discount_value_eur of 0 means the user has no
projected trips in that mode at all — state that plainly if it applies to the recommended or
currently-held subscription (e.g. a car-share candidate for someone with zero car-share usage
in their history).

Do not invent figures. Do not add commentary or questions. Do not mention holding or
deferring a decision — a pending-life-decision "Hold" candidate, when applicable, is
added deterministically by the API layer after this pipeline runs, not by you.
""",
    tools=[optimize_all_categories],
    output_key="recommendation",
    generate_content_config=build_content_config(_OPTIMIZER_TOKENS),
    include_contents="none",
)

communicator_agent = LlmAgent(
    name="communicator",
    model=_MODEL,
    description="Presents the portfolio optimization results as a clear, scannable report for the user.",
    instruction=f"""\
You are the Communicator agent for your Mobility Advisor.
Today's date: {_TODAY}.

The Optimizer has produced a deterministic portfolio comparison:
{{recommendation}}

Your job: write a concise verdict and reasoning. The frontend will display the scenario
table and deltas directly from stored data — you do NOT need to reproduce the full table.

Step 1 — call load_recommendation_history() to see up to the 3 most recent past reviews and
their outcomes.

CONTINUITY — if a prior review already flagged the same subscription with the same (or an
equivalent) recommended_action, acknowledge that continuity explicitly in your Reasoning
instead of re-stating the finding as if it were new, e.g. "This is the Nth review flagging
<subscription> — you kept it before; here's the updated picture." If the history is empty or
unrelated to this review's finding, say nothing about it.

REQUIRED OPTION SHAPE — whenever you state the recommended option's numbers (in the Summary
or Reasoning), give all three dimensions, not cost alone. The Optimizer's output already
carries total_annual_time_min/total_annual_co2_kg and their deltas verbatim — use them:
  Annual cost: €3,707 (subs €1,176 + trips €2,531)
  Saving vs. current: €253/year
  CO₂ impact: −38 kg CO₂/year
  Travel time: +2 h 10 min/year
A recommendation that only ever quotes the € figure is incomplete even if the saving is the
headline number.

SIGN CONVENTION — WHICH DELTA FIELD TO USE — the Optimizer's output carries two different
delta families per row; using the wrong one silently reverses your wording:
  - delta_cost_eur / delta_time_min / delta_co2_kg are each row minus the RECOMMENDED row
    (always 0 on the recommended row itself). Do not use these to describe "vs. your current
    setup" — on every row except the current one, that comparison is not what they mean.
  - delta_cost_vs_current_eur / delta_time_vs_current_min / delta_co2_vs_current_kg are each
    row minus the user's CURRENT setup (0 on the current row itself). These are what "vs.
    current", "saves/costs", "greener/dirtier", and "faster/slower" language must be based on
    — read them straight off the recommended row, no sign-flipping needed.
  In both families: negative = better than current (cheaper / faster / less CO2), positive =
  worse than current (more expensive / slower / more CO2). So a negative
  delta_co2_vs_current_kg means CO2 falls/greener; a positive one means CO2 rises/dirtier —
  and likewise positive delta_time_vs_current_min means travel time rises/slower, negative
  means it falls/faster. Get this backwards and the Verdict/Summary/Reasoning will contradict
  the numeric tiles the frontend renders directly from these same fields.

Output exactly this structure:

**Verdict:** [8-12 word headline for the recommended option, e.g. "Switch to BahnCard 25 saves €725 per year annually"]

**Confidence:** [high / medium / low — based on how clear-cut the recommended option is once
cost, travel time, AND CO2 are all considered together; high only when none of the three
dimensions meaningfully contradicts the verdict, medium if one does, low if the dimensions
pull in different directions or the numbers are close]

**Summary:** [1-2 sentences summarising the key finding, using the REQUIRED OPTION SHAPE above]

**Reasoning:**
- [bullet 1: why the recommended portfolio wins]
- [bullet 2: TRADE-OFF ACROSS DIMENSIONS — name the trade-off across cost, CO2, and travel
  time when they disagree, e.g. "cheaper but slower" or "greener but more expensive". If all
  three point the same direction, say so instead of manufacturing a trade-off.
- [bullet 3: BREAK-EVEN — if the recommended or currently-held subscription appears in the
  Optimizer's break_even list, state its discount_value_eur vs. annual_fee_eur and whether
  it breaks even (net_eur >= 0) or runs a net loss. This is the concrete "does this
  subscription pay for itself" answer — use it instead of a vague "similar cost" framing
  whenever a break_even entry is available for the subscription in question.
- [bullet 4: optional — continuity with a past review (per CONTINUITY above), or a
  cross-mode insight if interesting]

**Assumptions:**
- Rail trips are priced at their historical fare class (Sparpreis or Flexpreis), derived per
  route from ticket_type — not assumed to be Sparpreis across the board
- Trip frequencies extrapolated from historical data and calendar events
- [any other relevant assumption from the data]

Use all numbers from the Optimizer's output. Do not invent figures.
Speak directly to the user as "you"/"your" — not by name.
If "No subscriptions" is the best option, say so clearly.
""",
    tools=[load_recommendation_history],
    generate_content_config=build_content_config(_MEDIUM_REPORT_TOKENS),
    include_contents="none",
)

# ── Annual report pipeline agents ────────────────────────────────────────────
#
# The annual pipeline deliberately stays on the pre-deterministic, single-candidate LLM
# design rather than following analyst_agent/forecaster_agent/optimizer_agent above onto
# the trip-projection/simulation engine — annual_communicator_agent's report structure
# (compute_annual_report_stats() tables + a single proposed-change bullet) is written
# against that single-candidate shape, and porting it is deliberate follow-up work (see
# "Known limitations" in the merge plan). ADK also forbids sharing agent instances across
# SequentialAgents, so these are separate objects with distinct names even where the
# instruction text is shared (annual_forecaster_agent reuses the same InstructionProvider
# function as no non-annual counterpart exists for it to derive from).
#
# annual_analyst_agent's instruction is NOT derived from analyst_agent's (unlike a much
# earlier version) — analyst_agent is now the deterministic trip-projection agent above,
# structurally unrelated to what the annual analyst needs to produce (a year-scoped,
# per-subscription usage report). It is written out directly instead, year-scoped to
# REVIEW_YEAR throughout.
#
# No raw per-trip table is requested here (unlike an earlier version): the annual report's
# headline spend/CO2/subscription-value figures are computed deterministically by
# compute_annual_report_stats() and rendered by main.py, and a by-mode summary table
# replaces what used to be a full trip-by-trip dump — a raw ledger a reader can't act on
# isn't professional annual-report content. See annual_communicator_agent below.
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
    output_key="analysis",
    generate_content_config=build_content_config(_MEDIUM_REPORT_TOKENS),
)

annual_forecaster_agent = LlmAgent(
    name="annual_forecaster",
    model=_MODEL,
    description="Forecasts the user's forward mobility demand for the next 3–6 months based on their calendar.",
    instruction=_annual_forecaster_instruction,
    tools=[load_forecaster_context],
    output_key="forecast",
    generate_content_config=build_content_config(_SHORT_REPORT_TOKENS),
    include_contents="none",
)

annual_optimizer_agent = LlmAgent(
    name="annual_optimizer",
    model=_MODEL,
    description=_ANNUAL_OPTIMIZER_DESCRIPTION_BASE,
    instruction=_ANNUAL_OPTIMIZER_INSTRUCTION_BASE.replace(
        "over the past 12 months", f"in {_REVIEW_YEAR}"
    ),
    tools=[load_annual_optimizer_context, compute_co2_impact_kg],
    output_key="recommendation",
    generate_content_config=build_content_config(_MEDIUM_REPORT_TOKENS),
    include_contents="none",
)

def _annual_communicator_instruction(_ctx: ReadonlyContext) -> str:
    """Built fresh per invocation (not a module-level constant) because it embeds
    compute_annual_report_stats() figures, which are persona-specific — the same
    staleness hazard _load_home_city() guards against above: a persona switch via
    POST /api/activate swaps data/*.json on disk without restarting the process, so
    a value baked in at import time would silently keep reporting the previous
    persona's numbers.

    The three headline tables (Year at a Glance, Spend & Emissions by Mode,
    Subscription Value) are NOT computed by the LLM at all — they are rendered
    verbatim in Python by main.py from this same compute_annual_report_stats() call
    and swapped in for the <!-- ..._PLACEHOLDER --> markers below, the same
    mechanism the trips-table used previously. This is deliberate: letting the LLM
    re-derive spend/CO2/ROI arithmetic from free text is exactly what produced the
    contradictions in earlier reports (a "savings" figure in one section disagreeing
    with a "net loss" verdict for the same subscription in another). The LLM's job
    here is narration grounded in numbers it is handed, not computation.
    """
    stats = compute_annual_report_stats()
    by_mode_rows = [r for r in stats["by_mode"] if r["mode"] != "Total"]
    top_emitter = max(by_mode_rows, key=lambda r: r["co2_kg"]) if by_mode_rows else None
    top_emitter_share_pct = (
        round(100 * top_emitter["co2_kg"] / stats["total_co2_kg"]) if top_emitter and stats["total_co2_kg"] else 0
    )
    warnings_text = "; ".join(stats["data_quality_warnings"]) if stats["data_quality_warnings"] else "None."

    return f"""\
You are the Annual Report agent for your Mobility Advisor.
Today's date: {_TODAY}.

The Optimizer has produced this recommendation:
{{recommendation}}

The Analyst produced this usage report:
{{analysis}}

The Forecaster produced this outlook:
{{forecast}}

Authoritative figures for {_REVIEW_YEAR}, computed in code (use these exact numbers in your
prose below — never recompute, re-derive, or contradict them):
- Total trips: {stats['total_trips']}, dominant mode by trip count: {stats['dominant_mode']}
- Total CO₂ footprint, ALL modes: {stats['total_co2_kg']} kg
- Largest emission source: {top_emitter['mode'] if top_emitter else 'n/a'} ({top_emitter['co2_kg'] if top_emitter else 0} kg, ~{top_emitter_share_pct}% of the total footprint)
- CO₂ avoided on regional trips by choosing rail over a generic car-share for the same
  distance: {stats['rail_vs_car_saving_kg']} kg (rail: {stats['rail_co2_g_per_km']} g/km vs. car-share: {stats['carshare_co2_g_per_km']} g/km) — this is a secondary, rail-only figure and is NOT subtracted from the total footprint above.

Your job: produce a full annual mobility review that speaks directly to
the user as "you"/"your" throughout — not by name.

Structure your output EXACTLY as follows.

---
# Your Annual Mobility Review

**Period covered:** 1 January – 31 December {_REVIEW_YEAR}

---

## 1. Year at a Glance

Output exactly this line for this section, verbatim, and nothing else — the table is inserted
automatically afterward:
<!-- GLANCE_TABLE -->

---

## 2. Spend & Emissions by Mode

Output exactly this line for this section, verbatim, and nothing else — the table is inserted
automatically afterward:
<!-- BY_MODE_TABLE -->

---

## 3. Sustainability

Write 2–4 sentences of honest, plain-language narrative using ONLY the authoritative figures
given above. Explicitly name the largest emission source and its approximate share of the
total footprint — do not lead with or imply a "green year" framing if flights or another
high-emission mode dominate. You may separately mention the rail-vs-car-share saving as a
smaller, secondary positive, clearly distinguished from the total footprint.

---

## 4. Subscription Value

Output exactly this line for this section, verbatim, and nothing else — the content is inserted
automatically afterward:
<!-- SUBSCRIPTION_VALUE -->

---

## 5. Recommendations & Actions

State plainly, as a labeled line, whether any contract changes were executed this year. If
execution is mocked/pending (the normal case), write exactly:

> **Actions taken this year:** None.
> **Pending proposal:** awaiting your approval (see below).

Then include the optimizer's proposed change from {{recommendation}} as a single bullet. If
{{recommendation}} indicates a change was actually approved/executed, state that instead under
"Actions taken this year" and only list remaining open proposals under "Pending proposal".

---

## 6. Forward Outlook

Summarise {{forecast}} in 2–3 sentences: what demand signals suggest about the next quarter and whether the current portfolio still fits.

---

## 7. Methodology & Assumptions

- State that all data used is mock/synthetic, for demonstration purposes.
- State that every figure in this report is scoped to trips dated in {_REVIEW_YEAR} only —
  trips outside this year are excluded.
- State that BahnCard 50's discount value is computed only from Deutsche Bahn rail trips (fares
  already reflect the ~50% BahnCard discount, so the discount value equals the amount paid);
  other rail providers (e.g. FlixTrain) are not BahnCard fares and are excluded from that figure.
- Data quality notes: {warnings_text}

---
⚠️ **This report is informational. No changes have been made to your subscriptions.**
---
"""


annual_communicator_agent = LlmAgent(
    name="annual_communicator",
    model=_MODEL,
    description="Formats a full annual mobility review for the user from the optimizer's findings.",
    instruction=_annual_communicator_instruction,
    tools=[],
    generate_content_config=build_content_config(_LONG_REPORT_TOKENS),
    include_contents="none",
)
