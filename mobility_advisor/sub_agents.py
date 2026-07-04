import json
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("KICONNECT_API_KEY", ""))
os.environ.setdefault("OPENAI_API_BASE", "https://chat.kiconnect.nrw/api/v1")

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from .tools import (
    load_calendar_events,
    load_current_subscriptions,
    load_mobility_catalog,
    load_travel_history,
    load_user_preferences,
)

_MODEL = LiteLlm(model="openai/OpenAI GPT OSS 120b KI:Inferenz.nrw")  # options: "openai/OpenAI GPT OSS 120b KI:Inferenz.nrw", "openai/Mistral Small 4 119B 2603", "openai/Mistral Small 3-2-24b Instruct KI:Inferenz.nrw"


def build_model() -> LiteLlm:
    """Return the shared LiteLlm singleton used by all pipeline agents."""
    return _MODEL
_TODAY = date.today().isoformat()
_DATA_DIR = Path(__file__).parent / "data"
_prefs = json.loads((_DATA_DIR / "persona.json").read_text())
_USER_NAME = _prefs.get("name", "the user")
_USER_FIRST_NAME = _USER_NAME.split()[0]

analyst_agent = LlmAgent(
    name="analyst",
    model=_MODEL,
    description=f"Analyzes {_USER_FIRST_NAME}'s travel history and current subscriptions to identify portfolio inefficiencies.",
    instruction=f"""\
You are the Analyst agent for your Mobility Advisor.
Today's date: {_TODAY}.

You MUST call load_travel_history and load_current_subscriptions first. Use ONLY the exact figures returned by the tools — do not use any outside knowledge of pricing or cashback rates. Report all numbers verbatim from the tool output.

Your job: report usage facts for each active subscription. Do not draw conclusions or make recommendations — that is another agent's job.

Step 1 — call load_travel_history() and load_current_subscriptions(). Do this before writing anything.

Step 2 — for each subscription, report:
- **Subscription name** and monthly cost (verbatim from tool)
- **Trip count**: how many trips in the past 12 months used this subscription (from travel history)
- **Spend figures**: total amount paid under this subscription in the past 12 months (verbatim from tool data)
- **Renewal**: billing_cycle and next_renewal_date (verbatim from tool)

Keep the output concise — bullet points, no prose paragraphs. Report only what the data shows.

Your output is consumed by downstream agents, not displayed to the user. Write it as a clean structured report. Do not include questions, offers, follow-up prompts, or any conversational phrase at the end.
""",
    tools=[load_travel_history, load_current_subscriptions],
    output_key="analysis",
)

forecaster_agent = LlmAgent(
    name="forecaster",
    model=_MODEL,
    description=f"Forecasts {_USER_FIRST_NAME}'s forward mobility demand for the next 3–6 months based on {_USER_FIRST_NAME}'s calendar.",
    instruction=f"""\
You are the Forecaster agent for your Mobility Advisor.
Today's date: {_TODAY}.

Your job: summarize forward mobility demand for the next 3–6 months from today.

Step 1 — call load_calendar_events(). Do this before writing anything.

Step 2 — produce a brief forward-demand summary (3–5 bullet points):
- Expected dominant modes (rail, local transit, car-share, etc.)
- Approximate long-distance trip volume
- Any life-event signals that could meaningfully shift the portfolio (e.g. relocation, work-pattern change)
- Any notable gaps or uncertainties

Be factual and brief. Do not recommend actions — that is the Optimizer's job.

Your output is consumed by downstream agents, not displayed to the user. Write it as a clean structured report. Do not include questions, offers, follow-up prompts, or any conversational phrase at the end.
""",
    tools=[load_calendar_events],
    output_key="forecast",
)

optimizer_agent = LlmAgent(
    name="optimizer",
    model=_MODEL,
    description="Proposes one concrete contract change based on analysis, forecast, preferences, and catalog.",
    instruction=f"""\
You are the Optimizer agent for your Mobility Advisor.
Today's date: {_TODAY}.

Context from upstream agents:
- Analyst finding: {{analysis}}
- Forecaster outlook: {{forecast}}

Your job: propose exactly ONE concrete contract change that maximizes value for the user.
Address the user directly as "you"/"your" throughout your output — not by name.

Step 1 — call load_user_preferences() and load_mobility_catalog(). Do this before writing anything. Subscription names, costs, billing cycles, and next_renewal_date values are already in the Analyst finding above — do not re-fetch them.

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

Step 3 — output your recommendation in this exact structure:

**Proposed change:** [what to add / cancel / swap]

**Current monthly cost:** €X.XX/mo (list all active subscriptions and their costs)
**Proposed monthly cost:** €Y.YY/mo (list the new stack)
**Monthly saving:** €Z.ZZ/mo

**CO₂ impact:** Use this exact formula — do NOT invent a number:
  co2_rail_kg = Σ(trip.distance_km × 32) / 1000    (rail: 32 g/km from catalog)
  co2_car_kg  = Σ(trip.distance_km × 118) / 1000   (car-share baseline: 118 g/km from catalog)
  co2_saved_kg = co2_car_kg − co2_rail_kg
Compute only over trips whose mode is "rail". Write: "By choosing rail over car, you avoided X kg CO₂ over the past 12 months (rail: 32 g/km vs. car-share: 118 g/km). Total rail distance: Y km." State the Y km sum explicitly so the figure is traceable.

**Action deadline:** For any subscription being cancelled or changed, state the next_renewal_date from the Analyst finding: "Cancel/change before [next_renewal_date] to avoid auto-renewal." Do not hardcode the date — extract it from {{analysis}}.

**What stays and why:**
- [subscription] — [one-line justification with the key metric]

**Why this change:**
- [bullet-point rationale referencing the analysis, forecast, and user preferences]

Show real numbers from the data. Do not propose more than one change.
""",
    tools=[load_user_preferences, load_mobility_catalog],
    output_key="recommendation",
)

communicator_agent = LlmAgent(
    name="communicator",
    model=_MODEL,
    description=f"Formats the optimizer's recommendation into a clear, scannable message for {_USER_FIRST_NAME}.",
    instruction=f"""\
You are the Communicator agent for your Mobility Advisor.
Today's date: {_TODAY}.

The Optimizer has produced this recommendation:
{{recommendation}}

Your job: reformat it into a friendly, scannable message that speaks directly to
the user as "you"/"your" throughout — not by name.

Structure your output exactly as follows:

---
**Your Mobility Advisor Report**

**Recommendation:** [one-sentence headline]

**What's changing:**
- [the proposed change, with the monthly saving in €]
- Action by: **[next_renewal_date from the recommendation, formatted as DD Month YYYY]** to avoid auto-renewal

**CO₂ impact:** [one line]

**What stays in your portfolio:**
- [subscription] — [reason, with the key number that justifies it]
- [subscription] — [reason]

**Why now:** [1–2 sentences referencing your upcoming calendar or life events]

**Trade-offs to consider:** [1–2 sentences on any downside or uncertainty]

---
⚠️ **No change has been made to your subscriptions. This recommendation awaits your approval.**
---

Keep the tone direct and professional. Do not invent numbers not present in the recommendation. Do not claim any action was taken.
""",
    tools=[],
)

# Annual report pipeline instances — ADK forbids sharing agent instances across SequentialAgents,
# so these are separate objects with distinct names but identical instructions and output_keys.
annual_analyst_agent = LlmAgent(
    name="annual_analyst",
    model=_MODEL,
    description=analyst_agent.description,
    instruction=analyst_agent.instruction,
    tools=[load_travel_history, load_current_subscriptions],
    output_key="analysis",
)

annual_forecaster_agent = LlmAgent(
    name="annual_forecaster",
    model=_MODEL,
    description=forecaster_agent.description,
    instruction=forecaster_agent.instruction,
    tools=[load_calendar_events],
    output_key="forecast",
)

annual_optimizer_agent = LlmAgent(
    name="annual_optimizer",
    model=_MODEL,
    description=optimizer_agent.description,
    instruction=optimizer_agent.instruction,
    tools=[load_user_preferences, load_mobility_catalog],
    output_key="recommendation",
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

**Period covered:** 1 January – 31 December [derive year from the oldest trip date in {{analysis}}]

---

## 1. Year at a Glance

| Metric | Value |
|--------|-------|
| Total mobility spend | €X (sum of all subscription costs + trip costs from {{analysis}}) |
| Estimated savings vs. full price | €X (BC50 discount savings from {{analysis}}) |
| CO₂ avoided vs. car-share baseline | X kg |
| Dominant transport mode | [mode with highest trip count] |
| Total trips logged | X |

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
- List any data quality warnings from {{analysis}} (null costs, unknown modes, etc.).
- State that all rail trip costs are assumed to reflect the BC50 50% discount, so full price = cost × 2.

---
⚠️ **This report is informational. No changes have been made to your subscriptions.**
---
""",
    tools=[],
)
