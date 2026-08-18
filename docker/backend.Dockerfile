# Mobility Advisor backend (FastAPI + ADK agent pipeline).
#
# Base image ships uv itself, and its tag pins the exact Python the project requires
# (pyproject.toml: requires-python = ">=3.14"). Local dependency resolution already
# succeeds on 3.14.4, so cp314 wheels exist for the whole tree — no compiler toolchain
# needed here.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS base

# WeasyPrint (mobility_advisor/reporting/pdf.py) pulls in native Pango/Cairo bindings at
# call time, not at import time — a missing lib here won't fail the build or startup, it
# fails the first /api/annual-report request with a 500. fonts-inter matches the annual
# report's CSS (which names "Inter" with no @font-face, so it silently falls back to
# whatever's installed); fonts-dejavu-core is the fallback if fonts-inter is ever dropped.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-dejavu-core \
    fonts-inter \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependency layer cached independently of source changes.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .

# The app mutates mobility_advisor/data/*.json in place (atomic_write_json does
# mkstemp() in the *directory*, so write access to the directory is required, not just
# the files) and scenarios/activate.py writes data_backup_* as a sibling of data/ — so
# ownership must cover the whole package directory, not just data/.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app/mobility_advisor

EXPOSE 8000

# --- runtime target (default): production deps only, non-root -------------------------
FROM base AS runtime
RUN uv sync --locked --no-dev
USER appuser

# Single worker only: api/deps.py keeps per-session ADK state (InMemorySessionService)
# and an asyncio.Lock guarding analysis_history.json in process memory — a second
# worker process would neither share sessions nor serialize those writes.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- test target: adds the dev dependency group (pytest) for `docker compose run tests`
FROM base AS test
RUN uv sync --locked
# /app itself is root-owned (only mobility_advisor/ was chowned above, for the runtime
# image's write path); pytest's own cache dir needs appuser to own it too, or every run
# prints a harmless but noisy "Permission denied" cache warning.
RUN mkdir -p /app/.pytest_cache && chown appuser:appuser /app/.pytest_cache
USER appuser
CMD ["pytest"]
