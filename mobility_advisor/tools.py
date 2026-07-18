import calendar
import csv
import json
import os
import re
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from .models import (
    AnalysisHistory,
    CalendarEvents,
    CarUsage,
    CurrentSubscriptions,
    LifeEvents,
    MobilityCatalog,
    Subscription,
    TravelHistory,
    UserPreferences,
)

_DATA = Path(__file__).parent / "data"
_STATIC = Path(__file__).parent / "static"

USE_MOCK_DATA = True

# Frozen so mock scenarios stay reproducible regardless of the host machine's real date.
# Sourced from persona.json's "reference_date" (single source of truth, swapped in whenever
# a scenario is activated) so the fixtures and the app's notion of "today" can't drift apart.
_DEFAULT_REFERENCE_DATE = date(2026, 6, 15)


def _load_reference_date() -> date:
    try:
        raw = json.loads((_DATA / "persona.json").read_text())
        return date.fromisoformat(raw["reference_date"])
    except (FileNotFoundError, KeyError, ValueError):
        return _DEFAULT_REFERENCE_DATE


MOCK_TODAY = _load_reference_date()
REVIEW_YEAR = MOCK_TODAY.year - 1  # annual report always covers the last full calendar year

def load_user_preferences() -> dict:
    """Load the active user's mobility preferences derived from their persona profile.

    Returns a dict with keys: name (str), flexibility_need (str: low/medium/high),
    sustainability_weight (float 0-1, rounded), values_time_over_money (bool), notes (str),
    home_city (str), office_days (list[str], weekday codes e.g. "mon"), wfh_days (list[str]),
    and priority_weights (dict: cost/time/sustainability, the raw un-rounded priority floats
    that sum to ~1.0 — use these, not sustainability_weight/values_time_over_money alone, to
    weight which candidate to recommend).
    """
    raw = json.loads((_DATA / "persona.json").read_text())
    pd = raw["profileData"]
    wfh = pd["commute"]["wfh_days"]
    n = len(wfh)
    flexibility = "high" if n >= 4 else "medium" if n >= 2 else "low"
    p = pd["priorities"]
    prefs = {
        "name": pd["personal"]["full_name"] or "the user",
        "flexibility_need": flexibility,
        "sustainability_weight": round(p["sustainability"], 4),
        "values_time_over_money": p["time"] > p["cost"],
        "notes": pd.get("notes", ""),
        "home_city": pd.get("location", {}).get("home_city", ""),
        "office_days": pd["commute"].get("office_days", []),
        "wfh_days": wfh,
        "priority_weights": {
            "cost": p["cost"],
            "time": p["time"],
            "sustainability": p["sustainability"],
        },
    }
    return UserPreferences.model_validate(prefs).model_dump()


def load_life_events() -> dict:
    """Load life-event signals distilled offline from the active user's mail.

    A life event is a relocation, job change, mobility-relevant subscription change
    (activation/cancellation/non-renewal), household change, or other notable context
    (e.g. a recurring non-mobility subscription) — never raw mail; this is always the
    small, pre-extracted fixture life_events.json.

    Returns a dict with key 'events', a list of entries each containing: category (str:
    relocation/job_change/subscription_change/household_change/other), summary (str, one
    line), event_date (str or null, ISO date the event itself takes effect), signals
    (list[str], short machine-readable tags), source_mail_id (str or null), and detected_on
    (str, ISO date the extraction ran). An empty list is a legitimate result meaning no
    life-event signal was found in the user's mail — not a loading failure.
    """
    path = _DATA / "life_events.json"
    if not path.exists():
        return {"events": []}
    raw = json.loads(path.read_text())
    return LifeEvents.model_validate(raw).model_dump()


# Signals whose arrival would, on their own, invalidate the current commute-based
# portfolio if it takes effect — a home relocation or a change of work pattern resets
# which subscriptions make sense at all. Lower-impact signals (income_change,
# d_ticket_relevance_change, rail_card_relevance_change, non_mobility_spend, ...)
# deliberately do NOT gate deferral: they refine an existing setup rather than reset it,
# so the normal optimize-now path still applies. This narrow set is what keeps the
# "hold pending a decision" recommendation from ever firing spuriously (e.g. for Lena,
# whose only signals are ticket-relevance/spend changes, or Maja, who has none).
_PORTFOLIO_RESET_SIGNALS = frozenset({"home_base_change", "work_pattern_change"})

# How far ahead an unresolved reset event may sit and still justify holding. A move a
# couple of months out is worth waiting for; one years away should not freeze the
# portfolio indefinitely, so beyond this horizon the normal optimize-now path resumes.
_DECISION_HORIZON_DAYS = 275  # ~9 months


def detect_pending_portfolio_decision() -> dict:
    """Detect whether an unresolved, near-term life event would reset the portfolio.

    This is the deterministic gate for the Optimizer's "hold / defer pending a decision"
    recommendation: the pipeline may only propose holding subscriptions instead of acting
    now when this returns exists=True. It fires only for a genuine portfolio-resetting
    change — a relocation or work-pattern change (a life event whose signals include
    home_base_change or work_pattern_change) that is still upcoming (event_date on/after
    today) and lands within ~9 months. A persona with no life events (e.g. Maja), or only
    lower-impact signals such as a ticket-relevance or non-mobility-spend change (e.g.
    Lena), returns exists=False, so their reviews behave exactly as before. Once every
    qualifying event's date has passed (the move has happened or been called off), it
    returns exists=False again — the setup should then be re-optimized against the new
    reality, not held indefinitely.

    Returns a dict with keys:
      - exists (bool): whether a deferral-worthy pending decision was found.
      - reason (str): one-line explanation of the pending decision; "" when exists is False.
      - revisit_after (str | None): ISO date the last qualifying event takes effect — the
        point by which the uncertainty is certainly resolved and the review should be
        re-run; None when exists is False.
      - events (list[dict]): the qualifying life events (category, summary, event_date,
        signals), empty when exists is False.
    """
    today = MOCK_TODAY
    horizon_end = today + timedelta(days=_DECISION_HORIZON_DAYS)
    qualifying: list[tuple[dict, date]] = []
    for event in load_life_events()["events"]:
        if not (_PORTFOLIO_RESET_SIGNALS & set(event.get("signals", []))):
            continue
        raw_date = event.get("event_date")
        if not raw_date:
            continue  # undated reset signal: can't confirm it's near-term or unresolved
        try:
            event_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        if today <= event_date <= horizon_end:
            qualifying.append((event, event_date))

    if not qualifying:
        return {"exists": False, "reason": "", "revisit_after": None, "events": []}

    revisit_after = max(event_date for _, event_date in qualifying)
    categories = "/".join(sorted({event["category"] for event, _ in qualifying}))
    reason = (
        f"A pending {categories} is expected to take effect by "
        f"{revisit_after.isoformat()}, which would reset the current commute-based "
        f"portfolio — acting now risks a change the decision could immediately reverse."
    )
    return {
        "exists": True,
        "reason": reason,
        "revisit_after": revisit_after.isoformat(),
        "events": [
            {
                "category": event["category"],
                "summary": event["summary"],
                "event_date": event.get("event_date"),
                "signals": event.get("signals", []),
            }
            for event, _ in qualifying
        ],
    }


def load_car_usage() -> dict:
    """Load the active user's private car ownership/usage facts from the mock data store.

    Returns a dict with keys: owns_car (bool), mode (str, always "car_private"), type (str
    or null, e.g. Petrol/Diesel/Electric/Hybrid), size (str or null, e.g. "Medium car"), and
    monthly_km_estimate (float or null). All fields are false/null for a persona without a
    private car — that is a real "no private car" fact, not a missing-data gap.
    """
    raw = json.loads((_DATA / "car_usage.json").read_text())
    return CarUsage.model_validate(raw).model_dump()


def load_recommendation_history(limit: int = 3) -> dict:
    """Load a compact summary of the user's most recent past analysis recommendations and outcomes.

    Use this to give continuity to a new review — e.g. noting that this is the Nth review
    flagging the same subscription, and what the user decided last time — instead of
    re-analyzing cold every run.

    Returns a dict with key 'history', a list of up to the `limit` most recent entries
    (oldest first, newest last), each containing: date (str), verdict (str, that review's
    headline finding), outcome (str: pending/kept_current/executed), and recommended_action
    (str, the name of the alternative that review marked as recommended). Deliberately
    excludes full Recommendation/Alternative objects (metrics, reasoning, non-recommended
    alternatives) to keep this small. Returns an empty list if no analysis history exists yet
    (e.g. a brand-new persona) — that is a legitimate result, not a loading failure.
    """
    path = _DATA / "analysis_history.json"
    if not path.exists():
        return {"history": []}
    raw = json.loads(path.read_text())
    entries = AnalysisHistory.model_validate(raw).entries[-limit:]
    history = []
    for entry in entries:
        recommended = next(
            (alt for alt in entry.recommendation.alternatives if alt.isRecommended), None
        )
        history.append({
            "date": entry.date,
            "verdict": entry.recommendation.verdict,
            "outcome": entry.outcome,
            "recommended_action": recommended.name if recommended else "",
        })
    return {"history": history}


def load_current_subscriptions() -> dict:
    """Load the active user's currently held mobility subscriptions from the mock data store.

    Returns a dict with key 'subscriptions', a list of entries. Every entry is a full,
    exact mirror of one mobility_catalog.json product (enforced at validation time —
    a subscription can only ever reference a real catalog id), plus two
    subscription-specific fields. Every field below is always present; none are ever
    missing, and only next_renewal_date/started can be an empty string (never absent).

    id (str), provider (str), product (str), mode (str: rail/car_share/car_rental/
    flight/bus), monthly_cost_eur (float), billing_cycle (str), minimum_months (int),
    eligibility (dict: min_age/max_age, either may be null), benefits (dict, shape
    varies by mode), qualifying_threshold (dict or null, shape varies by mode),
    affiliated_airlines (list[str] or null, flight mode only), notes (str),
    next_renewal_date (str, "" if not applicable), started (str, "" if not applicable).
    """
    raw = json.loads((_DATA / "current_subscriptions.json").read_text())
    return CurrentSubscriptions.model_validate(raw).model_dump()


def load_mobility_catalog() -> dict:
    """Load the market-side mobility products catalog including pricing and benefits data.

    Returns a dict with key 'options', a list of available products each containing:
    id (str), provider (str), product (str), mode (str: rail/car_share/car_rental/flight/bus),
    monthly_cost_eur (float), benefits (dict), eligibility (dict), qualifying_threshold (dict or null).
    """
    raw = json.loads((_STATIC / "mobility_catalog.json").read_text())
    return MobilityCatalog.model_validate(raw).model_dump()


def load_relevant_mobility_catalog() -> dict:
    """Load the market catalog narrowed to options relevant to the active user.

    Same shape as load_mobility_catalog() (key 'options'), but filtered by two
    deterministic signals computed from the user's own data — not an embedding
    or relevance ranking:
      1. Mode relevance: drop a whole mode category (rail/car_share/car_rental/
         flight/bus) only if the user has never held a subscription in it nor
         taken a trip in it.
      2. Age eligibility: drop an option the user could not actually sign up
         for, per persona.json's age and the option's eligibility range.
    Each kept option also has its 'notes' field dropped — that field is
    free-text prose that duplicates numbers already present in 'benefits'/
    'monthly_cost_eur' on the same option.

    If applying the filter would remove every option (e.g. a brand-new profile
    with no subscriptions or trips yet), returns the full unfiltered catalog
    instead — with no usage signal, no filter criterion is trustworthy, and an
    empty catalog is worse than an oversized one.

    Use this (not load_mobility_catalog) when proposing or comparing contract
    options for the current user. load_mobility_catalog stays the source of
    truth for arbitrary lookups about any product regardless of relevance.
    """
    catalog = load_mobility_catalog()["options"]

    subs = load_current_subscriptions()["subscriptions"]
    trips = load_travel_history()["trips"]
    touched_modes = {s["mode"] for s in subs} | {
        t["mode"] for t in trips if t.get("mode")  # trips stay a messier data source, unchanged
    }

    persona = json.loads((_DATA / "persona.json").read_text())
    age = persona.get("profileData", {}).get("personal", {}).get("age")

    def eligible(option: dict) -> bool:
        if option["mode"] not in touched_modes:
            return False
        if age is None:
            return True
        elig = option["eligibility"]  # always present as a dict of {min_age, max_age}
        min_age, max_age = elig["min_age"], elig["max_age"]
        if min_age is not None and age < min_age:
            return False
        if max_age is not None and age > max_age:
            return False
        return True

    filtered = [
        {k: v for k, v in option.items() if k != "notes"}
        for option in catalog
        if eligible(option)
    ]
    return {"options": filtered or catalog}


_KNOWN_MODES = {"rail", "car_share", "car_rental", "flight", "bus"}


def _travel_history_result(trips: list) -> dict:
    """Build the load_travel_history return shape (trips + data_quality_warnings) for a given trip list."""
    warnings = []
    for trip in trips:
        label = f"{trip.date} {trip.origin}→{trip.destination}"
        if trip.cost_eur is None:
            warnings.append(f"{label}: cost_eur is null — excluded from spend totals")
        if not trip.mode:
            warnings.append(f"{label}: mode is empty — excluded from CO₂ and mode aggregations")
        elif trip.mode not in _KNOWN_MODES:
            warnings.append(f"{label}: unknown mode '{trip.mode}' — excluded from CO₂ and mode aggregations")

    result = {"trips": [t.model_dump() for t in trips]}
    if warnings:
        result["data_quality_warnings"] = warnings
    return result


def load_travel_history() -> dict:
    """Load Maja's 12-month travel history from the mock data store.

    Returns a dict with key 'trips', a list of past trips each containing:
    date (str), mode (str), origin (str), destination (str), distance_km (float),
    cost_eur (float or null), provider (str), booked_under (str or null).
    If any trips have data quality issues, a 'data_quality_warnings' key is included
    listing each problem so downstream agents can surface them to the user.
    """
    raw = json.loads((_DATA / "travel_history_raw.json").read_text())
    history = TravelHistory.model_validate(raw)
    return _travel_history_result(history.trips)


def load_annual_travel_history() -> dict:
    """Load travel history for the annual report, scoped to REVIEW_YEAR only.

    Same shape as load_travel_history, but trips outside REVIEW_YEAR (the last full
    calendar year) are excluded before any downstream agent sees them — the annual
    report's stated period must only ever reflect data actually filtered to that year,
    not the full unfiltered history.
    """
    raw = json.loads((_DATA / "travel_history_raw.json").read_text())
    history = TravelHistory.model_validate(raw)
    year_trips = [t for t in history.trips if t.date.startswith(str(REVIEW_YEAR))]
    return _travel_history_result(year_trips)


def load_calendar_events() -> dict:
    """Load upcoming calendar events — from mock data or live Outlook API.

    Returns a dict with key 'events', a list of upcoming events each containing:
    date (str), type (str: trip/meeting/life_event), description (str),
    location (str or null), signals (list[str] — demand or life-change indicators).
    """
    if USE_MOCK_DATA:
        raw = json.loads((_DATA / "calendar_events_live.json").read_text())
    else:
        from .outlook_calendar import fetch_calendar_events
        raw = fetch_calendar_events()
    return CalendarEvents.model_validate(raw).model_dump()


def load_analyst_context() -> dict:
    """Load all fixed-context data the Analyst agent needs, in one call: travel history,
    current subscriptions, and car usage.

    Internally calls load_travel_history(), load_current_subscriptions(), and
    load_car_usage() and returns their results together under one dict. This exists
    purely to save two tool-call round-trips versus calling the three individually — it
    changes zero fields and zero values versus calling them separately.

    Returns a dict with keys:
      - travel_history: exactly load_travel_history()'s return value (key 'trips', list
        of trip dicts; optional 'data_quality_warnings' list).
      - current_subscriptions: exactly load_current_subscriptions()'s return value (key
        'subscriptions', list of subscription dicts).
      - car_usage: exactly load_car_usage()'s return value (owns_car, mode, type, size,
        monthly_km_estimate).
    """
    return {
        "travel_history": load_travel_history(),
        "current_subscriptions": load_current_subscriptions(),
        "car_usage": load_car_usage(),
    }


def load_annual_analyst_context() -> dict:
    """Load all fixed-context data the Annual Analyst agent needs, in one call: travel
    history scoped to REVIEW_YEAR, current subscriptions, and car usage.

    Same shape and purpose as load_analyst_context(), with one difference: travel_history
    comes from load_annual_travel_history() (trips outside REVIEW_YEAR excluded) rather
    than load_travel_history() (full unfiltered history) — current_subscriptions and
    car_usage reflect the user's present-day state either way, so they are not
    year-scoped.

    Returns a dict with keys:
      - travel_history: exactly load_annual_travel_history()'s return value (key 'trips',
        list of trip dicts limited to REVIEW_YEAR; optional 'data_quality_warnings' list).
      - current_subscriptions: exactly load_current_subscriptions()'s return value.
      - car_usage: exactly load_car_usage()'s return value.
    """
    return {
        "travel_history": load_annual_travel_history(),
        "current_subscriptions": load_current_subscriptions(),
        "car_usage": load_car_usage(),
    }


def load_forecaster_context() -> dict:
    """Load all fixed-context data the Forecaster agent needs, in one call: upcoming
    calendar events and life-event signals.

    Internally calls load_calendar_events() and load_life_events() and returns their
    results together — saves one tool-call round-trip versus calling them individually;
    changes zero fields and zero values. Shared verbatim by forecaster_agent and
    annual_forecaster_agent — both need identical, forward-looking (not year-scoped) data.

    Returns a dict with keys:
      - calendar_events: exactly load_calendar_events()'s return value (key 'events').
      - life_events: exactly load_life_events()'s return value (key 'events'; an empty
        list is a legitimate result, not a loading failure).
    """
    return {
        "calendar_events": load_calendar_events(),
        "life_events": load_life_events(),
    }


def load_optimizer_context() -> dict:
    """Load all fixed-context data the Optimizer agent needs up front, in one call: user
    preferences, the user-relevant mobility catalog, and recent recommendation history.

    Internally calls load_user_preferences(), load_relevant_mobility_catalog(),
    load_recommendation_history(), and detect_pending_portfolio_decision() and returns
    their results together — saves three tool-call round-trips versus calling them
    individually; changes zero fields and zero values.

    Does NOT include compute_co2_impact_kg — that tool stays a separate, on-demand call
    invoked once per candidate action in Step 3 (with different target_subscription/
    new_product arguments each time), not once up front like the loaders bundled here.

    Returns a dict with keys:
      - user_preferences: exactly load_user_preferences()'s return value.
      - relevant_mobility_catalog: exactly load_relevant_mobility_catalog()'s return
        value (key 'options').
      - recommendation_history: exactly load_recommendation_history()'s return value
        (key 'history', up to the 3 most recent entries).
      - pending_portfolio_decision: exactly detect_pending_portfolio_decision()'s return
        value (keys exists/reason/revisit_after/events) — the deterministic gate for the
        Optimizer's "hold pending a decision" recommendation. exists=False for personas
        with no near-term portfolio-resetting life event, which is the normal case.
    """
    return {
        "user_preferences": load_user_preferences(),
        "relevant_mobility_catalog": load_relevant_mobility_catalog(),
        "recommendation_history": load_recommendation_history(),
        "pending_portfolio_decision": detect_pending_portfolio_decision(),
    }


def load_annual_optimizer_context() -> dict:
    """Load all fixed-context data the Annual Optimizer agent needs up front, in one
    call: user preferences and the user-relevant mobility catalog.

    Internally calls load_user_preferences() and load_relevant_mobility_catalog() and
    returns their results together — saves one tool-call round-trip versus calling them
    individually; changes zero fields and zero values.

    Deliberately excludes recommendation_history (unlike load_optimizer_context, the
    regular Optimizer's equivalent): the annual report's instruction has no CONTINUITY
    section referencing past recommendations, so recent-history data stays out of this
    agent's tool surface, matching annual_optimizer_agent's existing tools=[...] scoping.

    Does NOT include compute_co2_impact_kg — same reasoning as load_optimizer_context:
    stays a separate, on-demand per-candidate call.

    Returns a dict with keys:
      - user_preferences: exactly load_user_preferences()'s return value.
      - relevant_mobility_catalog: exactly load_relevant_mobility_catalog()'s return
        value (key 'options').
    """
    return {
        "user_preferences": load_user_preferences(),
        "relevant_mobility_catalog": load_relevant_mobility_catalog(),
    }


def compute_travel_stats(
    subscription_or_provider: str | None = None,
    mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    origin_filter: str | None = None,
    destination_filter: str | None = None,
) -> dict:
    """Aggregate Maja's travel history: trip counts, total spend, and distance, with optional filters.

    Use this for ANY counting, summing, or date-range question about trips — never tally
    the travel history JSON yourself.

    Args:
        subscription_or_provider: Optional filter, e.g. "BahnCard 50" or "Deutsche Bahn".
            Matched case-insensitively as a substring against each trip's booked_under
            field OR its provider field (a match on either counts). Pass None for no filter.
        mode: Optional exact-match filter on trip mode (e.g. "rail", "car_share"). Pass None for no filter.
        date_from: Optional inclusive ISO date string ("YYYY-MM-DD"); trips before this are excluded.
        date_to: Optional inclusive ISO date string ("YYYY-MM-DD"); trips after this are excluded.
        origin_filter: Optional substring to match against the trip's origin station name
            (case-insensitive). E.g. "Frankfurt" matches "Frankfurt (Main) Hbf". Pass None for no filter.
        destination_filter: Optional substring to match against the trip's destination station
            name (case-insensitive). Pass None for no filter.

    Returns a dict with keys: trip_count (int), total_spend_eur (float, sums only trips with
    non-null cost_eur), total_distance_km (float), trips_missing_cost (int, count of matched
    trips with null cost_eur), matched_filters (dict echoing the filters applied),
    subscription_renewal (dict with next_renewal_date/billing_cycle, or null — set when
    subscription_or_provider matches an entry in current_subscriptions.json by the same
    substring rule), and data_quality_warnings (list[str], unfiltered passthrough from
    load_travel_history so data issues are never hidden by a filter).
    """
    history_data = load_travel_history()
    trips = TravelHistory.model_validate({"trips": history_data["trips"]}).trips
    needle = subscription_or_provider.lower() if subscription_or_provider else None
    origin_needle = origin_filter.lower() if origin_filter else None
    destination_needle = destination_filter.lower() if destination_filter else None

    def matches(trip) -> bool:
        if mode is not None and trip.mode != mode:
            return False
        if date_from is not None and trip.date < date_from:
            return False
        if date_to is not None and trip.date > date_to:
            return False
        if origin_needle is not None and origin_needle not in trip.origin.lower():
            return False
        if destination_needle is not None and destination_needle not in trip.destination.lower():
            return False
        if needle is not None:
            booked = (trip.booked_under or "").lower()
            if needle not in booked and needle not in trip.provider.lower():
                return False
        return True

    matched = [trip for trip in trips if matches(trip)]
    total_spend_eur = sum(trip.cost_eur for trip in matched if trip.cost_eur is not None)
    total_distance_km = sum(trip.distance_km for trip in matched)
    trips_missing_cost = sum(1 for trip in matched if trip.cost_eur is None)

    subscription_renewal = None
    if needle is not None:
        subs = load_current_subscriptions()["subscriptions"]
        sub_match, _ = _resolve_unique_match(needle, subs, ("product", "provider"))
        if sub_match is not None:
            subscription_renewal = {
                "next_renewal_date": sub_match["next_renewal_date"],
                "billing_cycle": sub_match["billing_cycle"],
            }

    return {
        "trip_count": len(matched),
        "total_spend_eur": round(total_spend_eur, 2),
        "total_distance_km": round(total_distance_km, 2),
        "trips_missing_cost": trips_missing_cost,
        "matched_filters": {
            "subscription_or_provider": subscription_or_provider,
            "mode": mode,
            "date_from": date_from,
            "date_to": date_to,
            "origin_filter": origin_filter,
            "destination_filter": destination_filter,
        },
        "subscription_renewal": subscription_renewal,
        "data_quality_warnings": history_data.get("data_quality_warnings", []),
    }


def _resolve_unique_match(
    needle: str, candidates: list[dict], fields: tuple[str, ...]
) -> tuple[dict | None, str | None]:
    """Find exactly one candidate whose given fields contain needle as a case-insensitive substring.

    Falls back to token-overlap matching (≥ 2 alphanumeric words in common) when substring
    matching yields no results, to handle language/notation variants such as "2nd class" vs
    "2. Klasse" introduced by LLM paraphrasing.

    Returns (match, None) on exactly one match. Returns (None, error_message) if zero or
    more than one candidate matches — callers must treat both as failure, never guess.
    """
    needle_lower = needle.lower()

    # Primary: case-insensitive substring
    matches = [
        c for c in candidates if any(needle_lower in str(c.get(f, "")).lower() for f in fields)
    ]

    # Fallback: token overlap — handles variants like "2nd class" vs "2. Klasse"
    if not matches:
        needle_tokens = set(re.findall(r'\w+', needle_lower))
        matches = [
            c for c in candidates
            if any(
                len(needle_tokens & set(re.findall(r'\w+', str(c.get(f, "")).lower()))) >= 2
                for f in fields
            )
        ]

    if not matches:
        return None, f"no match for '{needle}'"
    if len(matches) > 1:
        names = ", ".join(c.get("product", "?") for c in matches)
        return None, f"ambiguous match for '{needle}': matched {len(matches)} entries ({names})"
    return matches[0], None


# Only car-sharing (e.g. MILES) requires membership to use the mode at all — rail passes,
# Deutschlandticket, and car-rental loyalty tiers are discount/rewards programs layered on
# top of a mode you can already use without any subscription (full-price ticket, pay-as-you-go
# rental), so losing them changes price, not which mode is usable.
_MODE_ACCESS_GATED_MODES = {"car_share"}


def _generic_car_co2_factor_kg_per_km() -> float:
    """kg CO2e/km for driving a car with no specific type/size known — the fallback used when
    a candidate removes the user's only access to car-sharing. Car_private/Car_Sharing/
    Car_Rental all share the same 'Null,Null' average in co2_factors.csv, so it doesn't matter
    which of the three the user would actually end up driving."""
    with (_STATIC / "co2_factors.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["mode"] == "Car_Sharing" and row["type"] == "Null" and row["size"] == "Null":
                return float(row["kg_co2e_per_km"])
    raise RuntimeError("Car_Sharing,Null,Null row missing from co2_factors.csv")


def _rail_and_carshare_co2_factors() -> tuple[float, float]:
    """Return (rail, car_share) generic CO2 factors in g/km, sourced from co2_factors.csv's
    Rail/Null/Null and Car_Sharing/Null/Null rows — the same generic-average rows
    _generic_car_co2_factor_kg_per_km already reads for the optimizer, so the annual report's
    fixed CO2 formula can never disagree with the optimizer's own per-candidate CO2 math about
    what a generic rail/car-share km costs. Used to interpolate real figures into
    annual_communicator's prompt instead of a hardcoded assumption."""
    rail_kg_per_km: float | None = None
    car_share_kg_per_km: float | None = None
    with (_STATIC / "co2_factors.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["type"] != "Null" or row["size"] != "Null":
                continue
            if row["mode"] == "Rail":
                rail_kg_per_km = float(row["kg_co2e_per_km"])
            elif row["mode"] == "Car_Sharing":
                car_share_kg_per_km = float(row["kg_co2e_per_km"])
    if rail_kg_per_km is None or car_share_kg_per_km is None:
        raise RuntimeError("Rail,Null,Null or Car_Sharing,Null,Null row missing from co2_factors.csv")
    return round(rail_kg_per_km * 1000, 2), round(car_share_kg_per_km * 1000, 2)


def compute_annual_report_stats() -> dict:
    """Deterministic, code-computed figures for the annual report.

    Spend, CO2, and per-subscription value are calculated here in Python rather than
    left to the LLM, so the report's headline numbers can never silently contradict
    each other the way free-text arithmetic spread across three separate agent stages
    could (e.g. a "savings" figure in one section disagreeing with a "net loss" verdict
    for the same subscription in another). annual_communicator_agent narrates around
    these figures instead of computing them itself; main.py's /api/annual-report
    endpoint substitutes the rendered tables into the report's placeholder sections.

    Trip-to-subscription attribution is done here by (mode, provider) match against
    load_annual_travel_history()'s year-scoped trips — not by the trip data's
    'booked_under' field, which is null for every mock trip and would otherwise make
    every subscription look completely unused.

    Returns a dict with keys:
      - review_year (int)
      - total_spend_eur (float): year-scoped trip costs (cost_eur present only) plus
        every active subscription's annualized fee
      - total_trips (int), trips_missing_cost (int)
      - dominant_mode (str): the mode with the most trips this year ("" if none)
      - by_mode (list[dict]): one row per mode present this year, each
        {mode, trips, distance_km, spend_eur, co2_kg}, sorted by co2_kg descending,
        followed by a final {mode: "Total", ...} row
      - total_co2_kg (float): sum of co2_emission_kg across every trip this year,
        all modes included — the honest total footprint
      - rail_vs_car_saving_kg (float): CO2 avoided by taking rail instead of a generic
        car-share for the same distance, computed over rail trips only. This is a
        secondary "smart regional choice" figure — it is NOT subtracted from
        total_co2_kg, which already reflects what was actually emitted.
      - rail_co2_g_per_km / carshare_co2_g_per_km (float): the factors behind the
        figure above, for the report's methodology section
      - subscriptions (list[dict]): one per active subscription, each
        {product, provider, mode, monthly_cost_eur, billing_cycle, annual_fee_eur,
         is_paid_subscription, trips_attributed, discount_value_eur, net_eur,
         qualifying_activity}. discount_value_eur/net_eur are None for €0 loyalty
        tiers — a break-even verdict is meaningless when there's no fee to break even
        against. qualifying_activity is None unless the subscription carries a usage
        threshold (e.g. Enterprise Silver's rentals_per_year).
      - data_quality_warnings (list[str])
    """
    history = load_annual_travel_history()
    trips = history["trips"]
    warnings = list(history.get("data_quality_warnings", []))

    total_trips = len(trips)
    trips_missing_cost = sum(1 for t in trips if t["cost_eur"] is None)

    by_mode_acc: dict[str, dict] = {}
    for t in trips:
        mode = t["mode"] or "unknown"
        row = by_mode_acc.setdefault(
            mode, {"mode": mode, "trips": 0, "distance_km": 0.0, "spend_eur": 0.0, "co2_kg": 0.0}
        )
        row["trips"] += 1
        row["distance_km"] += t["distance_km"] or 0.0
        row["spend_eur"] += t["cost_eur"] or 0.0
        row["co2_kg"] += t["co2_emission_kg"] or 0.0

    by_mode = sorted(by_mode_acc.values(), key=lambda r: r["co2_kg"], reverse=True)
    for row in by_mode:
        row["distance_km"] = round(row["distance_km"], 1)
        row["spend_eur"] = round(row["spend_eur"], 2)
        row["co2_kg"] = round(row["co2_kg"], 2)

    total_co2_kg = round(sum(r["co2_kg"] for r in by_mode), 2)
    trip_spend_eur = round(sum(r["spend_eur"] for r in by_mode), 2)
    dominant_mode = max(by_mode_acc.values(), key=lambda r: r["trips"])["mode"] if by_mode_acc else ""

    by_mode_with_total = by_mode + [{
        "mode": "Total",
        "trips": total_trips,
        "distance_km": round(sum(r["distance_km"] for r in by_mode), 1),
        "spend_eur": trip_spend_eur,
        "co2_kg": total_co2_kg,
    }]

    rail_g_per_km, carshare_g_per_km = _rail_and_carshare_co2_factors()
    rail_km = sum(t["distance_km"] or 0.0 for t in trips if t["mode"] == "rail")
    rail_vs_car_saving_kg = round(rail_km * (carshare_g_per_km - rail_g_per_km) / 1000, 2)

    subscriptions_raw = load_current_subscriptions()["subscriptions"]
    subscriptions = []
    for sub in subscriptions_raw:
        matched = [
            t for t in trips
            if t["mode"] == sub["mode"] and sub["provider"].lower() in (t["provider"] or "").lower()
        ]
        trips_attributed = len(matched)
        annual_fee_eur = round(sub["monthly_cost_eur"] * 12, 2)
        is_paid = sub["monthly_cost_eur"] > 0

        discount_value_eur = None
        net_eur = None
        if is_paid:
            discount_value_eur = round(
                sum(t["cost_eur"] for t in matched if t["cost_eur"] is not None), 2
            )
            net_eur = round(discount_value_eur - annual_fee_eur, 2)

        qualifying_activity = None
        threshold = sub.get("qualifying_threshold")
        if threshold and threshold.get("rentals_per_year") is not None:
            qualifying_activity = {"count": trips_attributed, "threshold": threshold["rentals_per_year"]}

        subscriptions.append({
            "product": sub["product"],
            "provider": sub["provider"],
            "mode": sub["mode"],
            "monthly_cost_eur": sub["monthly_cost_eur"],
            "billing_cycle": sub["billing_cycle"],
            "annual_fee_eur": annual_fee_eur,
            "is_paid_subscription": is_paid,
            "trips_attributed": trips_attributed,
            "discount_value_eur": discount_value_eur,
            "net_eur": net_eur,
            "qualifying_activity": qualifying_activity,
        })

    total_spend_eur = round(trip_spend_eur + sum(s["annual_fee_eur"] for s in subscriptions), 2)

    return {
        "review_year": REVIEW_YEAR,
        "total_spend_eur": total_spend_eur,
        "total_trips": total_trips,
        "trips_missing_cost": trips_missing_cost,
        "dominant_mode": dominant_mode,
        "by_mode": by_mode_with_total,
        "total_co2_kg": total_co2_kg,
        "rail_vs_car_saving_kg": rail_vs_car_saving_kg,
        "rail_co2_g_per_km": rail_g_per_km,
        "carshare_co2_g_per_km": carshare_g_per_km,
        "subscriptions": subscriptions,
        "data_quality_warnings": warnings,
    }


def compute_co2_impact_kg(
    target_subscription: str | None = None,
    new_product: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Compute the CO2 delta (kg/year) of one candidate portfolio change vs. the current portfolio.

    Grounded in real per-trip co2_emission_kg data (already computed offline from
    co2_factors.csv) — never invents or estimates a distance/emissions figure. Call this for
    EVERY candidate action before writing its CO2 impact line; do not compute CO2 yourself.

    Same add/remove/replace argument shape as apply_subscription_change: target_subscription
    is the current subscription being removed (None for a pure add), new_product is the
    catalog product being added (None for a pure cancel). Matched the same way
    apply_subscription_change matches them (case-insensitive substring against
    product/provider, falling back to token overlap) — must resolve to exactly one entry
    each; zero or multiple matches return an error rather than guessing.

    Most candidates are CO2-neutral by design: a subscription only changes emissions if
    removing it takes away the user's *last* remaining way to use a given transport mode at
    all. In the current catalog that is true only for car-sharing (membership-gated); rail
    cards, Deutschlandticket, and car-rental loyalty tiers are discount/rewards programs on
    top of a mode usable without any subscription, so changing/cancelling them is always
    neutral (0 kg) — e.g. downgrading BahnCard 50 to BahnCard 25 never affects CO2, only price.

    Args:
        target_subscription: Substring/name of the current subscription being removed or
            replaced, matched against current_subscriptions.json. None for a pure "add".
        new_product: Substring/name of the catalog product being added, matched against
            mobility_catalog.json. None for a pure "cancel".
        date_from: Optional inclusive ISO date ("YYYY-MM-DD") — same filter semantics as
            compute_travel_stats. Pass this (with date_to) when evaluating the ANNUAL report
            so affected trips are scoped to REVIEW_YEAR only, not the full travel history.
            Leave both None for the regular (non-annual) review, which uses all available trips.
        date_to: Optional inclusive ISO date ("YYYY-MM-DD"); see date_from.

    Returns a dict with: status ("ok" or "error"), mode_access_changed (bool, whether this
    candidate actually removes the user's last access to a gated mode), delta_kg (float,
    signed — positive means the candidate SAVES this many kg CO2/year vs. the current
    portfolio, negative means it emits this many kg MORE; always 0.0 when
    mode_access_changed is False), co2_before_kg / co2_after_kg (float, only meaningful when
    mode_access_changed is True), trips_affected (int), explanation (str, a ready-to-quote
    one-line sentence stating the signed number plainly — quote this verbatim as the CO2
    impact line, do not paraphrase or recompute it), and error (str or None).
    """

    def _result(
        *,
        mode_access_changed: bool = False,
        delta_kg: float = 0.0,
        co2_before_kg: float = 0.0,
        co2_after_kg: float = 0.0,
        trips_affected: int = 0,
        explanation: str,
        error: str | None = None,
    ) -> dict:
        return {
            "status": "error" if error else "ok",
            "mode_access_changed": mode_access_changed,
            "delta_kg": round(delta_kg, 2),
            "co2_before_kg": round(co2_before_kg, 2),
            "co2_after_kg": round(co2_after_kg, 2),
            "trips_affected": trips_affected,
            "explanation": explanation,
            "error": error,
        }

    if not target_subscription and not new_product:
        return _result(
            explanation="",
            error="at least one of target_subscription or new_product is required",
        )

    subs = load_current_subscriptions()["subscriptions"]
    target_match = None
    if target_subscription:
        target_match, error = _resolve_unique_match(target_subscription, subs, ("product", "provider"))
        if error:
            return _result(explanation="", error=error)

    catalog_match = None
    if new_product:
        catalog_options = load_mobility_catalog()["options"]
        catalog_match, error = _resolve_unique_match(new_product, catalog_options, ("product", "provider"))
        if error:
            return _result(explanation="", error=error)

    # Pure add: no historical trips can be attributed to a mode the user is only now gaining
    # (or a second subscription for a mode they already have) — stated honestly rather than guessed.
    if target_match is None:
        return _result(
            explanation=(
                "Neutral — 0 kg CO2/year. This adds a subscription without removing another, "
                "so it doesn't change which mode you currently use for any trip."
            )
        )

    changed_mode = target_match["mode"]
    if changed_mode not in _MODE_ACCESS_GATED_MODES:
        return _result(
            explanation=(
                "Neutral — 0 kg CO2/year. This changes price/tier only; it doesn't affect "
                f"which mode of transport you use (you can still use {changed_mode} with or "
                "without this subscription)."
            )
        )

    still_covered = (catalog_match is not None and catalog_match["mode"] == changed_mode) or any(
        s["mode"] == changed_mode and s is not target_match for s in subs
    )
    if still_covered:
        return _result(
            explanation=(
                "Neutral — 0 kg CO2/year. You keep another subscription covering "
                f"{changed_mode}, so access to this mode is unaffected."
            )
        )

    trips = load_travel_history()["trips"]
    affected = [
        t
        for t in trips
        if t.get("mode") == changed_mode
        and (date_from is None or t.get("date", "") >= date_from)
        and (date_to is None or t.get("date", "") <= date_to)
    ]
    co2_before_kg = sum(
        t["co2_emission_kg"] for t in affected if t.get("co2_emission_kg") is not None
    )
    generic_factor = _generic_car_co2_factor_kg_per_km()
    co2_after_kg = sum(
        t["distance_km"] * generic_factor for t in affected if t.get("distance_km") is not None
    )
    delta_kg = co2_before_kg - co2_after_kg
    period = "in the period considered" if (date_from or date_to) else "from the past 12 months"

    if delta_kg >= 0:
        explanation = (
            f"{delta_kg:.1f} kg CO2/year saved. Losing your only {changed_mode} subscription "
            f"means your {len(affected)} {changed_mode} trip(s) {period} would "
            f"shift to driving (at {generic_factor * 1000:.0f} g/km), which is actually lower "
            f"emissions than those trips currently produce ({co2_before_kg:.1f} kg → "
            f"{co2_after_kg:.1f} kg)."
        )
    else:
        explanation = (
            f"{abs(delta_kg):.1f} kg CO2/year more emissions. Losing your only {changed_mode} "
            f"subscription means your {len(affected)} {changed_mode} trip(s) {period} "
            f"would shift to driving (at {generic_factor * 1000:.0f} g/km), raising "
            f"emissions from {co2_before_kg:.1f} kg to {co2_after_kg:.1f} kg/year."
        )

    return _result(
        mode_access_changed=True,
        delta_kg=delta_kg,
        co2_before_kg=co2_before_kg,
        co2_after_kg=co2_after_kg,
        trips_affected=len(affected),
        explanation=explanation,
    )


def _add_months(d: date, months: int) -> date:
    """Add a number of months to a date, clamping the day to the target month's last valid day."""
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _compute_next_renewal_date(as_of: date, billing_cycle: str) -> str:
    """Compute the next renewal date as an ISO string from an as-of date and billing cycle."""
    if billing_cycle == "annual":
        return _add_months(as_of, 12).isoformat()
    if billing_cycle == "monthly":
        return _add_months(as_of, 1).isoformat()
    raise ValueError(f"unknown billing_cycle: {billing_cycle!r}")


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write data as JSON to path atomically (temp file + os.replace); never leaves a partial file."""
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def apply_subscription_change(
    action: Literal["add", "remove", "replace"],
    target_subscription: str | None = None,
    new_product: str | None = None,
    as_of: date | None = None,
) -> dict:
    """Apply one confirmed change to Maja's active subscriptions. The sole writer of current_subscriptions.json.

    Only call this after the user has explicitly instructed a specific change — never to
    evaluate whether a change is a good idea. mobility_catalog.json and every other
    fixture stay read-only; only current_subscriptions.json is ever written, and only on
    full success. No write of any kind happens on any error path.

    Args:
        action: "add" a new subscription, "remove" an existing one, or "replace" (remove
            the matched target and add the matched new_product in a single atomic write).
        target_subscription: Required for "remove"/"replace". Matched case-insensitively
            as a substring against each current subscription's product or provider field.
            Must resolve to exactly one subscription — zero or multiple matches both return
            an error with no write, rather than guessing which one was meant.
        new_product: Required for "add"/"replace". Matched the same way against
            mobility_catalog.json's options. Must resolve to exactly one catalog option —
            zero or multiple matches both return an error with no write.
        as_of: The date to treat as "today" when computing the new entry's started date
            and next_renewal_date. Defaults to MOCK_TODAY when omitted. Exists only for
            deterministic testing — leave unset in normal use.

    Returns a dict with: status ("applied" or "error"), action, removed (list of removed
    subscription dicts, empty if none), added (list of added subscription dicts, empty if
    none), before_count (int), after_count (int), file ("current_subscriptions.json"),
    warnings (list[str], e.g. noting a same-product replace), and error (str message, or
    None on success).
    """
    as_of = as_of or MOCK_TODAY
    warnings: list[str] = []

    def _error(message: str, before_count: int = 0) -> dict:
        return {
            "status": "error",
            "action": action,
            "removed": [],
            "added": [],
            "before_count": before_count,
            "after_count": before_count,
            "file": "current_subscriptions.json",
            "warnings": warnings,
            "error": message,
        }

    if action in ("remove", "replace") and not target_subscription:
        return _error(f"target_subscription is required for action={action!r}")
    if action in ("add", "replace") and not new_product:
        return _error(f"new_product is required for action={action!r}")

    # Load raw dicts to preserve all fields beyond the Pydantic model.
    raw_file = json.loads((_DATA / "current_subscriptions.json").read_text())
    subs_list = raw_file["subscriptions"]
    before_count = len(subs_list)

    target_match = None
    if action in ("remove", "replace"):
        target_match, error = _resolve_unique_match(
            target_subscription, subs_list, ("product", "provider")
        )
        if error:
            return _error(error, before_count)

    catalog_match = None
    if action in ("add", "replace"):
        catalog_options = load_mobility_catalog()["options"]
        catalog_match, error = _resolve_unique_match(
            new_product, catalog_options, ("product", "provider")
        )
        if error:
            return _error(error, before_count)

    new_sub = None
    if catalog_match is not None:
        try:
            next_renewal_date = _compute_next_renewal_date(as_of, catalog_match["billing_cycle"])
        except ValueError as exc:
            return _error(str(exc), before_count)
        new_sub = {
            **catalog_match,
            "next_renewal_date": next_renewal_date,
            "started": as_of.isoformat(),
        }
        try:
            Subscription.model_validate(new_sub)
        except (ValueError, ValidationError) as exc:
            return _error(f"new subscription entry failed validation: {exc}", before_count)

    if (
        action == "replace"
        and target_match is not None
        and catalog_match is not None
        and target_match["product"] == catalog_match["product"]
    ):
        warnings.append(
            f"replace target and new_product both resolved to '{catalog_match['product']}' — "
            "this resets the renewal clock on an unchanged product, not a real swap."
        )

    removed = [target_match] if target_match is not None else []
    added = [new_sub] if new_sub is not None else []
    new_subs_list = [s for s in subs_list if s is not target_match]
    if new_sub is not None:
        new_subs_list.append(new_sub)
    after_count = len(new_subs_list)

    try:
        CurrentSubscriptions.model_validate({"subscriptions": new_subs_list})
    except (ValueError, ValidationError) as exc:
        return _error(f"resulting subscriptions failed validation: {exc}", before_count)

    # Write raw dicts (not model_dump) to preserve all fields beyond the pipeline schema.
    _atomic_write_json(_DATA / "current_subscriptions.json", {"subscriptions": new_subs_list})

    return {
        "status": "applied",
        "action": action,
        "removed": removed,
        "added": added,
        "before_count": before_count,
        "after_count": after_count,
        "file": "current_subscriptions.json",
        "warnings": warnings,
        "error": None,
    }
