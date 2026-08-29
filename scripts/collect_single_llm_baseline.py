"""Section 6.4 naive single-LLM baseline: one unstructured prompt per persona, one LLM call,
no tools, no deterministic scoring engine, no post-hoc validation — contrasted against the
multi-agent pipeline's deterministic-engine-backed recommendation.

Feeds the same raw fixture data the real pipeline's agents read from disk (persona profile,
current subscriptions, travel history, calendar events, car usage, pre-extracted life-event
signals, and the shared mobility product catalog) into a single completion call against the
same backend/model the pipeline uses (agents/model.py's _MODEL), at the same temperature=0.0,
so the only variable being measured is architecture (single free-form call vs. multi-agent +
deterministic optimizer), not model choice or sampling.

Deliberately excludes: mail_raw.json (the dormant raw-email path the live pipeline itself never
reads — see CLAUDE.md's Data layer section; the pipeline's own equivalent input is the
pre-extracted life_events.json, which IS included here) and analysis_history.json (prior-review
continuity, not raw operational data needed to produce one fresh recommendation).

Usage: uv run python scripts/collect_single_llm_baseline.py [--personas a,b,c]
"""
import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mobility_advisor import env  # noqa: E402  (must run before litellm import)
from mobility_advisor import paths  # noqa: E402
from mobility_advisor.store.scenarios import activate_scenario  # noqa: E402
from mobility_advisor.agents.model import _MODEL  # noqa: E402

import litellm  # noqa: E402

ALL_PERSONAS = ["maja", "stefan", "lena", "katrin", "tobias", "sofia"]

RAW_FILES = [
    "persona.json",
    "current_subscriptions.json",
    "travel_history_raw.json",
    "calendar_events_live.json",
    "car_usage.json",
    "life_events.json",
]

SYSTEM_PROMPT = """You are a mobility subscription advisor. A user has given you their full \
mobility profile: personal details and priorities, their current subscriptions, their travel \
history over roughly the last 12 months, their upcoming calendar events, their private car \
usage (if any), any known upcoming life events, and the full catalog of mobility products \
available to subscribe to.

Analyze all of this and give ONE clear final recommendation: either keep the current \
subscription setup unchanged, or change it (cancel, downgrade, upgrade, and/or add specific \
named products from the catalog). Explain your reasoning using the actual numbers in the data \
provided. Give your best-estimate annual cost impact in EUR and CO2 impact in kg/year of your \
recommended change versus the user's current setup, computed from the data given, not made up. \
If any data looks missing, inconsistent, or malformed, say so explicitly rather than silently \
ignoring it or guessing a value for it.

End your answer with a short "FINAL RECOMMENDATION:" line summarizing the concrete action."""


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _build_user_prompt(persona: str) -> str:
    sections = []
    for fname in RAW_FILES:
        data = _load_json(paths.DATA_DIR / fname)
        sections.append(f"## {fname}\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```")
    catalog = _load_json(paths.PACKAGE_ROOT / "static" / "mobility_catalog.json")
    sections.append(f"## mobility_catalog.json (all available products)\n```json\n{json.dumps(catalog, ensure_ascii=False, indent=2)}\n```")
    return "\n\n".join(sections)


async def run_persona(persona: str) -> dict:
    activate_scenario(persona)
    user_prompt = _build_user_prompt(persona)

    t0 = time.monotonic()
    response = await litellm.acompletion(
        model=_MODEL.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=12000,
    )
    elapsed = time.monotonic() - t0

    message = response.choices[0].message
    usage = response.usage

    return {
        "persona": persona,
        "elapsed_seconds": round(elapsed, 2),
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "answer": message.content,
        "reasoning": getattr(message, "reasoning_content", None),
        "finish_reason": response.choices[0].finish_reason,
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--personas", type=str, default=",".join(ALL_PERSONAS))
    parser.add_argument("--out", type=str, default=str(REPO_ROOT / "docs" / "section6_baseline_raw.json"))
    args = parser.parse_args()
    personas = [p.strip() for p in args.personas.split(",") if p.strip()]

    results = {"generated_at": datetime.now().isoformat(), "model": _MODEL.model, "personas": {}}
    for persona in personas:
        print(f"=== {persona} ===")
        record = await run_persona(persona)
        results["personas"][persona] = record
        print(
            f"  {record['elapsed_seconds']}s, {record['total_tokens']} tok "
            f"(prompt {record['prompt_tokens']}, completion {record['completion_tokens']}), "
            f"finish_reason={record['finish_reason']}"
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRaw results written to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
