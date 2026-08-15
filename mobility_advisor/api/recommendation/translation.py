"""Lazy translation backfill for analysis_history.json entries read in a language other than
the one they were generated in.

/api/analyze never populates an entry's `_en`/`_de` sibling fields — its LLM output already
comes back in the request's language via the agent-prompt directive (i18n.LANGUAGE_DIRECTIVE),
so writing a sibling at generation time would be translating a language that hasn't been
requested yet. Instead, AnalysisHistoryEntry.language records what language the entry WAS
generated in, and this module fills in the other side's sibling fields the first time an entry
is read in that other language — GET /api/analysis-history calls backfill_translations() before
resolving each entry (see api/routes/analysis.py). Once filled, the sibling is cached on disk
(store/history.save_history), so every subsequent read of that entry in that language costs
zero LLM calls — this function's own pending-check is what makes that the steady state.

Modeled on the raw litellm JSON-extraction calls in extraction.py: same MODEL_ID, same
brace-scanning _parse_json_response, same "never raise" philosophy — a translation failure must
degrade to "the entry still shows its original-language prose" (exactly what
i18n.language_sibling's fallback already does for a missing sibling), not break the
/api/analysis-history response.
"""
from __future__ import annotations

import json
import logging

import litellm

from ...i18n import Language
from ...models import (
    ACTION_LANGUAGE_FIELDS,
    ALTERNATIVE_LANGUAGE_FIELDS,
    METRIC_LANGUAGE_FIELDS,
    RECOMMENDATION_LANGUAGE_FIELDS,
    AnalysisHistoryEntry,
)
from ..deps import MODEL_ID
from .extraction import _parse_json_response

log = logging.getLogger(__name__)

# Batched into one call, capped at the most recent N entries — an unbounded history shouldn't
# turn one language switch into dozens of translation calls; older entries pick up their
# siblings on a later read instead (this function is re-run, and re-checks what's still
# missing, on every GET /api/analysis-history).
_MAX_ENTRIES_PER_BATCH = 10

_TARGET_LANGUAGE_NAME: dict[Language, str] = {"en": "English", "de": "German (Deutsch)"}


def _system_prompt(target: Language) -> str:
    sie_line = '- address the user as "Sie"\n' if target == "de" else ""
    return f"""
Translate the free-text field values in the JSON object below into {_TARGET_LANGUAGE_NAME[target]}.
Output ONLY valid JSON with the exact same shape as the input (same keys, same nesting) — no
markdown fences, no surrounding text, no added or dropped keys.

Do NOT translate, transliterate, abbreviate or reword:
- every subscription/product/provider/tariff name, wherever one appears inside a string — copy
  it character-for-character (e.g. "BahnCard 25 (2. Klasse, Standard, Jahresabo)",
  "MILES Silber Pass")
- numbers, currency symbols and units (€, kg CO₂, min) — leave them exactly as given
- the "id" and "index" values — they are identifiers, not text; copy them through unchanged
{sie_line}
Translate every other string value naturally and fluently, preserving the original meaning and
tone.
""".strip()


def _metric_pending(metric, target: Language) -> dict | None:
    item: dict = {}
    if getattr(metric, f"label_{target}", None) is None and metric.label:
        item["label"] = metric.label
    if (
        isinstance(metric.value, str)
        and getattr(metric, f"value_{target}", None) is None
        and metric.value
    ):
        item["value"] = metric.value
    return item or None


def _fields_pending(obj, fields: tuple[str, ...], target: Language) -> dict:
    item: dict = {}
    for f in fields:
        if getattr(obj, f"{f}_{target}", None) is None and getattr(obj, f):
            item[f] = getattr(obj, f)
    return item


def _collect_pending(entry: AnalysisHistoryEntry, target: Language) -> dict | None:
    """Everything on `entry` that still needs a `_{target}` sibling, in the shape the LLM is
    asked to translate and return. None if nothing is pending — the common case once an entry
    has been backfilled once."""
    payload: dict = {}
    rec = entry.recommendation
    if entry.language != target:
        rec_fields = _fields_pending(rec, RECOMMENDATION_LANGUAGE_FIELDS, target)
        if rec_fields:
            payload.update(rec_fields)

        metrics_payload = []
        for i, metric in enumerate(rec.metrics):
            item = _metric_pending(metric, target)
            if item:
                item["index"] = i
                metrics_payload.append(item)
        if metrics_payload:
            payload["metrics"] = metrics_payload

        alts_payload = []
        for alt in rec.alternatives:
            item = _fields_pending(alt, ALTERNATIVE_LANGUAGE_FIELDS, target)
            if alt.action is not None:
                action_item = _fields_pending(alt.action, ACTION_LANGUAGE_FIELDS, target)
                if action_item:
                    item["action"] = action_item
            if item:
                item["id"] = alt.id
                alts_payload.append(item)
        if alts_payload:
            payload["alternatives"] = alts_payload

    resolved_source = entry.resolvedMessageLanguage or entry.language
    if (
        entry.resolvedMessage
        and resolved_source != target
        and getattr(entry, f"resolvedMessage_{target}", None) is None
    ):
        payload["resolvedMessage"] = entry.resolvedMessage

    return payload or None


def _apply_result_fields(obj, fields: tuple[str, ...], target: Language, result: dict) -> None:
    for f in fields:
        if f in result:
            setattr(obj, f"{f}_{target}", result[f])


def _apply_result(entry: AnalysisHistoryEntry, target: Language, result: dict) -> None:
    rec = entry.recommendation
    _apply_result_fields(rec, RECOMMENDATION_LANGUAGE_FIELDS, target, result)

    for metric_result in result.get("metrics", []):
        if not isinstance(metric_result, dict):
            continue
        idx = metric_result.get("index")
        if not isinstance(idx, int) or not (0 <= idx < len(rec.metrics)):
            continue
        _apply_result_fields(rec.metrics[idx], METRIC_LANGUAGE_FIELDS, target, metric_result)

    alts_by_id = {a.id: a for a in rec.alternatives}
    for alt_result in result.get("alternatives", []):
        if not isinstance(alt_result, dict):
            continue
        alt = alts_by_id.get(alt_result.get("id"))
        if alt is None:
            continue
        _apply_result_fields(alt, ALTERNATIVE_LANGUAGE_FIELDS, target, alt_result)
        action_result = alt_result.get("action")
        if alt.action is not None and isinstance(action_result, dict):
            _apply_result_fields(alt.action, ACTION_LANGUAGE_FIELDS, target, action_result)

    if "resolvedMessage" in result:
        setattr(entry, f"resolvedMessage_{target}", result["resolvedMessage"])


async def backfill_translations(entries: list[AnalysisHistoryEntry], target: Language) -> bool:
    """Fill in missing `_{target}` sibling fields on `entries`, in place, via one batched LLM
    call. Returns whether anything was translated (so the caller knows whether there's anything
    new to persist) — False is the steady state.

    Never raises: entries this fails to translate simply keep showing their original-language
    prose, exactly as if backfill_translations had never been called — the same graceful
    degradation i18n.t() and i18n.language_sibling() already apply everywhere else in this
    codebase.

    Note on partial responses: if the model's response is missing a field this call asked for
    (e.g. it silently drops one alternative), that field stays unset and _collect_pending will
    find it still missing on the NEXT call too — a translation gap is retried on every read
    until it succeeds, rather than being cached as "good enough" once a partial response comes
    back. This trades away part of the zero-further-calls steady state for entries the model
    keeps responding to incompletely, in exchange for never permanently freezing a field in the
    wrong language.
    """
    candidates = entries[:_MAX_ENTRIES_PER_BATCH]
    pending: dict[str, dict] = {}
    for entry in candidates:
        item = _collect_pending(entry, target)
        if item:
            pending[entry.id] = item
    if not pending:
        return False

    try:
        response = await litellm.acompletion(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": _system_prompt(target)},
                {"role": "user", "content": json.dumps({"entries": pending}, ensure_ascii=False)},
            ],
            temperature=0.0,
        )
        text = response.choices[0].message.content.strip()
        parsed = _parse_json_response(text)
        results = parsed.get("entries", {})
        entries_by_id = {e.id: e for e in candidates}
        applied = False
        for entry_id, result in results.items():
            entry = entries_by_id.get(entry_id)
            if entry is not None and isinstance(result, dict):
                _apply_result(entry, target, result)
                applied = True
        return applied
    except Exception as exc:
        log.warning("backfill_translations: failed to translate history entries to %r: %s", target, exc)
        return False


def merge_entry_siblings(dst: AnalysisHistoryEntry, src: AnalysisHistoryEntry, lang: Language) -> None:
    """Copy just the `_{lang}` sibling fields backfill_translations populated on `src` onto
    `dst`, filling only fields `dst` doesn't already have (idempotent) — used by
    get_analysis_history to merge a freshly-translated in-memory entry back onto a fresh reload
    from disk before persisting, so a concurrent write to the SAME entry (e.g. /api/execute
    recording its outcome) that landed while the translation call was in flight isn't clobbered
    by writing back a stale copy of the rest of the entry.
    """
    _merge_field_siblings(dst.recommendation, src.recommendation, RECOMMENDATION_LANGUAGE_FIELDS, lang)
    for dst_metric, src_metric in zip(dst.recommendation.metrics, src.recommendation.metrics):
        _merge_field_siblings(dst_metric, src_metric, METRIC_LANGUAGE_FIELDS, lang)
    src_alts_by_id = {a.id: a for a in src.recommendation.alternatives}
    for dst_alt in dst.recommendation.alternatives:
        src_alt = src_alts_by_id.get(dst_alt.id)
        if src_alt is None:
            continue
        _merge_field_siblings(dst_alt, src_alt, ALTERNATIVE_LANGUAGE_FIELDS, lang)
        if dst_alt.action is not None and src_alt.action is not None:
            _merge_field_siblings(dst_alt.action, src_alt.action, ACTION_LANGUAGE_FIELDS, lang)
    _merge_field_siblings(dst, src, ("resolvedMessage",), lang)


def _merge_field_siblings(dst, src, fields: tuple[str, ...], lang: Language) -> None:
    for f in fields:
        attr = f"{f}_{lang}"
        if not getattr(dst, attr, None) and getattr(src, attr, None):
            setattr(dst, attr, getattr(src, attr))
