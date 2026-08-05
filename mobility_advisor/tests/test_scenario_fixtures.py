"""Scenario-fixture consistency checks.

Guards against the class of bug fixed for maja/lena/stefan: calendar_events_live.json
and travel_history_raw.json were authored around a Frankfurt-based persona and never
re-homed when a scenario's persona.json.home_city was set to something else. Because
_forecaster_instruction() (sub_agents.py) uses home_city as the origin for every
calendar-derived trip and skips events whose location IS the home city, a location left
at the wrong city turns an intended local errand into a fabricated long-distance route —
this is exactly what inflated Maja's projected demand and flipped her BahnCard
recommendation (see scenarios/maja/SCENARIO.md). These tests check the fixture data
directly, independent of any LLM behavior, so a future scenario edit can't silently
reintroduce the same mismatch.
"""

import json
from pathlib import Path

import pytest

from mobility_advisor.tools import _normalize_to_city

_SCENARIOS = Path(__file__).parent.parent / "scenarios"
_PERSONAS = ["maja", "lena", "stefan", "katrin", "sofia", "tobias"]

_LONG_DISTANCE_SIGNALS = {
    "long_distance_rail_likely",
    "leisure",
    "possible_relocation",
    "work_pattern_change",
    "car_share_likely",
}


def _load(persona: str, filename: str) -> dict:
    return json.loads((_SCENARIOS / persona / filename).read_text(encoding="utf-8"))


def _home_city(persona: str) -> str:
    return _load(persona, "persona.json")["profileData"]["location"]["home_city"]


@pytest.mark.parametrize("persona", _PERSONAS)
def test_calendar_events_have_a_location(persona):
    """A null location can't be classified as local-vs-long-distance by the Forecaster's
    "location is {home_city}" check — every event must state one explicitly."""
    cal = _load(persona, "calendar_events_live.json")
    for event in cal["events"]:
        assert event.get("location") is not None, (
            f"{persona}: event {event.get('description')!r} has no location"
        )


@pytest.mark.parametrize("persona", _PERSONAS)
def test_local_transit_events_are_in_the_home_city(persona):
    """Every event tagged local_transit_regular must normalize to the persona's own
    home_city — this is the exact mismatch that turned Maja's Köln-local office days
    (tagged local_transit_regular but located "Frankfurt") into a fabricated 48/yr
    long-distance commute once the Forecaster used her real home_city ("Köln") as the
    trip origin."""
    home = _home_city(persona)
    cal = _load(persona, "calendar_events_live.json")
    for event in cal["events"]:
        if "local_transit_regular" not in event.get("signals", []):
            continue
        normalized = _normalize_to_city(event["location"])
        assert normalized == home, (
            f"{persona}: event {event.get('description')!r} is tagged local_transit_regular "
            f"but located in {event['location']!r} (normalizes to {normalized!r}), "
            f"not home_city {home!r}"
        )


@pytest.mark.parametrize("persona", _PERSONAS)
def test_non_home_events_carry_a_long_distance_signal(persona):
    """The inverse of the above: an event located somewhere other than home_city must be
    tagged with a signal that actually says so, so the Forecaster doesn't silently skip
    real forward demand (or a local_transit_regular tag doesn't silently smuggle in an
    out-of-town location)."""
    home = _home_city(persona)
    cal = _load(persona, "calendar_events_live.json")
    for event in cal["events"]:
        normalized = _normalize_to_city(event["location"])
        if normalized == home:
            continue
        signals = set(event.get("signals", []))
        assert signals & _LONG_DISTANCE_SIGNALS, (
            f"{persona}: event {event.get('description')!r} is located in "
            f"{event['location']!r} (away from home_city {home!r}) but carries no "
            f"long-distance-style signal — signals were {sorted(signals)}"
        )


@pytest.mark.parametrize("persona", _PERSONAS)
def test_history_is_anchored_at_home_city(persona):
    """The modal origin/destination city across travel_history_raw.json should be the
    persona's home_city — a history file built around a different city (as Lena's was,
    entirely Frankfurt-origin while persona.json said Hamburg) means every projected
    route's "origin" is wrong before the Forecaster even runs.

    Requires home_city to appear at least once among trip endpoints — not necessarily as
    the statistical mode. A persona can legitimately spend most of a business-travel
    history at a hub city away from home (Stefan's Frankfurt HQ visits, in
    scenarios/stefan/SCENARIO.md's own words) without that being a fixture bug; what's
    never legitimate is home_city appearing zero times, which is what Lena's original
    all-Frankfurt history did against a "Hamburg" home_city.
    """
    home = _home_city(persona)
    history = _load(persona, "travel_history_raw.json")
    cities: set[str] = set()
    for trip in history["trips"]:
        for key in ("origin", "destination"):
            loc = trip.get(key)
            if loc:
                cities.add(_normalize_to_city(loc))
    assert cities, f"{persona}: travel_history_raw.json has no usable origin/destination"
    assert home in cities, (
        f"{persona}: home_city {home!r} never appears among travel history's endpoints "
        f"({sorted(cities)})"
    )


@pytest.mark.parametrize("persona", _PERSONAS)
def test_office_day_events_fall_on_declared_office_days(persona):
    """A "weekly office day" calendar event dated on a persona's own wfh_day is the same
    class of authoring slip as the home-city mismatch — it contradicts data the fixture
    itself declares (persona.json's commute.office_days/wfh_days)."""
    from datetime import date

    persona_data = _load(persona, "persona.json")
    commute = persona_data["profileData"].get("commute", {})
    office_days = set(commute.get("office_days", []))
    wfh_days = set(commute.get("wfh_days", []))
    if not office_days and not wfh_days:
        pytest.skip(f"{persona}: no commute schedule declared")

    weekday_abbrev = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    cal = _load(persona, "calendar_events_live.json")
    for event in cal["events"]:
        desc = (event.get("description") or "").lower()
        if "office day" not in desc:
            continue
        event_date = date.fromisoformat(event["start_date"])
        weekday = weekday_abbrev[event_date.weekday()]
        assert weekday not in wfh_days, (
            f"{persona}: {event['description']!r} on {event['start_date']} falls on "
            f"{weekday}, a declared WFH day"
        )


@pytest.mark.parametrize("persona", _PERSONAS)
def test_life_events_do_not_contradict_current_subscriptions(persona):
    """A life event claiming a subscription lapsed/expired must not describe a
    subscription that current_subscriptions.json still lists as active — the two are
    different data sources (see CLAUDE.md's market-side vs. user-side split) and a stale
    life event contradicting the authoritative subscription list is exactly the kind of
    inconsistency that undermines a downstream agent's confidence in the data."""
    subs = _load(persona, "current_subscriptions.json")["subscriptions"]
    life_events = _load(persona, "life_events.json")["events"]

    # No currently-held subscription's own next_renewal_date may be in the past relative
    # to when a life event claims that same subscription lapsed/won't be renewed — a
    # genuinely past card being flagged as gone, with no matching active subscription, is
    # fine; the contradiction is a lapse claim for a card still actively held going
    # forward.
    for event in life_events:
        summary = event.get("summary", "")
        if "will not be renewed" not in summary.lower() and "expires" not in summary.lower():
            continue
        for sub in subs:
            if sub["product"].split(" (")[0].lower() not in summary.lower():
                continue
            assert sub.get("next_renewal_date", "") <= event.get("event_date", "9999-12-31") or not sub.get(
                "next_renewal_date"
            ), (
                f"{persona}: life event {summary!r} claims {sub['product']!r} lapsed on "
                f"{event.get('event_date')}, but current_subscriptions.json still shows "
                f"it renewing {sub.get('next_renewal_date')} (after the claimed lapse)"
            )
