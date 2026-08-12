"""The coordinator-routed chat endpoint, plus the ADK event-parsing helpers
(_collect_text/_has_function_call) shared by every route that drives a Runner."""
from fastapi import APIRouter, HTTPException
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.genai import types as gtypes

from ... import paths
from ...agent import root_agent
from ..deps import CHAT_APP, chat_service
from ..schemas import ChatRequest

router = APIRouter()


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


@router.post("/api/chat")
async def chat(req: ChatRequest):
    # Unlike /api/analyze, this endpoint didn't clear the trip-projection/optimization
    # scratch files before running — and derive_projected_trips_from_calendar() APPENDS to
    # _projected_trips_calendar.json rather than overwriting it. Activate persona B, then
    # ask "is my setup optimal?" in chat, and persona A's calendar-derived routes (still on
    # disk from whenever they were last written) got merged into B's run. Clearing here
    # matches /api/analyze's own paths.clear_scratch_files() call and is safe even
    # when this message doesn't touch optimization at all: the coordinator may or may not
    # route to optimization_pipeline, but no other code path depends on these files
    # surviving between requests (the alternatives builder is only ever read back within
    # the same /api/analyze call that wrote them).
    paths.clear_scratch_files()
    svc = chat_service(req.session_id)
    runner = Runner(
        agent=root_agent,
        app_name=CHAT_APP,
        session_service=svc,
        artifact_service=InMemoryArtifactService(),
        memory_service=InMemoryMemoryService(),
    )

    session = await svc.get_session(
        app_name=CHAT_APP, user_id="user", session_id=req.session_id
    )
    if session is None:
        await svc.create_session(
            app_name=CHAT_APP, user_id="user", session_id=req.session_id
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

    return {"text": reply, "action_taken": action_taken, "ran_optimization": ran_optimization}
