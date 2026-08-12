"""Shared, process-lifetime state the route modules depend on: per-session chat state,
the analysis-history write lock, and the model id used by the two raw litellm JSON-
extraction calls in recommendation/extraction.py."""
import asyncio

from google.adk.sessions.in_memory_session_service import InMemorySessionService

from ..agents.model import _MODEL

# Derived from agents.model._MODEL (the pipeline agents' own LiteLlm instance), not a
# second hardcoded copy of the model string — the two non-agent JSON-extraction calls in
# recommendation/extraction.py previously duplicated this literal independently, so
# changing the pipeline's model left them silently pointed at the old one.
MODEL_ID = _MODEL.model

_chat_services: dict[str, InMemorySessionService] = {}
CHAT_APP = "mobility_advisor_chat"


def chat_service(session_id: str) -> InMemorySessionService:
    if session_id not in _chat_services:
        _chat_services[session_id] = InMemorySessionService()
    return _chat_services[session_id]


# analysis_history.json is part of the single active, mutable dataset in data/ — guards
# every read-modify-write against it across /api/analyze, /api/execute, and the
# resolve/revert endpoints, all of which run concurrently against the same file.
history_lock = asyncio.Lock()
