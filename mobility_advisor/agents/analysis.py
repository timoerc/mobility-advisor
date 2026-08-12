"""Analyst and Forecaster — the first two stages of optimization_pipeline. The Analyst
derives projected trips from travel history; the Forecaster derives them from calendar/
car usage/life events and merges all three sources into the file the deterministic
Optimizer scores."""
from google.adk.agents import LlmAgent

from ..engine.projection import (
    derive_car_usage_trips,
    derive_projected_trips_from_calendar,
    derive_projected_trips_from_history,
    merge_projected_trip_sets,
)
from ..store.loaders import load_calendar_events, load_car_usage, load_life_events, load_travel_history
from .model import _MEDIUM_REPORT_TOKENS, _SHORT_REPORT_TOKENS, _TODAY, ReadonlyContext, _load_home_city, _MODEL, build_content_config


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
