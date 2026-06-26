import calendar
import json
import os
import re
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from .models import (
    CalendarEvents,
    CurrentSubscriptions,
    MobilityCatalog,
    Subscription,
    TravelHistory,
    UserPreferences,
)

_DATA = Path(__file__).parent / "data"

USE_MOCK_DATA = True

def load_user_preferences() -> dict:
    """Load Maja's personal mobility preferences and constraints from the mock data store.

    Returns a dict with keys: flexibility_need (str: low/medium/high),
    sustainability_weight (float 0-1), values_time_over_money (bool), and notes (str).
    """
    raw = json.loads((_DATA / "user_preferences.json").read_text())
    return UserPreferences.model_validate(raw).model_dump()


def load_current_subscriptions() -> dict:
    """Load Maja's currently active mobility subscriptions from the mock data store.

    Returns a dict with key 'subscriptions', a list of entries each containing:
    provider (str), product (str), monthly_cost_eur (float), started (str date), notes (str).
    """
    raw = json.loads((_DATA / "current_subscriptions.json").read_text())
    return CurrentSubscriptions.model_validate(raw).model_dump()


def load_mobility_catalog() -> dict:
    """Load the market-side mobility products catalog including pricing and CO2 data.

    Returns a dict with key 'options', a list of available products each containing:
    provider (str), product (str), mode (str: rail/regional/car_share/e_scooter),
    monthly_cost_eur (float), discount_rule (str or null), co2_g_per_km (int).
    """
    raw = json.loads((_DATA / "mobility_catalog.json").read_text())
    return MobilityCatalog.model_validate(raw).model_dump()


_KNOWN_MODES = {"rail", "regional", "car_share", "e_scooter", "bus", "local_transit"}


def load_travel_history() -> dict:
    """Load Maja's 12-month travel history from the mock data store.

    Returns a dict with key 'trips', a list of past trips each containing:
    date (str), mode (str), origin (str), destination (str), distance_km (float),
    cost_eur (float or null), provider (str), booked_under (str or null).
    If any trips have data quality issues, a 'data_quality_warnings' key is included
    listing each problem so downstream agents can surface them to the user.
    """
    raw = json.loads((_DATA / "travel_history.json").read_text())
    history = TravelHistory.model_validate(raw)
    result = history.model_dump()

    warnings = []
    for trip in history.trips:
        label = f"{trip.date} {trip.origin}→{trip.destination}"
        if trip.cost_eur is None:
            warnings.append(f"{label}: cost_eur is null — excluded from spend totals")
        if not trip.mode:
            warnings.append(f"{label}: mode is empty — excluded from CO₂ and mode aggregations")
        elif trip.mode not in _KNOWN_MODES:
            warnings.append(f"{label}: unknown mode '{trip.mode}' — excluded from CO₂ and mode aggregations")

    if warnings:
        result["data_quality_warnings"] = warnings

    return result


def load_calendar_events() -> dict:
    """Load upcoming calendar events — from mock data or live Outlook API.

    Returns a dict with key 'events', a list of upcoming events each containing:
    date (str), type (str: trip/meeting/life_event), description (str),
    location (str or null), signals (list[str] — demand or life-change indicators).
    """
    if USE_MOCK_DATA:
        raw = json.loads((_DATA / "calendar_events.json").read_text())
    else:
        from .outlook_calendar import fetch_calendar_events
        raw = fetch_calendar_events()
    return CalendarEvents.model_validate(raw).model_dump()


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


def _backup_subscriptions_file() -> Path:
    """Copy current_subscriptions.json to a timestamped backup alongside it; return the backup path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    src = _DATA / "current_subscriptions.json"
    backup_path = _DATA / f"current_subscriptions.json.bak_{timestamp}"
    shutil.copy2(src, backup_path)
    return backup_path


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
            and next_renewal_date. Defaults to date.today() when omitted. Exists only for
            deterministic testing — leave unset in normal use.

    Returns a dict with: status ("applied" or "error"), action, removed (list of removed
    subscription dicts, empty if none), added (list of added subscription dicts, empty if
    none), before_count (int), after_count (int), backup_path (str path to the pre-write
    backup taken just before the write, or None on error), file
    ("current_subscriptions.json"), warnings (list[str], e.g. noting a same-product
    replace), and error (str message, or None on success).
    """
    as_of = as_of or date.today()
    warnings: list[str] = []

    def _error(message: str, before_count: int = 0) -> dict:
        return {
            "status": "error",
            "action": action,
            "removed": [],
            "added": [],
            "before_count": before_count,
            "after_count": before_count,
            "backup_path": None,
            "file": "current_subscriptions.json",
            "warnings": warnings,
            "error": message,
        }

    if action in ("remove", "replace") and not target_subscription:
        return _error(f"target_subscription is required for action={action!r}")
    if action in ("add", "replace") and not new_product:
        return _error(f"new_product is required for action={action!r}")

    subs_list = load_current_subscriptions()["subscriptions"]
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
            "provider": catalog_match["provider"],
            "product": catalog_match["product"],
            "monthly_cost_eur": catalog_match["monthly_cost_eur"],
            "billing_cycle": catalog_match["billing_cycle"],
            "next_renewal_date": next_renewal_date,
            "started": as_of.isoformat(),
            "notes": catalog_match.get("discount_rule")
            or f"Added via mobility advisor on {as_of.isoformat()}.",
        }
        try:
            Subscription.model_validate(new_sub)
        except Exception as exc:
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
        validated = CurrentSubscriptions.model_validate({"subscriptions": new_subs_list})
    except Exception as exc:
        return _error(f"resulting subscriptions failed validation: {exc}", before_count)

    backup_path = _backup_subscriptions_file()
    _atomic_write_json(_DATA / "current_subscriptions.json", validated.model_dump())

    return {
        "status": "applied",
        "action": action,
        "removed": removed,
        "added": added,
        "before_count": before_count,
        "after_count": after_count,
        "backup_path": str(backup_path),
        "file": "current_subscriptions.json",
        "warnings": warnings,
        "error": None,
    }
