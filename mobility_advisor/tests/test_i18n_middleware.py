"""Verifies the X-Language header middleware (main.py's _language_middleware) actually makes
mobility_advisor.i18n.get_language() reflect the request's header inside a real request/response
cycle — not just in a unit test that calls language_scope() directly. This is the "does the
ContextVar really propagate through FastAPI's request handling" check CLAUDE.md's i18n plan
calls for, done against the cheapest real endpoint (GET /api/catalog — no LLM, no pipeline)."""
from fastapi.testclient import TestClient

import main as main_module
from mobility_advisor.i18n import get_language


def test_x_language_header_sets_request_language(monkeypatch):
    captured: list[str] = []
    original_catalog_lookup = main_module.catalog_lookup

    def spy_catalog_lookup(*args, **kwargs):
        # Called from inside the /api/catalog handler, downstream of the middleware — if the
        # ContextVar didn't actually propagate from the middleware into the request handler,
        # this would observe the default ("en") regardless of the header sent below.
        captured.append(get_language())
        return original_catalog_lookup(*args, **kwargs)

    monkeypatch.setattr(main_module, "catalog_lookup", spy_catalog_lookup)

    client = TestClient(main_module.app)
    client.get("/api/catalog", headers={"X-Language": "de"})
    client.get("/api/catalog", headers={"X-Language": "en"})
    client.get("/api/catalog")  # no header at all → normalize_language(None) defaults to "en"
    client.get("/api/catalog", headers={"X-Language": "de-DE"})  # tolerate a locale-style value

    assert captured == ["de", "en", "en", "de"]


def test_requests_do_not_leak_language_across_each_other(monkeypatch):
    # Each TestClient call gets its own ASGI-handling task, so each request should observe only
    # its own header — this guards against a regression to a shared mutable global instead of a
    # ContextVar (which is exactly why ContextVar, not a module-level variable, was chosen: a
    # plain global set by one request's middleware would be visible to — and clobberable by —
    # every other in-flight request on the same worker).
    captured: list[str] = []
    original_catalog_lookup = main_module.catalog_lookup

    def spy_catalog_lookup(*args, **kwargs):
        captured.append(get_language())
        return original_catalog_lookup(*args, **kwargs)

    monkeypatch.setattr(main_module, "catalog_lookup", spy_catalog_lookup)

    client = TestClient(main_module.app)
    sequence = ["de", "en", "de", "de", "en"]
    for lang in sequence:
        client.get("/api/catalog", headers={"X-Language": lang})

    assert captured == sequence
