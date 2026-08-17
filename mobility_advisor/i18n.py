"""Backend language plumbing for the EN/DE toggle.

Two independent mechanisms, each solving a different layer — see CLAUDE.md's i18n section
for the full design rationale:

1. A `ContextVar` (`_language`) carries the request's language into every deterministic string
   built in `main.py` and `tools.py`, including inside ADK `FunctionTool` calls several frames
   below the endpoint. `main.py`'s `X-Language` middleware sets it once per request; contextvars
   propagate into the asyncio tasks the ADK Runner spawns, so no plumbing is needed through tool
   signatures (which would otherwise leak `language` to the LLM as a callable argument).

2. `LANGUAGE_DIRECTIVE` + `localized()` give the six user-facing agent prompts (the coordinator,
   the two communicators, execution/qa/reject) an appended output-language instruction, applied
   via ADK's `InstructionProvider` mechanism. These read the SAME ContextVar — no session-state
   seeding required, so the language can change mid-chat-session for free.

HARD RULE: never call `t()` at module scope. Every module-level string constant is evaluated at
import time, long before any request sets `_language` — a module-scope `t()` call would bake in
whichever language happened to be current (or the default) for the lifetime of the process. Any
text that needs to vary by request belongs in the MESSAGES catalog and must be looked up inside a
function body, at call time.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Literal

Language = Literal["en", "de"]

_DEFAULT_LANGUAGE: Language = "en"
_language: ContextVar[Language] = ContextVar("language", default=_DEFAULT_LANGUAGE)

log = logging.getLogger(__name__)


def normalize_language(value: str | None) -> Language:
    """Coerce an arbitrary header value to a supported Language, defaulting to English for
    anything unrecognized (missing header, typo, a stray locale like "de-DE") rather than
    raising — a malformed X-Language header should degrade silently, not 500 the request."""
    if value and value.lower().startswith("de"):
        return "de"
    return "en"


def get_language() -> Language:
    return _language.get()


def set_language(lang: Language) -> None:
    _language.set(lang)


@contextmanager
def language_scope(lang: Language) -> Iterator[None]:
    """Scoped override — used by tests and by any one-off call that must run in a specific
    language regardless of the ambient request context."""
    token = _language.set(lang)
    try:
        yield
    finally:
        _language.reset(token)


def t(key: str, /, **kw: object) -> str:
    """Look up `key` in the active language's catalog and `.format(**kw)` it.

    Never raises. A missing key or a bad/missing format placeholder is logged and the raw
    template (or the key itself) is returned instead — a catalog typo must not become a
    KeyError, because main.py's `_with_pipeline_retry` swallows KeyError for two attempts and
    then reports "the pipeline did not produce a result", which would misattribute a string bug
    in this module to the LLM backend.
    """
    from mobility_advisor.messages import de as _de, en as _en

    catalog = _de.MESSAGES if get_language() == "de" else _en.MESSAGES
    template = catalog.get(key) or _en.MESSAGES.get(key) or key
    try:
        return template.format(**kw)
    except (KeyError, IndexError, ValueError):
        log.warning("i18n: failed to format key %r with params %r", key, kw)
        return template


def localize_unit(unit: str) -> str:
    """Translate a raw `MetricDelta.unit` string (e.g. "€/year", "kg CO2") to the active
    language's equivalent, by reverse-looking it up against every `metric.unit.*` catalog
    key in EITHER language and re-resolving that key via t(). Returns `unit` unchanged if it
    doesn't match any known unit string — covers ad-hoc units a metric might carry that were
    never meant to be a closed vocabulary.

    Built at call time, never module scope, per this module's HARD RULE above. There is no
    `unit_de` model field (unlike verdict_de/label_de/...): units are a small closed
    vocabulary already fully covered by the message catalog, so this reverse-index approach
    handles seeded fixtures AND live-generated units (which already come from t()) with one
    mechanism, instead of asking every seeded fixture to carry yet another sibling field.
    """
    from mobility_advisor.messages import de as _de, en as _en

    # Iterate the two catalogs' items separately, NOT merged into one dict — {**en, **de}
    # collapses each shared key down to a single (German) value, which would make an
    # English unit string un-matchable against its own English catalog value.
    for catalog in (_en.MESSAGES, _de.MESSAGES):
        for key, value in catalog.items():
            if key.startswith("metric.unit.") and value == unit:
                return t(key)
    return unit


def language_sibling(obj: object, field: str, lang: Language) -> object:
    """Return `obj`'s `{field}_{lang}` attribute if it's set and truthy, else `obj`'s base
    `field` attribute unchanged.

    The generalized, Pydantic-model equivalent of pick() above: pick() resolves a raw dict's
    `_de`-only sibling (seeded scenario fixtures); this resolves either direction (`_en` or
    `_de`) on a typed model, which is what a live-generated Recommendation needs — see
    models/api.py's per-field `_de`/`_en` sibling pairs (label_de/label_en, verdict_de/
    verdict_en, ...) and AnalysisHistoryEntry.language for how the base fields' own language
    is known. Building block for apply_language_siblings below, and used standalone by
    store/history.py's continuity summary, which only ever needs one field at a time.
    """
    value = getattr(obj, f"{field}_{lang}", None)
    return value if value else getattr(obj, field)


def apply_language_siblings(obj: object, fields: tuple[str, ...], lang: Language) -> None:
    """Mutate `obj` in place: resolve each name in `fields` via language_sibling() and write
    the result back onto the base attribute.

    Used by api/routes/analysis.py's recommendation-history resolvers to swap in whichever of
    a model's `_en`/`_de` siblings matches the active request's language, across every prose
    field on Recommendation/MetricDelta/Alternative/ProposedAction/AnalysisHistoryEntry in one
    shared mechanism instead of a hand-written `if` per field.
    """
    for f in fields:
        setattr(obj, f, language_sibling(obj, f, lang))


def pick(obj: dict, field: str) -> object:
    """Resolve a scenario-fixture field to its German sibling (`f"{field}_de"`) when the active
    language is German and that sibling is present and non-empty; otherwise returns the English
    field unchanged. Used for seeded scenario JSON (persona.json, life_events.json,
    calendar_events_live.json, analysis_history.json) — never for live LLM output, which already
    comes back in the request's language via the agent-prompt directive."""
    if get_language() == "de":
        de_value = obj.get(f"{field}_de")
        if de_value:
            return de_value
    return obj.get(field)


def pick_lang(obj: dict, field: str) -> object:
    """Resolve `field` to the active language's sibling, the reverse-direction counterpart of
    pick(): pick() assumes the base field is English with an optional `_de` sibling; this
    assumes the base field is German (e.g. mobility_catalog.json's `product`, authored in
    German because it doubles as the identity/matching key) with an optional `_en` sibling.
    Returns the base field unchanged in German mode, or when no non-empty `_en` sibling exists
    (a defensive fallback, not the expected path — every catalog option carries product_en)."""
    if get_language() == "en":
        en_value = obj.get(f"{field}_en")
        if en_value:
            return en_value
    return obj.get(field)


# ── Agent-prompt language directive ──────────────────────────────────────────────────────────
#
# Appended (not prepended) to each of the six user-facing agent instructions, so it has recency
# on its side. English is "" — the English path is byte-identical to the pre-i18n prompts.
LANGUAGE_DIRECTIVE: dict[Language, str] = {
    "en": "",
    "de": """

OUTPUT LANGUAGE — write ALL prose you output in German (Deutsch), addressing the user as "Sie".
This applies to your narrative text only. The following must be emitted EXACTLY as specified
elsewhere in this instruction, in English / original spelling, and must NOT be translated,
transliterated, abbreviated or reworded:
- the bold section markers **Verdict:** / **Confidence:** / **Summary:** / **Reasoning:** /
  **Assumptions:** — keep these English words verbatim
- the Confidence value, exactly one of: high, medium, low
- every subscription, product, provider and tariff name — e.g. "BahnCard 25 (2. Klasse,
  Standard, Jahresabo)", "MILES Silber Pass" — copy them character-for-character from the tool
  output. (This directive only fires in German mode; in English mode the tools already return
  the English display name — e.g. "BahnCard 25 (2nd class, standard, annual)" — which must
  likewise be quoted verbatim, never re-translated or reworded.)
- any text you were told to quote verbatim from a tool's `explanation` field
- the HTML comment markers <!-- GLANCE_TABLE -->, <!-- BY_MODE_TABLE -->,
  <!-- SUBSCRIPTION_VALUE -->

Numbers, currency symbols and units stay exactly as given (€, kg CO₂, min). History entries you
are given for continuity may be in another language — summarize them in your output language
regardless of what language they were written in.""",
}


def localized(base_instruction: str):
    """Wraps a plain instruction string into an ADK InstructionProvider that appends the active
    language's directive at call time. Use for agents whose instruction is a static string
    today; agents that already use an InstructionProvider (the Forecaster variants, the annual
    communicator) should instead append `LANGUAGE_DIRECTIVE[get_language()]` inline, at the end
    of their own provider function — and must apply the same inject_session_state() step this
    wrapper does below, for the same reason.

    ADK subtlety this exists to handle: `LlmAgent.canonical_instruction()` sets
    `bypass_state_injection=True` whenever `instruction` is a callable (InstructionProvider)
    rather than a plain string — see google.adk.agents.llm_agent and
    google.adk.flows.llm_flows.instructions._process_agent_instruction. That flag makes ADK
    skip its own `{key}` → session-state substitution entirely for provider-based instructions.
    A prompt like the communicator's, which reads `{recommendation}` from session state, would
    silently stop resolving that placeholder if this wrapper just returned the raw string — the
    literal text "{recommendation}" would reach the model instead of the optimizer's output.
    Calling inject_session_state() ourselves, exactly as ADK would have for a plain string,
    is the documented way to opt back into that substitution from inside a provider (see
    google.adk.utils.instructions_utils.inject_session_state's own docstring/example).
    """
    from google.adk.utils.instructions_utils import inject_session_state

    async def _provider(ctx) -> str:  # ctx: ReadonlyContext
        resolved = await inject_session_state(base_instruction, ctx)
        return resolved + LANGUAGE_DIRECTIVE[get_language()]

    return _provider
