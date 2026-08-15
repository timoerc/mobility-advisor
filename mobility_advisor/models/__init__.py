"""Pydantic models, re-exported as one flat surface so `from ..models import X` (or
`from mobility_advisor.models import X`) keeps working regardless of which submodule a
model actually lives in:

- fixtures.py    — the snake_case mock data store (catalog, subscriptions, travel
                    history, calendar, car usage, life events)
- projections.py — the deterministic trip-projection pipeline's intermediate shapes
- api.py         — the camelCase wire contract with the frontend
"""
from .api import (
    ACTION_LANGUAGE_FIELDS,
    ALTERNATIVE_LANGUAGE_FIELDS,
    METRIC_LANGUAGE_FIELDS,
    RECOMMENDATION_LANGUAGE_FIELDS,
    AnalysisHistory,
    AnalysisHistoryEntry,
    AnalysisRunResult,
    Alternative,
    DeltaVsCurrent,
    MetricDelta,
    ProposedAction,
    Recommendation,
)
from .fixtures import (
    BusBenefits,
    CalendarEvent,
    CalendarEvents,
    CarRentalBenefits,
    CarRentalThreshold,
    CarShareBenefits,
    CarUsage,
    CatalogOption,
    CurrentSubscriptions,
    Eligibility,
    FlightBenefits,
    FlightThreshold,
    LifeEvent,
    LifeEvents,
    MobilityCatalog,
    PriorityWeights,
    RailBenefits,
    Subscription,
    Trip,
    TravelHistory,
    UserPreferences,
    catalog_lookup,
)
from .projections import ProjectedTrip, ProjectedTripSet, RouteAlternative

__all__ = [
    "ACTION_LANGUAGE_FIELDS",
    "ALTERNATIVE_LANGUAGE_FIELDS",
    "METRIC_LANGUAGE_FIELDS",
    "RECOMMENDATION_LANGUAGE_FIELDS",
    "AnalysisHistory",
    "AnalysisHistoryEntry",
    "AnalysisRunResult",
    "Alternative",
    "BusBenefits",
    "CalendarEvent",
    "CalendarEvents",
    "CarRentalBenefits",
    "CarRentalThreshold",
    "CarShareBenefits",
    "CarUsage",
    "CatalogOption",
    "CurrentSubscriptions",
    "DeltaVsCurrent",
    "Eligibility",
    "FlightBenefits",
    "FlightThreshold",
    "LifeEvent",
    "LifeEvents",
    "MetricDelta",
    "MobilityCatalog",
    "PriorityWeights",
    "ProjectedTrip",
    "ProjectedTripSet",
    "ProposedAction",
    "RailBenefits",
    "Recommendation",
    "RouteAlternative",
    "Subscription",
    "Trip",
    "TravelHistory",
    "UserPreferences",
    "catalog_lookup",
]
