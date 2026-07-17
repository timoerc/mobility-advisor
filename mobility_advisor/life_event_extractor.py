import json
import os
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv

from .mail_filter import filter_emails
from .tools import MOCK_TODAY

load_dotenv()

_DATA = Path(__file__).parent / "data"
_OUTPUT = _DATA / "life_events.json"

OPENAI_API_KEY = os.getenv("KICONNECT_API_KEY", "")
OPENAI_API_BASE = "https://chat.kiconnect.nrw/api/v1"
MODEL = "OpenAI GPT OSS 120b KI:Inferenz.nrw"

LIFE_EVENT_PROMPT = """You are a data extraction assistant for a mobility advisor system.

Read the following email and decide whether it carries a life-event signal that could
plausibly shift the user's future mobility needs or spending pattern — a relocation, a
job change, a mobility-relevant subscription activation/cancellation/non-renewal, a
household change, or a recurring non-mobility subscription cost worth having as
background context. Ordinary trip bookings/receipts, delivery notifications, newsletters,
and unrelated personal mail are NOT life events — return no event for those.

Return a JSON object with exactly this shape:
{{
  "events": [
    {{
      "category": "relocation | job_change | subscription_change | household_change | other",
      "summary": "one-line plain-English summary of the event",
      "event_date": "YYYY-MM-DD or null - the date the event itself takes effect/occurs (e.g. move-in date, decision deadline, renewal/expiry date), not the email's received date",
      "signals": ["short machine-readable tags describing the mobility-relevant implication(s), e.g. home_base_change, commute_route_change, income_change, work_pattern_change, d_ticket_relevance_change (Deutschlandticket specifically), rail_card_relevance_change (BahnCard/rail-subscription specifically), car_share_relevance_change, non_mobility_spend — pick whichever tag(s) actually match this event, never a tag for a product this email doesn't mention"]
    }}
  ]
}}

Rules:
- category "relocation": a move, an apartment viewing/application, a change of home city.
- category "job_change": a new job offer, employer change, or work-location/commute-pattern change.
- category "subscription_change": a mobility-relevant subscription (rail card, Deutschlandticket,
  car-share, etc.) being activated, cancelled, or explicitly not renewed.
- category "household_change": a change to who lives with the user or their living situation,
  not itself a relocation.
- category "other": anything else worth flagging as background context, e.g. a recurring
  non-mobility subscription payment (streaming, gym, ...) — tag it with signal
  "non_mobility_spend" and keep the summary purely factual (name, amount, cadence).
- If the email is a routine trip booking/receipt, delivery notice, newsletter, or otherwise
  carries no life-event signal, return {{"events": []}}.
- Extract at most one event per email.
- Always return valid JSON, nothing else.

Email category: {category}
Email subject: {subject}

Email body:
{body}
"""


def _detect_events(mail: dict) -> list[dict]:
    prompt = LIFE_EVENT_PROMPT.format(
        category=mail.get("category", "unknown"),
        subject=mail["subject"],
        body=mail["body_text"][:10000],
    )

    response = requests.post(
        f"{OPENAI_API_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        },
    )
    response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown code blocks if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    extracted = json.loads(content)
    events = extracted.get("events", [])

    for event in events:
        event["source_mail_id"] = mail["id"]

    return events


def _atomic_write(path: Path, data: dict) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def run(use_mock: bool = True) -> None:
    if not use_mock:
        raise NotImplementedError("life_event_extractor only supports mock mail sources today.")

    raw = json.loads((_DATA / "mail_raw.json").read_text(encoding="utf-8"))
    all_mails = raw.get("emails", [])
    print(f"Using mock data — {len(all_mails)} mails loaded.")

    relevant = filter_emails(all_mails)
    non_booking = [m for m in relevant if not m["category"].startswith("booking_")]
    print(
        f"{len(non_booking)} non-booking mail(s) to check for life events "
        f"(of {len(relevant)} relevant total).\n"
    )

    detected_on = MOCK_TODAY.isoformat()
    all_events: list[dict] = []
    for mail in non_booking:
        print(f"Checking [{mail['category']}]: {mail['subject'][:50]}...")
        try:
            events = _detect_events(mail)
            if events:
                print(f"  -> {len(events)} life event(s) detected.")
                for event in events:
                    event["detected_on"] = detected_on
                all_events.extend(events)
            else:
                print("  -> No life event detected.")
        except Exception as e:
            print(f"  -> Error: {e}")

    _atomic_write(_OUTPUT, {"events": all_events})
    print(f"life_events.json written — {len(all_events)} event(s) total.")


if __name__ == "__main__":
    run(use_mock=True)
