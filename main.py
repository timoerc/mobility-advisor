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
from mobility_advisor.models import (
    AnalysisHistory,
    AnalysisHistoryEntry,
    AnalysisRunResult,
    CarUsage,
    CurrentSubscriptions,
    Recommendation,
    TravelHistory,
    catalog_lookup,
)
from mobility_advisor.pipeline import annual_report_pipeline, optimization_pipeline
from mobility_advisor.report_pdf import render_annual_report_pdf
from mobility_advisor.tools import MOCK_TODAY

_DATA = Path(__file__).parent / "mobility_advisor" / "data"
_SCENARIOS = Path(__file__).parent / "mobility_advisor" / "scenarios"
_KNOWN_PERSONAS = frozenset({"maja", "stefan", "lena"})
_SCENARIO_FILES = [
    "persona.json",
    "current_subscriptions.json",
    "travel_history_raw.json",
    "mail_raw.json",
    "calendar_events_live.json",
    "car_usage.json",
    "analysis_history.json",
]
_MODEL_ID = "openai/OpenAI GPT OSS 120b KI:Inferenz.nrw"

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Mobility Advisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

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


class ResolveAnalysisRequest(BaseModel):
    outcome: Literal["kept_current", "executed"]
    alternative_id: str
    message: str = ""


# ── Profile helpers ───────────────────────────────────────────────────────────


def _atomic_write(path: Path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
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
    """Copy all pipeline JSON files from scenarios/{persona_id}/ into data/."""
    scenario_dir = _SCENARIOS / persona_id
    if not scenario_dir.is_dir():
        return False
    for fname in _SCENARIO_FILES:
        src = scenario_dir / fname
        if src.exists():
            shutil.copy2(src, _DATA / fname)
    return True


# ── Analysis history helpers ──────────────────────────────────────────────────
# analysis_history.json lives only in data/ (never scenarios/) — it's part of the
# single active, mutable dataset and gets reset on every persona activation just
# like current_subscriptions.json, via _SCENARIO_FILES above.

_history_lock = asyncio.Lock()


def _load_history() -> AnalysisHistory:
    path = _DATA / "analysis_history.json"
    if not path.exists():
        return AnalysisHistory(entries=[])
    try:
        return AnalysisHistory.model_validate(json.loads(path.read_text()))
    except (json.JSONDecodeError, ValidationError):
        return AnalysisHistory(entries=[])


def _save_history(hist: AnalysisHistory) -> None:
    _atomic_write(_DATA / "analysis_history.json", hist.model_dump())


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
        persona = json.loads(pf.read_text())
        sf = folder / "current_subscriptions.json"
        subscriptions = (
            CurrentSubscriptions.model_validate(json.loads(sf.read_text())).model_dump()["subscriptions"]
            if sf.exists() else []
        )
        persona["profileData"]["subscriptions"] = subscriptions
        cf = folder / "car_usage.json"
        persona["profileData"]["car"] = (
            json.loads(cf.read_text()) if cf.exists() else CarUsage().model_dump()
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
    data = CurrentSubscriptions.model_validate(json.loads(path.read_text()))
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
    data = TravelHistory.model_validate(json.loads(path.read_text()))
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

{
  "verdict": "<concise 8-10 word headline for the RECOMMENDED option, e.g. 'Your BahnCard 50 did not pay off this year'>",
  "confidence": "<'high' if ROI is clear and unambiguous; 'medium' if borderline or uncertain; 'low' if highly uncertain>",
  "summaryText": "<1-2 sentences summarising the key finding and saving for the RECOMMENDED option>",
  "metrics": [
    {
      "value": <number>,
      "unit": "<e.g. '€/year', 'trips', 'kg CO2'>",
      "direction": "<one of: 'save' | 'reduce' | 'extra_cost' | 'increase' | 'neutral'>",
      "label": "<short label, e.g. 'Potential saving', 'Long-distance trips'>"
    }
  ],
  "reasoning": ["<bullet 1>", "<bullet 2>", ...],
  "assumptions": ["<assumption 1>", ...],
  "alternatives": [
    {
      "id": "<short slug, e.g. 'cancel' or 'keep'>",
      "name": "<human-readable name describing this OPTION, not just a product — see naming rules below>",
      "annualCostEur": <annual subscription cost for this option in EUR>,
      "savingsVsCurrentEur": <positive = saves vs current; negative = costs more vs current>,
      "co2Impact": "<e.g. 'Neutral' or '-42 kg CO2/month'>",
      "co2ImpactKg": <the signed kg/year number stated in this option's CO2 impact line;
        positive = this option SAVES CO2 vs. current, negative = it emits MORE; 0 for
        'Neutral' or the 'Keep current setup' row>,
      "tradeoff": "<one sentence>",
      "isRecommended": <true for exactly one alternative — the candidate the report marks Recommended — false for all others>,
      "action": {
        "title": "<imperative sentence, e.g. 'Cancel your BahnCard 50 (2. Klasse, Standard, Jahresabo)'>",
        "description": "<1-2 sentences with action details and deadline>",
        "consequence": "<what changes in the user's portfolio once this is applied, e.g. 'Your BahnCard 50 (2. Klasse, Standard, Jahresabo) will be cancelled and BahnCard 25 (2. Klasse, Standard, Jahresabo) will start in its place.' If this is a swap/replace, this field is what tells the execution step which current subscription to remove — it must always name that exact subscription, not just the new product. Do not say the change requires separate/manual action or 'awaits approval' — confirming applies it immediately in this prototype>"
      }
    }
  ]
}

Rules:
- The report contains 1 or 2 candidate "Option:" blocks (each optionally suffixed " — Recommended").
  Produce exactly one "alternatives" entry per Option block — with "action" set to that
  option's title/description/consequence derived from its "Change"/"Action by" lines, and
  isRecommended true only for the option suffixed " — Recommended" — PLUS always exactly one
  additional entry for the status-quo baseline:
    - id: a short slug like "keep"
    - name: the literal string "Keep current setup" — never the product name, even though the
      product being kept is the same one named elsewhere
    - annualCostEur: the report's "Your current setup" monthly figure x 12
    - savingsVsCurrentEur: 0
    - co2Impact: "Neutral"
    - co2ImpactKg: 0
    - isRecommended: false
    - action: JSON null (not an object, not omitted)
  Never produce more than 2 alternatives with a non-null "action". If the report somehow
  contains more than 2 Option blocks, use only the first 2.
- Exactly one alternative must have isRecommended: true, and its action must not be null.
- metrics must include at minimum: the monthly or annual saving (direction 'save') for the
  RECOMMENDED alternative, and CO2 impact (direction 'reduce' or 'neutral')
- for each alternative with a non-null action: annualCostEur and savingsVsCurrentEur come from
  THAT option's own "Monthly cost: €Y.YY/mo (saving €Z.ZZ/mo ...)" line, x 12 — never copy one
  option's numbers onto another
- alternatives[].name must always describe the ACTION for that row, never a bare product name
  on its own — two rows must never end up with an identical name just because they both
  reference the same product. Prefix with the verb that matches what actually happens to that
  product in this option: "Cancel <product>" (pure cancellation, nothing added), "Switch to
  <product>" / "Downgrade to <product>" / "Upgrade to <product>" (swap/replace), "Add
  <product>" (new subscription, nothing removed). Example: if an option cancels "BahnCard 50
  (2. Klasse, Standard, Jahresabo)" with nothing replacing it, that row's name is "Cancel
  BahnCard 50 (2. Klasse, Standard, Jahresabo)" — NOT "BahnCard 50 (2. Klasse, Standard,
  Jahresabo)" (which would be indistinguishable from the status-quo row keeping that same card)
- all numbers must come verbatim from the report below — never invent figures
- co2ImpactKg's sign must match that option's own "CO₂ impact" line: positive for a stated
  saving, negative for a stated increase, 0 for "Neutral" — never copy one option's CO2
  figure onto another
- product/subscription names (in every alternative's action.title/description/consequence, and
  in alternatives[].name) must be copied verbatim and in full from the report below, e.g.
  "BahnCard 25 (2. Klasse, Standard, Jahresabo)" — never shorten to a generic name like
  "BahnCard 25"; this name is executed literally if the user picks that alternative, so an
  underspecified name breaks execution for ANY alternative, not just the recommended one
- if a field value cannot be determined from the report below, use a sensible default (e.g.
  'Neutral' for co2Impact, 0 for co2ImpactKg, [] for assumptions)
""".strip()


def _clamp_actionable_alternatives(
    rec: Recommendation, max_actionable: int = 2
) -> Recommendation:
    """Defensively enforce the product cap of `max_actionable` actionable alternatives.

    The prompt already asks for this cap, but nothing stops the LLM from overshooting —
    this guarantees the API response can never violate it regardless of what the LLM
    returns. Keeps the recommended alternative, then earlier non-recommended actionable
    alternatives up to the cap (in original order), then all keep-current-setup row(s)
    (action is None) unchanged.
    """
    actionable = [a for a in rec.alternatives if a.action is not None]
    if len(actionable) <= max_actionable:
        return rec
    keep_rows = [a for a in rec.alternatives if a.action is None]
    recommended = [a for a in actionable if a.isRecommended]
    others = [a for a in actionable if not a.isRecommended]
    rec.alternatives = (recommended + others)[:max_actionable] + keep_rows
    return rec


_CO2_METHODOLOGY_ASSUMPTION = (
    "CO2 impact is 0 for any change that only adjusts price or tier on a mode you already "
    "use (e.g. BahnCard 50 → BahnCard 25) — it only changes when an action adds or removes "
    "your only means of accessing a transport mode, such as a car-sharing membership."
)


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
            alt.savingsVsCurrentEur = keep_cost - alt.annualCostEur
    for alt in rec.alternatives:
        if alt.action is None:
            alt.co2Impact = "Neutral"
            alt.co2ImpactKg = 0.0
    if _CO2_METHODOLOGY_ASSUMPTION not in rec.assumptions:
        rec.assumptions.append(_CO2_METHODOLOGY_ASSUMPTION)
    return rec


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
    # Strip markdown code fences if the model wraps its output
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:].lstrip("\n")
    parsed = json.loads(text)
    recommendation = Recommendation.model_validate(parsed)
    recommendation = _normalize_keep_current_setup(recommendation)
    return _clamp_actionable_alternatives(recommendation)


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
        detail=(
            f"The pipeline did not produce a result after {max_attempts} attempts "
            f"(last issue: missing input {last_error}). This can happen when a stage's "
            "response comes back empty — either an oversized prompt or an intermittent "
            "backend hiccup. Please try again."
        ),
    ) from last_error


# ── Analyse endpoint ──────────────────────────────────────────────────────────

@app.post("/api/analyze", response_model=AnalysisRunResult)
async def analyze(req: AnalyzeRequest):
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
            detail=f"The recommendation pipeline failed before producing a report: {exc}",
        ) from exc

    try:
        rec = await _extract_recommendation_json(report_text)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"JSON extraction failed: {exc}"
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
        report_text, sid = await _with_pipeline_retry(attempt)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"The annual report pipeline failed before producing a report: {exc}",
        ) from exc

    if "<!-- TRIPS_TABLE_PLACEHOLDER -->" in report_text:
        session = await runner.session_service.get_session(
            app_name="mobility_advisor_annual", user_id="user", session_id=sid
        )
        analysis_text = (session.state.get("analysis") or "") if session else ""
        report_text = report_text.replace(
            "<!-- TRIPS_TABLE_PLACEHOLDER -->", _extract_trips_table(analysis_text)
        )

    try:
        pdf_bytes = render_annual_report_pdf(report_text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF rendering failed: {exc}") from exc

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
        if event.is_final_response():
            t = _collect_text(event)
            if t.strip():
                last_text = t
        else:
            t = _collect_text(event)
            if t.strip() and not _has_function_call(event):
                fallback_text = t

    reply = last_text or fallback_text
    if not reply:
        raise HTTPException(status_code=500, detail="Execution agent produced no response")

    success = bool(tool_result and tool_result.get("status") == "applied")
    return {"success": success, "message": reply}


# ── Analysis history endpoints ────────────────────────────────────────────────

@app.get("/api/analysis-history", response_model=list[AnalysisHistoryEntry])
async def get_analysis_history():
    """Return this persona's analysis history, newest first. Entries are stored
    oldest-first on disk (mocked ones authored in narrative order, live ones
    appended as they occur), and reversed here for display."""
    hist = _load_history()
    return list(reversed(hist.entries))


@app.post("/api/analysis-history/{entry_id}/resolve")
async def resolve_analysis(entry_id: str, req: ResolveAnalysisRequest):
    """Record what the user decided about a past analysis: kept their current
    setup, or executed one of the proposed alternatives."""
    async with _history_lock:
        hist = _load_history()
        entry = next((e for e in hist.entries if e.id == entry_id), None)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"No analysis history entry '{entry_id}'.")
        entry.outcome = req.outcome
        entry.resolvedAlternativeId = req.alternative_id
        entry.resolvedMessage = req.message
        entry.resolvedAt = MOCK_TODAY.isoformat()
        _save_history(hist)
    return {"ok": True}


# ── Chat endpoint ─────────────────────────────────────────────────────────────

def _extract_trips_table(analysis_text: str) -> str:
    """Slice out the analyst's 'Trips considered (...)' section, verbatim.

    annual_analyst_agent's instruction always emits this table as the last thing
    in its report, after the subscription summary, so once the heading is found
    everything after it IS the table. Degrades to a plain note (not a crash) if
    the heading is missing, e.g. because the analyst stage's own output was
    truncated or failed.
    """
    idx = analysis_text.lower().find("trips considered")
    if idx == -1:
        return "_(Trip-level detail unavailable for this run.)_"
    return analysis_text[idx:]


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
    async for event in runner.run_async(
        user_id="user",
        session_id=req.session_id,
        new_message=gtypes.Content(
            role="user",
            parts=[gtypes.Part(text=req.text)],
        ),
    ):
        # The coordinator routing to execution_agent at all is treated as a possible data
        # mutation (execution_agent's only tool is apply_subscription_change) — callers use
        # this to invalidate anything cached from stale subscription data, e.g. the annual
        # report. Coarser than checking the inner tool call itself, but that call happens
        # inside the wrapped AgentTool and isn't visible as a separate event here.
        if any(call.name == "execution_agent" for call in event.get_function_calls() or []):
            action_taken = True

        if event.is_final_response():
            t = _collect_text(event)
            if t.strip():
                last_text = t
        else:
            t = _collect_text(event)
            if t.strip() and not _has_function_call(event):
                fallback_text = t

    reply = last_text or fallback_text
    if not reply:
        raise HTTPException(status_code=500, detail="Agent produced no response")

    return {"text": reply, "action_taken": action_taken}
