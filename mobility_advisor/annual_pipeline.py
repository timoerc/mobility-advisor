from google.adk.agents import SequentialAgent

from .sub_agents import (
    annual_analyst_agent,
    annual_communicator_agent,
    annual_forecaster_agent,
    annual_optimizer_agent,
)

annual_report_pipeline = SequentialAgent(
    name="annual_report_pipeline",
    description=(
        "Run a full annual mobility review (analyst, forecaster, optimizer, annual communicator) "
        "and return a complete year-in-review report. Use this when the user asks for an annual "
        "summary, yearly breakdown, or full annual mobility review."
    ),
    sub_agents=[
        annual_analyst_agent,
        annual_forecaster_agent,
        annual_optimizer_agent,
        annual_communicator_agent,
    ],
)
