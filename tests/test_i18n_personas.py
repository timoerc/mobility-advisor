"""Verifies GET /api/personas resolves each scenario's tagline_de sibling from the X-Language
header — the backend half of the fix for personas keeping a stale-language tagline on the
profile-selection screen (the other half is frontend/src/App.tsx re-fetching on language change,
since this endpoint alone can't fix a client that never re-requests it).

Same TestClient pattern as test_i18n_middleware.py: no LLM, no pipeline, just the header ->
pick() -> response round trip against the real maja fixture.
"""
from fastapi.testclient import TestClient

import main as main_module

_MAJA_TAGLINE_EN = "Occasional long-distance traveller · BahnCard 50"
_MAJA_TAGLINE_DE = "Gelegentliche Fernreisende · BahnCard 50"
_MAJA_PROFESSION_EN = "Consultant"
_MAJA_PROFESSION_DE = "Beraterin"


def _maja(personas: list[dict]) -> dict:
    match = next(p for p in personas if p["id"] == "maja")
    return match


def test_personas_tagline_follows_x_language_header():
    client = TestClient(main_module.app)

    de_personas = client.get("/api/personas", headers={"X-Language": "de"}).json()
    en_personas = client.get("/api/personas", headers={"X-Language": "en"}).json()
    no_header_personas = client.get("/api/personas").json()

    assert _maja(de_personas)["tagline"] == _MAJA_TAGLINE_DE
    assert _maja(en_personas)["tagline"] == _MAJA_TAGLINE_EN
    # normalize_language(None) defaults to "en" — matches the frontend's default before any
    # toggle, and the middleware behavior already covered by test_i18n_middleware.py.
    assert _maja(no_header_personas)["tagline"] == _MAJA_TAGLINE_EN


def test_personas_profession_and_notes_follow_x_language_header():
    # tagline, profession and notes all resolve their _de sibling the same way — see pick() in
    # list_personas() (api/routes/personas.py).
    client = TestClient(main_module.app)

    de_maja = _maja(client.get("/api/personas", headers={"X-Language": "de"}).json())
    en_maja = _maja(client.get("/api/personas", headers={"X-Language": "en"}).json())

    assert de_maja["profileData"]["personal"]["profession"] == _MAJA_PROFESSION_DE
    assert en_maja["profileData"]["personal"]["profession"] == _MAJA_PROFESSION_EN
    assert de_maja["profileData"]["notes"] != en_maja["profileData"]["notes"]


def test_personas_non_prose_fields_are_language_invariant():
    # Everything id/enum-shaped must stay byte-identical across languages — only tagline,
    # profession and notes vary via their _de siblings.
    client = TestClient(main_module.app)

    de_maja = _maja(client.get("/api/personas", headers={"X-Language": "de"}).json())
    en_maja = _maja(client.get("/api/personas", headers={"X-Language": "en"}).json())

    assert de_maja["id"] == en_maja["id"] == "maja"
    assert de_maja["avatar"] == en_maja["avatar"]
    assert de_maja["avatarBg"] == en_maja["avatarBg"]
    assert de_maja["tagline"] != en_maja["tagline"]
