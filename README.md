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
- A [Google AI Studio](https://aistudio.google.com/) API key (`gemini-2.5-flash` access)

---

## Setup

1. Clone the repo and enter the directory.

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Create a `.env` file in the repo root:
   ```
   GOOGLE_API_KEY=<your_key_from_ai_studio>
   GOOGLE_GENAI_USE_VERTEXAI=FALSE
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
└── data/
    ├── user_preferences.json
    ├── current_subscriptions.json
    ├── mobility_catalog.json
    ├── travel_history.json
    └── calendar_events.json
```

---

## Tier roadmap

| Tier | Status | Features |
|------|--------|----------|
| **Tier 1 — Basic** | ✅ Current | Mocked data, linear pipeline, single run, no persistence |
| Tier 2 — Intermediate | Planned | Persistent user state, RAG over contracts DB, calendar-driven forecasting, constraint capture |
| Tier 3 — Advanced | Planned | Multi-agent with context isolation, execution agent, life-event triggers, Docker, ADRs |
