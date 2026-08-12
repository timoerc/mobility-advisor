"""Mobility Advisor API — thin FastAPI wrapper over the ADK agent pipeline."""
from .. import env  # noqa: F401  (must run before anything touches litellm)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import analysis, chat, data, execution, personas

app = FastAPI(title="Mobility Advisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

for router_module in (personas, data, analysis, execution, chat):
    app.include_router(router_module.router)
