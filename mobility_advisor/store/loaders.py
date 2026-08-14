"""Loaders for the active persona's mock data store: preferences, subscriptions, market
catalog, travel history, calendar events, car usage, life events, and the bundled
per-agent context helpers that save a tool-call round-trip."""
import json

from .. import clock, paths
from ..i18n import pick, t
from ..models import (
    CalendarEvents,
    CarUsage,
    CurrentSubscriptions,
    LifeEvents,
    MobilityCatalog,
    TravelHistory,
    UserPreferences,
)

USE_MOCK_DATA = True

def load_user_preferences() -> dict:
    """Load the active user's mobility preferences derived from their persona profile.

    Returns a dict with keys: name (str), home_city (str), age (int or null), owns_car
    (bool), values_time_over_money (bool), notes (str), and priority_weights (dict:
    cost/time/sustainability, the raw priority floats from the frontend sliders that sum
    to ~1.0) — use priority_weights, not values_time_over_money alone, to weight which
    candidate/portfolio to recommend.
    """
    persona = json.loads((paths.DATA_DIR / "persona.json").read_text(encoding="utf-8"))
    car = json.loads((paths.DATA_DIR / "car_usage.json").read_text(encoding="utf-8"))
    pd = persona["profileData"]
    p = pd["priorities"]
    prefs = {
        "name": pd["personal"]["full_name"] or "the user",
        "home_city": pd.get("location", {}).get("home_city", ""),
        "age": pd["personal"].get("age"),
        "owns_car": car.get("owns_car", False),
        "values_time_over_money": p["time"] > p["cost"],
        "notes": pd.get("notes", ""),
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
    path = paths.DATA_DIR / "life_events.json"
    if not path.exists():
        return {"events": []}
    raw = json.loads(path.read_text())
    events = LifeEvents.model_validate(raw).model_dump()
    # summary_de sibling on seeded scenario fixtures, resolved for the active request's
    # language (see i18n.pick()) — this summary reaches the user both via the Forecaster's
    # restated life-event report and detect_pending_portfolio_decision()'s reason sentence.
    for event in events["events"]:
        event["summary"] = pick(event, "summary")
    return events

def load_car_usage() -> dict:
    """Load the active user's private car ownership/usage facts from the mock data store.

    Returns a dict with keys: owns_car (bool), mode (str, always "car_private"), type (str
    or null, e.g. Petrol/Diesel/Electric/Hybrid), size (str or null, e.g. "Medium car"), and
    monthly_km_estimate (float or null). All fields are false/null for a persona without a
    private car — that is a real "no private car" fact, not a missing-data gap.
    """
    raw = json.loads((paths.DATA_DIR / "car_usage.json").read_text())
    return CarUsage.model_validate(raw).model_dump()

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
    raw = json.loads((paths.DATA_DIR / "current_subscriptions.json").read_text(encoding="utf-8"))
    return CurrentSubscriptions.model_validate(raw).model_dump()


def load_mobility_catalog() -> dict:
    """Load the market-side mobility products catalog including pricing and benefits data.

    Returns a dict with key 'options', a list of available products each containing:
    id (str), provider (str), product (str), mode (str: rail/car_share/car_rental/flight/bus),
    monthly_cost_eur (float), benefits (dict), eligibility (dict), qualifying_threshold (dict or null).
    """
    raw = json.loads((paths.STATIC_DIR / "mobility_catalog.json").read_text(encoding="utf-8"))
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

    persona = json.loads((paths.DATA_DIR / "persona.json").read_text(encoding="utf-8"))
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
            warnings.append(t("data.tripExcludedNullCost", label=label))
        if not trip.mode:
            warnings.append(t("data.tripExcludedEmptyMode", label=label))
        elif trip.mode not in _KNOWN_MODES:
            warnings.append(t("data.tripExcludedUnknownMode", label=label, mode=trip.mode))

    result = {"trips": [t.model_dump() for t in trips]}
    if warnings:
        result["data_quality_warnings"] = warnings
    return result


def load_travel_history() -> dict:
    """Load the active user's 12-month travel history from the mock data store.

    Returns a dict with key 'trips', a list of past trips each containing:
    date (str), mode (str), origin (str), destination (str), distance_km (float),
    cost_eur (float or null), provider (str), booked_under (str or null).
    If any trips have data quality issues, a 'data_quality_warnings' key is included
    listing each problem so downstream agents can surface them to the user.
    """
    raw = json.loads((paths.DATA_DIR / "travel_history_raw.json").read_text(encoding="utf-8"))
    history = TravelHistory.model_validate(raw)
    return _travel_history_result(history.trips)


def load_annual_travel_history() -> dict:
    """Load travel history for the annual report, scoped to clock.REVIEW_YEAR only.

    Same shape as load_travel_history, but trips outside clock.REVIEW_YEAR (the last full
    calendar year) are excluded before any downstream agent sees them — the annual
    report's stated period must only ever reflect data actually filtered to that year,
    not the full unfiltered history.
    """
    raw = json.loads((paths.DATA_DIR / "travel_history_raw.json").read_text(encoding="utf-8"))
    history = TravelHistory.model_validate(raw)
    year_trips = [t for t in history.trips if t.date.startswith(str(clock.REVIEW_YEAR))]
    return _travel_history_result(year_trips)


def load_calendar_events() -> dict:
    """Load upcoming calendar events — from mock data or live Outlook API.

    Returns a dict with key 'events', a list of upcoming events each containing:
    date (str), type (str: trip/meeting/life_event), description (str),
    location (str or null), signals (list[str] — demand or life-change indicators).
    """
    if USE_MOCK_DATA:
        raw = json.loads((paths.DATA_DIR / "calendar_events_live.json").read_text(encoding="utf-8"))
    else:
        from ..integrations.outlook_calendar import fetch_calendar_events
        raw = fetch_calendar_events()
    events = CalendarEvents.model_validate(raw).model_dump()
    # description_de sibling on seeded scenario fixtures, resolved for the active request's
    # language (see i18n.pick()) — restated verbatim in the Forecaster's summary.
    for event in events["events"]:
        event["description"] = pick(event, "description")
    return events


def load_annual_analyst_context() -> dict:
    """Load all fixed-context data the Annual Analyst agent needs, in one call: travel
    history scoped to clock.REVIEW_YEAR, current subscriptions, and car usage.

    Internally calls load_annual_travel_history(), load_current_subscriptions(), and
    load_car_usage() and returns their results together under one dict. This exists
    purely to save two tool-call round-trips versus calling the three individually — it
    changes zero fields and zero values versus calling them separately. Unlike the
    regular (non-annual) Analyst, which derives projected trips deterministically
    instead of using a bundled context call like this one, the Annual Analyst stays on
    the older, LLM-narrated design (see CLAUDE.md's Four-stage pipelines section).

    Returns a dict with keys:
      - travel_history: exactly load_annual_travel_history()'s return value (key 'trips',
        list of trip dicts limited to clock.REVIEW_YEAR; optional 'data_quality_warnings' list).
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


def load_annual_optimizer_context() -> dict:
    """Load all fixed-context data the Annual Optimizer agent needs up front, in one
    call: user preferences and the user-relevant mobility catalog.

    Internally calls load_user_preferences() and load_relevant_mobility_catalog() and
    returns their results together — saves one tool-call round-trip versus calling them
    individually; changes zero fields and zero values.

    Deliberately excludes recommendation_history: the annual report's instruction has no
    CONTINUITY section referencing past recommendations (unlike the regular Communicator,
    which reads load_recommendation_history() directly — see CLAUDE.md's Four-stage
    pipelines section), so recent-history data stays out of this agent's tool surface,
    matching annual_optimizer_agent's existing tools=[...] scoping.

    Does NOT include compute_co2_impact_kg — that tool stays a separate, on-demand call
    invoked once per candidate action in Step 3 (with different target_subscription/
    new_product arguments each time), not once up front like the loaders bundled here.

    Returns a dict with keys:
      - user_preferences: exactly load_user_preferences()'s return value.
      - relevant_mobility_catalog: exactly load_relevant_mobility_catalog()'s return
        value (key 'options').
    """
    return {
        "user_preferences": load_user_preferences(),
        "relevant_mobility_catalog": load_relevant_mobility_catalog(),
    }


