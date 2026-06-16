# Mobility Advisor

An agentic AI system that answers one question: **"Is my mobility setup optimal right now?"**

Built for a joint course at **University of Cologne × BCG Platinion**. The system analyzes a traveler's current subscription portfolio, forecasts forward demand, and recommends concrete contract changes — with full cost and CO₂ transparency and a human-in-the-loop gate before any change is made.

---

## What it does (Tier 1)

A linear pipeline of four AI agents runs in sequence:

1. **Analyst** — reviews 12 months of travel history against active subscriptions; flags under-used contracts
2. **Forecaster** — reads upcoming calendar events; summarizes forward demand and life-event signals
3. **Optimizer** — combines findings with the market catalog; proposes one concrete change with €/mo savings and CO₂ delta
4. **Communicator** — formats a scannable recommendation for the user; explicitly notes that no change has been made and approval is required

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

5. Open the URL shown in the terminal, select **mobility_advisor_pipeline**, and send:
   > Is my mobility setup optimal right now?

The four agents run in sequence. The final output is a recommendation with savings, CO₂ impact, and a clear "awaiting your approval" note.

---

## Project structure

```
mobility_advisor/
├── __init__.py          # ADK package entry point
├── agent.py             # root_agent (SequentialAgent)
├── sub_agents.py        # analyst, forecaster, optimizer, communicator
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

| Scenario | Signal | Expected outcome |
|---|---|---|
| `01_happy_path` | BC50 savings far below card cost; no upcoming long-distance travel | Unambiguous recommendation to cancel BC50 |
| `02_edge_case` | Erratic usage; BC50 borderline break-even; possible relocation | Hedged conditional recommendation |
| `03_failure_recovery` | 6 of 20 travel history entries malformed (null costs, empty/unknown mode) | Pipeline completes with partial result and data quality warnings |

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
