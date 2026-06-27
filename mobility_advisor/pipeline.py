from google.adk.agents import SequentialAgent

from .sub_agents import analyst_agent, communicator_agent, forecaster_agent, optimizer_agent

optimization_pipeline = SequentialAgent(
    name="mobility_advisor_pipeline",
    description=(
        "Run the full four-stage portfolio review (analyst, forecaster, optimizer, "
        "communicator) and return the final user-facing recommendation report. Use this "
        "for any question about whether the overall mobility setup is optimal, or whether "
        "to change/cancel/add/downgrade/upgrade a subscription."
    ),
    sub_agents=[analyst_agent, forecaster_agent, optimizer_agent, communicator_agent],
)
