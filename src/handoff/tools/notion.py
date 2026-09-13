# Copyright (c) 2026 ZINKUNO
# SPDX-License-Identifier: MIT
"""Notion, over the REST API.

Handoff writes into Notion rather than reading from it. A run produces a
short, durable record — what it handled, what it asked about, what the human
said — and a Notion page is where a team already looks for that.

One credential:

* ``NOTION_API_KEY`` — an internal integration secret (``ntn_…`` on new
  integrations, ``secret_…`` on older ones). Created at
  https://www.notion.so/my-integrations.

And one destination, either of:

* ``NOTION_DATABASE_ID`` — each run appends a row. Preferred: a database gives
  you filtering and a table view for free, which is what makes a week of runs
  readable.
* ``NOTION_PARENT_PAGE_ID`` — each run appends a child page instead.

The integration only sees pages you have explicitly shared with it. That is
Notion's design, not an oversight, and it is the single most common reason a
valid key still returns 404: the page exists, but the integration was never
invited. The error text below says so, because "object_not_found" on its own
sends people to check a key that was never wrong.
"""

from __future__ import annotations

from typing import Any

from handoff import config

NOTION_API = "https://api.notion.com/v1"
#: Pinned. Notion routes on this header, and an unpinned client breaks the day
#: they ship a new shape.
NOTION_VERSION = "2022-06-28"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _client():
    import httpx

    return httpx.Client(timeout=20.0)


def configured() -> bool:
    return bool(config.NOTION_API_KEY)


def _dashed(raw: str) -> str:
    """Accept an id copied from a Notion URL (32 hex chars, no dashes).

    Notion's API wants the UUID form. Everyone pastes the URL form, so accept
    both rather than failing on the shape people actually have to hand.
    """
    clean = raw.strip().replace("-", "")
    if len(clean) != 32:
        return raw.strip()
    return f"{clean[:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:]}"


def _blocks(body: str) -> list[dict[str, Any]]:
    """Plain text into Notion paragraph blocks.

    A block's rich text is capped at 2000 characters, so long lines are split
    rather than silently rejected by the API.
    """
    blocks: list[dict[str, Any]] = []
    for line in body.splitlines():
        chunks = [line[i : i + 1900] for i in range(0, max(len(line), 1), 1900)] or [""]
        for chunk in chunks:
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": chunk}}]
                        if chunk
                        else []
                    },
                }
            )
    return blocks[:100]  # one request may carry 100 children


def _error(response) -> str:
    """Notion's own message, plus the sharing hint when that is the real cause."""
    try:
        payload = response.json()
    except Exception:
        return f"{response.status_code}: {response.text[:160]}"

    code = payload.get("code", "")
    message = payload.get("message", response.text[:160])
    if code == "object_not_found":
        message += (
            " — the integration has not been invited to this page. Open it in Notion, "
            "'...' → Connections → add your integration."
        )
    return message


def create_page(title: str, body: str = "", parent_id: str = "") -> dict[str, Any]:
    """Create one page: a database row if a database is configured, else a child page."""
    if not configured():
        return {"ok": False, "error": "NOTION_API_KEY is not set"}

    database = _dashed(parent_id or config.NOTION_DATABASE_ID)
    page = _dashed(config.NOTION_PARENT_PAGE_ID)

    if parent_id or config.NOTION_DATABASE_ID:
        parent = {"database_id": database}
        # A database row's title lives in whichever property is of type
        # "title". Its name varies per database, so it is resolved rather than
        # assumed to be "Name".
        prop = _title_property(database)
        properties = {prop: {"title": [{"text": {"content": title[:2000]}}]}}
    elif page:
        parent = {"page_id": page}
        properties = {"title": {"title": [{"text": {"content": title[:2000]}}]}}
    else:
        return {
            "ok": False,
            "error": "Set NOTION_DATABASE_ID (preferred) or NOTION_PARENT_PAGE_ID",
        }

    payload: dict[str, Any] = {"parent": parent, "properties": properties}
    if body:
        payload["children"] = _blocks(body)

    with _client() as http:
        response = http.post(f"{NOTION_API}/pages", headers=_headers(), json=payload)

    if response.status_code >= 300:
        return {"ok": False, "error": _error(response)}

    created = response.json()
    return {"ok": True, "page_id": created.get("id"), "url": created.get("url")}


def _title_property(database_id: str) -> str:
    """Which property of this database holds the title."""
    try:
        with _client() as http:
            response = http.get(
                f"{NOTION_API}/databases/{database_id}", headers=_headers()
            )
        if response.status_code < 300:
            for name, spec in (response.json().get("properties") or {}).items():
                if spec.get("type") == "title":
                    return name
    except Exception:
        pass
    return "Name"


def append(page_id: str, body: str) -> dict[str, Any]:
    """Append paragraphs to an existing page."""
    if not configured():
        return {"ok": False, "error": "NOTION_API_KEY is not set"}

    with _client() as http:
        response = http.patch(
            f"{NOTION_API}/blocks/{_dashed(page_id)}/children",
            headers=_headers(),
            json={"children": _blocks(body)},
        )

    if response.status_code >= 300:
        return {"ok": False, "error": _error(response)}
    return {"ok": True, "page_id": page_id}


def search(query: str, limit: int = 5) -> dict[str, Any]:
    """Search the pages this integration can see."""
    if not configured():
        return {"ok": False, "error": "NOTION_API_KEY is not set"}

    with _client() as http:
        response = http.post(
            f"{NOTION_API}/search",
            headers=_headers(),
            json={"query": query, "page_size": max(1, min(limit, 20))},
        )

    if response.status_code >= 300:
        return {"ok": False, "error": _error(response)}

    results = []
    for item in response.json().get("results", []):
        results.append(
            {
                "id": item.get("id"),
                "url": item.get("url"),
                "type": item.get("object"),
                "title": _read_title(item),
            }
        )
    return {"ok": True, "results": results}


def _read_title(item: dict[str, Any]) -> str:
    for spec in (item.get("properties") or {}).values():
        if spec.get("type") == "title":
            parts = spec.get("title") or []
            return "".join(p.get("plain_text", "") for p in parts)
    return ""


def check() -> dict[str, Any]:
    """Prove the key works, and that the destination is actually reachable."""
    if not configured():
        return {"ok": False, "error": "NOTION_API_KEY is not set"}

    with _client() as http:
        response = http.get(f"{NOTION_API}/users/me", headers=_headers())
        if response.status_code >= 300:
            return {"ok": False, "error": _error(response)}
        bot = response.json()

        target = _dashed(config.NOTION_DATABASE_ID or config.NOTION_PARENT_PAGE_ID)
        if not target:
            return {
                "ok": True,
                "bot": bot.get("name", "integration"),
                "note": "key works, but no NOTION_DATABASE_ID or NOTION_PARENT_PAGE_ID is set",
            }

        # A key that authenticates still cannot write to a page nobody shared.
        # Check the destination too, so `doctor` is honest about it.
        kind = "databases" if config.NOTION_DATABASE_ID else "pages"
        reachable = http.get(f"{NOTION_API}/{kind}/{target}", headers=_headers())

    if reachable.status_code >= 300:
        return {"ok": False, "bot": bot.get("name"), "error": _error(reachable)}

    return {"ok": True, "bot": bot.get("name", "integration"), "destination": kind[:-1]}
