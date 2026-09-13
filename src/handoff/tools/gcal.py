# Copyright (c) 2026 ZINKUNO
# SPDX-License-Identifier: MIT
"""Google Calendar, over the Calendar API.

Triage that only files tickets is half a morning's work. The other half is
time: a real ask needs a slot to do it in, and a follow-up needs a reminder
that is not a sticky note. So a run can read today's schedule, find the gaps,
and book the work it just filed.

**It reuses the Google project you already made for Gmail.** The OAuth client
JSON at ``~/.gmail-mcp/gcp-oauth.keys.json`` is the same file; only the scope
differs, so there is no second console project to create. The consent runs
once (``handoff connect gcal``) and writes a refreshing token to
``~/.handoff/google-calendar.json``.

Scope is ``calendar.events`` — read and write events, and nothing else. It
cannot delete your calendars or read your contacts, and the consent screen
says exactly that.

``GOOGLE_CALENDAR_ID`` picks the calendar; ``primary`` (the default) is the
one whose name is your email address.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from handoff import config

CALENDAR_API = "https://www.googleapis.com/calendar/v3"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def token_path() -> Path:
    return Path.home() / ".handoff" / "google-calendar.json"


def client_secrets_path() -> Path:
    """Shared with the Gmail MCP server — one Google project, two scopes."""
    return Path.home() / ".gmail-mcp" / "gcp-oauth.keys.json"


def configured() -> bool:
    return token_path().exists()


def _credentials():
    """Load the stored token, refreshing it if it has expired.

    Returns ``None`` rather than raising when nothing is stored: an
    unconfigured integration is a normal state, and every caller here reports
    it as one.
    """
    if not token_path().exists():
        return None
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError:
        return None

    creds = Credentials.from_authorized_user_file(str(token_path()), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path().write_text(creds.to_json())
    return creds


def connect(timeout: float = 300.0) -> dict[str, Any]:
    """Run the one-time Google consent flow in a browser."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        return {
            "ok": False,
            "error": "Install the Google client libraries: pip install google-auth-oauthlib",
        }

    secrets = client_secrets_path()
    if not secrets.exists():
        return {
            "ok": False,
            "error": (
                f"No OAuth client file at {secrets}. Google Cloud Console → APIs & "
                "Services → Credentials → your OAuth client → Download JSON, save it "
                "there. (The Gmail connection uses the same file.)"
            ),
        }

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
        creds = flow.run_local_server(port=0, timeout_seconds=timeout)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}

    token_path().parent.mkdir(parents=True, exist_ok=True)
    token_path().write_text(creds.to_json())
    return {"ok": True, "message": f"Signed in — token stored at {token_path()}"}


def _client(creds):
    import httpx

    return httpx.Client(
        timeout=20.0, headers={"Authorization": f"Bearer {creds.token}"}
    )


def _calendar() -> str:
    return config.GOOGLE_CALENDAR_ID or "primary"


def _error(response) -> str:
    try:
        return response.json().get("error", {}).get("message", response.text[:160])
    except Exception:
        return f"{response.status_code}: {response.text[:160]}"


def list_events(hours_ahead: int = 24, max_results: int = 20) -> dict[str, Any]:
    """What is already on the calendar between now and ``hours_ahead``."""
    creds = _credentials()
    if creds is None:
        return {"ok": False, "error": "Google Calendar is not connected — run: handoff connect gcal"}

    now = datetime.now(UTC)
    with _client(creds) as http:
        response = http.get(
            f"{CALENDAR_API}/calendars/{_calendar()}/events",
            params={
                "timeMin": now.isoformat(),
                "timeMax": (now + timedelta(hours=hours_ahead)).isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": max(1, min(max_results, 100)),
            },
        )

    if response.status_code >= 300:
        return {"ok": False, "error": _error(response)}

    events = []
    for item in response.json().get("items", []):
        start = item.get("start", {})
        end = item.get("end", {})
        events.append(
            {
                "id": item.get("id"),
                "summary": item.get("summary", "(no title)"),
                "start": start.get("dateTime") or start.get("date"),
                "end": end.get("dateTime") or end.get("date"),
                "all_day": "date" in start,
            }
        )
    return {"ok": True, "events": events, "calendar": _calendar()}


def create_event(
    summary: str,
    start: str,
    end: str = "",
    description: str = "",
    minutes: int = 30,
) -> dict[str, Any]:
    """Book one event.

    Args:
        summary: The event title.
        start: RFC3339 start time, e.g. ``2026-09-15T14:00:00Z``.
        end: RFC3339 end time. Defaults to ``start`` plus ``minutes``.
        description: Body text — put the reason the agent booked it here.
        minutes: Length, used only when ``end`` is empty.
    """
    creds = _credentials()
    if creds is None:
        return {"ok": False, "error": "Google Calendar is not connected — run: handoff connect gcal"}

    if not end:
        try:
            begins = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except ValueError:
            return {"ok": False, "error": f"start must be RFC3339, got {start!r}"}
        end = (begins + timedelta(minutes=minutes)).isoformat()

    body = {
        "summary": summary[:1000],
        "description": description[:8000],
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }

    with _client(creds) as http:
        response = http.post(
            f"{CALENDAR_API}/calendars/{_calendar()}/events", json=body
        )

    if response.status_code >= 300:
        return {"ok": False, "error": _error(response)}

    created = response.json()
    return {"ok": True, "event_id": created.get("id"), "url": created.get("htmlLink")}


def find_free_slot(minutes: int = 30, within_hours: int = 24) -> dict[str, Any]:
    """The first gap long enough for ``minutes`` of work.

    Deliberately simple: it walks the busy blocks in order and returns the
    first opening. A full scheduling solver would be a different product, and
    "the next free half hour" is what the workflow actually asks for.
    """
    listed = list_events(hours_ahead=within_hours, max_results=100)
    if not listed.get("ok"):
        return listed

    need = timedelta(minutes=minutes)
    cursor = datetime.now(UTC) + timedelta(minutes=5)
    horizon = cursor + timedelta(hours=within_hours)

    for event in listed["events"]:
        if event["all_day"]:
            continue
        try:
            begins = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
            ends = datetime.fromisoformat(event["end"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if begins - cursor >= need:
            return {"ok": True, "start": cursor.isoformat(), "end": (cursor + need).isoformat()}
        cursor = max(cursor, ends)

    if cursor + need <= horizon:
        return {"ok": True, "start": cursor.isoformat(), "end": (cursor + need).isoformat()}
    return {"ok": False, "error": f"no {minutes}-minute gap in the next {within_hours}h"}


def check() -> dict[str, Any]:
    """Prove the token is live and the calendar is readable."""
    if not client_secrets_path().exists() and not token_path().exists():
        return {
            "ok": False,
            "error": f"no OAuth client at {client_secrets_path()} — same file the Gmail connection uses",
        }
    if not token_path().exists():
        return {"ok": False, "error": "not signed in — run: handoff connect gcal"}

    try:
        creds = _credentials()
    except Exception as exc:
        return {"ok": False, "error": f"stored token could not be refreshed: {str(exc)[:120]}"}
    if creds is None:
        return {"ok": False, "error": "install the Google client libraries: pip install google-auth-oauthlib"}

    with _client(creds) as http:
        response = http.get(f"{CALENDAR_API}/calendars/{_calendar()}")

    if response.status_code >= 300:
        return {"ok": False, "error": _error(response)}

    calendar = response.json()
    return {"ok": True, "calendar": calendar.get("summary", _calendar()), "timezone": calendar.get("timeZone")}
