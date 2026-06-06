# Mobility Advisor

> *Continuously optimizing the traveler's mobility portfolio.*

Agentic AI system that continuously optimizes a user's mobility contract portfolio by integrating multi-modal travel data, contracts, and calendar signals via multi-agent orchestration.

Developed as part of a joint university course by **University of Cologne (UoC)** and **BCG Platinion**.

---

## Use Case

Modern commuters hold a mix of mobility subscriptions — public transit passes, rail cards, shared mobility memberships — but rarely have the time or data to evaluate whether their setup is actually optimal.

**Mobility Advisor** addresses this by acting as a continuous, AI-driven portfolio manager for personal mobility. It analyzes travel behavior, active contracts, and upcoming demand to surface inefficiencies and recommend right-sized alternatives — with transparent cost and CO₂ trade-offs. It answers the core question:

> *"Is my mobility setup optimal right now?"*

---

## Key Features

- **Behavioral Analysis**: Continuously analyzes real travel behavior across transportation modes and active contracts to surface inefficiencies.
- **Portfolio Recommendations**: Recommends right-sized contract combinations with transparent cost and CO₂ trade-offs.
- **Life Event Triggering**: Detects life events (relocation, job change, family changes) via opt-in signals to prompt portfolio reviews.
- **Demand Forecasting**: Models upcoming travel demand using calendar feeds and historical patterns rather than relying purely on past data.
- **Human-in-the-Loop Execution**: Executes approved changes via DB and partner APIs, with mandatory user validation at every critical step.
- **Reporting & Ad-hoc Queries**: Annual mobility review (savings, CO₂ avoided) plus a conversational interface for on-demand optimization queries.

---

## Data Sources

| Source | Description |
|---|---|
| Mobility Setup | Baseline subscriptions and contracts captured at onboarding |
| Travel History | Multi-modal trip data across corporate and private providers |
| Calendar Feeds | Upcoming meetings and events for forward demand modeling |
| Contracts Catalog | Public transit tiers, BahnCard pricing, shared mobility memberships |
| CO₂ Emission Factors | Emissions coefficients per transport mode |
| Opt-in Signals | Automated life event detection (e.g., email parsing) |

---

## Multi-Agent Architecture

The system is designed around four specialized agents with strict context isolation:

| Agent | Responsibility |
|---|---|
| **Analyst** | Uncovers inefficiencies in historical multi-modal portfolio data |
| **Forecaster** | Builds forward-looking demand assumptions from calendar and life event signals |
| **Optimizer** | Simulates scenarios balancing cost savings vs. CO₂ targets |
| **Communicator** | Drafts recommendations and executes approved changes via partner APIs |

---

## Project Status

🚧 Under active development.
