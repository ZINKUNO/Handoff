# Copyright (c) 2026 ZINKUNO
# SPDX-License-Identifier: MIT
"""The integrations Handoff calls directly, exposed to the agent as tools.

Most integrations arrive as MCP servers and the agent gets their tools for
free. Four do not — Notion, Telegram, Airtable and Google Calendar are either
OAuth-only as MCP servers, or two HTTP calls that do not warrant a subprocess
— so their tool surface is defined here instead.

``builtin_tools(names)`` is the mirror of ``mcp.servers.load_agent_tools``:
give it the names a workflow asked for, get back the tools the agent can
actually use. Unconfigured integrations are skipped rather than raising, for
the same reason as there — a workflow naming five integrations should run on
the three that are connected and say so, not refuse to start.

Every tool returns ``{"ok": …}`` and never raises. A workflow that finished
its real work should not be marked failed because Notion was briefly down,
and the model needs to *see* the failure to decide whether to carry on.
"""

from __future__ import annotations

from typing import Any

from strands import tool

# --- Notion -----------------------------------------------------------------


@tool
def notion_create_page(title: str, body: str = "") -> dict:
    """Create a Notion page — a run record, a brief, a report.

    Args:
        title: The page title. One line, specific.
        body: Plain text. Newlines become paragraphs.

    Returns:
        ok, and the new page's id and url.
    """
    from handoff.tools import notion

    return notion.create_page(title, body)


@tool
def notion_append(page_id: str, body: str) -> dict:
    """Add paragraphs to an existing Notion page.

    Args:
        page_id: The page to append to.
        body: Plain text. Newlines become paragraphs.

    Returns:
        Whether the append succeeded.
    """
    from handoff.tools import notion

    return notion.append(page_id, body)


@tool
def notion_search(query: str, limit: int = 5) -> dict:
    """Find a Notion page by name, among those shared with this integration.

    Args:
        query: Words from the page title.
        limit: How many results to return.

    Returns:
        Matching pages, with ids you can append to.
    """
    from handoff.tools import notion

    return notion.search(query, limit)


# --- Telegram ---------------------------------------------------------------


@tool
def telegram_send(text: str) -> dict:
    """Send the user a message on Telegram.

    Use this to report what a run did, not to ask a question — asking is
    `telegram_ask`, which gives them buttons to answer with.

    Args:
        text: What to say. A few lines at most; this lands on a phone.

    Returns:
        Whether it was delivered.
    """
    from handoff.tools import telegram

    return telegram.send(text)


@tool
def telegram_ask(question: str, options: list[str], decision_id: str = "") -> dict:
    """Ask the user something on their phone, with tappable answers.

    Args:
        question: What you could not decide, and why. Be specific enough that
            they can answer in five seconds without opening anything.
        options: The answers, as short labels, e.g.
            ["File a ticket", "Archive", "Draft a reply", "Leave it"].
        decision_id: The interrupt this question belongs to, so their tap can
            be matched back to it.

    Returns:
        Whether the question was delivered. The answer arrives later, when
        they tap — it is not returned here.
    """
    from handoff.tools import telegram

    buttons = [(label, f"{decision_id}:{label}"[:64]) for label in options[:6]]
    return telegram.send(question, buttons=buttons)


# --- Airtable ---------------------------------------------------------------


@tool
def airtable_log_decision(
    item: str,
    action: str,
    confidence: float,
    decided_by: str,
    reasoning: str = "",
) -> dict:
    """Append one decision to the review log.

    Args:
        item: What was being decided about — a subject line, a PR title.
        action: What was done, e.g. "archive", "file_ticket".
        confidence: Your confidence at the time, 0 to 1. Record what you
            actually had, not what looks good.
        decided_by: "agent" if you called it, "human" if they did.
        reasoning: One sentence on why.

    Returns:
        Whether the row was written.
    """
    from handoff.tools import airtable

    return airtable.log_decision(item, action, confidence, decided_by, reasoning)


# --- Google Calendar --------------------------------------------------------


@tool
def calendar_list_events(hours_ahead: int = 24) -> dict:
    """What is already on the user's calendar.

    Args:
        hours_ahead: How far forward to look.

    Returns:
        Events with start and end times.
    """
    from handoff.tools import gcal

    return gcal.list_events(hours_ahead)


@tool
def calendar_find_free_slot(minutes: int = 30, within_hours: int = 24) -> dict:
    """Find the next gap long enough to do a piece of work in.

    Args:
        minutes: How long the work needs.
        within_hours: How far ahead to search.

    Returns:
        A start and end time you can pass straight to calendar_create_event.
    """
    from handoff.tools import gcal

    return gcal.find_free_slot(minutes, within_hours)


@tool
def calendar_create_event(
    summary: str, start: str, end: str = "", description: str = "", minutes: int = 30
) -> dict:
    """Book time on the user's calendar.

    Args:
        summary: The event title. Name the actual task.
        start: RFC3339 start time, e.g. "2026-09-15T14:00:00Z".
        end: RFC3339 end time. Omit to use `minutes` instead.
        description: Why this is booked — say which item it came from.
        minutes: Length, when `end` is omitted.

    Returns:
        The created event's id and link.
    """
    from handoff.tools import gcal

    return gcal.create_event(summary, start, end, description, minutes)


# --- wiring -----------------------------------------------------------------

#: Server name -> the tools a workflow gets by naming it.
BUILTIN_TOOLS: dict[str, list[Any]] = {
    "notion": [notion_create_page, notion_append, notion_search],
    "telegram": [telegram_send, telegram_ask],
    "airtable": [airtable_log_decision],
    "gcal": [calendar_list_events, calendar_find_free_slot, calendar_create_event],
}


def builtin_tools(names: list[str]) -> list[Any]:
    """Tools for the named built-in integrations that are actually configured."""
    from handoff import config
    from handoff.mcp.servers import MCP_SERVERS

    tools: list[Any] = []
    for name in names:
        if name not in BUILTIN_TOOLS:
            continue
        spec = MCP_SERVERS.get(name)
        if spec is None or not spec.configured:
            continue
        # In mock mode nothing with a credential is opened: a demo should not
        # post into a real Slack, a real Notion, or a real person's phone.
        if config.USE_MOCK_TOOLS and (spec.required_env or spec.require_file):
            continue
        tools.extend(BUILTIN_TOOLS[name])
    return tools


def configured_names() -> list[str]:
    """Which built-in integrations are ready — for the dashboard and doctor."""
    from handoff.mcp.servers import MCP_SERVERS

    return [n for n in BUILTIN_TOOLS if (s := MCP_SERVERS.get(n)) and s.configured]
