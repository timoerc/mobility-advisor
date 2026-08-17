"""Read-only data endpoints backing the dashboard: current subscriptions, raw travel
history, and the market catalog."""
import json

from fastapi import APIRouter

from ... import clock, paths
from ...models import CurrentSubscriptions, TravelHistory, catalog_lookup
from ...store.loaders import _localize_entries

router = APIRouter()


@router.get("/api/current-subscriptions")
async def get_current_subscriptions():
    """Return the active, mutable subscriptions list (mobility_advisor/data/current_subscriptions.json).

    Unlike /api/personas — which reads each persona's frozen scenario template and is used to
    seed onboarding/edit state fresh on persona switch — this reflects whatever apply_subscription_change
    has actually applied so far in the current session, so the frontend can re-sync after an execution
    instead of continuing to show its last-loaded (now stale) subscriptions list.
    """
    path = paths.DATA_DIR / "current_subscriptions.json"
    if not path.exists():
        return {"subscriptions": []}
    data = CurrentSubscriptions.model_validate(json.loads(path.read_text(encoding="utf-8")))
    # Localize `product` to the active request's language (see store/loaders._localize_entries)
    # so the home screen's subscription list matches the language of everything around it.
    return {"subscriptions": _localize_entries(data.model_dump()["subscriptions"])}


@router.get("/api/travel-history")
async def get_travel_history():
    """Return the active persona's raw multi-modal travel history plus the frozen reference date.

    Read-only; mirrors the shape of load_travel_history() (mobility_advisor/store/loaders.py)
    but is served unaggregated so the dashboard can filter trips by time range and compute
    CO2/spend/distance/mode breakdowns client-side without a refetch on every range switch.
    The reference_date is MOCK_TODAY (the persona's frozen "today"), which the client must
    use as the range anchor instead of the real clock, since the mock trips are all dated
    relative to it.
    """
    path = paths.DATA_DIR / "travel_history_raw.json"
    if not path.exists():
        return {"trips": [], "reference_date": clock.MOCK_TODAY.isoformat()}
    data = TravelHistory.model_validate(json.loads(path.read_text(encoding="utf-8")))
    return {"trips": data.model_dump()["trips"], "reference_date": clock.MOCK_TODAY.isoformat()}


@router.get("/api/catalog")
async def get_catalog():
    """Return the mobility catalog for frontend dropdown population."""
    catalog = catalog_lookup()
    return {"options": list(catalog.values())}
