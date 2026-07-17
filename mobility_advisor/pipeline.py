from google.adk.agents import ParallelAgent, SequentialAgent

from .sub_agents import (
    analyst_agent,
    annual_analyst_agent,
    annual_communicator_agent,
    annual_forecaster_agent,
    annual_optimizer_agent,
    communicator_agent,
    forecaster_agent,
    optimizer_agent,
)

optimization_pipeline = SequentialAgent(
    name="mobility_advisor_pipeline",
    description=(
        "Run the full four-stage portfolio review (analyst, forecaster, optimizer, "
        "communicator) and return the final user-facing recommendation report. Use this "
        "for any question about whether the overall mobility setup is optimal, or whether "
        "to change/cancel/add/downgrade/upgrade a subscription."
    ),
    sub_agents=[
        ParallelAgent(
            name="analyst_forecaster_parallel",
            description=(
                "Runs the Analyst and Forecaster stages concurrently — they are mutually "
                "independent (Analyst reads travel/subscription/car data, Forecaster reads "
                "calendar/life-event data; neither reads the other's output) — to cut one "
                "full LLM round-trip off the pipeline's critical path versus running them "
                "sequentially."
            ),
            sub_agents=[analyst_agent, forecaster_agent],
        ),
        optimizer_agent,
        communicator_agent,
    ],
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
