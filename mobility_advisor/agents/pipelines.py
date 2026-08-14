from google.adk.agents import ParallelAgent, SequentialAgent

from .analysis import analyst_agent, forecaster_agent
from .annual import (
    annual_analyst_agent,
    annual_communicator_agent,
    annual_forecaster_agent,
    annual_optimizer_agent,
)
from .optimization import communicator_agent, optimizer_agent

optimization_pipeline = SequentialAgent(
    # Matches the Python variable name and every reference to it in agent.py's
    # COORDINATOR_INSTRUCTION ("Call optimization_pipeline", etc.) — AgentTool derives the
    # tool name the coordinator LLM actually sees from agent.name, not from the Python
    # variable it's assigned to, so a mismatch here left the model bridging "call
    # optimization_pipeline" against a tool literally named "mobility_advisor_pipeline"
    # from context alone. Every other agent in this file already follows var-name ==
    # agent.name == instruction text (annual_report_pipeline, qa_agent, execution_agent,
    # reject_agent) — this was the one exception.
    name="optimization_pipeline",
    description=(
        "Run the full four-stage portfolio review (analyst, forecaster, optimizer, "
        "communicator) and return the final user-facing recommendation report. Use this "
        "for any question about whether the overall mobility setup is optimal, or whether "
        "to change/cancel/add/downgrade/upgrade a subscription."
    ),
    # Sequential, NOT parallel: unlike the annual pipeline below, the Forecaster here reads
    # a file the Analyst wrote (merge_projected_trip_sets() combines the Analyst's
    # _projected_trips_history.json with the Forecaster's own calendar/car-usage trips) —
    # running the two concurrently would race the Analyst's write against the Forecaster's
    # read of the same file.
    sub_agents=[analyst_agent, forecaster_agent, optimizer_agent, communicator_agent],
)

annual_report_pipeline = SequentialAgent(
    name="annual_report_pipeline",
    description=(
        "Run a full annual mobility review (analyst, forecaster, optimizer, annual "
        "communicator) and return a complete year-in-review report. Use this when the "
        "user asks for an annual summary, yearly breakdown, or full annual mobility review."
    ),
    sub_agents=[
        ParallelAgent(
            name="annual_analyst_forecaster_parallel",
            description=(
                "Runs the Annual Analyst and Annual Forecaster stages concurrently — same "
                "independence rationale as the regular pipeline's parallel block."
            ),
            sub_agents=[annual_analyst_agent, annual_forecaster_agent],
        ),
        annual_optimizer_agent,
        annual_communicator_agent,
    ],
)
