"""Mobility Advisor API — thin FastAPI wrapper over the ADK agent pipeline."""
import json
import os
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
_MODEL_ID = "openai/OpenAI GPT OSS 120b KI:Inferenz.nrw"

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Mobility Advisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
    personal: _Personal = _Personal()
    location: dict = {}
    commute: _Commute = _Commute()
    car: _Car = _Car()
    subscriptions: list[_Subscription] = []
    priorities: _Priorities = _Priorities()
    integrations: dict = {}
    monthlyBudgetEur: float = 0
    notes: str = ""


class ActivateRequest(BaseModel):
    persona_id: str


class AnalyzeRequest(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    session_id: str
    text: str


# ── Profile helpers ───────────────────────────────────────────────────────────

_PERSONA_PROFILES = _DATA / "persona_profiles.json"


def _load_persona_profiles() -> dict:
    if _PERSONA_PROFILES.exists():
        return json.loads(_PERSONA_PROFILES.read_text())
    return {}


def _flexibility(wfh_days: list[str]) -> str:
    n = len(wfh_days)
    if n >= 4:
        return "high"
    if n >= 2:
        return "medium"
    return "low"


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


def _prefs_and_subs_from_payload(payload: ProfilePayload) -> tuple[dict, dict]:
    prefs = {
        "name": payload.personal.full_name or "the user",
        "flexibility_need": _flexibility(payload.commute.wfh_days),
        "sustainability_weight": round(payload.priorities.sustainability, 4),
        "values_time_over_money": payload.priorities.time > payload.priorities.cost,
        "notes": payload.notes,
    }
    subs = {
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
    return prefs, subs


def _activate_from_stored(persona_id: str) -> bool:
    """Write a stored persona's data to the active data files. Returns False if not found."""
    profiles = _load_persona_profiles()
    entry = profiles.get(persona_id)
    if not entry:
        return False
    _atomic_write(_DATA / "user_preferences.json", entry["user_preferences"])
    _atomic_write(_DATA / "current_subscriptions.json", entry["current_subscriptions"])
    return True


# ── Profile endpoints ─────────────────────────────────────────────────────────

@app.post("/api/profile")
async def save_profile(payload: ProfilePayload):
    """Save a persona's profile and make it the active data set."""
    prefs, subs = _prefs_and_subs_from_payload(payload)

    # Persist per-persona
    profiles = _load_persona_profiles()
    profiles[payload.persona_id] = {
        "user_preferences": prefs,
        "current_subscriptions": subs,
    }
    _atomic_write(_PERSONA_PROFILES, profiles)

    # Make active
    _atomic_write(_DATA / "user_preferences.json", prefs)
    _atomic_write(_DATA / "current_subscriptions.json", subs)
    return {"ok": True}


@app.post("/api/activate")
async def activate_persona(req: ActivateRequest):
    """Switch the active data set to a previously saved persona."""
    found = _activate_from_stored(req.persona_id)
    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"No saved profile for persona '{req.persona_id}'. Complete onboarding first.",
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

    if not last_text:
        raise HTTPException(status_code=500, detail="Agent produced no response")

    return {"text": last_text}
