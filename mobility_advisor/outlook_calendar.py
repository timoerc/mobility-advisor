import json
import os

import msal
import requests
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

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
    end_raw = event.get("end", {}).get("dateTime", "")
    is_all_day = event.get("isAllDay", False)
    is_online = event.get("isOnlineMeeting", False)
    location = event.get("location", {}).get("displayName", "") or None

    if is_all_day:
        date = start_raw[:10] if start_raw else ""
        time_start = None
        time_end = None
        meeting_type = "all_day"
    else:
        date = datetime.strptime(start_raw[:19], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d") if start_raw else ""
        time_start = start_raw[11:16] if start_raw else None
        time_end = end_raw[11:16] if end_raw else None

        has_physical_location = bool(
            location and
            "Teams" not in location and
            "Zoom" not in location and
            "teams.microsoft" not in location
        )

        if is_online and has_physical_location:
            meeting_type = "unclear"
        elif is_online:
            meeting_type = "online"
        else:
            meeting_type = "in_person"

    return {
        "date": date,
        "time_start": time_start,
        "time_end": time_end,
        "type": meeting_type,
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