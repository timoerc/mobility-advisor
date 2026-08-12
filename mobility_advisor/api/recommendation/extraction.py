"""LLM-based extraction fallback: when the deterministic optimizer's scratch files
aren't available (builder.build_alternatives_from_optimization returns None), a
Recommendation is instead reconstructed from the communicator's free-text report via a
raw litellm JSON-extraction call. Also used for the narrower "qualitative fields only"
verdict extraction that layers on top of the deterministic path."""
import json

import litellm

from ...models import Recommendation
from ..deps import MODEL_ID
from .finalize import finalize_recommendation

_JSON_SYSTEM_PROMPT = """
Convert the mobility advisor's recommendation report into this exact JSON structure.
Output ONLY valid JSON — no markdown fences, no surrounding text.

The report follows a fixed structure — **Verdict:** / **Confidence:** / **Summary:** /
**Reasoning:** (bullets) / **Assumptions:** (bullets) — and describes ONLY the recommended
option compared against the user's current setup; it does not enumerate other candidates as
separate labelled blocks. Reconstruct exactly two "alternatives" entries from it: one for the
recommended option, one for the "Keep current setup" baseline it is compared against.

{
  "verdict": "<the report's Verdict line, verbatim>",
  "confidence": "<the report's Confidence value: 'high' | 'medium' | 'low', lowercase>",
  "summaryText": "<the report's Summary text, verbatim or condensed to 1-2 sentences>",
  "metrics": [
    {
      "value": <number>,
      "unit": "<e.g. '€/year', 'kg CO2/year', 'min/year'>",
      "direction": "<one of: 'save' | 'reduce' | 'extra_cost' | 'increase' | 'neutral'>",
      "label": "<short label, e.g. 'Potential saving', 'CO2 impact'>"
    }
  ],
  "reasoning": ["<one entry per bullet under Reasoning>"],
  "assumptions": ["<one entry per bullet under Assumptions>"],
  "alternatives": [
    {
      "id": "recommended",
      "name": "<what changes — see naming rules below>",
      "annualCostEur": <the recommended option's total annual cost in EUR, from an
        "Annual cost: €X" mention in the Summary or Reasoning>,
      "savingsVsCurrentEur": <the report's stated "Saving vs. current: €Y/year" figure;
        negate it if the report frames this option as costing MORE than current>,
      "co2Impact": "<e.g. 'Neutral' or '-38 kg CO2/year', from the report's CO2 impact line>",
      "co2ImpactKg": <that same figure's signed number — positive = this option SAVES CO2
        vs. current, negative = it emits MORE; 0 if the report doesn't state one>,
      "tradeoff": "<one sentence, from the trade-off bullet in Reasoning>",
      "isRecommended": true,
      "action": {
        "title": "<imperative sentence naming the concrete change, e.g. 'Switch to
          BahnCard 25 (2. Klasse, Standard, Jahresabo)'>",
        "description": "<1-2 sentences with action details>",
        "consequence": "<what changes in the user's portfolio once applied — name the
          exact subscription(s) added/removed, copied verbatim from the report. Do not
          say the change requires separate/manual approval — confirming applies it
          immediately in this prototype>"
      }
    },
    {
      "id": "keep",
      "name": "Keep current setup",
      "annualCostEur": <the recommended entry's annualCostEur minus its
        savingsVsCurrentEur — i.e. what the current setup costs today>,
      "savingsVsCurrentEur": 0,
      "co2Impact": "Neutral",
      "co2ImpactKg": 0,
      "tradeoff": "No change to cost or emissions",
      "isRecommended": false,
      "action": null
    }
  ]
}

Rules:
- Exactly one alternative — the "recommended" entry — has isRecommended: true and a non-null
  action. The "keep" entry always has isRecommended: false and action: null. (This fallback
  path has no way to reconstruct a distinct "Hold pending decision" option from the report
  text — that case is handled deterministically upstream, before this extraction ever runs.)
- All numbers must come verbatim from the report below — never invent figures. If a number
  genuinely cannot be determined, use a sensible default (0 for a cost/CO2 figure, "Neutral"
  for co2Impact, [] for assumptions) rather than guessing.
- alternatives[0].name must describe the ACTION, not a bare product name — e.g. "Switch to
  BahnCard 25 (2. Klasse, Standard, Jahresabo)", "Cancel BahnCard 50 (2. Klasse, Standard,
  Jahresabo)", "Add MILES Silber Pass" — matching whichever verb (switch/cancel/add/upgrade/
  downgrade) the report's own language uses for this change.
- Subscription/product names (in action.title/description/consequence and in
  alternatives[0].name) must be copied verbatim and in full from the report — never
  shortened (e.g. "BahnCard 25 (2. Klasse, Standard, Jahresabo)", not "BahnCard 25") — this
  name is executed literally if the user picks this alternative.
- confidence must be exactly "high", "medium", or "low", lowercase.
""".strip()

_VERDICT_SYSTEM_PROMPT = """
Extract ONLY the qualitative summary from this mobility advisor report.
Output valid JSON — no markdown fences.

{
  "verdict": "<concise 8-10 word headline>",
  "confidence": "<high | medium | low>",
  "summaryText": "<1-2 sentences>",
  "reasoning": ["<bullet 1>", "<bullet 2>", ...],
  "assumptions": ["<assumption 1>", ...]
}

Rules:
- verdict: summarize the recommended action and its key benefit
- confidence: high if cost gap is clear, medium if borderline, low if uncertain
- summaryText: the recommended option, how much it saves, and key tradeoff
- reasoning: 2-4 bullets explaining why this portfolio wins
- assumptions: key model assumptions (Sparpreis pricing, trip frequencies, etc.)
""".strip()


def _parse_json_response(text: str) -> dict:
    """Extract a JSON object from an LLM completion's raw text.

    Brace-scans for the outermost {...} span instead of only stripping a LEADING markdown
    fence (```/```json). The old approach — `if text.startswith("```")` — was defeated by
    any preamble before the fence (e.g. "Here is the JSON:\n```json\n{...}\n```", which
    GPT-OSS-120B being a reasoning model produces more often than not) or a label variant
    like "```JSON"/"``` json" the exact `startswith("json")` check didn't catch, either of
    which fed the whole prose blob straight into json.loads and raised JSONDecodeError on a
    completion that was otherwise perfectly parseable. Brace-scanning is agnostic to
    whatever wrapping the model used around the object.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        # No object-shaped span at all — let json.loads raise its own clear error against
        # the original text rather than silently returning something empty.
        return json.loads(text)
    return json.loads(text[start : end + 1])


_VALID_CONFIDENCE_LEVELS = {"high", "medium", "low"}


def _normalize_confidence_and_lists(parsed: dict) -> dict:
    """Coerce an LLM-extracted dict's confidence/reasoning/assumptions into the shapes
    downstream code expects, in place, tolerating small deviations a completion can
    introduce without failing the whole extraction over what is narration, not numbers:

    - confidence not exactly "high"/"medium"/"low" (wrong case, or a synonym like
      "moderate") would otherwise raise a pydantic ValidationError deep inside
      Recommendation construction — there is no `.get(..., default)` fallback for an
      out-of-range Literal value, only for a missing key.
    - reasoning/assumptions returned as a single string instead of a list.
    """
    confidence = str(parsed.get("confidence", "medium")).strip().lower()
    parsed["confidence"] = confidence if confidence in _VALID_CONFIDENCE_LEVELS else "medium"
    for key in ("reasoning", "assumptions"):
        value = parsed.get(key)
        if isinstance(value, str):
            parsed[key] = [value]
    return parsed


def _parse_verdict_response(text: str) -> dict:
    """Synchronous core of extract_verdict(), split out so it's directly unit-testable
    without an async LLM call: brace-scans, normalizes confidence/reasoning/assumptions,
    then drops an empty-string verdict/summaryText so the caller's `.get(key, default)`
    fallback kicks in — `.get` only catches a MISSING key, not "", so a blank string would
    otherwise render as a blank dashboard headline instead of the intended fallback (e.g.
    analyze()'s `verdict.get("verdict", rec_alt.name)`).
    """
    parsed = _normalize_confidence_and_lists(_parse_json_response(text))
    if not (parsed.get("verdict") or "").strip():
        parsed.pop("verdict", None)
    if not (parsed.get("summaryText") or "").strip():
        parsed.pop("summaryText", None)
    return parsed


async def extract_verdict(report_text: str) -> dict:
    """Extract only qualitative fields from the communicator's text output."""
    response = await litellm.acompletion(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": _VERDICT_SYSTEM_PROMPT},
            {"role": "user", "content": report_text},
        ],
        temperature=0.0,
    )
    text = response.choices[0].message.content.strip()
    return _parse_verdict_response(text)


async def extract_recommendation_json(report_text: str) -> Recommendation:
    response = await litellm.acompletion(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": _JSON_SYSTEM_PROMPT},
            {"role": "user", "content": report_text},
        ],
        temperature=0.0,
    )
    text = response.choices[0].message.content.strip()
    parsed = _normalize_confidence_and_lists(_parse_json_response(text))
    recommendation = Recommendation.model_validate(parsed)
    return finalize_recommendation(recommendation)
