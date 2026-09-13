# Copyright (c) 2026 ZINKUNO
# SPDX-License-Identifier: MIT
"""Airtable, over the REST API.

Every decision a run makes — handled alone, or escalated and answered — is
appended here as a row. That log is not decoration: it is the evidence that
the confidence gate is calibrated. A week of rows answers "how often does it
ask?" and "when it acted alone, was it right?" without anyone re-reading a
transcript.

Three values:

* ``AIRTABLE_API_KEY``  — a personal access token (``pat…``) from
  https://airtable.com/create/tokens, with ``data.records:write`` and
  ``schema.bases:read`` on the base you pick.
* ``AIRTABLE_BASE_ID``  — ``app…``, from the base's API page or its URL.
* ``AIRTABLE_TABLE``    — the table name, e.g. ``Decisions``.

Airtable rejects a write to a field that does not exist, so unknown fields are
dropped against the table's real schema before sending rather than failing the
whole row. A log that silently loses one column is better than a run that
fails because someone renamed a column.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from handoff import config

AIRTABLE_API = "https://api.airtable.com/v0"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }


def _client():
    import httpx

    return httpx.Client(timeout=20.0)


def configured() -> bool:
    return bool(config.AIRTABLE_API_KEY and config.AIRTABLE_BASE_ID and config.AIRTABLE_TABLE)


def _error(response) -> str:
    try:
        payload = response.json().get("error", {})
    except Exception:
        return f"{response.status_code}: {response.text[:160]}"
    if isinstance(payload, str):
        return payload
    message = payload.get("message", response.text[:160])
    if payload.get("type") == "NOT_FOUND":
        message += " — check AIRTABLE_BASE_ID and AIRTABLE_TABLE, and that the token's scope covers this base."
    return message


def _field_names() -> set[str]:
    """The columns the table actually has, or an empty set if unreadable."""
    try:
        with _client() as http:
            response = http.get(
                f"{AIRTABLE_API}/meta/bases/{config.AIRTABLE_BASE_ID}/tables",
                headers=_headers(),
            )
        if response.status_code >= 300:
            return set()
        for table in response.json().get("tables", []):
            if table.get("name") == config.AIRTABLE_TABLE or table.get("id") == config.AIRTABLE_TABLE:
                return {f.get("name") for f in table.get("fields", [])}
    except Exception:
        pass
    return set()


def append_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Append rows. Unknown columns are dropped, not fatal."""
    if not configured():
        return {"ok": False, "error": "Airtable needs AIRTABLE_API_KEY, AIRTABLE_BASE_ID and AIRTABLE_TABLE"}
    if not rows:
        return {"ok": True, "created": 0}

    known = _field_names()
    dropped: set[str] = set()
    records = []
    for row in rows[:10]:  # Airtable takes 10 records per request
        fields = dict(row)
        if known:
            dropped |= set(fields) - known
            fields = {k: v for k, v in fields.items() if k in known}
        records.append({"fields": fields})

    with _client() as http:
        response = http.post(
            f"{AIRTABLE_API}/{config.AIRTABLE_BASE_ID}/{config.AIRTABLE_TABLE}",
            headers=_headers(),
            json={"records": records, "typecast": True},
        )

    if response.status_code >= 300:
        return {"ok": False, "error": _error(response)}

    created = response.json().get("records", [])
    result: dict[str, Any] = {"ok": True, "created": len(created), "ids": [r.get("id") for r in created]}
    if dropped:
        result["dropped_fields"] = sorted(dropped)
    return result


def log_decision(
    item: str,
    action: str,
    confidence: float,
    decided_by: str,
    reasoning: str = "",
    workflow: str = "",
    run_id: str = "",
) -> dict[str, Any]:
    """Append one decision. ``decided_by`` is "agent" or "human"."""
    return append_rows(
        [
            {
                "Item": item[:1000],
                "Action": action,
                "Confidence": round(float(confidence), 3),
                "Decided by": decided_by,
                "Reasoning": reasoning[:1000],
                "Workflow": workflow,
                "Run": run_id,
                "At": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        ]
    )


def check() -> dict[str, Any]:
    """Prove the token reaches this base and this table."""
    if not config.AIRTABLE_API_KEY:
        return {"ok": False, "error": "AIRTABLE_API_KEY is not set"}
    if not (config.AIRTABLE_BASE_ID and config.AIRTABLE_TABLE):
        return {"ok": False, "error": "AIRTABLE_BASE_ID and AIRTABLE_TABLE must both be set"}

    try:
        with _client() as http:
            # A read of one record proves scope, base and table in one call
            # without writing anything into the user's log.
            response = http.get(
                f"{AIRTABLE_API}/{config.AIRTABLE_BASE_ID}/{config.AIRTABLE_TABLE}",
                headers=_headers(),
                params={"maxRecords": 1},
            )
    except Exception as exc:  # pragma: no cover - network
        return {"ok": False, "error": str(exc)[:160]}

    if response.status_code >= 300:
        return {"ok": False, "error": _error(response)}

    fields = _field_names()
    return {
        "ok": True,
        "table": config.AIRTABLE_TABLE,
        "columns": len(fields),
        "missing": sorted({"Item", "Action", "Confidence", "Decided by"} - fields) if fields else [],
    }
