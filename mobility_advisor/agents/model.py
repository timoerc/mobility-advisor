"""The shared LiteLlm model singleton, generation-config helper, and the per-invocation
context (today's date, home city) every agent instruction is built against."""
import json

from .. import env  # noqa: F401  (must run before anything touches litellm)

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from .. import clock, paths

_MODEL = LiteLlm(model="openai/OpenAI GPT OSS 120b KI:Inferenz.nrw")  # options: "openai/OpenAI GPT OSS 120b KI:Inferenz.nrw", "openai/Mistral Small 4 119B 2603", "openai/Mistral Small 3-2-24b Instruct KI:Inferenz.nrw"


def build_model() -> LiteLlm:
    """Return the shared LiteLlm singleton used by all pipeline agents."""
    return _MODEL


# Output-length tiers for the pipeline agents below (see build_content_config).
_SHORT_REPORT_TOKENS = 4096   # analyst / annual forecaster: trip projection / forecast summaries.
# Bumped from an earlier 1024/2048 budget — GPT-OSS-120B's internal reasoning tokens count
# against max_output_tokens, so a tight budget across several sequential tool calls could
# exhaust it before any visible text was written, producing an empty response — confirmed
# empirically against Stefan's larger dataset (3 subscriptions).
_MEDIUM_REPORT_TOKENS = 4096  # forecaster / communicator / annual agents: structured output
# with a scoring or recommendation breakdown.
_OPTIMIZER_TOKENS = 8192      # optimizer: simulation results + scoring analysis over every
# candidate scenario optimize_all_categories() returns — the largest structured payload
# any agent in this pipeline handles.
_LONG_REPORT_TOKENS = 4096    # annual_communicator: full multi-section annual review


def build_content_config(max_output_tokens: int) -> types.GenerateContentConfig:
    """Deterministic generation config shared by the pipeline agents.

    temperature=0.0: analyst/forecaster/optimizer/communicator perform exact
    arithmetic and verbatim transcription from tool output (BahnCard ROI
    comparison, CO2-emission formulas, cost sums) rather than creative
    composition, and this report may be re-run and compared — reproducibility
    matters more here than sampling diversity.
    """
    return types.GenerateContentConfig(
        temperature=0.0, max_output_tokens=max_output_tokens
    )


_TODAY = clock.MOCK_TODAY.isoformat()
_REVIEW_YEAR = clock.REVIEW_YEAR


def _load_home_city() -> str:
    """Read the active persona's home city fresh from disk on every call.

    Unlike a module-level constant (evaluated once, at process start), this must be
    read per-invocation: switching personas via POST /api/activate swaps data/persona.json
    on disk without restarting the backend process, so any value cached at import time goes
    stale the moment a second persona is activated in the same running server — exactly the
    scenario the demo personas exist to exercise live.

    Called from an InstructionProvider, which runs on every Forecaster invocation — a
    missing or truncated persona.json previously raised straight out of json.loads() here,
    killing the pipeline before the Forecaster stage could even start (analyst's output
    would already be on disk, but the run would never reach the optimizer). Falls back to
    "" (the same default a present-but-empty profileData.location.home_city would already
    produce) so a corrupt/missing file degrades to "no known home city" instead of a hard
    crash.
    """
    try:
        prefs = json.loads((paths.DATA_DIR / "persona.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return ""
    return prefs.get("profileData", {}).get("location", {}).get("home_city", "")


__all__ = [
    "ReadonlyContext",
    "_MODEL",
    "build_model",
    "build_content_config",
    "_SHORT_REPORT_TOKENS",
    "_MEDIUM_REPORT_TOKENS",
    "_OPTIMIZER_TOKENS",
    "_LONG_REPORT_TOKENS",
    "_TODAY",
    "_REVIEW_YEAR",
    "_load_home_city",
]
