# Mobility Advisor

An agentic AI system that answers one question: **"Is my mobility setup optimal right now?"**

Built for a joint course at **University of Cologne × BCG Platinion**. The system analyzes a traveler's current subscription portfolio, forecasts forward demand, and recommends concrete contract changes — with full cost and CO₂ transparency and a human-in-the-loop gate before any change is made.

---

## Architecture

A **Coordinator** agent (`mobility_advisor/agent.py`) classifies every incoming message and routes it to one of five tools:

- **`reject_agent`** — fixed refusal for out-of-scope or instruction-override messages
- **`optimization_pipeline`** — the core 4-stage review: Analyst → Forecaster → Optimizer → Communicator
- **`qa_agent`** — factual lookups (spend, counts, renewal dates) without a full review
- **`execution_agent`** — applies an explicitly-instructed subscription change, single-confirmation human-in-the-loop
- **`annual_report_pipeline`** — same 4 stages, ending in an Annual Communicator that renders a structured year-in-review PDF

The Communicator only ever *drafts* a recommendation — nothing is executed unless the user explicitly says so via `execution_agent`.

The LLM is served via the **KIConnect** proxy (ADK's `LiteLlm` wrapper), not native Gemini — see `mobility_advisor/agents/model.py::build_model()`.

---

## Personas

Six self-contained fixture sets live under `mobility_advisor/scenarios/`, each isolating a different pipeline behavior:

| Persona | Holds | Tests | Expected result |
|---|---|---|---|
| `maja` | BahnCard 50 + Enterprise Silver | Basic over-subscription detection | Downgrade BC50 → BC25 (Enterprise Silver is a free automatic tier, untouched either way) |
| `katrin` | BahnCard 25 + Deutschland-Ticket | Fare-class-driven upgrade (Flexpreis-heavy long-distance travel) | Upgrade to BahnCard 50, saving €318/yr; Deutschland-Ticket kept by a near-tie |
| `sofia` | Deutschland-Ticket + MILES Basis | The "add/upgrade a product" case | Add BahnCard 25, upgrade MILES Basis → Silber, drop the Deutschland-Ticket |
| `tobias` | BahnCard 50 + Deutschland-Ticket | Forward signal overriding a strong historical ROI | Downgrade/cancel BC50 ahead of renewal |
| `stefan` | Car + BC50 + Deutschland-Ticket + MILES Silber | Hedging under genuine ambiguity (possible relocation) | Conditional recommendation, not a single confident action |
| `lena` | BahnCard 50 Young + Deutschland-Ticket | Graceful degradation on corrupted trip data | Completes with a Data Quality Warnings section, never crashes |

Each scenario's `SCENARIO.md` has the full rationale. Switch the active dataset with:

```bash
./mobility_advisor/scenarios/activate_scenario.sh <name>
```

This backs up `mobility_advisor/data/` to a timestamped folder before overwriting it — restore with `cp data_backup_<timestamp>/*.json data/`.

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Python 3.14+
- A KIConnect API key (`KICONNECT_API_KEY`) — used by the LLM agents
- A Google AI Studio API key (`GOOGLE_API_KEY`) — required by the ADK runtime itself
- Optional: `OUTLOOK_CLIENT_ID`/`OUTLOOK_TENANT_ID` for live Outlook calendar ingestion, `ORS_API_KEY` for distance enrichment — see `sample.env` for the full list

---

## Setup

1. Clone the repo and enter the directory.
2. Install backend dependencies: `uv sync`
3. Copy `sample.env` to `.env` and fill in your keys.
4. Install frontend dependencies: `cd frontend && npm install`

---

## Running the full stack

**Terminal 1 — backend** (from the repo root):
```bash
uv run uvicorn main:app --reload --port 8000
```

**Terminal 2 — frontend**:
```bash
cd frontend && npm run dev
```

Open **http://localhost:5173**. Vite proxies `/api/*` to `localhost:8000` — if the backend isn't running, the frontend still loads and falls back to canned mock recommendations.

### Key API endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/chat` | Send a message to the Coordinator (routes to whichever tool fits) |
| `POST /api/analyze` | Run the full 4-agent pipeline directly, returns a structured `Recommendation` |
| `POST /api/annual-report` | Run the annual pipeline and return a rendered PDF |
| `POST /api/execute` | Apply an explicitly-approved subscription change |
| `POST /api/activate` | Switch the active persona/scenario |

See `mobility_advisor/api/routes/` for the complete list (profile onboarding, history, catalog, etc.), or run the backend and open `/docs` for the live OpenAPI schema.

### Agent-only debugging (no frontend)

```bash
uv run adk web
```
> `adk web`/`adk api_server` bind to port 8000 too — stop them before running `uvicorn main:app`.

---

## Project structure

```
mobility-advisor/
├── main.py                 # uvicorn entry point — 3-line shim over mobility_advisor/api/app.py
└── mobility_advisor/
    ├── agent.py             # Coordinator (root_agent) — routes to the 5 tools below
    ├── paths.py             # single source of truth for data/static/scenario dirs + scratch files
    ├── clock.py              # MOCK_TODAY / REVIEW_YEAR, frozen to the active persona's reference date
    ├── env.py                 # KIConnect proxy env bootstrap, imported before anything touches litellm
    ├── agents/                 # ADK agent definitions
    │   ├── model.py             # shared LiteLlm singleton + generation config
    │   ├── analysis.py           # analyst_agent, forecaster_agent
    │   ├── optimization.py        # optimizer_agent, communicator_agent
    │   ├── annual.py               # the 4 annual-pipeline agents
    │   ├── qa.py / execution.py / reject.py
    │   └── pipelines.py            # optimization_pipeline, annual_report_pipeline
    ├── engine/                  # deterministic compute: geocoding, fare calibration, trip
    │                              # aggregation/projection, pricing, portfolio simulation,
    │                              # the optimizer, and travel/annual-report statistics
    ├── store/                   # fixture I/O: loaders, history, the pending-decision gate,
    │                              # subscription mutations, scenario activation
    ├── api/                      # FastAPI app
    │   ├── app.py                  # app + CORS + router wiring
    │   ├── schemas.py                # request-body models
    │   ├── deps.py                    # shared process-lifetime state
    │   ├── routes/                     # personas, data, analysis, execution, chat
    │   └── recommendation/              # builder (deterministic), extraction (LLM fallback),
    │                                      # finalize (shared post-processing chain)
    ├── integrations/              # ORS client + the offline mail/calendar ETL scripts
    ├── reporting/                  # annual report PDF rendering + Markdown table renderers
    │   └── templates/                # annual_report.html / .css
    ├── models/                      # Pydantic models (fixtures / projections / API wire contract)
    ├── static/mobility_catalog.json   # market catalog (shared across all personas)
    ├── data/                          # active dataset (swapped by activate_scenario.sh)
    └── scenarios/                      # 6 persona fixture sets — see Personas above
tests/                                  # pytest suite (mirrors the package layout above)
```

---

## Tier status

- **Tier 1** (basic linear pipeline, all-mocked, reactive single run) — done, frozen as the baseline.
- **Tier 2 + Tier 3** — in progress together, not strictly sequential. The Coordinator routing layer, `execution_agent`, and real Outlook calendar ingestion are already Tier-3-shaped pieces that have landed ahead of full Tier 2 completion. Still open: a dedicated Validation agent, disk-persisted orchestrator state, continuous life-event-triggered evaluation, and execution against real provider APIs.

See `.claude/TIERS_CONTEXT.md` for the full tier definitions and gap list.
