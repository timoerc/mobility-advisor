"""Mobility Advisor API — thin FastAPI wrapper over the ADK agent pipeline."""
import json
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("KICONNECT_API_KEY", ""))
os.environ.setdefault("OPENAI_API_BASE", "https://chat.kiconnect.nrw/api/v1")

import litellm
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import InMemoryRunner, Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types as gtypes
from pydantic import BaseModel

from mobility_advisor.agent import root_agent
from mobility_advisor.pipeline import optimization_pipeline

_DATA = Path(__file__).parent / "mobility_advisor" / "data"
_SCENARIOS = Path(__file__).parent / "mobility_advisor" / "scenarios"
_KNOWN_PERSONAS = frozenset({"maja", "stefan", "lena"})
_SCENARIO_FILES = [
    "persona.json",
    "current_subscriptions.json",
    "travel_history.json",
    "calendar_events.json",
    "mobility_catalog.json",
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
    employment_status: str = ""
    profession: str = ""
    household_context: str = ""


class _Commute(BaseModel):
    wfh_days: list[str] = []
    office_days: list[str] = []


class _Car(BaseModel):
    owns_car: bool = False
    fuel_type: str | None = None
    car_size: str | None = None
    efficiency: float | None = None
    efficiency_unit: str | None = None
    monthly_km_estimate: float | None = None


class _Subscription(BaseModel):
    model_config = {"extra": "ignore"}
    provider: str
    product: str
    monthly_cost_eur: float
    billing_cycle: str = "monthly"
    next_renewal_date: str = ""
    started: str = ""
    notes: str = ""


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
    car: _Car = _Car()
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


# ── Profile helpers ───────────────────────────────────────────────────────────


def _atomic_write(path: Path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _subs_from_payload(payload: ProfilePayload) -> dict:
    return {
        "subscriptions": [
            {
                "provider": s.provider,
                "product": s.product,
                "monthly_cost_eur": s.monthly_cost_eur,
                "billing_cycle": s.billing_cycle,
                "next_renewal_date": s.next_renewal_date,
                "started": s.started,
                "notes": s.notes,
            }
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
            "car": payload.car.model_dump(),
            "priorities": payload.priorities.model_dump(),
            "integrations": payload.integrations,
            "notes": payload.notes,
        },
    }


def _activate_from_scenario(persona_id: str) -> bool:
    """Copy all 5 pipeline JSON files from scenarios/{persona_id}/ into data/."""
    scenario_dir = _SCENARIOS / persona_id
    if not scenario_dir.is_dir():
        return False
    for fname in _SCENARIO_FILES:
        src = scenario_dir / fname
        if src.exists():
            shutil.copy2(src, _DATA / fname)
    return True


# ── Profile endpoints ─────────────────────────────────────────────────────────

@app.post("/api/profile")
async def save_profile(payload: ProfilePayload):
    """Save a persona's full profile and make it the active data set."""
    _atomic_write(_DATA / "persona.json", _persona_from_payload(payload))
    _atomic_write(_DATA / "current_subscriptions.json", _subs_from_payload(payload))
    if payload.persona_id not in _KNOWN_PERSONAS:
        # Custom/new profile, not one of the pre-built scenario personas: there is no
        # real travel or calendar history for them, so clear out whatever scenario data
        # happened to be active last instead of silently analysing it as if it were theirs.
        _atomic_write(_DATA / "travel_history.json", {"trips": []})
        _atomic_write(_DATA / "calendar_events.json", {"events": []})
    return {"ok": True}


@app.get("/api/personas")
async def list_personas():
    """Assemble each persona from persona.json + current_subscriptions.json."""
    result = []
    for folder in sorted(_SCENARIOS.iterdir()):
        if not folder.is_dir():
            continue
        pf = folder / "persona.json"
        if not pf.exists():
            continue
        persona = json.loads(pf.read_text())
        sf = folder / "current_subscriptions.json"
        subscriptions = json.loads(sf.read_text()).get("subscriptions", []) if sf.exists() else []
        persona["profileData"]["subscriptions"] = subscriptions
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


# ── JSON extraction ───────────────────────────────────────────────────────────

_JSON_SYSTEM_PROMPT = """
Convert the optimizer recommendation into this exact JSON structure.
Output ONLY valid JSON — no markdown fences, no surrounding text.

{
  "verdict": "<concise 8-10 word headline, e.g. 'Your BahnCard 50 did not pay off this year'>",
  "confidence": "<'high' if ROI is clear and unambiguous; 'medium' if borderline or uncertain; 'low' if highly uncertain>",
  "summaryText": "<1-2 sentences summarising the key finding and saving>",
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
      "name": "<human-readable name>",
      "annualCostEur": <annual subscription cost for this option in EUR>,
      "savingsVsCurrentEur": <positive = saves vs current; negative = costs more vs current>,
      "co2Impact": "<e.g. 'Neutral' or '-42 kg CO2/month'>",
      "tradeoff": "<one sentence>",
      "isRecommended": <true for the proposed action, false for all others>
    }
  ],
  "proposedAction": {
    "title": "<imperative sentence, e.g. 'Cancel your BahnCard 50 renewal'>",
    "description": "<1-2 sentences with action details and deadline>",
    "consequence": "<what happens after the action is taken>"
  }
}

Rules:
- metrics must include at minimum: the annual or monthly saving (direction 'save') and CO2 impact (direction 'reduce' or 'neutral')
- alternatives must include at minimum: the recommended action (isRecommended: true) and the status-quo 'Keep current setup' (isRecommended: false, savingsVsCurrentEur: 0)
- for 'Keep current setup': annualCostEur = current monthly cost x 12, savingsVsCurrentEur = 0
- for the recommended action: annualCostEur = proposed monthly cost x 12, savingsVsCurrentEur = monthly saving x 12
- all numbers must come verbatim from the optimizer output — never invent figures
- if a field value cannot be determined from the optimizer output, use a sensible default (e.g. 'Neutral' for co2Impact, [] for assumptions)
""".strip()


async def _extract_recommendation_json(optimizer_output: str) -> dict:
    response = await litellm.acompletion(
        model=_MODEL_ID,
        messages=[
            {"role": "system", "content": _JSON_SYSTEM_PROMPT},
            {"role": "user", "content": optimizer_output},
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
    return json.loads(text)


# ── Analyse endpoint ──────────────────────────────────────────────────────────

@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    runner = InMemoryRunner(agent=optimization_pipeline, app_name="mobility_advisor_analyze")
    sid = f"analysis_{uuid4().hex[:12]}"

    await runner.session_service.create_session(
        app_name="mobility_advisor_analyze",
        user_id="user",
        session_id=sid,
    )

    async for _ in runner.run_async(
        user_id="user",
        session_id=sid,
        new_message=gtypes.Content(
            role="user",
            parts=[gtypes.Part(text="Analyse my current mobility setup and subscriptions.")],
        ),
    ):
        pass

    session = await runner.session_service.get_session(
        app_name="mobility_advisor_analyze",
        user_id="user",
        session_id=sid,
    )
    optimizer_output = (session.state or {}).get("recommendation", "")

    if not optimizer_output:
        raise HTTPException(status_code=500, detail="Pipeline produced no recommendation")

    try:
        return await _extract_recommendation_json(optimizer_output)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"JSON extraction failed: {exc}"
        ) from exc


# ── Chat endpoint ─────────────────────────────────────────────────────────────

def _collect_text(event) -> str:
    if not event.content:
        return ""
    return "".join(
        part.text
        for part in (event.content.parts or [])
        if hasattr(part, "text") and part.text
    )


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
    async for event in runner.run_async(
        user_id="user",
        session_id=req.session_id,
        new_message=gtypes.Content(
            role="user",
            parts=[gtypes.Part(text=req.text)],
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

    reply = last_text or fallback_text
    if not reply:
        raise HTTPException(status_code=500, detail="Agent produced no response")

    return {"text": reply}
