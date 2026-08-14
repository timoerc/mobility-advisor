"""Verifies the fix in i18n.localized(): ADK's LlmAgent.canonical_instruction() sets
bypass_state_injection=True whenever `instruction` is a callable (InstructionProvider), which
makes ADK skip its own {key} session-state substitution entirely for provider-based
instructions (see google.adk.flows.llm_flows.instructions._process_agent_instruction and
google.adk.agents.llm_agent.LlmAgent.canonical_instruction). Without calling
inject_session_state() ourselves inside the provider (as i18n.localized() now does), the
communicator agent's "{recommendation}" placeholder would reach the model as literal text
instead of the optimizer's actual output — a silent regression, not a crash, so it would not
be caught by the existing test suite's structural assertions. This test constructs a real ADK
session/context (no LLM call) and checks the provider's resolved output directly.

No pytest-asyncio in this project's dependencies, so each test drives its own coroutine via
asyncio.run() rather than using async def test_* directly.
"""
import asyncio

from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from mobility_advisor import tools
from mobility_advisor.i18n import language_scope, localized
from mobility_advisor.sub_agents import _annual_communicator_instruction, annual_communicator_agent, communicator_agent


async def _make_readonly_context(state: dict, agent=communicator_agent) -> ReadonlyContext:
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="test_app", user_id="test_user", session_id="test_session", state=state
    )
    invocation_context = InvocationContext(
        session_service=session_service,
        artifact_service=InMemoryArtifactService(),
        invocation_id="test-invocation",
        agent=agent,
        session=session,
    )
    return ReadonlyContext(invocation_context)


def test_localized_still_resolves_session_state_placeholders():
    async def run():
        ctx = await _make_readonly_context({"recommendation": "RECOMMENDATION_PAYLOAD_MARKER"})
        provider = localized("Optimizer output: {recommendation}\nEnd.")
        return await provider(ctx)

    resolved = asyncio.run(run())
    assert "RECOMMENDATION_PAYLOAD_MARKER" in resolved
    assert "{recommendation}" not in resolved


def test_localized_appends_german_directive_after_state_injection():
    async def run():
        ctx = await _make_readonly_context({"recommendation": "X"})
        provider = localized("Base: {recommendation}")
        with language_scope("de"):
            return await provider(ctx)

    resolved = asyncio.run(run())
    assert resolved.startswith("Base: X")
    assert "OUTPUT LANGUAGE" in resolved
    assert "German (Deutsch)" in resolved


def test_localized_english_directive_is_empty():
    async def run():
        ctx = await _make_readonly_context({"recommendation": "X"})
        provider = localized("Base: {recommendation}")
        with language_scope("en"):
            return await provider(ctx)

    resolved = asyncio.run(run())
    assert resolved == "Base: X"


def test_communicator_agent_instruction_is_a_localized_provider():
    # communicator_agent.instruction must be the callable localized() produces (not a plain
    # string) — this is what makes ADK treat it as an InstructionProvider at all.
    assert callable(communicator_agent.instruction)

    async def run():
        ctx = await _make_readonly_context({"recommendation": "STEFAN_TEST_MARKER"})
        return await communicator_agent.instruction(ctx)

    resolved = asyncio.run(run())
    assert "STEFAN_TEST_MARKER" in resolved
    assert "{recommendation}" not in resolved


def test_annual_communicator_resolves_placeholders_and_appends_directive(monkeypatch):
    # Regression test for a real, pre-existing bug found while wiring the language directive:
    # _annual_communicator_instruction embeds {annual_recommendation}/{annual_analysis}/
    # {annual_forecast} ADK template placeholders but — being an InstructionProvider — never
    # had them resolved (ADK skips its automatic {key} substitution for any callable
    # instruction; see i18n.localized()'s docstring). Before the fix, the LLM would have
    # received the literal text "{annual_recommendation}" instead of the optimizer's output,
    # on every annual report, in both languages.
    original_data = tools._DATA
    tools._DATA = original_data.parent / "scenarios" / "stefan"
    try:
        async def run():
            ctx = await _make_readonly_context(
                {
                    "annual_recommendation": "OPTIMIZER_MARKER",
                    "annual_analysis": "ANALYST_MARKER",
                    "annual_forecast": "FORECAST_MARKER",
                },
                agent=annual_communicator_agent,
            )
            with language_scope("de"):
                return await _annual_communicator_instruction(ctx)

        resolved = asyncio.run(run())
    finally:
        tools._DATA = original_data

    assert "OPTIMIZER_MARKER" in resolved
    assert "ANALYST_MARKER" in resolved
    assert "FORECAST_MARKER" in resolved
    assert "{annual_recommendation}" not in resolved
    assert "{annual_analysis}" not in resolved
    assert "{annual_forecast}" not in resolved
    assert "OUTPUT LANGUAGE" in resolved  # directive appended


def test_all_six_user_facing_agents_are_localized():
    # The six agents whose output a user ever sees directly (root_agent/coordinator, both
    # communicators, execution/qa/reject) must all carry the language directive. The
    # intermediate pipeline stages (analyst/forecaster/optimizer/annual_*) are deliberately
    # excluded — their own instructions state their output is "consumed by downstream agents,
    # not displayed to the user" — so this test only covers the six that need it.
    from mobility_advisor.agent import root_agent
    from mobility_advisor.execution_agent import execution_agent
    from mobility_advisor.qa_agent import qa_agent
    from mobility_advisor.reject_agent import reject_agent
    from mobility_advisor.sub_agents import annual_communicator_agent, communicator_agent

    for agent in [root_agent, communicator_agent, annual_communicator_agent, execution_agent, qa_agent, reject_agent]:
        assert callable(agent.instruction), f"{agent.name}.instruction should be a localized() provider"
