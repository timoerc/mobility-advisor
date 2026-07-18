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
    load_analyst_context,
    load_annual_analyst_context,
    load_annual_optimizer_context,
    load_forecaster_context,
    load_optimizer_context,
)

_MODEL = LiteLlm(model="openai/OpenAI GPT OSS 120b KI:Inferenz.nrw")  # options: "openai/OpenAI GPT OSS 120b KI:Inferenz.nrw", "openai/Mistral Small 4 119B 2603", "openai/Mistral Small 3-2-24b Instruct KI:Inferenz.nrw"


def build_model() -> LiteLlm:
    """Return the shared LiteLlm singleton used by all pipeline agents."""
    return _MODEL


# Output-length tiers for the pipeline agents below (see build_content_config).
_SHORT_REPORT_TOKENS = 2048   # analyst / forecaster: concise bullet-point summaries. Bumped
# from 1024 — analyst/forecaster each gained an extra tool call (load_car_usage,
# load_life_events) plus more required output. GPT-OSS-120B's internal reasoning tokens count
# against max_output_tokens, so with the old 1024 budget the reasoning across 3 sequential
# tool calls could exhaust it before any visible text was written, producing an empty
# response — confirmed empirically against Stefan's larger dataset (3 subscriptions):
# 1024 tokens -> 1/4 successful runs, 2048 tokens -> 4/4.
_MEDIUM_REPORT_TOKENS = 4096  # optimizer / communicator: structured recommendation with numeric
# derivations. Bumped from 2048 — the optimizer picked up the same kind of extra load
# (load_optimizer_context's 3-way bundle, plus 1-2 compute_co2_impact_kg calls per candidate,
# plus the new PREFERENCE WEIGHTING/CONTINUITY reasoning) that motivated the _SHORT_REPORT_TOKENS
# bump above, but was left at the old budget. Reproduced directly: a live run against Maja's
# data had the optimizer make 3 tool-call rounds (~70s of reasoning) and then return an empty
# final response, which crashed the pipeline with `KeyError: Context variable not found:
# 'recommendation'` when the communicator tried to read {recommendation} from session state —
# the same failure mode, just previously undersized for a different agent.
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
    scenario the three demo personas (maja/stefan/lena) exist to exercise live.
    """
    prefs = json.loads((_DATA_DIR / "persona.json").read_text())
    return prefs.get("profileData", {}).get("location", {}).get("home_city", "")


def _forecaster_instruction(_ctx: ReadonlyContext) -> str:
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
    description="Analyzes the user's travel history and current subscriptions to identify portfolio inefficiencies.",
    instruction=f"""\
You are the Analyst agent for your Mobility Advisor.
Today's date: {_TODAY}.

You MUST call load_analyst_context() first. Use ONLY the exact figures returned by the tool — do not use any outside knowledge of pricing or cashback rates. Report all numbers verbatim from the tool output.

Your job: report usage facts for each active subscription. Do not draw conclusions or make recommendations — that is another agent's job.

Step 1 — call load_analyst_context(). This returns travel history (key 'travel_history'), current subscriptions (key 'current_subscriptions'), and car usage (key 'car_usage') together in one call. Do this before writing anything.

Step 2 — for each subscription, report:
- **Subscription name** and monthly cost (verbatim from tool)
- **Trip count**: how many trips in the past 12 months used this subscription (from travel history)
- **Spend figures**: total amount paid under this subscription in the past 12 months (verbatim from tool data)
- **Renewal**: billing_cycle and next_renewal_date (verbatim from tool)
- **Duration/ticket type**: where a trip's duration_min and ticket_type fields are present in the travel history data, mention them alongside the trip count — this surfaces travel time, not just cost, for later steps that weigh time

Step 3 — report private car ownership from load_analyst_context()'s car_usage field: if owns_car is true, state "Holds a private <type> <size> car, ~<monthly_km_estimate> km/month"; if false, state "No private car."

Keep the output concise — bullet points, no prose paragraphs. Report only what the data shows.

Your output is consumed by downstream agents, not displayed to the user. Write it as a clean structured report. Do not include questions, offers, follow-up prompts, or any conversational phrase at the end.
""",
    tools=[load_analyst_context],
    output_key="analysis",
    generate_content_config=build_content_config(_SHORT_REPORT_TOKENS),
)

forecaster_agent = LlmAgent(
    name="forecaster",
    model=_MODEL,
    description="Forecasts the user's forward mobility demand for the next 3–6 months based on their calendar.",
    instruction=_forecaster_instruction,
    tools=[load_forecaster_context],
    output_key="forecast",
    generate_content_config=build_content_config(_SHORT_REPORT_TOKENS),
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

Step 1 — call load_annual_optimizer_context(). This returns user preferences (key 'user_preferences') and the user-relevant mobility catalog (key 'relevant_mobility_catalog') together in one call. Do this before writing anything. Subscription names, costs, billing cycles, and next_renewal_date values are already in the Analyst finding above — do not re-fetch them.

Step 2 — combining the upstream findings with the user's preferences and the market catalog, identify the single highest-impact change.

PREFERENCE WEIGHTING — load_annual_optimizer_context()'s user_preferences field returns priority_weights (raw cost/time/
sustainability floats summing to ~1.0). Use these, not just sustainability_weight/
values_time_over_money, to decide WHICH change is your pick, not merely how you phrase it:
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
    description="Proposes one or (when genuinely comparable) up to two candidate actions based on analysis, forecast, preferences, and catalog — normally concrete contract changes, but holding the portfolio pending an unresolved near-term life decision when the data flags one.",
    instruction=f"""\
You are the Optimizer agent for your Mobility Advisor.
Today's date: {_TODAY}.

Context from upstream agents:
- Analyst finding: {{analysis}}
- Forecaster outlook: {{forecast}}

Your job: propose the highest-value action(s) for the user's contract portfolio. Default to
exactly ONE recommended change. Only propose a second candidate action when it is genuinely
comparable in value to the first AND materially different in kind — never as padding. See the
CANDIDATE CAP rule in Step 3 for the exact bar a second candidate must clear.
Address the user directly as "you"/"your" throughout your output — not by name.

Step 1 — call load_optimizer_context(). This returns user preferences (key 'user_preferences'), the user-relevant mobility catalog (key 'relevant_mobility_catalog'), and recent recommendation history (key 'recommendation_history') together in one call. Do this before writing anything. Subscription names, costs, billing cycles, and next_renewal_date values are already in the Analyst finding above — do not re-fetch them.

Step 2 — combining the upstream findings with the user's preferences and the market catalog, identify the highest-impact change(s), applying the CANDIDATE CAP rule below to decide whether one or two candidates are warranted.

CONTINUITY — check load_optimizer_context()'s recommendation_history field's past entries. If a prior review already
flagged the same subscription with the same (or an equivalent) recommended_action, acknowledge
that continuity explicitly instead of re-stating the finding as if it were new, e.g. "This is
the Nth review flagging <subscription> — you kept it before; here's the updated picture." If
the history is empty or unrelated to this review's finding, say nothing about it.

PENDING PORTFOLIO DECISION (deferral gate) — load_optimizer_context()'s pending_portfolio_decision
field is a deterministic signal of whether an unresolved, near-term life event (a relocation or
work-pattern change) would reset the user's whole portfolio. Honor its "exists" flag EXACTLY —
do not second-guess it from the forecast prose:
- If pending_portfolio_decision.exists is FALSE (the normal case — most reviews): you MUST NOT
  propose any hold / defer / "wait and see" candidate, and MUST NOT mention deferral at all.
  Proceed exactly as you otherwise would — pick the highest-value concrete change(s). Stop
  reading this section.
- If pending_portfolio_decision.exists is TRUE: you MUST add ONE extra candidate block, a
  "Hold pending decision" candidate, ALONGSIDE the single best concrete change, and you MUST
  mark the Hold candidate Recommended: YES and the concrete change Recommended: NO. The
  pending reset makes acting now premature: any change justified by the move happening (or by
  it NOT happening) is a bet on a decision that is not resolved yet, so holding until it
  resolves is the correct call. Do NOT mark the concrete change Recommended in this case, and
  do NOT rationalise acting now with "the ticket looks unused" or "the move probably makes it
  redundant" — that is exactly the premature call the Hold exists to prevent, because it
  silently assumes one outcome of the very decision that is still open. Still include the
  concrete change as the second (Recommended: NO) candidate, so the user can see the option
  they are choosing to defer.
  Fill the Hold candidate's Step 3 block using the SAME structure as any other candidate, with
  these field values (this reuses the existing shape — it is not a new format):
    - Candidate name: "Hold pending decision"
    - Proposed change: "Make no change now — hold [list every current subscription by exact
      name] as-is until the pending decision resolves."
    - Proposed monthly cost: equal to the Current portfolio cost (nothing changes).
    - Monthly saving: €0.00/mo — deliberate; it avoids a change the decision could reverse.
    - CO₂ impact: state "Neutral — no change (0 kg)". Do NOT call compute_co2_impact_kg for
      this candidate; there is no product change to price.
    - Action deadline: "Revisit after <the pending_portfolio_decision.revisit_after date> once
      the pending change resolves." Use that revisit_after date, NOT a renewal date.
    - What stays and why: every current subscription — all kept intact pending the decision.
    - Why this candidate: cite pending_portfolio_decision.reason and the specific event
      summaries from pending_portfolio_decision.events, and note that the acting-now
      candidate's figures would themselves be reset if the change goes ahead.

PREFERENCE WEIGHTING (does NOT apply when the PENDING PORTFOLIO DECISION gate above is active —
there the Hold is always the Recommended pick regardless of weights) — load_optimizer_context()'s
user_preferences field returns priority_weights (raw cost/time/
sustainability floats summing to ~1.0). Use these, not just sustainability_weight/
values_time_over_money, to decide WHICH candidate is your Recommended pick, not merely how you
phrase it:
- Weight each candidate's €-saving, time/convenience impact, and CO2 impact by these three
  weights before choosing the winner. A candidate that wins on the user's highest-weighted
  dimension can outrank a candidate that only wins on a lower-weighted one, even with a smaller
  raw €-saving.
- If sustainability is the highest weight (or clearly elevated vs. the other two), prefer a
  CO2-reducing candidate at modest extra cost over a cheaper but CO2-neutral one.
- If values_time_over_money is true, never recommend a slower or less convenient option purely
  because it saves money.
- State explicitly in "Why this candidate" which preference weight(s) drove the pick — this
  must be visible reasoning, not just a number used silently.

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

NAMING — always use the exact, full product name as it appears in load_optimizer_context()'s
relevant_mobility_catalog field's "product" field (e.g. "BahnCard 25 (2. Klasse, Standard, Jahresabo)")
or in the Analyst finding's subscription names — never a short form like "BahnCard 25" alone. The
catalog has several same-numbered tiers (Standard, Young, Senior, Probe, 1st/2nd class) that a short
name cannot distinguish, and this name is what gets executed later — an underspecified name
cannot be applied. This applies everywhere you name a specific product, in every candidate block.

Step 3 — output your recommendation in this exact structure:

**Current portfolio cost:** €X.XX/mo (list all active subscriptions and their costs)

For EACH candidate action (see CANDIDATE CAP below), repeat this entire block — do not merge
two candidates into one block, and do not omit any sub-field:

## Candidate: [short name, e.g. "Cancel BahnCard 50" or "Downgrade to BahnCard 25"]
**Recommended:** [YES for exactly one candidate — your single highest-value pick — NO for every other candidate]
**Proposed change:** [what to add / cancel / swap — if this is a swap/replace, explicitly
name BOTH the exact current subscription being removed AND the exact new product being
added, e.g. "Replace your BahnCard 50 (2. Klasse, Standard, Jahresabo) with a BahnCard 25
(2. Klasse, Standard, Jahresabo)" — never just "Downgrade to BahnCard 25"]
**Proposed monthly cost:** €Y.YY/mo (list the new stack)
**Monthly saving:** €Z.ZZ/mo (vs. Current portfolio cost above)
**CO₂ impact:** Call compute_co2_impact_kg with THIS candidate's own target_subscription/
new_product (same names as this candidate's Proposed change above — never another candidate's)
and state its "explanation" field verbatim — do NOT compute CO₂ yourself or invent a number.
(Exception: a "Hold pending decision" candidate makes no product change — state "Neutral — no
change (0 kg)" and do NOT call compute_co2_impact_kg for it.)
**Action deadline:** For any subscription being cancelled or changed, state the next_renewal_date from the Analyst finding: "Cancel/change before [next_renewal_date] to avoid auto-renewal." Do not hardcode the date — extract it from {{analysis}}.
**What stays and why:**
- [subscription] — [one-line justification with the key metric]
**Why this candidate:** [bullet-point rationale referencing the analysis, forecast, and user preferences — including which preference weight(s) (cost/time/sustainability) drove this pick per PREFERENCE WEIGHTING above — and, if there is more than one candidate, what specifically makes this one different in kind from the others, not just in degree]

CANDIDATE CAP: propose at most 2 candidate blocks total. Default to exactly 1. Only add a
second candidate when it is genuinely comparable in value to the first AND materially
different in kind — e.g. a different discrete plan tier (BahnCard 25 vs. BahnCard 50), full
cancellation vs. a partial downgrade of the same subscription, or a genuinely different mode
(e.g. a car-share membership instead of a rail card) — never two candidates that differ only
by a small numeric variation on the same underlying choice (e.g. rounding, or a €2/month gap
between near-identical options). If you are unsure whether a second candidate clears this bar,
do not include it — one strong recommendation beats a padded list. When the PENDING PORTFOLIO
DECISION gate above is active (exists=TRUE), the "Hold pending decision" candidate and the
single best concrete change ARE the two candidates — that pairing is a sanctioned use of this
2-candidate cap, not padding, and you must not add a third.

Show real numbers from the data.
""",
    tools=[load_optimizer_context, compute_co2_impact_kg],
    output_key="recommendation",
    generate_content_config=build_content_config(_MEDIUM_REPORT_TOKENS),
    include_contents="none",
)

communicator_agent = LlmAgent(
    name="communicator",
    model=_MODEL,
    description="Formats the optimizer's recommendation (one or, when warranted, up to two candidate actions) into a clear, scannable message for the user.",
    instruction=f"""\
You are the Communicator agent for your Mobility Advisor.
Today's date: {_TODAY}.

The Optimizer has produced this recommendation, containing one or two candidate actions:
{{recommendation}}

Your job: reformat it into a friendly, scannable message that speaks directly to
the user as "you"/"your" throughout — not by name. If the Optimizer proposed more than one
candidate, present all of them, clearly marking which one is the recommended pick — never
invent a candidate that isn't in the Optimizer's output, and never drop one that is.

Structure your output exactly as follows:

---
**Your Mobility Advisor Report**

**Your current setup:** €X.XX/mo (copy the Optimizer's "Current portfolio cost" line and
subscription list verbatim)

**Recommendation:** [one-sentence headline for the candidate marked Recommended: YES]

For EACH candidate action from the Optimizer, in the same order, repeat this block:

**Option: [short candidate name]**[append " — Recommended" only on the candidate marked Recommended: YES]
- Change: [the proposed change, one sentence]
- Monthly cost: €Y.YY/mo (saving €Z.ZZ/mo vs. your current setup) — copy these two numbers
  verbatim from this candidate's own "Proposed monthly cost" / "Monthly saving" lines, never
  the other candidate's numbers
- Action by: **[next_renewal_date, formatted as DD Month YYYY]** to avoid auto-renewal
- CO₂ impact: [one line]
- Trade-off: [1–2 sentences on the downside or uncertainty specific to THIS candidate]

HOLD CANDIDATE: if a candidate is a "Hold pending decision" one (its Monthly saving is €0.00/mo
and it proposes making no change now), adapt exactly two of its lines and leave the rest as
normal: render "- Monthly cost: €Y.YY/mo (no change)" (no saving clause), and replace the
"Action by … to avoid auto-renewal" line with "- Revisit by: **[the candidate's revisit date
from its Action deadline, formatted as DD Month YYYY]** — once your pending move/job decision
resolves". Never invent this candidate — only render it when the Optimizer actually produced it.

(Output exactly one Option block per candidate the Optimizer actually gave you — never add a
second Option block if the Optimizer proposed only one.)

**What stays in your portfolio:**
- [subscription] — [reason, with the key number that justifies it]
- [subscription] — [reason]

**Why now:** [1–2 sentences referencing your upcoming calendar or life events]

---
⚠️ **No change has been made to your subscriptions. This recommendation awaits your approval.**
---

Keep the tone direct and professional. Do not invent numbers not present in the recommendation.
Do not claim any action was taken. Do not shorten or paraphrase a product name — copy it exactly
as given in the recommendation above (e.g. keep "BahnCard 25 (2. Klasse, Standard, Jahresabo)"
intact, never just "BahnCard 25"). Every Option block's "Change" line must name both the exact
subscription being removed and the exact product being added for a swap/replace — this wording
is what gets executed later if the user picks that option, so an underspecified name breaks
execution for whichever option the user ends up choosing, not just the recommended one.
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
#
# No raw per-trip table is requested here (unlike an earlier version): the annual report's
# headline spend/CO2/subscription-value figures are now computed deterministically by
# compute_annual_report_stats() and rendered by main.py, and a by-mode summary table replaces
# what used to be a full trip-by-trip dump — a raw ledger a reader can't act on isn't
# professional annual-report content. See annual_communicator_agent below.
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
        .replace("load_analyst_context", "load_annual_analyst_context")
        .replace("in the past 12 months", f"in {_REVIEW_YEAR}")
    ),
    tools=[load_annual_analyst_context],
    output_key="analysis",
    generate_content_config=build_content_config(_MEDIUM_REPORT_TOKENS),
)

annual_forecaster_agent = LlmAgent(
    name="annual_forecaster",
    model=_MODEL,
    description=forecaster_agent.description,
    instruction=forecaster_agent.instruction,
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
