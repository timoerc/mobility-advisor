import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("KICONNECT_API_KEY", ""))
os.environ.setdefault("OPENAI_API_BASE", "https://chat.kiconnect.nrw/api/v1")

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from .tools import (
    MOCK_TODAY,
    REVIEW_YEAR,
    compute_co2_impact_kg,
    compute_portfolio_score,
    derive_car_usage_trips,
    derive_projected_trips_from_calendar,
    derive_projected_trips_from_history,
    load_annual_travel_history,
    load_calendar_events,
    load_car_usage,
    load_current_subscriptions,
    load_relevant_mobility_catalog,
    load_simulation_candidates,
    load_travel_history,
    load_user_preferences,
    merge_projected_trip_sets,
    simulate_portfolio,
)

_MODEL = LiteLlm(model="openai/OpenAI GPT OSS 120b KI:Inferenz.nrw")  # options: "openai/OpenAI GPT OSS 120b KI:Inferenz.nrw", "openai/Mistral Small 4 119B 2603", "openai/Mistral Small 3-2-24b Instruct KI:Inferenz.nrw"


def build_model() -> LiteLlm:
    """Return the shared LiteLlm singleton used by all pipeline agents."""
    return _MODEL


# Output-length tiers for the pipeline agents below (see build_content_config).
_SHORT_REPORT_TOKENS = 4096   # analyst / forecaster: trip projection summaries
_MEDIUM_REPORT_TOKENS = 4096  # communicator: structured recommendation with scoring breakdown
_OPTIMIZER_TOKENS = 8192      # optimizer: simulation results + scoring analysis
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
_prefs = json.loads((_DATA_DIR / "persona.json").read_text(encoding="utf-8"))
_USER_NAME = _prefs.get("name", "the user")
_USER_FIRST_NAME = _USER_NAME.split()[0]
_profile = _prefs.get("profileData", {})
_USER_HOME_CITY = _profile.get("location", {}).get("home_city", "unknown")

analyst_agent = LlmAgent(
    name="analyst",
    model=_MODEL,
    description=f"Derives projected trips from {_USER_FIRST_NAME}'s travel history.",
    instruction=f"""\
You are the Analyst agent for your Mobility Advisor.
Today's date: {_TODAY}.

Your job: derive projected recurring trips from historical travel patterns.

Step 1 — call load_travel_history() to examine the user's travel history.

Step 2 — call derive_projected_trips_from_history(). This tool:
- Groups historical trips by route (direction-independent)
- Extrapolates to annual frequency
- Computes per-mode alternatives (rail, car_share, car_rental, flight) with cost/time/CO2
- Writes the result to _projected_trips_history.json

Step 3 — output a summary of what was projected:
- How many recurring routes were found
- Total projected annual trips
- For each route: route name, annual frequency, and number of mode alternatives
- Any warnings from the tool

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
    description=f"Derives projected trips from {_USER_FIRST_NAME}'s calendar, car usage, and life events, then merges all trip sources.",
    instruction=f"""\
You are the Forecaster agent for your Mobility Advisor.
Today's date: {_TODAY}.

Your job: derive projected trips from calendar events, car usage, and life events,
then merge all trip sources into a single projected trip set.

The Analyst has already derived projected trips from travel history.

Step 1 — call load_calendar_events() to see the user's upcoming events over the next 12 months.

Step 2 — for each calendar event that implies a trip to a DIFFERENT city,
call derive_projected_trips_from_calendar(origin, destination, frequency_per_year).
The user's home city is {_USER_HOME_CITY} — always use "{_USER_HOME_CITY}" as the origin parameter.
Estimate frequency: a weekly recurring meeting = 48/yr, a monthly event = 12/yr, a one-off trip = 1/yr.
Skip events that are local (location is {_USER_HOME_CITY} or same city), virtual/online,
or life events without a concrete travel destination.

Step 3 — call load_car_usage() to check if the user has car usage data. If monthly_km_estimate > 0,
call derive_car_usage_trips() to generate car-based projected trips.

Step 4 — call merge_projected_trip_sets() to combine all sources (history, calendar, car usage)
into a single merged trip set. This tool also flags duplicate routes across sources.

Step 5 — output a summary:
- How many trips from each source (history, calendar, car usage)
- Total merged trips and annual instances
- Any duplicate warnings
- Life-event signals from the calendar that could shift mobility needs

Keep the output concise — bullet points, no prose. Your output is consumed by downstream agents.
Do not include questions, offers, or conversational phrases at the end.
""",
    tools=[
        load_calendar_events,
        derive_projected_trips_from_calendar,
        derive_car_usage_trips,
        load_car_usage,
        merge_projected_trip_sets,
    ],
    output_key="forecast",
    generate_content_config=build_content_config(_MEDIUM_REPORT_TOKENS),
    include_contents="none",
)

# Frozen verbatim copy of the pre-multi-candidate optimizer instruction/description,
# used only to build annual_optimizer_agent below. annual_communicator_agent's Step 4
# ("include the optimizer's proposed change as a single bullet") and the rest of the
# annual report are written against this single-candidate shape and must not receive
# optimizer_agent's multi-candidate output.
_ANNUAL_OPTIMIZER_DESCRIPTION_BASE = "Proposes one concrete contract change based on analysis, forecast, preferences, and catalog."
_ANNUAL_OPTIMIZER_INSTRUCTION_BASE = f"""\
You are the Optimizer agent for your Mobility Advisor.
Today's date: {_TODAY}.

Context from upstream agents:
- Analyst finding: {{analysis}}
- Forecaster outlook: {{forecast}}

Your job: propose exactly ONE concrete contract change that maximizes value for the user.
Address the user directly as "you"/"your" throughout your output — not by name.

Step 1 — call load_user_preferences() and load_relevant_mobility_catalog(). Do this before writing anything. Subscription names, costs, billing cycles, and next_renewal_date values are already in the Analyst finding above — do not re-fetch them.

Step 2 — combining the upstream findings with the user's preferences and the market catalog, identify the single highest-impact change.

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

NAMING — always use the exact, full product name as it appears in load_relevant_mobility_catalog's
"product" field (e.g. "BahnCard 25 (2. Klasse, Standard, Jahresabo)") or in the Analyst
finding's subscription names — never a short form like "BahnCard 25" alone. The catalog has
several same-numbered tiers (Standard, Young, Senior, Probe, 1st/2nd class) that a short
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
- [bullet-point rationale referencing the analysis, forecast, and user preferences]

Show real numbers from the data. Do not propose more than one change.
"""

optimizer_agent = LlmAgent(
    name="optimizer",
    model=_MODEL,
    description="Simulates subscription portfolios and finds the mathematically optimal one via scoring.",
    instruction=f"""\
You are the Optimizer agent for your Mobility Advisor.
Today's date: {_TODAY}.

Context from upstream agents:
- Analyst finding: {{analysis}}
- Forecaster outlook: {{forecast}}

Your job: simulate candidate subscription portfolios against the merged projected trips
and find the optimal portfolio using mathematical scoring.

Step 1 — call load_user_preferences() and load_simulation_candidates().

Step 2 — generate 5–10 candidate portfolios to simulate. Always include:
- [] (empty list = "Do Nothing" / no subscriptions baseline)
- Each single chooseable subscription alone (e.g. ["db_bc25_2nd_annual_standard"])
- The user's current subscriptions (from {{analysis}})
- 2–3 sensible combinations (e.g. BahnCard + Deutschlandticket, BahnCard + MILES tier)

Do NOT include subscriptions filtered out by load_simulation_candidates (1st class BahnCards,
BC100, automatic tiers like Enterprise/Miles&More).

Step 3 — for each candidate portfolio, call simulate_portfolio(subscription_ids).
Collect all simulation results.

Step 4 — call compute_portfolio_score(simulation_results, weights) with the user's
preference weights from Step 1. This returns a ranked list with normalized scores.

Step 5 — output a structured report with the scoring weights from load_user_preferences,
the ranked portfolios from compute_portfolio_score, and a recommended portfolio.
Include the score, annual cost, travel time, and CO2 for each portfolio.
If "Do Nothing" ranks #1, say so clearly.
Show real numbers from simulation results. Do not invent figures.
Your output is consumed by downstream agents. Do not include questions or conversational phrases.
""",
    tools=[load_user_preferences, load_simulation_candidates, simulate_portfolio, compute_portfolio_score],
    output_key="recommendation",
    generate_content_config=build_content_config(_OPTIMIZER_TOKENS),
    include_contents="none",
)

communicator_agent = LlmAgent(
    name="communicator",
    model=_MODEL,
    description=f"Presents the portfolio optimization results as a clear, scannable report for {_USER_FIRST_NAME}.",
    instruction=f"""\
You are the Communicator agent for your Mobility Advisor.
Today's date: {_TODAY}.

The Optimizer has produced a portfolio ranking with simulation results:
{{recommendation}}

Your job: present the results as a friendly, scannable report that speaks directly to
the user as "you"/"your" throughout — not by name.

Structure your output exactly as follows:

---
**Your Mobility Portfolio Optimization**

**Recommended portfolio:** [name of the #1 ranked portfolio]
[one-sentence summary of why it wins]

**Scoring breakdown** (weights from your preferences):

| Portfolio | Score | Annual Cost | Travel Time | CO₂ |
|-----------|-------|-------------|-------------|-----|
| [#1 name] | [score] | €[cost] | [time] min | [co2] kg |
| [#2 name] | [score] | €[cost] | [time] min | [co2] kg |
| ... | ... | ... | ... | ... |

**What the recommended portfolio means for you:**
- Subscriptions: [list subscriptions in the portfolio, or "None" for Do Nothing]
- Annual subscription cost: €[amount]
- Annual trip cost (after discounts): €[amount]
- Total annual mobility cost: €[amount]
- How you'd travel: [describe the dominant modes for your trips]

**Compared to doing nothing:**
- Cost difference: €[amount saved or extra] per year
- Time difference: [minutes saved or extra] per year
- CO₂ difference: [kg saved or extra] per year

**Cross-mode highlights:**
[If the simulation shows interesting mode switches — e.g. rail beating car-share on certain
routes, or flight being optimal for long distances — call them out in 2–3 bullets]

---
⚠️ **No change has been made to your subscriptions. This recommendation awaits your approval.**
---

Keep the tone direct and professional. Use all numbers verbatim from the Optimizer's output.
Do not invent numbers. If "Do Nothing" is the best option, say so clearly — do not spin it.
""",
    tools=[],
    generate_content_config=build_content_config(_MEDIUM_REPORT_TOKENS),
    include_contents="none",
)

# Annual report pipeline instances — ADK forbids sharing agent instances across SequentialAgents,
# so these are separate objects with distinct names. Forecaster's instruction is reused verbatim
# (forward-looking, not year-scoped); analyst and optimizer instructions are derived from their
# non-annual counterparts via targeted replacement so both the tool call and the wording are
# scoped to REVIEW_YEAR — without this, the report's stated period and its actual figures could
# silently diverge (the analyst would report on the full unfiltered history again).
annual_analyst_agent = LlmAgent(
    name="annual_analyst",
    model=_MODEL,
    description=analyst_agent.description,
    instruction=(
        analyst_agent.instruction
        .replace(
            f"Today's date: {_TODAY}.",
            f"Today's date: {_TODAY}. This report covers only calendar year {_REVIEW_YEAR} "
            f"— every figure must be scoped to {_REVIEW_YEAR} only.",
        )
        .replace("load_travel_history", "load_annual_travel_history")
        .replace("in the past 12 months", f"in {_REVIEW_YEAR}")
        + f"""

Step 3 — after the subscription summary, output a "Trips considered ({_REVIEW_YEAR})" table listing
EVERY trip returned by load_annual_travel_history(), one row per trip, verbatim — do not omit,
summarize, or round any trip. Columns: date | mode | origin → destination | distance_km | cost_eur | provider.
This table exists so the report's figures can be manually cross-checked against the raw data — completeness
matters more than brevity here.
"""
    ),
    tools=[load_annual_travel_history, load_current_subscriptions],
    output_key="analysis",
    generate_content_config=build_content_config(_MEDIUM_REPORT_TOKENS),
)

annual_forecaster_agent = LlmAgent(
    name="annual_forecaster",
    model=_MODEL,
    description=forecaster_agent.description,
    instruction=forecaster_agent.instruction,
    tools=[load_calendar_events],
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
    tools=[load_user_preferences, load_relevant_mobility_catalog, compute_co2_impact_kg],
    output_key="recommendation",
    generate_content_config=build_content_config(_MEDIUM_REPORT_TOKENS),
    include_contents="none",
)

annual_communicator_agent = LlmAgent(
    name="annual_communicator",
    model=_MODEL,
    description=f"Formats a full annual mobility review for {_USER_FIRST_NAME} from the optimizer's findings.",
    instruction=f"""\
You are the Annual Report agent for your Mobility Advisor.
Today's date: {_TODAY}.

The Optimizer has produced this recommendation:
{{recommendation}}

The Analyst produced this usage report:
{{analysis}}

The Forecaster produced this outlook:
{{forecast}}

Your job: produce a full annual mobility review that speaks directly to
the user as "you"/"your" throughout — not by name.

Structure your output EXACTLY as follows. Use all figures verbatim from the upstream context — do not invent numbers.

---
# Your Annual Mobility Review

**Period covered:** 1 January – 31 December {_REVIEW_YEAR}

---

## 1. Year at a Glance

| Metric | Value |
|--------|-------|
| Total mobility spend | €X (sum of all subscription costs + trip costs from {{analysis}}) |
| Estimated savings vs. full price | €X (BC50 discount savings from {{analysis}}) |
| CO₂ avoided vs. car-share baseline | X kg |
| Dominant transport mode | [mode with highest trip count] |
| Total trips logged | X |

IMPORTANT: output ONLY that 5-row table for this section, nothing else. Each "Value" cell must be a
single computed number/label you derived — never paste, quote, or reproduce raw text, bullet points,
or the trips table from {{analysis}} here. The full trip-by-trip data belongs only in Section 7 below.

---

## 2. Subscription ROI

For each active subscription, report whether it broke even over the year.

Use this format for each:

**[Product name]** — €X.XX/mo (€X.XX/yr)
- Trips attributed: X
- Value delivered: €X in discounts / unlimited regional travel used X times / etc.
- Verdict: ✅ Paid off / ⚠️ Borderline / ❌ Did not break even
- Key figure: [the single number that determines the verdict]

---

## 3. CO₂ Report

Compute from {{analysis}} using these exact formulas:
- Rail trips: distance_km × 32 g/km ÷ 1000 = kg CO₂
- Car-share baseline: same distance × 118 g/km ÷ 1000 = kg CO₂
- CO₂ avoided = car-share baseline − rail actual

Write:
> You traveled X km by rail, emitting X kg CO₂. Choosing rail over car avoided X kg CO₂ (rail: 32 g/km vs. car-share: 118 g/km).

Then list mode split: X% rail, X% regional, X% car-share, etc. by trip count.

---

## 4. Recommendations Taken This Year

List any optimizer recommendations from {{recommendation}} that were noted as approved. If execution is mocked/pending, write:

> ⚠️ No contract changes have been executed yet. The recommendation below is awaiting approval.

Then include the optimizer's proposed change as a single bullet.

---

## 5. Forward Outlook

Summarise {{forecast}} in 2–3 sentences: what demand signals suggest about the next quarter and whether the current portfolio still fits.

---

## 6. Assumptions & Data Quality

- State which data is mock/synthetic.
- State that all figures in this report are limited to trips dated in {_REVIEW_YEAR} — trips outside this year are excluded.
- List any data quality warnings from {{analysis}} (null costs, unknown modes, etc.).
- State that all rail trip costs are assumed to reflect the BC50 50% discount, so full price = cost × 2.

---

## 7. Trips Considered (Verification)

Output exactly this line for this section, verbatim, and nothing else — do not reproduce, summarize,
or add any trip data yourself here; the real trip table is inserted automatically afterward:
<!-- TRIPS_TABLE_PLACEHOLDER -->

---
⚠️ **This report is informational. No changes have been made to your subscriptions.**
---
""",
    tools=[],
    generate_content_config=build_content_config(_LONG_REPORT_TOKENS),
    include_contents="none",
)
