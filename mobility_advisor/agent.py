from google.adk.agents import SequentialAgent

from .sub_agents import analyst_agent, communicator_agent, forecaster_agent, optimizer_agent

# TODO (Tier 2): add persistent user state, RAG over contracts catalog, calendar-driven forecasting, constraint capture
root_agent = SequentialAgent(
    name="mobility_advisor_pipeline",
    description="Tier 1 Mobility Advisor: analyze → forecast → optimize → communicate.",
    sub_agents=[analyst_agent, forecaster_agent, optimizer_agent, communicator_agent],
)
