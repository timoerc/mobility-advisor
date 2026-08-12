"""The sole writer of current_subscriptions.json. Everything else in the store/engine
layers treats subscription fixtures as read-only."""
import calendar
import json
from datetime import date
from typing import Literal

from pydantic import ValidationError

from .. import clock, paths
from ..engine.stats import _resolve_unique_match
from ..models import CurrentSubscriptions, Subscription
from .loaders import load_mobility_catalog

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


def apply_subscription_change(
    action: Literal["add", "remove", "replace"],
    target_subscription: str | None = None,
    new_product: str | None = None,
    as_of: date | None = None,
) -> dict:
    """Apply one confirmed change to the active user's subscriptions. The sole writer of current_subscriptions.json.

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
            and next_renewal_date. Defaults to clock.MOCK_TODAY when omitted. Exists only for
            deterministic testing — leave unset in normal use.

    Returns a dict with: status ("applied" or "error"), action, removed (list of removed
    subscription dicts, empty if none), added (list of added subscription dicts, empty if
    none), before_count (int), after_count (int), file ("current_subscriptions.json"),
    warnings (list[str], e.g. noting a same-product replace), and error (str message, or
    None on success).
    """
    as_of = as_of or clock.MOCK_TODAY
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
    raw_file = json.loads((paths.DATA_DIR / "current_subscriptions.json").read_text(encoding="utf-8"))
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
    paths.atomic_write_json(paths.DATA_DIR / "current_subscriptions.json", {"subscriptions": new_subs_list})

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
