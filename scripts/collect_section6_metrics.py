"""Section 6 evaluation harness: runs /api/analyze for every scenario persona, N times each,
in-process against the real FastAPI app (no separate uvicorn process needed), and records
per-run pass/fail, wall-clock runtime, and LLM token usage.

"Pass" means the pipeline completed and returned a recommendation whose recommended
alternative matches the expected outcome documented in CLAUDE.md's scenario table (matched by
keyword against the alternative's name/action, since exact wording can vary between runs).
"Stability" is measured by comparing the recommended alternative's id across repeated runs of
the same persona.

Token usage is captured by monkeypatching the acompletion() function ADK's LiteLLMClient calls
(google.adk.models.lite_llm.acompletion) so every underlying litellm call in a run — across all
four pipeline stages, including any tool-call round-trips — is summed into one total. This is
independent of streaming vs. non-streaming mode: ADK always resolves usage onto the model
response object litellm returns, whether that object is streamed or not, and either way its
`.usage` attribute is what the wrapper reads.

Usage: uv run python scripts/collect_section6_metrics.py [--repeats N] [--personas a,b,c]
"""
import argparse
import asyncio
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mobility_advisor import env  # noqa: E402  (must run before litellm/ADK import)
from mobility_advisor import paths  # noqa: E402

import httpx  # noqa: E402
import google.adk.models.lite_llm as lite_llm_mod  # noqa: E402

from mobility_advisor.api.app import app  # noqa: E402

ALL_PERSONAS = ["maja", "stefan", "lena", "katrin", "tobias", "sofia"]

# Keyword(s) that must appear (case-insensitive) in the recommended alternative's id/name/action
# fields for a run to count as matching CLAUDE.md's documented expected outcome.
EXPECTED_OUTCOME_KEYWORDS = {
    "maja": ["cancel", "bahncard 50", "bahncard50", "bc50"],
    "stefan": ["hold", "pending"],
    "lena": [],  # no specific alternative expected; pass criterion is "completes with warnings"
    "katrin": ["bahncard 50", "bahncard50", "bc50"],
    "tobias": ["cancel", "downgrade", "bahncard 50", "bahncard50", "bc50"],
    "sofia": ["miles"],
}

_usage_log: list[dict] = []

# ADK's lite_llm module only binds `acompletion` (and friends) into its own globals lazily, on
# first real use, via _ensure_litellm_imported() — which re-clobbers module globals from litellm
# every time it runs until its _LITELLM_IMPORTED guard flips true. Patching lite_llm_mod.acompletion
# before that first real call would just get silently overwritten the moment the pipeline made its
# first LLM call. Force the real import now so our patch below is the one that sticks.
lite_llm_mod._ensure_litellm_imported()
_orig_acompletion = lite_llm_mod.acompletion


async def _tracked_acompletion(*args, **kwargs):
    resp = await _orig_acompletion(*args, **kwargs)
    usage = getattr(resp, "usage", None)
    if usage is not None:
        _usage_log.append(
            {
                "model": kwargs.get("model"),
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(usage, "total_tokens", 0) or 0,
            }
        )
    return resp


lite_llm_mod.acompletion = _tracked_acompletion


def _matches_expected(persona: str, rec: dict) -> bool:
    keywords = EXPECTED_OUTCOME_KEYWORDS.get(persona, [])
    if not keywords:
        return True
    alts = rec.get("alternatives", [])
    recommended = next((a for a in alts if a.get("isRecommended")), None)
    if recommended is None:
        return False
    haystack = " ".join(
        [
            recommended.get("id", ""),
            recommended.get("name", ""),
            (recommended.get("action") or {}).get("title", "") if recommended.get("action") else "",
        ]
    ).lower()
    return any(kw in haystack for kw in keywords)


async def run_persona(client: httpx.AsyncClient, persona: str, repeats: int) -> dict:
    activate_resp = await client.post("/api/activate", json={"persona_id": persona})
    activate_resp.raise_for_status()

    runs = []
    for i in range(repeats):
        _usage_log.clear()
        t0 = time.monotonic()
        try:
            resp = await client.post(
                "/api/analyze",
                json={"session_id": f"metrics_{persona}_{i}"},
                timeout=300.0,
            )
            elapsed = time.monotonic() - t0
            ok_http = resp.status_code == 200
            body = resp.json() if ok_http else {"error": resp.text}
        except Exception as exc:  # network/timeout/etc.
            elapsed = time.monotonic() - t0
            ok_http = False
            body = {"error": str(exc)}

        prompt_tokens = sum(u["prompt_tokens"] for u in _usage_log)
        completion_tokens = sum(u["completion_tokens"] for u in _usage_log)
        total_tokens = sum(u["total_tokens"] for u in _usage_log)
        n_calls = len(_usage_log)

        rec = body.get("recommendation", {}) if ok_http else {}
        recommended_alt = next(
            (a for a in rec.get("alternatives", []) if a.get("isRecommended")), None
        )
        matches_expected = _matches_expected(persona, rec) if ok_http else False

        run_record = {
            "run_index": i,
            "http_ok": ok_http,
            "elapsed_seconds": round(elapsed, 2),
            "llm_calls": n_calls,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "verdict": rec.get("verdict"),
            "recommended_alternative_id": recommended_alt.get("id") if recommended_alt else None,
            "recommended_alternative_name": recommended_alt.get("name") if recommended_alt else None,
            "data_quality_warnings": rec.get("dataQualityWarnings", []),
            "matches_expected_outcome": matches_expected,
            "error": body.get("error") if not ok_http else None,
        }
        runs.append(run_record)
        print(
            f"  [{persona}] run {i + 1}/{repeats}: "
            f"{'OK' if ok_http else 'FAIL'} "
            f"{run_record['elapsed_seconds']}s "
            f"{total_tokens} tok "
            f"-> {run_record['recommended_alternative_id']} "
            f"(expected match: {matches_expected})"
        )

    recommended_ids = {r["recommended_alternative_id"] for r in runs if r["http_ok"]}
    stable = len(recommended_ids) <= 1

    return {
        "persona": persona,
        "runs": runs,
        "stable_recommendation": stable,
        "distinct_recommendations": sorted(x for x in recommended_ids if x is not None),
        "all_passed_http": all(r["http_ok"] for r in runs),
        "all_matched_expected": all(r["matches_expected_outcome"] for r in runs),
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--personas", type=str, default=",".join(ALL_PERSONAS))
    parser.add_argument("--out", type=str, default=str(REPO_ROOT / "docs" / "section6_metrics_raw.json"))
    args = parser.parse_args()

    personas = [p.strip() for p in args.personas.split(",") if p.strip()]

    # Back up whatever data/ currently holds (mirrors scenarios/activate_scenario.sh's own
    # non-destructive backup behavior) so this harness never loses in-progress fixture edits.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = paths.PACKAGE_ROOT / f"data_backup_{timestamp}_metrics"
    shutil.copytree(paths.DATA_DIR, backup_dir)
    print(f"Backed up data/ -> {backup_dir}")

    results = {"generated_at": datetime.now().isoformat(), "repeats": args.repeats, "personas": {}}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for persona in personas:
            print(f"\n=== {persona} ===")
            results["personas"][persona] = await run_persona(client, persona, args.repeats)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nRaw results written to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
