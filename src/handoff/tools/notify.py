# Copyright (c) 2026 ZINKUNO
# SPDX-License-Identifier: MIT
"""Telling the human something happened — or that something needs them."""

from __future__ import annotations

from typing import Any

from strands import tool

from handoff import config
from handoff.models import InterruptPayload


def _post_slack(message: str, target: str = "") -> bool:
    """Post to Slack. `target` is a channel name, or a webhook URL override."""
    from handoff.tools import slack

    channel = "" if target.startswith("http") else target
    webhook = target if target.startswith("http") else ""

    if not slack.configured() and not webhook:
        # Nothing to post with. Not an error — the console fallback is the
        # configured behaviour until a token or webhook exists.
        return False

    try:
        result = slack.post(message, channel=channel, webhook=webhook)
    except Exception as exc:  # pragma: no cover - network
        print(f"[handoff] Slack notify failed: {exc}")
        return False

    if not result.get("ok"):
        print(f"[handoff] Slack refused the message: {result.get('error')}")
        return False
    return True


def _send_telegram(message: str, buttons: list[tuple[str, str]] | None = None) -> bool:
    """Send to Telegram. Buttons turn a question into something tappable."""
    from handoff.tools import telegram

    if not telegram.configured():
        return False

    try:
        result = telegram.send(message, buttons=buttons)
    except Exception as exc:  # pragma: no cover - network
        print(f"[handoff] Telegram notify failed: {exc}")
        return False

    if not result.get("ok"):
        print(f"[handoff] Telegram refused the message: {result.get('error')}")
        return False
    return True


def _publish_sns(message: str, subject: str = "Handoff") -> bool:
    if not config.SNS_TOPIC_ARN:
        return False
    try:
        import boto3

        boto3.client("sns", region_name=config.AWS_REGION).publish(
            TopicArn=config.SNS_TOPIC_ARN, Subject=subject[:100], Message=message
        )
        return True
    except Exception as exc:  # pragma: no cover - requires AWS
        print(f"[handoff] SNS notify failed: {exc}")
        return False


def send_notification(
    message: str,
    channel: str = "",
    target: str = "",
    subject: str = "Handoff",
    buttons: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Send one notification through the configured channel.

    Falls back to stdout rather than failing the run — a workflow that
    completed successfully should not be marked failed because Slack was down.

    ``buttons`` are honoured by channels that can render them (Telegram) and
    ignored by the ones that cannot, so a caller never has to branch on which
    channel is configured.
    """
    channel = channel or config.NOTIFY_CHANNEL

    sent = False
    if channel == "slack":
        sent = _post_slack(message, target)
    elif channel == "telegram":
        sent = _send_telegram(message, buttons)
    elif channel in ("sns", "email", "ses"):
        sent = _publish_sns(message, subject)

    if not sent:
        print(f"[handoff:{channel or 'console'}] {message}")

    return {"sent": sent, "channel": channel or "console", "message": message}


@tool
def notify_user(message: str, channel: str = "", target: str = "") -> dict:
    """Send a short message to the user.

    Args:
        message: What to say. Keep it to a line or two.
        channel: "slack", "telegram", "sns", or "console". Defaults to the
            workflow's configured channel.
        target: Channel name or webhook override, if the channel needs one.

    Returns:
        Whether the message went out, and on which channel.
    """
    return send_notification(message, channel, target)


def notify_decision_needed(payload: InterruptPayload) -> dict[str, Any]:
    """Tell the user a decision is waiting, with a deep link to the screen.

    Called from the HITL gate's ``on_interrupt`` callback, which is the one
    moment Handoff is allowed to be interrupting on purpose.
    """
    url = f"{config.UI_BASE_URL}/decide/{payload.interrupt_id}"
    confidence = payload.agent_analysis.confidence
    message = (
        "Handoff needs your input\n"
        f"Item: {payload.item.summary or payload.item.subject}\n"
        f"From: {payload.item.sender}\n"
        f"Why: {payload.reason}\n"
        f"My best guess: {payload.agent_analysis.suggested_action or 'unclear'} "
        f"({confidence:.0%} confidence)\n"
        f"Decide: {url}"
    )
    result = send_notification(
        message,
        subject="Handoff — decision needed",
        buttons=_decision_buttons(payload),
    )
    result["url"] = url
    return result


#: Option keys are what the resume path expects; these are what a human reads.
_OPTION_LABELS = {
    "approve_suggested": "Do what you suggested",
    "file_ticket": "File a ticket",
    "archive": "Archive it",
    "draft_reply": "Draft a reply",
    "skip": "Leave it",
}


def _decision_buttons(payload: InterruptPayload) -> list[tuple[str, str]]:
    """One tappable answer per option, carrying the interrupt id back.

    Telegram caps callback data at 64 bytes, which is why the id and the
    option key travel rather than the whole payload.
    """
    return [
        (_OPTION_LABELS.get(option, option.replace("_", " ").capitalize()),
         f"{payload.interrupt_id}:{option}")
        for option in payload.options[:6]
    ]


def notify_batch(payloads: list[InterruptPayload]) -> dict[str, Any]:
    """One notification for everything a run set aside — not one per item."""
    if len(payloads) == 1:
        return notify_decision_needed(payloads[0])
    lines = [f"Handoff needs your call on {len(payloads)} items"]
    for p in payloads:
        lines.append(
            f"- {p.item.subject or p.item.summary} ({p.item.sender}) — "
            f"{p.agent_analysis.confidence:.0%} sure about "
            f"{p.agent_analysis.suggested_action or 'what to do'}"
        )
    lines.append(f"Decide: {config.UI_BASE_URL}/#waiting")
    result = send_notification("\n".join(lines), subject="Handoff — decisions needed")
    result["url"] = f"{config.UI_BASE_URL}/#waiting"
    return result
