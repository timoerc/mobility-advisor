"""Applies an explicitly-approved subscription change and records the outcome against
the analysis history entry it resolves."""
import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from google.adk.runners import InMemoryRunner
from google.genai import types as gtypes

from ... import clock, paths
from ...agents.execution import execution_agent
from ...i18n import t
from ...models import CurrentSubscriptions
from ...store.history import load_history, save_history
from ..deps import history_lock
from ..schemas import ExecuteRequest
from .chat import _collect_text, _has_function_call

router = APIRouter()


@router.post("/api/execute")
async def execute(req: ExecuteRequest):
    runner = InMemoryRunner(agent=execution_agent, app_name="mobility_advisor_execute")
    sid = f"execute_{uuid4().hex[:12]}"

    # Snapshot the subscription stack BEFORE the agent mutates it, so a successful change can later be
    # reverted by restoring this exact state (the executed action is free text and not reliably
    # invertible on its own). Persisted server-side on the history entry below, in this same request.
    prev_path = paths.DATA_DIR / "current_subscriptions.json"
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
        async with history_lock:
            hist = load_history()
            newest = hist.entries[-1] if hist.entries else None
            if newest and newest.id == req.analysis_id and newest.outcome != "executed":
                newest.outcome = "executed"
                newest.resolvedAlternativeId = req.alternative_id
                newest.resolvedMessage = reply
                newest.resolvedAt = clock.MOCK_TODAY.isoformat()
                newest.revertSnapshot = previous_subscriptions
                save_history(hist)
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
