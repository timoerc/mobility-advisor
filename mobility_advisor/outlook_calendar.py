import json
import os

import msal
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID")
TENANT_ID = os.getenv("OUTLOOK_TENANT_ID")
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["Calendars.Read"]

_DATA = Path(__file__).parent / "data"


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


def _convert_event(event: dict) -> dict:
    start_raw = event.get("start", {}).get("dateTime", "")
    location = event.get("location", {}).get("displayName", "") or None
    return {
        "date": start_raw[:10] if start_raw else "",
        "type": "meeting",
        "description": event.get("subject", ""),
        "location": location,
        "signals": [],
    }


def fetch_calendar_events() -> dict:
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        "https://graph.microsoft.com/v1.0/me/events?$select=subject,start,end,location&$top=50",
        headers=headers,
    )
    response.raise_for_status()

    events = response.json().get("value", [])
    result = {"events": [_convert_event(e) for e in events]}

    live_path = _DATA / "calendar_events_live.json"
    live_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(events)} events fetched and saved to {live_path.name}")

    return result