"""Mobility Advisor API — thin FastAPI wrapper over the ADK agent pipeline."""
from .. import env  # noqa: F401  (must run before anything touches litellm)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..i18n import normalize_language, set_language
from .routes import analysis, chat, data, execution, personas

app = FastAPI(title="Mobility Advisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    # NB: allow_headers=["*"] only wildcards because allow_credentials is unset (False) here —
    # per the CORS spec, "*" in Access-Control-Allow-Headers is NOT honored when credentials
    # are allowed, so a future `allow_credentials=True` would silently stop the frontend's
    # X-Language header (below) from reaching this API cross-origin.
    allow_headers=["*"],
)


@app.middleware("http")
async def _language_middleware(request, call_next):
    """Sets the request's language (mobility_advisor.i18n's ContextVar) from the frontend's
    X-Language header for the lifetime of this request — read by every deterministic string
    built across this package, including inside ADK FunctionTool calls several frames below
    this handler (contextvars propagate into the asyncio tasks the ADK Runner spawns). A header
    middleware — rather than a field on each request body model — covers the GET endpoints
    (personas, analysis-history, catalog, ...) that a body field would miss, for free."""
    set_language(normalize_language(request.headers.get("x-language")))
    return await call_next(request)


for router_module in (personas, data, analysis, execution, chat):
    app.include_router(router_module.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Liveness probe — deliberately touches neither the LLM proxy nor disk, so it
    stays fast and green independent of KICONNECT_API_KEY or fixture state."""
    return {"status": "ok"}
