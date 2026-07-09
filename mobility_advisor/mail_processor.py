import json
import os
from pathlib import Path

import msal
import requests
from dotenv import load_dotenv

from .mail_filter import clean_body, filter_emails

load_dotenv()

CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID")
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["Mail.Read"]

_DATA = Path(__file__).parent / "data"
_DELTA_LINK_FILE = Path(__file__).parent / "mail_delta_link.txt"
_RAW_OUTPUT = _DATA / "travel_history_raw.json"

OPENAI_API_KEY = os.getenv("KICONNECT_API_KEY", "")
OPENAI_API_BASE = "https://chat.kiconnect.nrw/api/v1"
MODEL = "OpenAI GPT OSS 120b KI:Inferenz.nrw"

EXTRACTION_PROMPT = """You are a data extraction assistant for a mobility advisor system.

Extract structured trip data from the following email. The user's home city is Frankfurt.

Return a JSON object with exactly these fields:
{{
  "trips": [
    {{
      "date": "YYYY-MM-DD",
      "mode": "rail | flight | bus | car_share | car_rental",
      "origin": "full station or city name",
      "destination": "full station or city name",
      "departure_time": "HH:MM or null",
      "arrival_time": "HH:MM or null",
      "duration_min": integer or null,
      "cost_eur": float or null,
      "provider": "provider name — for flights, use EXACTLY one of these names: Aegean Airlines, Air Astana, Air Canada, Air China, Air Dolomiti, Air India, Air New Zealand, All Nippon Airways, Asiana Airlines, Austrian Airlines, Avianca, Brussels Airlines, Cathay Pacific Airways, Copa Airlines, Croatia Airlines, Discover Airlines, EGYPTAIR, Ethiopian Airlines, Eurowings, EVA Air, ITA Airways, LATAM, LOT Polish Airlines, Lufthansa, Lufthansa City Airlines, Luxair, Olympic Airlines, Shenzhen Airline, Singapore Airlines, South African Airways, SWISS International Air Lines, TAP Portugal, Thai Airways, Turkish Airlines, United. If the airline is not in this list, use its name as-is.",
      "ticket_type": "ticket type or null (rail examples: Sparpreis, Flexpreis, Super Sparpreis, Super Sparpreis Young, Deutschlandticket, BahnCard 50 — use exact wording from the email if it matches one of these, otherwise use the exact wording from the email as-is; flight: Economy / Business; bus: Standard; car: daily rate / one-way)",
      "type": "mode-specific — see rules below; use null (JSON null, not the string Null) when not determinable",
      "size": "mode-specific — see rules below; use null when not applicable or not determinable",
      "distance_km": null,
      "co2_emission_kg": null,
      "real_travel_duration_min": null,
      "booked_under": null
    }}
  ]
}}

Rules:
- Extract ALL trips mentioned (outbound + return separately)
- If no price is found, set cost_eur to null
- For rail: mode = "rail"
- For flights: mode = "flight"
- For FlixBus/coach: mode = "bus"
- For MILES/car-share: mode = "car_share"
- For Enterprise/Sixt/Hertz: mode = "car_rental"
- For life events (Mietvertrag etc.): return {{"trips": []}}
- Set arrival_time if mentioned in the email (HH:MM), otherwise null
- Calculate duration_min from departure_time and arrival_time if both are available, otherwise null
- Always set real_travel_duration_min to null (post-processing fills this)

--- TYPE AND SIZE RULES (fill these fields for every trip) ---

RAIL:
  type = null   [post-processing fills this, leave null]
  size = null

CAR_SHARE and CAR_RENTAL:
  type: Determine the engine/drivetrain from any clue in the email (vehicle name, model, description).
    - "Electric" — explicitly electric (e.g. Tesla, e-Golf, i3, Zoe, ID.4)
    - "Hybrid"   — explicitly hybrid (e.g. Prius, Yaris Hybrid, plug-in hybrid)
    - "Diesel"   — explicitly diesel
    - "Petrol"   — explicitly petrol/gasoline
    - "Fuel"     — a specific car model is named AND no electric/hybrid indication is present
                   (e.g. "VW Golf", "BMW 1er", "Kompaktklasse z.B. Volkswagen Golf", "Ford Focus")
    - null       — no car model or engine hint at all
  size: Determine from vehicle class name or model.
    - "Small Car"  — city cars, minis, subcompacts (e.g. Smart, VW Polo, Fiat 500, BMW 1er, Corsa)
    - "Medium Car" — compact/mid-size (e.g. VW Golf, BMW 3er, Kompaktklasse, Mittelklasse, Passat)
    - "Large Car"  — large/SUV/premium (e.g. BMW 5er, Mercedes E-Klasse, SUV, Oberklasse)
    - null         — no vehicle class or model hint at all
  Examples:
    "Fahrzeugklasse: Kompaktklasse (z.B. Volkswagen Golf oder ähnlich)" → type="Fuel", size="Medium Car"
    "BMW 1er"                                                            → type="Fuel", size="Small Car"
    "Tesla Model 3"                                                      → type="Electric", size="Medium Car"
    "Toyota Prius Hybrid"                                                → type="Hybrid", size="Medium Car"

BUS:
  type: "Coach" (long-distance/intercity, FlixBus is always Coach) | "Local Bus" (urban/local) | null (unclear)
  size = null

FLIGHT:
  type: Classify by geography of origin and destination.
    - "domestic"   — both cities/airports in the same country
    - "short-haul" — both on the same continent (e.g. both in Europe)
    - "long-haul"  — different continents (e.g. Europe and Asia, Europe and America)
    - null         — cannot determine
  size = null

- Always return valid JSON, nothing else

Email category: {category}
Email subject: {subject}

Email body:
{body}
"""


def _get_token() -> str:
    app = msal.PublicClientApplication(client_id=CLIENT_ID, authority=AUTHORITY)
    accounts = app.get_accounts()
    result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(f"Auth failed: {result.get('error_description')}")
    return result["access_token"]


def fetch_new_mails(token: str) -> list[dict]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Prefer": 'outlook.body-content-type="text"',
    }

    if _DELTA_LINK_FILE.exists():
        url = _DELTA_LINK_FILE.read_text(encoding="utf-8").strip()
        print("Fetching new mails via delta link...")
    else:
        url = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages/delta?$select=subject,from,receivedDateTime,body,hasAttachments"
        print("First run — fetching all mails...")

    all_mails = []
    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        all_mails.extend(data.get("value", []))
        url = data.get("@odata.nextLink")

    delta_link = data.get("@odata.deltaLink", "")
    if delta_link:
        _DELTA_LINK_FILE.write_text(delta_link, encoding="utf-8")

    normalized = []
    for mail in all_mails:
        body_html = mail.get("body", {}).get("content", "")
        normalized.append({
            "id": mail.get("id", ""),
            "received_datetime": mail.get("receivedDateTime", ""),
            "sender_email": mail.get("from", {}).get("emailAddress", {}).get("address", ""),
            "sender_name": mail.get("from", {}).get("emailAddress", {}).get("name", ""),
            "subject": mail.get("subject", ""),
            "body_text": clean_body(body_html),
            "has_attachment": mail.get("hasAttachments", False),
            "attachments": [],
        })

    print(f"{len(normalized)} mails fetched.")
    return normalized


def extract_trip(mail: dict) -> list[dict]:
    prompt = EXTRACTION_PROMPT.format(
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
    trips = extracted.get("trips", [])

    for trip in trips:
        trip["source_mail_id"] = mail["id"]

    return trips


def _enrich_rail_trips(trips: list[dict]) -> list[dict]:
    """Set type/size for rail trips based on distance_km (>100 → Intercity, ≤100 → Regional)."""
    for trip in trips:
        if trip.get("mode") == "rail":
            trip["size"] = None
            dist = trip.get("distance_km")
            if dist is not None:
                trip["type"] = "Intercity" if dist > 100 else "Regional"
            else:
                trip["type"] = None
    return trips


def save_raw(trips: list[dict]) -> None:
    if _RAW_OUTPUT.exists():
        existing = json.loads(_RAW_OUTPUT.read_text(encoding="utf-8"))
        existing_refs = {t.get("booking_ref") for t in existing.get("trips", []) if t.get("booking_ref")}
        new_trips = [t for t in trips if t.get("booking_ref") not in existing_refs]
        existing["trips"].extend(new_trips)
        result = existing
    else:
        result = {"trips": trips}

    _RAW_OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"travel_history_raw.json updated — {len(result['trips'])} trips total.")


def run(use_mock: bool = False) -> None:
    if use_mock:
        raw = json.loads((_DATA / "mail_raw.json").read_text(encoding="utf-8"))
        all_mails = raw.get("emails", [])
        print(f"Using mock data — {len(all_mails)} mails loaded.")
    else:
        token = _get_token()
        all_mails = fetch_new_mails(token)

    relevant = filter_emails(all_mails)
    print(f"{len(relevant)} relevant mails to process.\n")

    all_trips = []
    for mail in relevant:
        print(f"Processing [{mail['category']}]: {mail['subject'][:50]}...")
        try:
            trips = extract_trip(mail)
            if trips:
                print(f"  -> {len(trips)} trip(s) extracted.")
                all_trips.extend(trips)
            else:
                print(f"  -> No trips extracted (life event or irrelevant).")
        except Exception as e:
            print(f"  -> Error: {e}")

    if all_trips:
        all_trips = _enrich_rail_trips(all_trips)
        save_raw(all_trips)
    else:
        print("No trips extracted.")


if __name__ == "__main__":
    run(use_mock=True)
