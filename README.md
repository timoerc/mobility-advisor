# Mobility Advisor

An agentic AI system that answers one question: **"Is my mobility setup optimal right now?"**

Built for a joint course at **University of Cologne × BCG Platinion**. The system analyzes a traveler's current subscription portfolio, forecasts forward demand, and recommends concrete contract changes — with full cost and CO₂ transparency and a human-in-the-loop gate before any change is made.

---

## What it does (Tier 1)

Two pipelines share the same four AI agents:

**`mobility_advisor_pipeline`** — single-run recommendation:

1. **Analyst** — reviews 12 months of travel history against active subscriptions; flags under-used contracts
2. **Forecaster** — reads upcoming calendar events; summarizes forward demand and life-event signals
3. **Optimizer** — combines findings with the market catalog; proposes one concrete change with €/mo savings and CO₂ delta
4. **Communicator** — formats a scannable recommendation for the user; explicitly notes that no change has been made and approval is required

**`annual_report_pipeline`** — full year-in-review:

Runs the same analyst → forecaster → optimizer stages, then an **Annual Communicator** renders a structured 6-section report:
1. Year at a Glance (total spend, savings, CO₂ avoided, dominant mode)
2. Subscription ROI (break-even verdict per product)
3. CO₂ Report (rail vs. car-share baseline, mode split)
4. Recommendations Taken This Year
5. Forward Outlook
6. Assumptions & Data Quality

Reference persona: **Maja Hoffmann**, Product Manager, Frankfurt — hybrid worker with BahnCard 50, Deutschland-Ticket, and MILES car-sharing.

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Python 3.12+
- A [Google AI Studio](https://aistudio.google.com/) API key (required by the ADK runtime)
- A KIConnect API key (used for the LLM agents via the KIConnect proxy)

---

## Setup

1. Clone the repo and enter the directory.

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Copy `sample.env` to `.env` and fill in your keys:
   ```
   GOOGLE_GENAI_USE_VERTEXAI=FALSE
   GOOGLE_API_KEY=<your_google_ai_studio_key>
   KICONNECT_API_KEY=<your_kiconnect_key>
   ```

4. Run the ADK web UI:
   ```bash
   uv run adk web
   ```

5. Open the URL shown in the terminal. Two pipelines are available:

   **Single-run recommendation** — select **mobility_advisor_pipeline** and send:
   > Is my mobility setup optimal right now?

   **Annual report** — select **annual_report_pipeline** and send:
   > Generate my annual mobility report.

The four agents run in sequence. The final output includes savings, CO₂ impact, and a clear "awaiting your approval" note.

---

## Project structure

```
mobility_advisor/
├── __init__.py          # ADK package entry point
├── agent.py             # root_agent + annual_report_agent (SequentialAgents)
├── sub_agents.py        # analyst, forecaster, optimizer, communicator, annual_communicator
├── tools.py             # 5 loader functions (mock data)
├── models.py            # Pydantic models for all fixtures
├── data/                # active data files (replaced by scenario activation)
│   ├── user_preferences.json
│   ├── current_subscriptions.json
│   ├── mobility_catalog.json
│   ├── travel_history.json
│   └── calendar_events.json
└── scenarios/           # self-contained fixture sets for testing
    ├── activate_scenario.sh
    ├── 01_happy_path/
    ├── 02_edge_case/
    └── 03_failure_recovery/
```

---

## Scenario testing

Three pre-built scenarios let you exercise different pipeline behaviours without modifying `data/` by hand. Run the activation script from the `mobility_advisor/` directory:

```bash
./scenarios/activate_scenario.sh 01_happy_path
```

The script backs up the current `data/` with a timestamp before overwriting, so switching is non-destructive.

Both pipelines work with all three scenarios.

| Scenario | Signal | Single-run outcome | Annual report outcome |
|---|---|---|---|
| `01_happy_path` | BC50 savings far below card cost; no upcoming long-distance travel | Unambiguous recommendation to cancel BC50 | Clean report; strong CO₂ saving from rail; BC50 clearly did not break even |
| `02_edge_case` | Erratic usage; BC50 borderline break-even; possible relocation | Hedged conditional recommendation | Borderline BC50 verdict; hedged forward outlook; relocation flagged |
| `03_failure_recovery` | 6 of 20 travel history entries malformed (null costs, empty/unknown mode) | Pipeline completes with partial result and data quality warnings | Data quality warnings populated in Section 6; totals marked as partial |

To restore the original `data/` after testing:

```bash
cp data_backup_<timestamp>/*.json data/
```

---

## Tier roadmap

| Tier | Status | Features |
|------|--------|----------|
| **Tier 1 — Basic** | ✅ Current | Mocked data, linear pipeline, single run, no persistence |
| Tier 2 — Intermediate | Planned | Persistent user state, RAG over contracts DB, calendar-driven forecasting, constraint capture |
| Tier 3 — Advanced | Planned | Multi-agent with context isolation, execution agent, life-event triggers, Docker, ADRs |
