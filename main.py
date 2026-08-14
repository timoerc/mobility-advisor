"""Mobility Advisor API — thin FastAPI wrapper over the ADK agent pipeline."""
import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Literal
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("KICONNECT_API_KEY", ""))
os.environ.setdefault("OPENAI_API_BASE", "https://chat.kiconnect.nrw/api/v1")

import litellm
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import InMemoryRunner, Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types as gtypes
from pydantic import BaseModel, ValidationError

from mobility_advisor.agent import root_agent
from mobility_advisor.execution_agent import execution_agent
from mobility_advisor.i18n import get_language, normalize_language, pick, set_language, t
from mobility_advisor.models import (
    Alternative,
    AnalysisHistory,
    AnalysisHistoryEntry,
    AnalysisRunResult,
    CarUsage,
    CurrentSubscriptions,
    DeltaVsCurrent,
    MetricDelta,
    ProposedAction,
    Recommendation,
    TravelHistory,
    catalog_lookup,
)
from mobility_advisor.pipeline import annual_report_pipeline, optimization_pipeline
from mobility_advisor.report_pdf import render_annual_report_pdf
from mobility_advisor.sub_agents import _MODEL as _PIPELINE_MODEL
from mobility_advisor.tools import MOCK_TODAY, compute_annual_report_stats, detect_pending_portfolio_decision

_DATA = Path(__file__).parent / "mobility_advisor" / "data"
_SCENARIOS = Path(__file__).parent / "mobility_advisor" / "scenarios"
_KNOWN_PERSONAS = frozenset({"maja", "stefan", "lena", "katrin", "tobias", "sofia"})
_SCENARIO_FILES = [
    "persona.json",
    "current_subscriptions.json",
    "travel_history_raw.json",
    "mail_raw.json",
    "calendar_events_live.json",
    "car_usage.json",
    "analysis_history.json",
    "life_events.json",
]
# Derived from sub_agents._MODEL (the pipeline agents' own LiteLlm instance), not a second
# hardcoded copy of the model string — main.py's two non-agent JSON-extraction calls
# (_extract_verdict/_extract_recommendation_json) previously duplicated this literal
# independently, so changing the pipeline's model left them silently pointed at the old one.
_MODEL_ID = _PIPELINE_MODEL.model

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Mobility Advisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    # NB: allow_headers=["*"] only wildcards because allow_credentials is unset (False) here —
    # per the CORS spec, "*" in Access-Control-Allow-Headers is NOT honored when credentials
    # are allowed, so a future `allow_credentials=True` would silently stop the frontend's
    # X-Language header (below) from reaching this API cross-origin.
    allow_headers=["*"],
)


@app.middleware("http")
async def _language_middleware(request, call_next):
    """Sets the request's language (mobility_advisor.i18n's ContextVar) from the frontend's
    X-Language header for the lifetime of this request — read by every deterministic string
    built in main.py and tools.py, including inside ADK FunctionTool calls several frames below
    this handler (contextvars propagate into the asyncio tasks the ADK Runner spawns). A header
    middleware — rather than a field on each request body model — covers the GET endpoints
    (personas, analysis-history, catalog, ...) that a body field would miss, for free."""
    set_language(normalize_language(request.headers.get("x-language")))
    return await call_next(request)

# ── Per-session chat state ────────────────────────────────────────────────────

_chat_services: dict[str, InMemorySessionService] = {}
_CHAT_APP = "mobility_advisor_chat"


def _chat_service(session_id: str) -> InMemorySessionService:
    if session_id not in _chat_services:
        _chat_services[session_id] = InMemorySessionService()
    return _chat_services[session_id]


# ── Request / response models ─────────────────────────────────────────────────

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


# ── Profile helpers ───────────────────────────────────────────────────────────


def _atomic_write(path: Path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _subs_from_payload(payload: ProfilePayload) -> dict:
    return {
        "subscriptions": [
            {"id": s.id, "next_renewal_date": s.next_renewal_date, "started": s.started}
            for s in payload.subscriptions
        ]
    }


def _persona_from_payload(payload: ProfilePayload) -> dict:
    full_name = payload.personal.full_name or "the user"
    initials = "".join(w[0].upper() for w in full_name.split()[:2]) if full_name != "the user" else "?"
    return {
        "id": payload.persona_id,
        "name": full_name,
        "tagline": payload.personal.profession or "New user",
        "avatar": initials,
        "avatarBg": payload.avatarBg,
        "profileData": {
            "personal": payload.personal.model_dump(),
            "location": payload.location,
            "commute": payload.commute.model_dump(),
            "priorities": payload.priorities.model_dump(),
            "integrations": payload.integrations,
            "notes": payload.notes,
        },
    }


def _activate_from_scenario(persona_id: str) -> bool:
    """Copy all pipeline JSON files from scenarios/{persona_id}/ into data/.

    Also clears the derived _projected_trips_*/_optimization_results.json scratch files
    (see _clear_optimization_scratch_files) — without this, switching personas left the
    PREVIOUS persona's projected trips and optimization results sitting in data/, readable
    by _build_alternatives_from_optimization() with no freshness check, until something
    happened to regenerate them. A stale file "looking valid" is worse than one that's
    simply absent, since absence correctly triggers the LLM-extraction fallback instead of
    silently serving a different persona's numbers.
    """
    scenario_dir = _SCENARIOS / persona_id
    if not scenario_dir.is_dir():
        return False
    for fname in _SCENARIO_FILES:
        src = scenario_dir / fname
        if src.exists():
            shutil.copy2(src, _DATA / fname)
    _clear_optimization_scratch_files()
    return True


# ── Analysis history helpers ──────────────────────────────────────────────────
# analysis_history.json is part of the single active, mutable dataset in data/ — each
# scenario also ships its own seed copy (scenarios/<persona>/analysis_history.json), copied
# into data/ on every persona activation via _SCENARIO_FILES above, same as
# current_subscriptions.json.

_history_lock = asyncio.Lock()


def _load_history() -> AnalysisHistory:
    path = _DATA / "analysis_history.json"
    if not path.exists():
        return AnalysisHistory(entries=[])
    try:
        return AnalysisHistory.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError):
        return AnalysisHistory(entries=[])


def _save_history(hist: AnalysisHistory) -> None:
    _atomic_write(_DATA / "analysis_history.json", hist.model_dump())


def _resolve_recommendation_language(rec: Recommendation) -> Recommendation:
    """Swap in the German sibling fields (verdict_de, summaryText_de, ...) seeded on scenario
    analysis_history.json entries, when the active request is German — see models.py's _de
    fields and CLAUDE.md's i18n notes. A live /api/analyze run never populates these siblings
    (its LLM output already comes back in the request's language via the agent-prompt
    directive), so this is always a no-op for freshly-generated recommendations; it only
    matters for seeded scenario history read back through GET /api/analysis-history."""
    if get_language() != "de":
        return rec
    if rec.verdict_de:
        rec.verdict = rec.verdict_de
    if rec.summaryText_de:
        rec.summaryText = rec.summaryText_de
    if rec.reasoning_de:
        rec.reasoning = rec.reasoning_de
    if rec.assumptions_de:
        rec.assumptions = rec.assumptions_de
    for metric in rec.metrics:
        if metric.label_de:
            metric.label = metric.label_de
        if metric.value_de:
            metric.value = metric.value_de
    for alt in rec.alternatives:
        if alt.name_de:
            alt.name = alt.name_de
        if alt.tradeoff_de:
            alt.tradeoff = alt.tradeoff_de
        if alt.action is not None:
            if alt.action.title_de:
                alt.action.title = alt.action.title_de
            if alt.action.description_de:
                alt.action.description = alt.action.description_de
            if alt.action.consequence_de:
                alt.action.consequence = alt.action.consequence_de
    return rec


def _resolve_history_entry_language(entry: AnalysisHistoryEntry) -> AnalysisHistoryEntry:
    _resolve_recommendation_language(entry.recommendation)
    if get_language() == "de" and entry.resolvedMessage_de:
        entry.resolvedMessage = entry.resolvedMessage_de
    return entry


# ── Profile endpoints ─────────────────────────────────────────────────────────

@app.post("/api/profile")
async def save_profile(payload: ProfilePayload):
    """Save a persona's full profile and make it the active data set."""
    try:
        subscriptions = CurrentSubscriptions.model_validate(_subs_from_payload(payload)).model_dump()
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid subscriptions: {exc}") from exc
    _atomic_write(_DATA / "persona.json", _persona_from_payload(payload))
    _atomic_write(_DATA / "current_subscriptions.json", subscriptions)
    _atomic_write(_DATA / "car_usage.json", payload.car.model_dump())
    if payload.persona_id not in _KNOWN_PERSONAS:
        # Custom/new profile, not one of the pre-built scenario personas: there is no
        # real travel or calendar history for them, so clear out whatever scenario data
        # happened to be active last instead of silently analysing it as if it were theirs.
        _atomic_write(_DATA / "travel_history_raw.json", {"trips": []})
        _atomic_write(_DATA / "calendar_events_live.json", {"events": []})
        _atomic_write(_DATA / "analysis_history.json", {"entries": []})
        _atomic_write(_DATA / "life_events.json", {"events": []})
    # Same reasoning as _activate_from_scenario: this profile save just became the active
    # persona/dataset, so any scratch files from whichever persona ran last must not linger.
    _clear_optimization_scratch_files()
    return {"ok": True}


@app.get("/api/personas")
async def list_personas():
    """Assemble each persona from persona.json + current_subscriptions.json + car_usage.json."""
    result = []
    for folder in sorted(_SCENARIOS.iterdir()):
        if not folder.is_dir():
            continue
        pf = folder / "persona.json"
        if not pf.exists():
            continue
        persona = json.loads(pf.read_text(encoding="utf-8"))
        # tagline_de sibling in the scenario fixture, resolved for the active request's
        # language — see mobility_advisor.i18n.pick(). persona.json is a raw dict, not
        # Pydantic-validated, so this is the only place the German variant needs wiring.
        persona["tagline"] = pick(persona, "tagline")
        sf = folder / "current_subscriptions.json"
        subscriptions = (
            CurrentSubscriptions.model_validate(json.loads(sf.read_text(encoding="utf-8"))).model_dump()["subscriptions"]
            if sf.exists() else []
        )
        persona["profileData"]["subscriptions"] = subscriptions
        cf = folder / "car_usage.json"
        persona["profileData"]["car"] = (
            json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else CarUsage().model_dump()
        )
        result.append(persona)
    return result


@app.post("/api/activate")
async def activate_persona(req: ActivateRequest):
    """Switch the active data set to a named scenario."""
    if req.persona_id not in _KNOWN_PERSONAS:
        raise HTTPException(
            status_code=404,
            detail=f"No scenario for persona '{req.persona_id}'.",
        )
    found = _activate_from_scenario(req.persona_id)
    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"No scenario directory for persona '{req.persona_id}'.",
        )
    return {"ok": True}


@app.get("/api/current-subscriptions")
async def get_current_subscriptions():
    """Return the active, mutable subscriptions list (mobility_advisor/data/current_subscriptions.json).

    Unlike /api/personas — which reads each persona's frozen scenario template and is used to
    seed onboarding/edit state fresh on persona switch — this reflects whatever apply_subscription_change
    has actually applied so far in the current session, so the frontend can re-sync after an execution
    instead of continuing to show its last-loaded (now stale) subscriptions list.
    """
    path = _DATA / "current_subscriptions.json"
    if not path.exists():
        return {"subscriptions": []}
    data = CurrentSubscriptions.model_validate(json.loads(path.read_text(encoding="utf-8")))
    return {"subscriptions": data.model_dump()["subscriptions"]}


@app.get("/api/travel-history")
async def get_travel_history():
    """Return the active persona's raw multi-modal travel history plus the frozen reference date.

    Read-only; mirrors the shape of load_travel_history() (mobility_advisor/tools.py) but is served
    unaggregated so the dashboard can filter trips by time range and compute CO2/spend/distance/mode
    breakdowns client-side without a refetch on every range switch. The reference_date is MOCK_TODAY
    (the persona's frozen "today"), which the client must use as the range anchor instead of the real
    clock, since the mock trips are all dated relative to it.
    """
    path = _DATA / "travel_history_raw.json"
    if not path.exists():
        return {"trips": [], "reference_date": MOCK_TODAY.isoformat()}
    data = TravelHistory.model_validate(json.loads(path.read_text(encoding="utf-8")))
    return {"trips": data.model_dump()["trips"], "reference_date": MOCK_TODAY.isoformat()}


@app.get("/api/catalog")
async def get_catalog():
    """Return the mobility catalog for frontend dropdown population."""
    catalog = catalog_lookup()
    return {"options": list(catalog.values())}


# ── JSON extraction ───────────────────────────────────────────────────────────

_JSON_SYSTEM_PROMPT = """
Convert the mobility advisor's recommendation report into this exact JSON structure.
Output ONLY valid JSON — no markdown fences, no surrounding text.

LANGUAGE: the report below may be written in English or German (the communicator agent that
produced it follows the user's selected language). Preserve that language verbatim in every
extracted free-text string — verdict, summaryText, reasoning, assumptions, tradeoff, and every
action.{title,description,consequence} field. Do not translate them into English or into any
other language, regardless of what language this system prompt itself is written in.

The report follows a fixed structure — **Verdict:** / **Confidence:** / **Summary:** /
**Reasoning:** (bullets) / **Assumptions:** (bullets) — and describes ONLY the recommended
option compared against the user's current setup; it does not enumerate other candidates as
separate labelled blocks. Reconstruct exactly two "alternatives" entries from it: one for the
recommended option, one for the "Keep current setup" baseline it is compared against.

The section labels above are normally English even in a German-language report (the
communicator agent is instructed to keep them verbatim), but tolerate the German equivalents
too if they appear: **Urteil:** = Verdict, **Vertrauen:** = Confidence, **Zusammenfassung:** =
Summary, **Begründung:** = Reasoning, **Annahmen:** = Assumptions.

{
  "verdict": "<the report's Verdict line, verbatim>",
  "confidence": "<the report's Confidence value: 'high' | 'medium' | 'low', lowercase>",
  "summaryText": "<the report's Summary text, verbatim or condensed to 1-2 sentences>",
  "metrics": [
    {
      "value": <number>,
      "unit": "<e.g. '€/year', 'kg CO2/year', 'min/year'>",
      "direction": "<one of: 'save' | 'reduce' | 'extra_cost' | 'increase' | 'neutral'>",
      "label": "<short label, e.g. 'Potential saving', 'CO2 impact'>"
    }
  ],
  "reasoning": ["<one entry per bullet under Reasoning>"],
  "assumptions": ["<one entry per bullet under Assumptions>"],
  "alternatives": [
    {
      "id": "recommended",
      "name": "<what changes — see naming rules below>",
      "annualCostEur": <the recommended option's total annual cost in EUR, from an
        "Annual cost: €X" mention in the Summary or Reasoning>,
      "savingsVsCurrentEur": <the report's stated "Saving vs. current: €Y/year" figure;
        negate it if the report frames this option as costing MORE than current>,
      "co2Impact": "<e.g. 'Neutral' or '-38 kg CO2/year', from the report's CO2 impact line>",
      "co2ImpactKg": <that same figure's signed number — positive = this option SAVES CO2
        vs. current, negative = it emits MORE; 0 if the report doesn't state one>,
      "tradeoff": "<one sentence, from the trade-off bullet in Reasoning>",
      "isRecommended": true,
      "action": {
        "title": "<imperative sentence naming the concrete change, e.g. 'Switch to
          BahnCard 25 (2. Klasse, Standard, Jahresabo)'>",
        "description": "<1-2 sentences with action details>",
        "consequence": "<what changes in the user's portfolio once applied — name the
          exact subscription(s) added/removed, copied verbatim from the report. Do not
          say the change requires separate/manual approval — confirming applies it
          immediately in this prototype>"
      }
    },
    {
      "id": "keep",
      "name": "Keep current setup",
      "annualCostEur": <the recommended entry's annualCostEur minus its
        savingsVsCurrentEur — i.e. what the current setup costs today>,
      "savingsVsCurrentEur": 0,
      "co2Impact": "Neutral",
      "co2ImpactKg": 0,
      "tradeoff": "No change to cost or emissions",
      "isRecommended": false,
      "action": null
    }
  ]
}

Rules:
- Exactly one alternative — the "recommended" entry — has isRecommended: true and a non-null
  action. The "keep" entry always has isRecommended: false and action: null. (This fallback
  path has no way to reconstruct a distinct "Hold pending decision" option from the report
  text — that case is handled deterministically upstream, before this extraction ever runs.)
- All numbers must come verbatim from the report below — never invent figures. If a number
  genuinely cannot be determined, use a sensible default (0 for a cost/CO2 figure, "Neutral"
  for co2Impact, [] for assumptions) rather than guessing.
- alternatives[0].name must describe the ACTION, not a bare product name — e.g. "Switch to
  BahnCard 25 (2. Klasse, Standard, Jahresabo)", "Cancel BahnCard 50 (2. Klasse, Standard,
  Jahresabo)", "Add MILES Silber Pass" — matching whichever verb (switch/cancel/add/upgrade/
  downgrade) the report's own language uses for this change.
- Subscription/product names (in action.title/description/consequence and in
  alternatives[0].name) must be copied verbatim and in full from the report — never
  shortened (e.g. "BahnCard 25 (2. Klasse, Standard, Jahresabo)", not "BahnCard 25") — this
  name is executed literally if the user picks this alternative.
- confidence must be exactly "high", "medium", or "low", lowercase.
- The "keep" entry's "name"/"tradeoff" fields are shown above in English ("Keep current
  setup" / "No change to cost or emissions") only as illustrative placeholder text for the
  JSON shape — write them in the SAME language as the rest of your extraction (i.e. the
  report's own language), not necessarily English.
""".strip()


def _clamp_actionable_alternatives(
    rec: Recommendation, max_actionable: int = 5
) -> Recommendation:
    """Defensively enforce the product cap of `max_actionable` actionable alternatives.

    On the deterministic path (_build_alternatives_from_optimization), optimize_all_
    categories() can surface up to 5 scenarios, so the default cap here matches that. On
    the LLM-extraction fallback path (_extract_recommendation_json), _JSON_SYSTEM_PROMPT
    only ever asks for one actionable alternative (the report itself only ever describes
    one recommended option — see that prompt's own docstring-equivalent comment), so this
    is normally a no-op there; it exists as a hard backstop regardless of what either path
    actually returns. Keeps the recommended alternative, then earlier non-recommended
    actionable alternatives up to the cap (in original order), then all keep-current-setup
    row(s) (action is None) unchanged.
    """
    actionable = [a for a in rec.alternatives if a.action is not None]
    if len(actionable) <= max_actionable:
        return rec
    keep_rows = [a for a in rec.alternatives if a.action is None]
    recommended = [a for a in actionable if a.isRecommended]
    others = [a for a in actionable if not a.isRecommended]
    rec.alternatives = (recommended + others)[:max_actionable] + keep_rows
    return rec


def _co2_methodology_assumption(weights: dict | None) -> str:
    """A subscription changes what each transport mode costs you; projected usage of each
    mode shifts in response (a logit mode share over generalized cost, not an all-or-
    nothing pick — see _mode_shares() in tools.py), and CO2 and travel time follow from
    that shift. This replaces the old "CO2 is 0 unless a mode becomes newly (un)available"
    methodology, which was only true because mode choice used to ignore price entirely.
    """
    from mobility_advisor.tools import _generalized_cost_rates

    value_of_time, co2_price = _generalized_cost_rates(weights)
    return t(
        "assumption.co2Methodology",
        valueOfTime=f"{value_of_time:.2f}",
        co2Price=f"{co2_price:.3f}",
    )


def _load_optimization_weights() -> dict | None:
    """The flat cost_weight/time_weight/sustainability_weight dict optimize_all_categories()
    persisted for this run, or None if no deterministic run has happened yet (LLM-extraction
    fallback path)."""
    opt_path = _DATA / "_optimization_results.json"
    if not opt_path.exists():
        return None
    return json.loads(opt_path.read_text(encoding="utf-8")).get("weights")


def _dedupe_warnings(warnings: list[str]) -> list[str]:
    """Collapse exact-duplicate warning strings into a single "(×N)" line, preserving
    first-seen order. Upstream (tools.py), the same warning — e.g. "car_share: driving route
    API failed, using heuristic" — is appended once per affected historical route rather than
    once per mode, so an API outage or missing ORS_API_KEY can otherwise repeat an identical
    line many times in the Data quality notes panel."""
    counts: dict[str, int] = {}
    order: list[str] = []
    for w in warnings:
        if w not in counts:
            order.append(w)
        counts[w] = counts.get(w, 0) + 1
    return [f"{w} (×{counts[w]})" if counts[w] > 1 else w for w in order]


def _load_optimization_warnings() -> list[str]:
    """Deterministic warnings optimize_all_categories() persisted for this run — malformed
    travel-history entries, travel-reduction damping, rail-fare calibration notes, etc. (see
    tools.py's derive_projected_trips_from_history/merge_projected_trip_sets). Empty list
    when no deterministic run has happened yet (LLM-extraction fallback path), matching
    Recommendation.dataQualityWarnings's default."""
    opt_path = _DATA / "_optimization_results.json"
    if not opt_path.exists():
        return []
    warnings = json.loads(opt_path.read_text(encoding="utf-8")).get("warnings", [])
    return _dedupe_warnings(warnings)


def _normalize_keep_current_setup(rec: Recommendation) -> Recommendation:
    """Deterministically guarantee cost/CO2 deltas can never contradict the cost figures they're
    derived from, regardless of what the LLM extraction step produced.

    savingsVsCurrentEur is defined as "vs. the current setup" — i.e. vs. the status-quo
    'Keep current setup' row's own annualCostEur — so it is recomputed here as exactly that
    difference for every alternative, never trusted as an independently-extracted number. This
    also covers alternatives whose action reconfirms/renews something unchanged (annualCostEur
    equal to the keep row's), which must show a €0 delta by the same logic, not a stray figure
    like a "vs. cancelling" saving that answers a different question.

    Separately, the keep row itself (action is None) is the baseline by definition, so it also
    always shows Neutral/0 CO2 regardless of extraction. Also records the CO2 methodology as an
    assumption so it's visible to the user rather than silently applied.
    """
    keep_rows = [alt for alt in rec.alternatives if alt.action is None]
    if keep_rows:
        keep_cost = keep_rows[0].annualCostEur
        for alt in rec.alternatives:
            alt.savingsVsCurrentEur = round(keep_cost - alt.annualCostEur, 2)
    for alt in rec.alternatives:
        if alt.action is None:
            alt.co2Impact = "Neutral"
            alt.co2ImpactKg = 0.0
    assumption = _co2_methodology_assumption(_load_optimization_weights())
    if assumption not in rec.assumptions:
        rec.assumptions.append(assumption)
    return rec


_STATIC = Path(__file__).parent / "mobility_advisor" / "static"

# Scratch files the deterministic trip-projection/optimization engine (tools.py) writes
# during a pipeline run and _build_alternatives_from_optimization() below reads back.
_OPTIMIZATION_SCRATCH_FILES = [
    "_projected_trips_history.json",
    "_projected_trips_calendar.json",
    "_projected_trips_car_usage.json",
    "_projected_trips_merged.json",
    "_optimization_results.json",
]


def _clear_optimization_scratch_files() -> None:
    """Delete this run's scratch files before the pipeline executes.

    Without this, a stale _optimization_results.json from a previous run (a different
    persona, or an earlier request in the same persona) stays on disk untouched by
    persona activation (_activate_from_scenario only copies scenario JSON in, never
    clears these) and by a failed run (optimize_all_categories()'s error paths return
    before writing the file). _build_alternatives_from_optimization() would then
    silently read that stale file — with no freshness check — and serve a previous
    run's (possibly a different persona's) alternatives as if they were this run's,
    including writing them into analysis_history.json as this run's outcome. Deleting
    first makes "file absent" mean exactly what it should: this run's Optimizer agent
    did not (yet, or at all) call optimize_all_categories(), which correctly triggers
    the LLM-extraction fallback below instead of serving contaminated data.
    """
    for fname in _OPTIMIZATION_SCRATCH_FILES:
        (_DATA / fname).unlink(missing_ok=True)


def _build_alternatives_from_optimization() -> list[Alternative] | None:
    """Build Alternative objects deterministically from _optimization_results.json.

    Returns None if the file doesn't exist (fallback to LLM extraction).
    """
    opt_path = _DATA / "_optimization_results.json"
    if not opt_path.exists():
        return None

    opt = json.loads(opt_path.read_text(encoding="utf-8"))
    scenarios = opt.get("scenarios", [])
    if not scenarios:
        return None

    catalog_raw = json.loads((_STATIC / "mobility_catalog.json").read_text(encoding="utf-8"))
    catalog_by_id = {o["id"]: o for o in catalog_raw["options"]}
    current_ids = set(opt.get("current_subscription_ids", []))
    break_even_by_ids = {
        tuple(sorted(b["subscription_ids"])): b for b in opt.get("break_even", [])
    }

    # Search all_ranked (every simulated candidate), not the possibly-truncated `scenarios`
    # display subset — "No subscriptions" and the current portfolio are always present in
    # all_ranked (optimize_all_categories() guarantees both), so this should never actually
    # fall through to the `max(...)` fallback below in practice.
    all_ranked = opt.get("all_ranked", scenarios)

    # Find the baseline (no subs or current) cost/time/co2 for savingsVsCurrentEur and for
    # the recommended row's own tradeoff (see below).
    keep_cost = keep_time = keep_co2 = None
    for s in all_ranked:
        if s.get("is_current") or (not s["subscription_ids"] and not current_ids):
            keep_cost = s["total_annual_cost_eur"]
            keep_time = s["total_annual_time_min"]
            keep_co2 = s["total_annual_co2_kg"]
            break
    if keep_cost is None:
        # Should not happen — optimize_all_categories() always simulates both the current
        # portfolio and "No subscriptions". Fall back to the worst candidate rather than
        # crashing the whole recommendation, but flag it loudly: silently treating the
        # priciest scenario as "the status quo" would make every savingsVsCurrentEur look
        # artificially large.
        print("Warning: _build_alternatives_from_optimization found no current/baseline "
              "scenario — falling back to the most expensive candidate as the status quo baseline.")
        worst = max(all_ranked, key=lambda s: s["total_annual_cost_eur"])
        keep_cost = worst["total_annual_cost_eur"]
        keep_time = worst["total_annual_time_min"]
        keep_co2 = worst["total_annual_co2_kg"]

    alts: list[Alternative] = []
    for s in scenarios:
        ids = set(s["subscription_ids"])
        is_keep = s.get("is_current") or (not ids and not current_ids)

        if is_keep:
            alts.append(Alternative(
                id="keep",
                name=t("alt.keep.name"),
                annualCostEur=s["total_annual_cost_eur"],
                savingsVsCurrentEur=0,
                co2Impact=t("alt.co2.neutral"),
                co2ImpactKg=0.0,
                tradeoff=t("alt.keep.tradeoff"),
                isRecommended=s.get("is_recommended", False),
                action=None,
                deltaCostVsRecommendedEur=s.get("delta_cost_eur", 0),
                deltaTimeVsRecommendedMin=s.get("delta_time_min", 0),
                deltaCo2VsRecommendedKg=s.get("delta_co2_kg", 0),
                deltaVsCurrent=DeltaVsCurrent(),
            ))
            continue

        # Build action from diff vs current portfolio. Free tiers (Enterprise Silver, Miles
        # & More, etc. — monthly_cost_eur == 0) are excluded from both sides of the diff:
        # they're automatic loyalty tiers the optimizer never proposes adding or removing
        # (see SKIP_IDS in optimize_all_categories()), so surfacing one as "Cancel
        # Enterprise Silver" alongside a real BahnCard swap is just confusing — there is
        # nothing to decide about a €0/mo tier the user isn't being asked to give up.
        added = {
            sid for sid in (ids - current_ids)
            if catalog_by_id.get(sid, {}).get("monthly_cost_eur", 0) > 0
        }
        removed = {
            sid for sid in (current_ids - ids)
            if catalog_by_id.get(sid, {}).get("monthly_cost_eur", 0) > 0
        }

        added_names = [catalog_by_id[sid]["product"] for sid in sorted(added) if sid in catalog_by_id]
        removed_names = [catalog_by_id[sid]["product"] for sid in sorted(removed) if sid in catalog_by_id]
        # " + " everywhere a card joins multiple product names — matches the separator
        # optimize_all_categories() already uses for its combo labels (tools.py), so a
        # two-product cancel/add reads the same as a two-product portfolio label instead of
        # switching between ", " and " + " depending on which code path built the string.
        added_joined = " + ".join(added_names)
        removed_joined = " + ".join(removed_names)

        if added_names and removed_names:
            action_title = t("alt.action.replace.title", removed=removed_joined, added=added_joined)
            name = t("alt.action.replace.name", label=s["label"])
            consequence = t("alt.action.replace.consequence", removed=removed_joined, added=added_joined)
        elif added_names:
            action_title = t("alt.action.add.title", added=added_joined)
            name = t("alt.action.add.name", label=s["label"])
            consequence = t("alt.action.add.consequence", added=added_joined)
        elif removed_names:
            action_title = t("alt.action.cancel.title", removed=removed_joined)
            name = t("alt.action.cancel.name", removed=removed_joined)
            consequence = t("alt.action.cancel.consequence", removed=removed_joined)
        else:
            action_title = s["label"]
            name = s["label"]
            consequence = t("alt.action.noChange.consequence")

        # Generate tradeoff string from deltas vs. the user's CURRENT setup — every row's
        # own card states what the user is being asked to give up or gain relative to what
        # they hold today, the recommended row included.
        d_cost = s["total_annual_cost_eur"] - keep_cost
        d_time = s["total_annual_time_min"] - keep_time if keep_time is not None else 0
        d_co2 = s["total_annual_co2_kg"] - keep_co2 if keep_co2 is not None else 0
        tradeoff_parts = []
        if abs(d_cost) >= 1:
            if d_cost > 0:
                tradeoff_parts.append(t("alt.tradeoff.moreExpensive", amount=round(d_cost)))
            else:
                tradeoff_parts.append(t("alt.tradeoff.cheaper", amount=round(abs(d_cost))))
        if abs(d_time) >= 10:
            if d_time > 0:
                tradeoff_parts.append(t("alt.tradeoff.moreTime", minutes=round(d_time)))
            else:
                tradeoff_parts.append(t("alt.tradeoff.lessTime", minutes=round(d_time)))
        if abs(d_co2) >= 1:
            if d_co2 > 0:
                tradeoff_parts.append(t("alt.tradeoff.moreCo2", kg=round(d_co2)))
            else:
                tradeoff_parts.append(t("alt.tradeoff.lessCo2", kg=round(d_co2)))

        # Break-even for this row's resulting portfolio as a whole, not for its added/removed
        # subscriptions scored independently. optimize_all_categories() now computes
        # break-even for every non-baseline candidate it simulates (see _compute_break_even),
        # not just single-subscription ones, so the row's own subscription_ids usually has a
        # direct match — showing that one combined figure instead of one line per added/
        # removed id avoids double-counting: two cards' discount_value_eur are each computed
        # independently against the "no subscriptions" baseline, so summing both lines (e.g.
        # for "Add BahnCard 25 + Deutschlandticket") overstates what holding both together
        # actually saves, since they compete for the same trips. Falls back to the
        # per-added/removed-id lookup only for a row with no whole-portfolio match (should
        # not normally happen, since `s` is itself one of optimize_all_categories()'s
        # simulated candidates).
        break_even_parts = []
        row_break_even = break_even_by_ids.get(tuple(sorted(ids)))
        if row_break_even is not None:
            verb = t("alt.breakEven.breaksEven") if row_break_even["breaks_even"] else t("alt.breakEven.netLoss")
            break_even_parts.append(t(
                "alt.breakEven.line",
                label=s["label"], verb=verb,
                discount=f"{row_break_even['discount_value_eur']:.0f}",
                fee=f"{row_break_even['annual_fee_eur']:.0f}",
            ))
        else:
            for sid in sorted(added | removed):
                break_even = break_even_by_ids.get((sid,))
                if break_even is None:
                    continue
                verb = t("alt.breakEven.breaksEven") if break_even["breaks_even"] else t("alt.breakEven.netLoss")
                product = catalog_by_id.get(sid, {}).get("product", break_even["label"])
                break_even_parts.append(t(
                    "alt.breakEven.line",
                    label=product, verb=verb,
                    discount=f"{break_even['discount_value_eur']:.0f}",
                    fee=f"{break_even['annual_fee_eur']:.0f}",
                ))
        if break_even_parts:
            tradeoff_parts.append("; ".join(break_even_parts))

        if tradeoff_parts:
            tradeoff = "; ".join(tradeoff_parts)
        else:
            tradeoff = t("alt.tradeoff.sameAsCurrent")

        # CO2 impact vs. current setup (positive = saves CO2), consistent with
        # savingsVsCurrentEur's baseline.
        co2_impact_kg = round(-d_co2, 1)
        # The human-readable string uses the opposite sign convention from co2ImpactKg —
        # it shows the raw emissions delta (d_co2: negative = fewer emissions = greener),
        # matching the tradeoff text's own "+X kg CO₂ per year"/"-X kg CO₂ per year"
        # phrasing above. Previously wrapped in abs(...), which made an option emitting 40
        # kg MORE than current render identically to one saving 40 kg — the same string for
        # opposite outcomes, on a field that's part of the wire contract (persisted into
        # analysis_history.json) even though today's frontend doesn't render it.
        d_co2_rounded = round(d_co2)
        co2_impact_str = t("alt.co2Impact.value", delta=d_co2_rounded) if d_co2_rounded != 0 else t("alt.co2.neutral")

        slug = "_".join(s["subscription_ids"]) if s["subscription_ids"] else "none"

        alts.append(Alternative(
            id=slug,
            name=name,
            annualCostEur=s["total_annual_cost_eur"],
            savingsVsCurrentEur=round(keep_cost - s["total_annual_cost_eur"], 2),
            co2ImpactKg=co2_impact_kg,
            co2Impact=co2_impact_str,
            tradeoff=tradeoff,
            isRecommended=s.get("is_recommended", False),
            action=ProposedAction(
                title=action_title,
                description=t("alt.action.description", title=action_title),
                consequence=consequence,
            ),
            deltaCostVsRecommendedEur=s.get("delta_cost_eur", 0),
            deltaTimeVsRecommendedMin=s.get("delta_time_min", 0),
            deltaCo2VsRecommendedKg=s.get("delta_co2_kg", 0),
            deltaVsCurrent=DeltaVsCurrent(
                costEur=round(d_cost, 2),
                timeMin=round(d_time, 1),
                co2Kg=round(d_co2, 2),
            ),
            addedProducts=added_names,
            removedProducts=removed_names,
        ))

    # Deterministic "hold pending decision" row — detect_pending_portfolio_decision() is a
    # strict gate that only fires for a genuine, near-term relocation/work-pattern change
    # (see its docstring in tools.py), so this is a no-op for every persona without one. When
    # it does fire, the row is added here as a candidate but NOT marked recommended yet —
    # _enforce_hold_when_decision_pending() (called by /api/analyze after this function
    # returns) is what promotes it over whatever scored best, same as it already does on the
    # LLM-extraction fallback path. Cost is pinned to keep_cost (same convention as "Keep
    # current setup") so Recommendation's deliberate-hold validator exception accepts it.
    decision = detect_pending_portfolio_decision()
    if decision["exists"]:
        alts.append(Alternative(
            id="hold",
            name=t("alt.hold.name"),
            annualCostEur=keep_cost,
            savingsVsCurrentEur=0,
            co2Impact=t("alt.co2.neutral"),
            co2ImpactKg=0.0,
            tradeoff=decision["reason"],
            isRecommended=False,
            action=None,
            deltaVsCurrent=DeltaVsCurrent(),
        ))

    # Ensure exactly one recommended and one keep row
    has_recommended = any(a.isRecommended for a in alts)
    # Deliberately excludes the recommended row itself: when the current/baseline portfolio
    # is ALSO the top-ranked candidate, the loop above emits a single row with id="keep",
    # action=None, isRecommended=True — that row satisfies `a.action is None` but is not a
    # separate baseline to compare against. Without the `and not a.isRecommended` exclusion,
    # has_keep was True here even though no non-recommended no-action row exists, so the
    # append below never ran — leaving Recommendation with a null-action recommended row and
    # no other no-action row for its validator's "deliberate hold" exception to match against
    # (see models.py's _validate_alternatives_shape), which raised ValueError and turned into
    # an HTTP 500 on every "current setup is already optimal" result — exactly the "Do
    # Nothing" case the coordinator's own instructions advertise as a valid outcome.
    has_keep = any(a.action is None and not a.isRecommended for a in alts)

    if not has_recommended and alts:
        alts[0].isRecommended = True
    if not has_keep:
        # The recommended row may itself already use id="keep" (the is_keep branch above,
        # when the current portfolio is also the top-ranked candidate) — this baseline row
        # must not collide with it, or Recommendation's unique-ids validator rejects the
        # whole result.
        existing_ids = {a.id for a in alts}
        baseline_id = "keep_baseline" if "keep" in existing_ids else "keep"
        alts.append(Alternative(
            id=baseline_id,
            name=t("alt.keep.name"),
            annualCostEur=keep_cost,
            savingsVsCurrentEur=0,
            tradeoff=t("alt.keep.tradeoff"),
            isRecommended=False,
            action=None,
            deltaVsCurrent=DeltaVsCurrent(),
        ))

    # Sort: recommended first, then by cost, keep-current last
    def _sort_key(a):
        if a.isRecommended:
            return (0,)
        if a.action is None:
            return (2,)
        return (1, a.annualCostEur)
    alts.sort(key=_sort_key)

    return alts


_VERDICT_SYSTEM_PROMPT = """
Extract ONLY the qualitative summary from this mobility advisor report.
Output valid JSON — no markdown fences.

LANGUAGE: the report below may be written in English or German. Preserve that language
verbatim in verdict/summaryText/reasoning/assumptions — do not translate them. The section
labels are normally English even in a German report, but tolerate German equivalents too:
**Urteil:** = Verdict, **Vertrauen:** = Confidence, **Zusammenfassung:** = Summary,
**Begründung:** = Reasoning, **Annahmen:** = Assumptions.

{
  "verdict": "<concise 8-10 word headline>",
  "confidence": "<high | medium | low>",
  "summaryText": "<1-2 sentences>",
  "reasoning": ["<bullet 1>", "<bullet 2>", ...],
  "assumptions": ["<assumption 1>", ...]
}

Rules:
- verdict: summarize the recommended action and its key benefit
- confidence: high if cost gap is clear, medium if borderline, low if uncertain — always
  output the English word "high"/"medium"/"low" for this field regardless of the report's
  language, never a translated equivalent (e.g. never "hoch"/"mittel"/"niedrig")
- summaryText: the recommended option, how much it saves, and key tradeoff
- reasoning: 2-4 bullets explaining why this portfolio wins
- assumptions: key model assumptions (Sparpreis pricing, trip frequencies, etc.)
""".strip()


def _parse_json_response(text: str) -> dict:
    """Extract a JSON object from an LLM completion's raw text.

    Brace-scans for the outermost {...} span instead of only stripping a LEADING markdown
    fence (```/```json). The old approach — `if text.startswith("```")` — was defeated by
    any preamble before the fence (e.g. "Here is the JSON:\n```json\n{...}\n```", which
    GPT-OSS-120B being a reasoning model produces more often than not) or a label variant
    like "```JSON"/"``` json" the exact `startswith("json")` check didn't catch, either of
    which fed the whole prose blob straight into json.loads and raised JSONDecodeError on a
    completion that was otherwise perfectly parseable. Brace-scanning is agnostic to
    whatever wrapping the model used around the object.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        # No object-shaped span at all — let json.loads raise its own clear error against
        # the original text rather than silently returning something empty.
        return json.loads(text)
    return json.loads(text[start : end + 1])


_VALID_CONFIDENCE_LEVELS = {"high", "medium", "low"}
# Defense in depth: _VERDICT_SYSTEM_PROMPT/_JSON_SYSTEM_PROMPT both explicitly instruct the
# model to always emit the English enum word regardless of the report's language, but a German
# request is exactly the condition most likely to make a model slip and translate it anyway —
# without this map, "hoch" would silently fall through to the "medium" default below instead
# of correctly resolving to "high", degrading confidence invisibly on every German response
# that gets this one word wrong.
_CONFIDENCE_SYNONYMS = {
    "hoch": "high",
    "mittel": "medium",
    "niedrig": "low",
    "gering": "low",
}


def _normalize_confidence_and_lists(parsed: dict) -> dict:
    """Coerce an LLM-extracted dict's confidence/reasoning/assumptions into the shapes
    downstream code expects, in place, tolerating small deviations a completion can
    introduce without failing the whole extraction over what is narration, not numbers:

    - confidence not exactly "high"/"medium"/"low" (wrong case, a German synonym like
      "hoch", or an unrelated synonym like "moderate") would otherwise raise a pydantic
      ValidationError deep inside Recommendation construction — there is no
      `.get(..., default)` fallback for an out-of-range Literal value, only for a missing key.
    - reasoning/assumptions returned as a single string instead of a list.
    """
    confidence = str(parsed.get("confidence", "medium")).strip().lower()
    confidence = _CONFIDENCE_SYNONYMS.get(confidence, confidence)
    parsed["confidence"] = confidence if confidence in _VALID_CONFIDENCE_LEVELS else "medium"
    for key in ("reasoning", "assumptions"):
        value = parsed.get(key)
        if isinstance(value, str):
            parsed[key] = [value]
    return parsed


def _parse_verdict_response(text: str) -> dict:
    """Synchronous core of _extract_verdict(), split out so it's directly unit-testable
    without an async LLM call: brace-scans, normalizes confidence/reasoning/assumptions,
    then drops an empty-string verdict/summaryText so the caller's `.get(key, default)`
    fallback kicks in — `.get` only catches a MISSING key, not "", so a blank string would
    otherwise render as a blank dashboard headline instead of the intended fallback (e.g.
    analyze()'s `verdict.get("verdict", rec_alt.name)`).
    """
    parsed = _normalize_confidence_and_lists(_parse_json_response(text))
    if not (parsed.get("verdict") or "").strip():
        parsed.pop("verdict", None)
    if not (parsed.get("summaryText") or "").strip():
        parsed.pop("summaryText", None)
    return parsed


async def _extract_verdict(report_text: str) -> dict:
    """Extract only qualitative fields from the communicator's text output."""
    response = await litellm.acompletion(
        model=_MODEL_ID,
        messages=[
            {"role": "system", "content": _VERDICT_SYSTEM_PROMPT},
            {"role": "user", "content": report_text},
        ],
        temperature=0.0,
    )
    text = response.choices[0].message.content.strip()
    return _parse_verdict_response(text)


async def _extract_recommendation_json(report_text: str) -> Recommendation:
    response = await litellm.acompletion(
        model=_MODEL_ID,
        messages=[
            {"role": "system", "content": _JSON_SYSTEM_PROMPT},
            {"role": "user", "content": report_text},
        ],
        temperature=0.0,
    )
    text = response.choices[0].message.content.strip()
    parsed = _normalize_confidence_and_lists(_parse_json_response(text))
    recommendation = Recommendation.model_validate(parsed)
    return _finalize_recommendation(recommendation)


def _load_optimization_context() -> tuple[float | None, float | None, float | None, dict | None]:
    """(keep_cost, keep_time, keep_co2, weights) for the current run's status-quo baseline
    and persona priority weights, or all-None if no deterministic optimization has run yet."""
    opt_path = _DATA / "_optimization_results.json"
    if not opt_path.exists():
        return None, None, None, None
    opt = json.loads(opt_path.read_text(encoding="utf-8"))
    weights = opt.get("weights")
    all_ranked = opt.get("all_ranked", opt.get("scenarios", []))
    current_ids = set(opt.get("current_subscription_ids", []))
    for s in all_ranked:
        if s.get("is_current") or (not s["subscription_ids"] and not current_ids):
            return (
                s["total_annual_cost_eur"],
                s["total_annual_time_min"],
                s["total_annual_co2_kg"],
                weights,
            )
    return None, None, None, weights


_HEADLINE_DROP_THRESHOLDS = {"cost": 1.0, "co2": 1.0, "time": 15.0}


def _format_time_headline(abs_time_min: float) -> tuple[float, str]:
    """Minutes below 90 render as whole minutes; above that, hours to 1 decimal — same
    breakpoint AlternativeRow uses for the vs-current strip."""
    if abs_time_min < 90:
        return round(abs_time_min), t("metric.unit.minPerYear")
    return round(abs_time_min / 60, 1), t("metric.unit.hPerYear")


def _build_pending_decision_metrics(alts: list[Alternative], decision: dict) -> list[MetricDelta]:
    """Decision-framed headline tiles for when a portfolio-resetting life event is pending:
    the date the uncertainty resolves, the value being left on the table by holding instead
    of taking the best deferred alternative, and what kind of decision is pending."""
    best_deferred = max(
        (a for a in alts if a.action is not None),
        key=lambda a: a.savingsVsCurrentEur,
        default=None,
    )
    value_on_hold = best_deferred.savingsVsCurrentEur if best_deferred else 0.0
    category_key = decision["events"][0]["category"] if decision.get("events") else None
    category_label = (
        t(f"lifeEvent.category.{category_key}") if category_key else t("metric.pendingDecision.lifeEvent")
    )
    return [
        MetricDelta(value=decision["revisit_after"], unit="", direction="neutral", label=t("metric.pendingDecision.revisitBy")),
        MetricDelta(
            # max(0, ...), not abs(...) — savingsVsCurrentEur is negative when even the best
            # deferred alternative is WORSE than the status quo (no candidate improves on
            # holding), and abs() flipped that into a positive "Value on hold €X" figure,
            # implying value is being left on the table when there is none.
            value=max(0, round(value_on_hold)),
            unit=t("metric.unit.eurPerYear"),
            direction="neutral",
            label=t("metric.pendingDecision.valueOnHold"),
        ),
        MetricDelta(
            value=category_label, unit="", direction="neutral", label=t("metric.pendingDecision.decisionPending")
        ),
    ]


def _build_headline_metrics(alts: list[Alternative], decision: dict) -> list[MetricDelta]:
    """Headline tiles for the top of the recommendation.

    Normal case: up to three tiles built from the recommended alternative's deltaVsCurrent —
    one per dimension. A dimension whose |delta| is below its drop threshold
    (_HEADLINE_DROP_THRESHOLDS) is omitted, except cost, which always survives so the row is
    never empty. Tiles are ordered by strikingness = |delta| / |current total| * the
    persona's own weight for that dimension, so the most persona-relevant, largest-magnitude
    change leads.

    Pending-decision case: when decision["exists"], the normal tiles would show a change the
    Hold recommendation deliberately isn't making (its deltaVsCurrent is all zeros) — build
    decision-framed tiles instead (see _build_pending_decision_metrics).
    """
    if decision["exists"]:
        return _build_pending_decision_metrics(alts, decision)

    rec_alt = next((a for a in alts if a.isRecommended), alts[0])
    delta = rec_alt.deltaVsCurrent or DeltaVsCurrent()
    keep_cost, keep_time, keep_co2, weights = _load_optimization_context()
    w = weights or {}
    w_cost = w.get("cost_weight", 0.34)
    w_time = w.get("time_weight", 0.33)
    w_co2 = w.get("sustainability_weight", 0.33)

    def strikingness(value: float, total: float | None, weight: float) -> float:
        if not total:
            return 0.0
        return abs(value) / abs(total) * weight

    cost_metric = MetricDelta(
        value=abs(round(delta.costEur)),
        unit=t("metric.unit.eurPerYear"),
        direction="save" if delta.costEur < 0 else ("extra_cost" if delta.costEur > 0 else "neutral"),
        label=t("metric.potentialSaving") if delta.costEur < 0 else (t("metric.extraCost") if delta.costEur > 0 else t("metric.noChange")),
    )
    co2_metric = MetricDelta(
        value=abs(round(delta.co2Kg, 1)),
        unit=t("metric.unit.kgCo2PerYear"),
        direction="reduce" if delta.co2Kg < 0 else ("increase" if delta.co2Kg > 0 else "neutral"),
        label=t("metric.co2Reduction") if delta.co2Kg < 0 else (t("metric.co2Increase") if delta.co2Kg > 0 else t("metric.noCo2Change")),
    )
    time_value, time_unit = _format_time_headline(abs(delta.timeMin))
    time_metric = MetricDelta(
        value=time_value,
        unit=time_unit,
        direction="reduce" if delta.timeMin < 0 else ("increase" if delta.timeMin > 0 else "neutral"),
        label=t("metric.timeSaved") if delta.timeMin < 0 else (t("metric.extraTravelTime") if delta.timeMin > 0 else t("metric.noTimeChange")),
    )

    ranked = sorted(
        [
            ("cost", delta.costEur, strikingness(delta.costEur, keep_cost, w_cost), cost_metric),
            ("co2", delta.co2Kg, strikingness(delta.co2Kg, keep_co2, w_co2), co2_metric),
            ("time", delta.timeMin, strikingness(delta.timeMin, keep_time, w_time), time_metric),
        ],
        key=lambda c: c[2],
        reverse=True,
    )

    metrics = []
    for dim, value, _score, metric in ranked:
        if dim != "cost" and abs(value) < _HEADLINE_DROP_THRESHOLDS[dim]:
            continue
        metrics.append(metric)
    return metrics


def _enforce_hold_when_decision_pending(rec: Recommendation) -> Recommendation:
    """When a portfolio-resetting life decision is pending, make the deliberate "Hold pending
    decision" alternative the recommended one — deterministically, not at the LLM's discretion.

    detect_pending_portfolio_decision() is a strict gate: it fires ONLY for a genuine, near-term
    relocation / work-pattern change (see its docstring), so this override never touches an
    ordinary review — for every persona without such a signal it is a no-op and the pipeline's
    own pick stands. When the gate IS active, holding until the decision resolves is the correct
    conservative call (acting now bets on a decision that isn't settled), but the optimizer LLM
    does not reliably choose it — so if it recommended a concrete change instead, re-point the
    recommendation at the Hold row here and rewrite the headline fields to match, keeping the
    concrete change visible as the non-recommended option the user is deferring.
    """
    decision = detect_pending_portfolio_decision()
    if not decision["exists"]:
        return rec
    # Matched on id alone (not a name substring like "hold pending") so this survives the
    # alternative's display name being translated — see CLAUDE.md's i18n section.
    hold = next(
        (a for a in rec.alternatives if a.action is None and a.id == "hold"),
        None,
    )
    if hold is None or hold.isRecommended:
        # No hold candidate to promote (optimizer omitted it), or it is already the pick.
        return rec
    for alt in rec.alternatives:
        alt.isRecommended = alt is hold
    revisit = decision["revisit_after"]
    rec.verdict = t("verdict.holdUntilResolved", revisit=revisit)
    rec.summaryText = decision["reason"]
    rec.confidence = "low"
    rec.metrics = _build_pending_decision_metrics(rec.alternatives, decision)
    return rec


def _finalize_recommendation(rec: Recommendation) -> Recommendation:
    """Run the standard post-construction mutation chain, then re-validate the result as a
    whole — the one place both /api/analyze's deterministic path and
    _extract_recommendation_json's LLM-extraction fallback path finish building a
    Recommendation, so both get the same guarantee.

    Recommendation has no validate_assignment=True, so _normalize_keep_current_setup,
    _enforce_hold_when_decision_pending, and _clamp_actionable_alternatives each mutate an
    already-validated model without _validate_alternatives_shape (the model_validator
    enforcing unique ids / exactly one recommended / at least one keep row) ever running
    again. Turning validate_assignment on would not reliably fix this either: two of the
    three functions mutate nested Alternative objects' own fields in place (never
    reassigning any of Recommendation's own top-level fields), and the ONE reassignment
    _enforce_hold_when_decision_pending performs only happens on the rare pending-decision
    path — the ordinary case (no pending decision, alternatives at or under the cap) would
    still trigger zero revalidation. Round-tripping through model_dump()/model_validate()
    here instead re-runs every validator unconditionally against the mutation chain's final
    state, regardless of which functions did or didn't reassign anything.
    """
    rec = _normalize_keep_current_setup(rec)
    rec = _enforce_hold_when_decision_pending(rec)
    rec = _clamp_actionable_alternatives(rec)
    return Recommendation.model_validate(rec.model_dump())


# ── Pipeline retry helper ─────────────────────────────────────────────────────

_MAX_PIPELINE_ATTEMPTS = 2


async def _with_pipeline_retry(attempt_fn, max_attempts: int = _MAX_PIPELINE_ATTEMPTS):
    """Retry attempt_fn() up to max_attempts times when it raises KeyError.

    attempt_fn should run one full pipeline invocation (its own fresh session)
    and raise KeyError if a stage produced an empty response — either because a
    downstream stage's {analysis}/{forecast}/{recommendation} template referenced
    session state an earlier stage never wrote, or because the final stage's own
    output came back empty. Confirmed via direct testing against this backend
    (KIConnect / GPT-OSS-120B): this happens intermittently even for prompts well
    within a sane context budget, so it is NOT a reliable sign of an oversized
    prompt — it's flaky-upstream-call behavior, which a retry is the standard fix
    for. Every attempt must use its own fresh session so a failed run's partial
    state is never reused by the next attempt.
    """
    last_error: KeyError | None = None
    for _ in range(max_attempts):
        try:
            return await attempt_fn()
        except KeyError as exc:
            last_error = exc
    raise HTTPException(
        status_code=500,
        detail=t("error.pipelineRetryExhausted", attempts=max_attempts, lastError=str(last_error)),
    ) from last_error


# ── Analyse endpoint ──────────────────────────────────────────────────────────

@app.post("/api/analyze", response_model=AnalysisRunResult)
async def analyze(req: AnalyzeRequest):
    _clear_optimization_scratch_files()
    runner = InMemoryRunner(agent=optimization_pipeline, app_name="mobility_advisor_analyze")

    async def attempt() -> str:
        sid = f"analysis_{uuid4().hex[:12]}"
        await runner.session_service.create_session(
            app_name="mobility_advisor_analyze",
            user_id="user",
            session_id=sid,
        )

        last_text = ""
        fallback_text = ""
        async for event in runner.run_async(
            user_id="user",
            session_id=sid,
            new_message=gtypes.Content(
                role="user",
                parts=[gtypes.Part(text="Analyse my current mobility setup and subscriptions.")],
            ),
        ):
            if event.is_final_response():
                t = _collect_text(event)
                if t.strip():
                    last_text = t
            else:
                t = _collect_text(event)
                if t.strip() and not _has_function_call(event):
                    fallback_text = t

        # communicator_agent (the pipeline's last stage) has no output_key, so its
        # actual final report is only available from the event stream above — NOT
        # from session.state["recommendation"], which is optimizer_agent's
        # pre-Communicator draft (see its output_key in sub_agents.py) and is not
        # what adk web/chat show.
        report_text = last_text or fallback_text
        if not report_text:
            raise KeyError("communicator produced an empty response")
        return report_text

    try:
        report_text = await _with_pipeline_retry(attempt)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=t("error.pipelineNoReport", error=str(exc)),
        ) from exc

    try:
        det_alts = _build_alternatives_from_optimization()
        if det_alts is not None:
            try:
                verdict = await _extract_verdict(report_text)
            except Exception as exc:
                # The deterministic alternatives (det_alts) are the load-bearing artifact
                # here — already fully computed and persisted to _optimization_results.json.
                # The verdict is decorative narration on top of them, and every field below
                # already has a sensible fallback (rec_alt.name, "medium", ""/[]). A parse
                # hiccup on this one call must not throw away an entire completed
                # four-stage pipeline run — see _parse_json_response's docstring for how
                # often this backend needs the tolerance this is guarding against.
                # Greppable prefix + active language: a parse failure specifically on German
                # requests (e.g. from a translated section marker like **Urteil:** the
                # extractor doesn't recognize) would otherwise degrade silently into a
                # plausible-looking but empty-summary, medium-confidence result with no signal
                # anywhere that anything went wrong — this line is the only trace of it.
                print(
                    f"VERDICT_EXTRACTION_FALLBACK: language={get_language()!r} "
                    f"verdict extraction failed, using deterministic fallbacks: {exc}"
                )
                verdict = {}
            rec_alt = next((a for a in det_alts if a.isRecommended), det_alts[0])
            metrics = _build_headline_metrics(det_alts, detect_pending_portfolio_decision())
            rec = Recommendation(
                verdict=verdict.get("verdict", rec_alt.name),
                confidence=verdict.get("confidence", "medium"),
                summaryText=verdict.get("summaryText", ""),
                metrics=metrics,
                reasoning=verdict.get("reasoning", []),
                assumptions=verdict.get("assumptions", []),
                alternatives=det_alts,
                dataQualityWarnings=_load_optimization_warnings(),
            )
            rec = _finalize_recommendation(rec)
        else:
            rec = await _extract_recommendation_json(report_text)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=t("error.jsonExtractionFailed", error=str(exc))
        ) from exc

    entry_id = f"hist_{uuid4().hex[:10]}"
    try:
        async with _history_lock:
            hist = _load_history()
            hist.entries.append(
                AnalysisHistoryEntry(id=entry_id, date=MOCK_TODAY.isoformat(), recommendation=rec)
            )
            _save_history(hist)
    except Exception as exc:
        # Losing the history-log write is far cheaper than failing the whole call
        # after an already-completed pipeline run — log and continue regardless.
        print(f"Warning: failed to append analysis history entry: {exc}")

    return AnalysisRunResult(id=entry_id, recommendation=rec)


# ── Annual report endpoint ────────────────────────────────────────────────────

@app.post("/api/annual-report")
async def annual_report(req: AnalyzeRequest):
    """Run annual_report_pipeline directly (no coordinator routing), then convert the
    annual_communicator's Markdown report into a styled PDF and return it as
    application/pdf. Unlike /api/analyze, this pipeline's final agent has no
    output_key, so its report only exists on the last event, not in session state."""
    runner = InMemoryRunner(agent=annual_report_pipeline, app_name="mobility_advisor_annual")

    async def attempt() -> tuple[str, str]:
        sid = f"annual_{uuid4().hex[:12]}"
        await runner.session_service.create_session(
            app_name="mobility_advisor_annual",
            user_id="user",
            session_id=sid,
        )

        report_text = ""
        async for event in runner.run_async(
            user_id="user",
            session_id=sid,
            new_message=gtypes.Content(
                role="user",
                parts=[gtypes.Part(text="Generate my full annual mobility report.")],
            ),
        ):
            if event.is_final_response():
                report_text = _collect_text(event)

        if not report_text:
            raise KeyError("annual_communicator produced an empty response")
        return report_text, sid

    try:
        report_text, _sid = await _with_pipeline_retry(attempt)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=t("error.annualPipelineNoReport", error=str(exc)),
        ) from exc

    # The three data-heavy sections (Year at a Glance, Spend & Emissions by Mode,
    # Subscription Value) are rendered here in Python from the same deterministic
    # compute_annual_report_stats() the communicator's prompt was built from, and
    # substituted for the placeholder markers the communicator was instructed to
    # emit verbatim — the LLM never formats these numbers itself, so they can't
    # drift from what the report's narrative sections say about them.
    stats = compute_annual_report_stats()
    report_text = (
        report_text
        .replace("<!-- GLANCE_TABLE -->", _render_glance_table(stats))
        .replace("<!-- BY_MODE_TABLE -->", _render_by_mode_table(stats))
        .replace("<!-- SUBSCRIPTION_VALUE -->", _render_subscription_value(stats))
    )

    try:
        pdf_bytes = render_annual_report_pdf(report_text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=t("error.pdfRenderingFailed", error=str(exc))) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="annual-mobility-review.pdf"'},
    )


# ── Execute endpoint ──────────────────────────────────────────────────────────

@app.post("/api/execute")
async def execute(req: ExecuteRequest):
    runner = InMemoryRunner(agent=execution_agent, app_name="mobility_advisor_execute")
    sid = f"execute_{uuid4().hex[:12]}"

    # Snapshot the subscription stack BEFORE the agent mutates it, so a successful change can later be
    # reverted by restoring this exact state (the executed action is free text and not reliably
    # invertible on its own). Persisted server-side on the history entry below, in this same request.
    prev_path = _DATA / "current_subscriptions.json"
    previous_subscriptions = (
        CurrentSubscriptions.model_validate(json.loads(prev_path.read_text(encoding="utf-8"))).model_dump()
        if prev_path.exists()
        else None
    )

    await runner.session_service.create_session(
        app_name="mobility_advisor_execute",
        user_id="user",
        session_id=sid,
    )

    # consequence is where the recommendation states plainly what's being removed and what
    # replaces it (e.g. "Your BahnCard 50 will be cancelled and BahnCard 25 will start in
    # its place") — without it, a replace/swap action can reach the execution agent naming
    # only the new product, with nothing saying which current subscription it replaces.
    instruction = f"{req.action_title}\n\n{req.action_description}"
    if req.action_consequence:
        instruction += f"\n\n{req.action_consequence}"

    last_text = ""
    fallback_text = ""
    tool_result: dict | None = None
    async for event in runner.run_async(
        user_id="user",
        session_id=sid,
        new_message=gtypes.Content(
            role="user",
            parts=[gtypes.Part(text=instruction)],
        ),
    ):
        for fr in event.get_function_responses():
            if fr.name == "apply_subscription_change":
                tool_result = fr.response
        # `text`, not `t` — `t` is also this module's i18n translate function (imported from
        # mobility_advisor.i18n), and a bare assignment to `t` here would shadow it for the
        # rest of this handler, including the t(...) calls later in this function.
        if event.is_final_response():
            text = _collect_text(event)
            if text.strip():
                last_text = text
        else:
            text = _collect_text(event)
            if text.strip() and not _has_function_call(event):
                fallback_text = text

    reply = last_text or fallback_text
    if not reply:
        raise HTTPException(status_code=500, detail=t("error.executionAgentNoResponse"))

    success = bool(tool_result and tool_result.get("status") == "applied")

    # Record the executed outcome + revert snapshot on the newest history entry in THIS request, so a
    # successful mutation and its record land together server-side. There is no second round-trip that
    # could fail and leave an applied-but-unrecorded change with no way to revert.
    if success and req.analysis_id:
        async with _history_lock:
            hist = _load_history()
            newest = hist.entries[-1] if hist.entries else None
            if newest and newest.id == req.analysis_id and newest.outcome != "executed":
                newest.outcome = "executed"
                newest.resolvedAlternativeId = req.alternative_id
                newest.resolvedMessage = reply
                newest.resolvedAt = MOCK_TODAY.isoformat()
                newest.revertSnapshot = previous_subscriptions
                _save_history(hist)
            else:
                # The subscription mutation already happened (success is True) — that
                # can't be undone here — but it can no longer be tied to an analysis
                # history entry, most likely because a newer analysis ran in between this
                # change being proposed and confirmed. Surfacing this only via a server log
                # left the user with an applied change that silently can never be reverted
                # through the history UI, with the response still claiming plain success.
                print(f"Warning: applied change but could not record it against analysis {req.analysis_id}")
                reply = f"{reply}\n\n{t('error.unlinkedExecutionNote')}"

    return {"success": success, "message": reply}


# ── Analysis history endpoints ────────────────────────────────────────────────

@app.get("/api/analysis-history", response_model=list[AnalysisHistoryEntry])
async def get_analysis_history():
    """Return this persona's analysis history, newest first. Entries are stored
    oldest-first on disk (mocked ones authored in narrative order, live ones
    appended as they occur), and reversed here for display."""
    hist = _load_history()
    return [_resolve_history_entry_language(e) for e in reversed(hist.entries)]


@app.post("/api/analysis-history/{entry_id}/resolve")
async def resolve_analysis(entry_id: str, req: ResolveAnalysisRequest):
    """Record that the user kept their current setup for the newest analysis.

    Executed changes are recorded by /api/execute itself; this endpoint only handles the
    kept-current decision, which changes nothing on disk.

    Only the newest, not-yet-executed entry can be resolved — older analyses are a read-only ledger,
    and an already-executed one must be reverted before it can be decided again.
    """
    async with _history_lock:
        hist = _load_history()
        if not hist.entries:
            raise HTTPException(status_code=404, detail=t("error.noAnalysisHistoryEntry", entryId=entry_id))
        newest = hist.entries[-1]
        if newest.id != entry_id:
            raise HTTPException(
                status_code=409,
                detail=t("error.onlyNewestCanBeResolved"),
            )
        if newest.outcome == "executed":
            raise HTTPException(
                status_code=409,
                detail=t("error.alreadyExecutedMustRevertFirst"),
            )
        newest.outcome = req.outcome
        newest.resolvedAlternativeId = req.alternative_id
        newest.resolvedMessage = req.message
        newest.resolvedAt = MOCK_TODAY.isoformat()
        # A kept-current decision changed nothing, so there is nothing to undo.
        newest.revertSnapshot = None
        _save_history(hist)
    return {"ok": True}


@app.post("/api/analysis-history/{entry_id}/revert")
async def revert_analysis(entry_id: str):
    """Undo an executed change on the newest analysis: restore the subscription stack captured just
    before the change and reset the entry to 'kept_current' (net effect: no change) so it can be
    decided again. Only the newest, executed entry that still has a stored snapshot can be reverted.
    """
    async with _history_lock:
        hist = _load_history()
        if not hist.entries:
            raise HTTPException(status_code=404, detail=t("error.noAnalysisHistoryEntry", entryId=entry_id))
        newest = hist.entries[-1]
        if newest.id != entry_id:
            raise HTTPException(status_code=409, detail=t("error.onlyNewestCanBeReverted"))
        if newest.outcome != "executed" or newest.revertSnapshot is None:
            raise HTTPException(status_code=409, detail=t("error.noExecutedChangeToRevert"))
        restored = CurrentSubscriptions.model_validate(newest.revertSnapshot)
        _atomic_write(_DATA / "current_subscriptions.json", restored.model_dump())
        newest.outcome = "kept_current"
        newest.resolvedAlternativeId = None
        newest.resolvedMessage = t("revert.resolvedMessage")
        newest.resolvedAt = MOCK_TODAY.isoformat()
        newest.revertSnapshot = None
        _save_history(hist)
    return {"success": True, "message": t("revert.message")}


# ── Chat endpoint ─────────────────────────────────────────────────────────────

_MODE_DISPLAY_KEYS = {
    "rail": "mode.rail",
    "flight": "mode.flight",
    "car_rental": "mode.carRental",
    "car_share": "mode.carShare",
    "bus": "mode.bus",
    "unknown": "mode.unknown",
}


def _mode_display_label(mode: str) -> str:
    key = _MODE_DISPLAY_KEYS.get(mode)
    return t(key) if key else mode.replace("_", " ").title()


def _render_glance_table(stats: dict) -> str:
    """Render annual_communicator_agent's "Year at a Glance" section (Section 1) as a
    fixed 5-row Markdown table from compute_annual_report_stats() — pure data, no LLM
    formatting involved, so it can't drift from what Section 4 says about the same
    subscriptions."""
    discount_total = sum(
        s["discount_value_eur"] for s in stats["subscriptions"] if s["discount_value_eur"] is not None
    )
    rows = [
        (t("report.glance.totalSpend"), f"€{stats['total_spend_eur']:,.2f}"),
        (t("report.glance.savings"), f"€{discount_total:,.2f}"),
        (t("report.glance.totalCo2"), f"{stats['total_co2_kg']:,.1f} kg"),
        (t("report.glance.co2Avoided"), f"{stats['rail_vs_car_saving_kg']:,.1f} kg"),
        (t("report.glance.tripsLogged"), str(stats["total_trips"])),
    ]
    lines = [f"| {t('report.glance.header.metric')} | {t('report.glance.header.value')} |", "|--------|-------|"]
    lines += [f"| {label} | {value} |" for label, value in rows]
    return "\n".join(lines)


def _render_by_mode_table(stats: dict) -> str:
    """Render Section 2 "Spend & Emissions by Mode" — an aggregated-by-mode table that
    replaces what used to be a raw per-trip dump. Still fully cross-checkable (every
    trip that fed compute_annual_report_stats() is accounted for in some row) but
    scannable, the way a professional annual report should be."""
    lines = [
        f"| {t('report.byMode.header.mode')} | {t('report.byMode.header.trips')} | "
        f"{t('report.byMode.header.distance')} | {t('report.byMode.header.spend')} | "
        f"{t('report.byMode.header.co2')} |",
        "|------|-------|----------|-------|-----|",
    ]
    for row in stats["by_mode"]:
        # "Total" is an internal sentinel written by tools.py's compute_annual_report_stats()
        # and matched by exact string equality here — it is never itself displayed, so it must
        # stay untranslated (see that function's comment on the same value).
        is_total = row["mode"] == "Total"
        label = t("report.byMode.total") if is_total else _mode_display_label(row["mode"])
        lines.append(
            f"| {label} | {row['trips']} | {row['distance_km']:,.0f} km | "
            f"€{row['spend_eur']:,.2f} | {row['co2_kg']:,.1f} kg |"
        )
    return "\n".join(lines)


def _render_subscription_value(stats: dict) -> str:
    """Render Section 4 "Subscription Value" — one block per active subscription.

    Three cases, keyed off compute_annual_report_stats()'s has_discount_value /
    is_paid_subscription flags:
      - has_discount_value: a paid subscription with a real per-trip discount (e.g.
        BahnCard) — gets a discount-vs-fee net figure and a break-even verdict.
      - is_paid_subscription but not has_discount_value: a paid flat-fee
        unlimited-access pass (e.g. Deutschlandticket, BahnCard 100) — there's no
        discrete per-trip fare to discount, so it gets a usage line instead of a
        fabricated €0.00 "discount value" / break-even verdict.
      - neither: a €0 loyalty/status tier (e.g. a car-rental loyalty program) — gets
        a plain activity status line; there is no fee to break even against, so a
        break-even verdict for it would be meaningless (the bug this replaces).
    """
    blocks = []
    for sub in stats["subscriptions"]:
        header = f"**{sub['product']}**"
        if sub["has_discount_value"]:
            header += t("report.subValue.header.discount", monthly=f"{sub['monthly_cost_eur']:.2f}", annual=f"{sub['annual_fee_eur']:.2f}")
            net = sub["net_eur"]
            if net >= 0:
                verdict = t("report.subValue.paidOff")
            elif net >= -0.1 * sub["annual_fee_eur"]:
                verdict = t("report.subValue.borderline")
            else:
                verdict = t("report.subValue.didNotBreakEven")
            sign = "+" if net >= 0 else "−"
            # Blank line between the header paragraph and the bullet list below is
            # required — python-markdown (unlike CommonMark) treats a list that
            # directly follows a paragraph with no blank line as a lazy continuation
            # of that paragraph, flattening the bullets into running prose.
            blocks.append(
                f"{header}\n\n"
                + t("report.subValue.tripsAttributedWithMode", count=sub["trips_attributed"], provider=sub["provider"], mode=sub["mode"].replace("_", " ")) + "\n"
                + t("report.subValue.discountValue", amount=f"{sub['discount_value_eur']:.2f}") + "\n"
                + t("report.subValue.netVsFee", sign=sign, amount=f"{abs(net):.2f}") + "\n"
                + t("report.subValue.verdict", verdict=verdict)
            )
        elif sub["is_paid_subscription"]:
            header += t("report.subValue.header.flatFee", monthly=f"{sub['monthly_cost_eur']:.2f}", annual=f"{sub['annual_fee_eur']:.2f}")
            blocks.append(
                f"{header}\n\n"
                + t("report.subValue.tripsCoveredThisYear", count=sub["trips_attributed"]) + "\n"
                + t("report.subValue.flatFeeNoBreakEven")
            )
        else:
            header += t("report.subValue.header.loyalty")
            qa = sub["qualifying_activity"]
            activity_line = (
                t("report.subValue.activityThisYear", count=qa["count"], threshold=qa["threshold"])
                if qa
                else t("report.subValue.tripsAttributedSimple", count=sub["trips_attributed"])
            )
            blocks.append(
                f"{header}\n\n"
                f"{activity_line}\n"
                + t("report.subValue.loyaltyNoBreakEven")
            )
    return "\n\n".join(blocks)


def _collect_text(event) -> str:
    if not event.content:
        return ""
    texts = []
    for part in event.content.parts or []:
        if getattr(part, "text", None):
            texts.append(part.text)
        elif getattr(part, "function_response", None):
            # skip_summarization=True (optimization_pipeline, execution_agent,
            # annual_report_pipeline) makes the coordinator relay the sub-agent's report
            # as a raw function_response instead of a text part — surface it the same way.
            result = part.function_response.response.get("result")
            if isinstance(result, str):
                texts.append(result)
    return "".join(texts)


def _has_function_call(event) -> bool:
    return bool(event.get_function_calls() or event.get_function_responses())


@app.post("/api/chat")
async def chat(req: ChatRequest):
    # Unlike /api/analyze, this endpoint didn't clear the trip-projection/optimization
    # scratch files before running — and derive_projected_trips_from_calendar() APPENDS to
    # _projected_trips_calendar.json rather than overwriting it. Activate persona B, then
    # ask "is my setup optimal?" in chat, and persona A's calendar-derived routes (still on
    # disk from whenever they were last written) got merged into B's run. Clearing here
    # matches /api/analyze's own _clear_optimization_scratch_files() call and is safe even
    # when this message doesn't touch optimization at all: the coordinator may or may not
    # route to optimization_pipeline, but no other code path depends on these files
    # surviving between requests (main._build_alternatives_from_optimization() is only ever
    # read back within the same /api/analyze call that wrote them).
    _clear_optimization_scratch_files()
    svc = _chat_service(req.session_id)
    runner = Runner(
        agent=root_agent,
        app_name=_CHAT_APP,
        session_service=svc,
        artifact_service=InMemoryArtifactService(),
        memory_service=InMemoryMemoryService(),
    )

    session = await svc.get_session(
        app_name=_CHAT_APP, user_id="user", session_id=req.session_id
    )
    if session is None:
        await svc.create_session(
            app_name=_CHAT_APP, user_id="user", session_id=req.session_id
        )

    last_text = ""
    fallback_text = ""
    action_taken = False
    ran_optimization = False
    async for event in runner.run_async(
        user_id="user",
        session_id=req.session_id,
        new_message=gtypes.Content(
            role="user",
            parts=[gtypes.Part(text=req.text)],
        ),
    ):
        function_calls = event.get_function_calls() or []
        # The coordinator routing to execution_agent at all is treated as a possible data
        # mutation (execution_agent's only tool is apply_subscription_change) — callers use
        # this to invalidate anything cached from stale subscription data, e.g. the annual
        # report. Coarser than checking the inner tool call itself, but that call happens
        # inside the wrapped AgentTool and isn't visible as a separate event here.
        if any(call.name == "execution_agent" for call in function_calls):
            action_taken = True
        # Whether the coordinator actually routed to the full optimization pipeline this
        # turn — the frontend used to guess this by regexing the USER's own message
        # (/full.?analysis|run analysis|analyse|analyze/i against req.text) to decide
        # whether to navigate to the analysis screen, independently of what the coordinator
        # actually did. "Don't run a full analysis, just tell me the date" matched that
        # regex and navigated away from the answer despite the coordinator correctly
        # routing to LOOKUP instead. Exposing the real routing decision here lets the
        # frontend react to what happened, not to a guess about the user's wording.
        if any(call.name == "optimization_pipeline" for call in function_calls):
            ran_optimization = True

        # `text`, not `t` — see the identical note in the /api/execute handler above; `t` is
        # also this module's i18n translate function and would otherwise be shadowed for the
        # rest of this handler.
        if event.is_final_response():
            text = _collect_text(event)
            if text.strip():
                last_text = text
        else:
            text = _collect_text(event)
            if text.strip() and not _has_function_call(event):
                fallback_text = text

    reply = last_text or fallback_text
    if not reply:
        raise HTTPException(status_code=500, detail=t("error.agentNoResponse"))

    return {"text": reply, "action_taken": action_taken, "ran_optimization": ran_optimization}
