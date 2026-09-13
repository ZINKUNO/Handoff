# Copyright (c) 2026 ZINKUNO
# SPDX-License-Identifier: MIT
"""Turning a tap on a phone into a resumed run.

``notify`` sends a waiting decision to Telegram with the options as buttons.
This is the other half: it long-polls for the taps and feeds each one into
``submit_decision``, the same entry point the browser's decision screen uses.
The run resumes, the learner records the rule, and the person never opened a
laptop.

Polling rather than a webhook is a deliberate trade. A webhook needs a public
HTTPS URL, which means a tunnel or a deploy before anything works at all;
``getUpdates`` with a long timeout costs one idle connection and works from a
laptop behind NAT. At this volume — a handful of decisions a day — the
difference is invisible.

Two properties matter for correctness:

* **Offsets are persisted.** Telegram replays every un-acknowledged update, so
  a listener that forgot its offset would re-answer decisions on restart.
* **Already-resolved taps are acknowledged, not applied.** Two taps on the
  same question, or a decision answered in the browser first, must not run the
  resume path twice.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from handoff import config
from handoff.tools import telegram


def _offset_path() -> Path:
    return config.ensure_state_dir() / "telegram_offset.json"


def read_offset() -> int:
    try:
        return int(json.loads(_offset_path().read_text()).get("offset", 0))
    except Exception:
        return 0


def write_offset(offset: int) -> None:
    _offset_path().write_text(json.dumps({"offset": offset}))


def parse_callback(data: str) -> tuple[str, str]:
    """``"int_abc123:file_ticket"`` -> ``("int_abc123", "file_ticket")``."""
    interrupt_id, _, action = (data or "").partition(":")
    return interrupt_id.strip(), action.strip()


def handle_tap(interrupt_id: str, action: str) -> dict[str, Any]:
    """Apply one tapped answer. Safe to call twice for the same tap."""
    from handoff.store import get_store

    if not interrupt_id or not action:
        return {"ok": False, "error": "button carried no decision"}

    payload = get_store().get_interrupt(interrupt_id)
    if payload is None:
        return {"ok": False, "error": f"no pending decision {interrupt_id}"}
    if payload.resolved:
        # Answered already — in the browser, or by a double tap. Report it as
        # handled so the tap is acknowledged and never retried.
        return {"ok": True, "already_resolved": True, "interrupt_id": interrupt_id}

    from handoff.agents.executor import submit_decision

    outcome = submit_decision(interrupt_id, action, note="answered on Telegram")
    return {"ok": True, "interrupt_id": interrupt_id, "action": action, "outcome": outcome}


def poll_once(offset: int = 0, timeout: int = 25) -> tuple[int, list[dict[str, Any]]]:
    """One long-poll. Returns the next offset and what was handled."""
    result = telegram.poll_updates(offset=offset, timeout=timeout)
    if not result.get("ok"):
        return offset, [{"ok": False, "error": result.get("error")}]

    handled: list[dict[str, Any]] = []
    for update in result.get("updates", []):
        # Advance past every update, handled or not. An update we don't
        # understand must still not be replayed forever.
        offset = max(offset, int(update.get("update_id", 0)) + 1)

        query = update.get("callback_query")
        if not query:
            continue

        interrupt_id, action = parse_callback(query.get("data", ""))
        outcome = handle_tap(interrupt_id, action)

        if outcome.get("already_resolved"):
            reply = "Already answered."
        elif outcome.get("ok"):
            reply = f"Done — {action.replace('_', ' ')}."
        else:
            reply = str(outcome.get("error", "Could not apply that."))[:180]

        try:
            telegram.answer_callback(query.get("id", ""), reply)
        except Exception:  # pragma: no cover - network
            pass
        handled.append(outcome)

    return offset, handled


def listen(
    timeout: int = 25,
    once: bool = False,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    """Long-poll until interrupted, applying every tap.

    Args:
        timeout: Seconds to hold each poll open.
        once: Poll a single time and return — what the tests use.
        on_event: Called with each handled result, for printing.
    """
    if not telegram.configured():
        raise RuntimeError(
            "Telegram is not configured — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"
        )

    offset = read_offset()
    while True:
        try:
            offset, handled = poll_once(offset, timeout)
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # pragma: no cover - network
            # A dropped connection should pause, not end the listener; this
            # process is expected to outlive a flaky café wifi.
            print(f"[handoff] Telegram poll failed: {exc}")
            time.sleep(5)
            continue

        write_offset(offset)
        for event in handled:
            if on_event is not None:
                on_event(event)

        if once:
            return
