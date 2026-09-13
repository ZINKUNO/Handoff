# Copyright (c) 2026 ZINKUNO
# SPDX-License-Identifier: MIT
"""Telegram, over the Bot API.

This is the integration that makes the gate feel real. When a run stops on
something it cannot call, the question goes to the phone in the person's
pocket with the answers as buttons — *file a ticket*, *archive*, *draft a
reply*, *leave it* — and one tap resolves it. No laptop, no dashboard.

Two values, both from the phone:

* ``TELEGRAM_BOT_TOKEN`` — from @BotFather (``/newbot``). Looks like
  ``123456789:AA…``.
* ``TELEGRAM_CHAT_ID``   — who to message. Send your new bot any message,
  then run ``handoff doctor telegram``: it reads the pending update and
  prints the id for you, because hunting for it is otherwise the one
  genuinely annoying step.

The buttons are ``callback_data`` on an inline keyboard. Handoff encodes the
interrupt id into them, so a tap is unambiguous even when three decisions are
waiting at once. Resolving a tap needs a webhook or a poll; ``handoff listen
--telegram`` polls, which keeps setup to two values and no public URL.
"""

from __future__ import annotations

from typing import Any

from handoff import config

#: Telegram caps a message at 4096 characters and silently rejects longer.
MESSAGE_LIMIT = 4096


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}"


def _client():
    import httpx

    return httpx.Client(timeout=20.0)


def configured() -> bool:
    return bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)


def _call(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not config.TELEGRAM_BOT_TOKEN:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN is not set"}
    try:
        with _client() as http:
            response = http.post(_api(method), json=payload)
        body = response.json()
    except Exception as exc:  # pragma: no cover - network
        return {"ok": False, "error": str(exc)[:160]}

    if not body.get("ok"):
        # Telegram's description is specific ("chat not found", "bot was
        # blocked by the user") and each needs a different fix, so it is
        # passed through rather than flattened.
        return {"ok": False, "error": body.get("description", "unknown")}
    return {"ok": True, "result": body.get("result")}


def send(text: str, chat_id: str = "", buttons: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    """Send one message, optionally with a row of tappable answers.

    Args:
        text: What to say. Truncated to Telegram's 4096-character limit.
        chat_id: Override the configured recipient.
        buttons: ``(label, callback_data)`` pairs rendered as an inline keyboard.
    """
    chat = chat_id or config.TELEGRAM_CHAT_ID
    if not chat:
        return {"ok": False, "error": "TELEGRAM_CHAT_ID is not set"}

    payload: dict[str, Any] = {
        "chat_id": chat,
        "text": text[:MESSAGE_LIMIT],
        "disable_web_page_preview": True,
    }
    if buttons:
        # One button per row: the labels are sentences ("Draft a reply"), and
        # Telegram truncates them side by side on a phone.
        payload["reply_markup"] = {
            "inline_keyboard": [
                [{"text": label, "callback_data": data[:64]}] for label, data in buttons
            ]
        }

    result = _call("sendMessage", payload)
    if result["ok"]:
        return {"ok": True, "message_id": result["result"].get("message_id"), "chat_id": chat}
    return result


def answer_callback(callback_id: str, text: str = "") -> dict[str, Any]:
    """Acknowledge a tap so the button stops spinning on the phone."""
    return _call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text[:200]})


def poll_updates(offset: int = 0, timeout: int = 0) -> dict[str, Any]:
    """Read pending updates. ``timeout`` > 0 long-polls."""
    result = _call("getUpdates", {"offset": offset, "timeout": timeout})
    if not result["ok"]:
        return result
    return {"ok": True, "updates": result["result"]}


def discover_chat_id() -> str:
    """The chat id of whoever last messaged the bot, or "".

    Exists so that setup is "message your bot, run doctor" rather than
    "construct a getUpdates URL by hand".
    """
    result = poll_updates()
    if not result.get("ok"):
        return ""
    for update in reversed(result.get("updates", [])):
        message = update.get("message") or update.get("callback_query", {}).get("message") or {}
        chat = message.get("chat") or {}
        if chat.get("id"):
            return str(chat["id"])
    return ""


def check() -> dict[str, Any]:
    """Verify the token, and help find the chat id when it is missing."""
    if not config.TELEGRAM_BOT_TOKEN:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN is not set"}

    me = _call("getMe", {})
    if not me["ok"]:
        return {"ok": False, "error": me["error"]}
    username = me["result"].get("username", "bot")

    if not config.TELEGRAM_CHAT_ID:
        found = discover_chat_id()
        if found:
            return {
                "ok": False,
                "bot": username,
                "error": f"token works; set TELEGRAM_CHAT_ID={found}",
                "chat_id": found,
            }
        return {
            "ok": False,
            "bot": username,
            "error": f"token works; send @{username} any message, then run this again",
        }

    # Sending is the only real proof: a token can be valid while the bot has
    # never been started by this chat, and that fails only on send.
    sent = send("Handoff is connected.")
    if not sent.get("ok"):
        return {"ok": False, "bot": username, "error": sent.get("error")}
    return {"ok": True, "bot": username, "chat_id": config.TELEGRAM_CHAT_ID}
