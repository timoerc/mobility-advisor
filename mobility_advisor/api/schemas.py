"""Request-body models for the FastAPI routes. Response shapes are mobility_advisor.models
(the camelCase wire contract) — these are the inbound-only counterparts."""
from typing import Literal

from pydantic import BaseModel

from ..models import CarUsage


class _Personal(BaseModel):
    full_name: str = ""
    age: int | None = None
    employment_status: str = ""
    profession: str = ""
    household_context: str = ""


class _Commute(BaseModel):
    wfh_days: list[str] = []
    office_days: list[str] = []


class _Subscription(BaseModel):
    """The client may only choose a catalog id + dates — every other field (mode,
    provider, product, pricing, ...) is derived server-side from mobility_catalog.json
    by Subscription's own validator, never trusted from the client."""
    model_config = {"extra": "ignore"}
    id: str
    # Explicitly nullable: a usage-threshold subscription (e.g. a car-rental loyalty
    # tier reached by rental volume, not signed up on a date) legitimately has no
    # start/renewal date, and the frontend round-trips that as JSON null rather than
    # omitting the key — a plain `str` field rejects an explicit null even with a
    # default, since Pydantic only applies defaults to *missing* keys.
    next_renewal_date: str | None = None
    started: str | None = None


class _Priorities(BaseModel):
    cost: float = 1 / 3
    time: float = 1 / 3
    sustainability: float = 1 / 3


class ProfilePayload(BaseModel):
    model_config = {"extra": "ignore"}
    persona_id: str = "current"
    avatarBg: str = "#888888"
    personal: _Personal = _Personal()
    location: dict = {}
    commute: _Commute = _Commute()
    car: CarUsage = CarUsage()
    subscriptions: list[_Subscription] = []
    priorities: _Priorities = _Priorities()
    integrations: dict = {}
    notes: str = ""


class ActivateRequest(BaseModel):
    persona_id: str


class AnalyzeRequest(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    session_id: str
    text: str


class ExecuteRequest(BaseModel):
    session_id: str
    action_title: str
    action_description: str
    action_consequence: str = ""
    # The analysis this execution resolves, and which alternative was chosen. When present,
    # /api/execute records the executed outcome + revert snapshot on the newest history entry in the
    # same request that applies the change — so recording can't be lost to a failed second call.
    analysis_id: str | None = None
    alternative_id: str | None = None


class ResolveAnalysisRequest(BaseModel):
    # Only "kept current setup" is recorded here now — an executed change is recorded server-side by
    # /api/execute in the same request that applies it, so it can't be lost to a failed second call.
    outcome: Literal["kept_current"]
    alternative_id: str
    message: str = ""
