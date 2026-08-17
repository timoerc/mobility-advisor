"""The sole writer of current_subscriptions.json. Everything else in the store/engine
layers treats subscription fixtures as read-only."""
import calendar
import json
from datetime import date
from typing import Literal

from pydantic import ValidationError

from .. import clock, paths
from ..engine.stats import _resolve_unique_match
from ..i18n import pick_lang, t
from ..models import CurrentSubscriptions, Subscription
from .loaders import _localize_entries

def _backfilled_product_en(sub: dict, catalog_by_id: dict) -> dict:
    """A subscription dict read straight off current_subscriptions.json (as target_match is,
    deliberately bypassing Subscription._resolve_from_catalog — see apply_subscription_change's
    comment on why) may predate mobility_catalog.json's product_en field: the six scenario
    fixtures and mobility_advisor/data/'s copies were written before that field existed, and
    nothing regenerates them from the catalog on every read. Backfill product_en from the
    catalog by id before handing the entry to _localize_entries for display, so an English
    receipt doesn't silently fall back to the German name just because the on-disk fixture is
    stale. (catalog_match-derived entries, e.g. `added`, already carry product_en directly
    from the catalog and are unaffected by this.)"""
    if sub.get("product_en"):
        return sub
    catalog_entry = catalog_by_id.get(sub.get("id"))
    if catalog_entry and catalog_entry.get("product_en"):
        return {**sub, "product_en": catalog_entry["product_en"]}
    return sub


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
        return _error(t("subscriptionChange.error.targetRequired", action=repr(action)))
    if action in ("add", "replace") and not new_product:
        return _error(t("subscriptionChange.error.newProductRequired", action=repr(action)))

    # Load raw dicts to preserve all fields beyond the Pydantic model. Deliberately NOT
    # load_current_subscriptions()/load_mobility_catalog() — both localize `product` to the
    # active request language for display, which would persist an English (or German, in a
    # German request) display name into current_subscriptions.json as if it were the
    # canonical identity key. The canonical, catalog-matching `product` value is always the
    # German one; only the returned removed/added lists below get localized for display.
    raw_file = json.loads((paths.DATA_DIR / "current_subscriptions.json").read_text(encoding="utf-8"))
    subs_list = raw_file["subscriptions"]
    before_count = len(subs_list)

    # Loaded unconditionally (not just for add/replace): target_match below is read straight
    # off disk, bypassing Subscription._resolve_from_catalog (see the comment above) — a
    # scenario fixture written before mobility_catalog.json grew product_en won't carry it,
    # so it needs backfilling from this catalog-by-id lookup before display. See
    # _backfilled_product_en.
    catalog_options = json.loads(
        (paths.STATIC_DIR / "mobility_catalog.json").read_text(encoding="utf-8")
    )["options"]
    catalog_by_id = {o["id"]: o for o in catalog_options}

    # A user or the LLM may name a subscription/product by either its German (canonical) or
    # English (display-only) name — e.g. under an English request, "cancel my BahnCard 50
    # (2nd class, standard, annual)". Matching both fields covers either.
    match_fields = ("product", "product_en", "provider")

    target_match = None
    if action in ("remove", "replace"):
        target_match, error = _resolve_unique_match(
            target_subscription, subs_list, match_fields
        )
        if error:
            return _error(error, before_count)

    catalog_match = None
    if action in ("add", "replace"):
        catalog_match, error = _resolve_unique_match(
            new_product, catalog_options, match_fields
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
            return _error(t("subscriptionChange.error.newEntryInvalid", error=str(exc)), before_count)

    if (
        action == "replace"
        and target_match is not None
        and catalog_match is not None
        and target_match["product"] == catalog_match["product"]
    ):
        warnings.append(
            t("subscriptionChange.warn.replaceIsNoOp", product=pick_lang(catalog_match, "product"))
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
        return _error(t("subscriptionChange.error.resultInvalid", error=str(exc)), before_count)

    # Write raw dicts (not model_dump) to preserve all fields beyond the pipeline schema. Always
    # the canonical (German product name, notes included) form — never the localized display
    # copies returned below.
    paths.atomic_write_json(paths.DATA_DIR / "current_subscriptions.json", {"subscriptions": new_subs_list})

    # removed/added are what the execution agent quotes verbatim in its user-facing receipt
    # (agents/execution.py rule 4) — localize them here so that receipt matches the active
    # request's language instead of always reading the canonical German fixture data.
    return {
        "status": "applied",
        "action": action,
        "removed": _localize_entries([_backfilled_product_en(s, catalog_by_id) for s in removed]),
        "added": _localize_entries([_backfilled_product_en(s, catalog_by_id) for s in added]),
        "before_count": before_count,
        "after_count": after_count,
        "file": "current_subscriptions.json",
        "warnings": warnings,
        "error": None,
    }
