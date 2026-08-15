"""Profile onboarding/editing, the persona picker, and scenario activation."""
import json

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from ... import paths
from ...i18n import pick, t
from ...models import CarUsage, CurrentSubscriptions
from ...store.scenarios import activate_scenario
from ..schemas import ActivateRequest, ProfilePayload

router = APIRouter()


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
        "tagline": payload.personal.profession or t("persona.newUser"),
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


@router.post("/api/profile")
async def save_profile(payload: ProfilePayload):
    """Save a persona's full profile and make it the active data set."""
    try:
        subscriptions = CurrentSubscriptions.model_validate(_subs_from_payload(payload)).model_dump()
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid subscriptions: {exc}") from exc
    paths.atomic_write_json(paths.DATA_DIR / "persona.json", _persona_from_payload(payload))
    paths.atomic_write_json(paths.DATA_DIR / "current_subscriptions.json", subscriptions)
    paths.atomic_write_json(paths.DATA_DIR / "car_usage.json", payload.car.model_dump())
    if payload.persona_id not in paths.known_personas():
        # Custom/new profile, not one of the pre-built scenario personas: there is no
        # real travel or calendar history for them, so clear out whatever scenario data
        # happened to be active last instead of silently analysing it as if it were theirs.
        paths.atomic_write_json(paths.DATA_DIR / "travel_history_raw.json", {"trips": []})
        paths.atomic_write_json(paths.DATA_DIR / "calendar_events_live.json", {"events": []})
        paths.atomic_write_json(paths.DATA_DIR / "analysis_history.json", {"entries": []})
        paths.atomic_write_json(paths.DATA_DIR / "life_events.json", {"events": []})
    # Same reasoning as activate_scenario: this profile save just became the active
    # persona/dataset, so any scratch files from whichever persona ran last must not linger.
    paths.clear_scratch_files()
    return {"ok": True}


@router.get("/api/personas")
async def list_personas():
    """Assemble each persona from persona.json + current_subscriptions.json + car_usage.json."""
    result = []
    for folder in sorted(paths.SCENARIOS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        pf = folder / "persona.json"
        if not pf.exists():
            continue
        persona = json.loads(pf.read_text(encoding="utf-8"))
        # tagline_de/profession_de/notes_de siblings in the scenario fixture, resolved for the
        # active request's language — see mobility_advisor.i18n.pick(). persona.json is a raw
        # dict, not Pydantic-validated, so this is the only place the German variants need wiring.
        persona["tagline"] = pick(persona, "tagline")
        personal = persona["profileData"]["personal"]
        personal["profession"] = pick(personal, "profession")
        persona["profileData"]["notes"] = pick(persona["profileData"], "notes")
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


@router.post("/api/activate")
async def activate_persona(req: ActivateRequest):
    """Switch the active data set to a named scenario."""
    if req.persona_id not in paths.known_personas():
        raise HTTPException(
            status_code=404,
            detail=f"No scenario for persona '{req.persona_id}'.",
        )
    found = activate_scenario(req.persona_id)
    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"No scenario directory for persona '{req.persona_id}'.",
        )
    return {"ok": True}
