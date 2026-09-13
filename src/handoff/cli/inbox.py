# Copyright (c) 2026 ZINKUNO
# SPDX-License-Identifier: MIT
"""`handoff answers` — take decisions from the phone.

Run this beside the scheduler and every question the gate raises can be
answered by tapping a button in Telegram. It is the same ``submit_decision``
path the browser uses, so a run resumes identically whichever surface answered
it, and the learner records the rule either way.
"""

from __future__ import annotations

import argparse

from handoff.cli import _ui


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("answers", help="Take waiting decisions from Telegram")
    p.set_defaults(handle=handle)
    c = p.add_subparsers(dest="answers_command", metavar="<action>")

    p_listen = c.add_parser("listen", help="Long-poll for tapped answers until stopped (the default)")
    p_listen.add_argument("--once", action="store_true", help="Poll a single time and exit")
    p_listen.add_argument("--timeout", type=int, default=25, help="Seconds to hold each poll open")

    c.add_parser("pending", help="Decisions currently waiting on a human")

    p_send = c.add_parser("send", help="Re-send a waiting decision to Telegram")
    p_send.add_argument("interrupt_id", nargs="?", default="", help="Defaults to every pending one")


def handle(args: argparse.Namespace) -> int:
    from handoff.store import get_store

    action = args.answers_command or "listen"

    if action == "pending":
        pending = get_store().pending_interrupts()
        rows = [
            {
                "interrupt_id": p.interrupt_id,
                "item": p.item.subject or p.item.summary,
                "sender": p.item.sender,
                "suggested": p.agent_analysis.suggested_action,
                "confidence": round(p.agent_analysis.confidence, 2),
            }
            for p in pending
        ]
        _ui.emit(
            rows,
            lambda: _ui.table(
                "Waiting on you",
                ["id", "item", "from", "suggested", "confidence"],
                [[r["interrupt_id"], r["item"], r["sender"], r["suggested"], r["confidence"]] for r in rows],
            ),
        )
        return 0

    if action == "send":
        from handoff.tools.notify import notify_decision_needed

        store = get_store()
        if args.interrupt_id:
            payload = store.get_interrupt(args.interrupt_id)
            if payload is None:
                raise KeyError(f"No decision with id '{args.interrupt_id}'")
            targets = [payload]
        else:
            targets = store.pending_interrupts()

        results = [notify_decision_needed(p) for p in targets]
        _ui.emit(results, lambda: _ui.dim(f"sent {len(results)} decision(s)"))
        return 0

    # listen
    from handoff.tools import telegram
    from handoff.tools import telegram_listener as listener

    if not telegram.configured():
        _ui.fail("Telegram is not connected — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        _ui.dim("Message @BotFather → /newbot, then run: handoff doctor telegram")
        return 1

    if not _ui.json_mode():
        _ui.dim("listening for tapped answers — Ctrl-C to stop")

    def report(event: dict) -> None:
        if event.get("already_resolved"):
            _ui.dim(f"{event['interrupt_id']} was already answered")
        elif event.get("ok"):
            _ui.ok(f"{event['interrupt_id']} → {event['action']}")
        else:
            _ui.warn(str(event.get("error", "unhandled tap")))

    try:
        listener.listen(timeout=args.timeout, once=args.once, on_event=report)
    except KeyboardInterrupt:
        if not _ui.json_mode():
            _ui.dim("stopped")
    return 0
