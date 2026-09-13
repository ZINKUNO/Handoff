# Copyright (c) 2026 ZINKUNO
# SPDX-License-Identifier: MIT
"""The four direct integrations: Notion, Telegram, Airtable, Google Calendar.

Nothing here touches the network. What is tested is the part that is actually
easy to get wrong and expensive to discover at 8am — the id shapes people
paste, the payload a button carries, what happens when a column was renamed,
and whether a tap that arrives twice acts twice.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from handoff import config, doctor
from handoff.tools import airtable, gcal, notion, telegram
from handoff.tools import telegram_listener as listener


class TestNotionIds:
    def test_accepts_the_id_shape_people_paste_from_a_url(self):
        assert notion._dashed("a1b2c3d4e5f6478899aabbccddeeff00") == (
            "a1b2c3d4-e5f6-4788-99aa-bbccddeeff00"
        )

    def test_leaves_a_dashed_uuid_alone(self):
        uuid = "a1b2c3d4-e5f6-4788-99aa-bbccddeeff00"
        assert notion._dashed(uuid) == uuid

    def test_passes_anything_else_through_untouched(self):
        # Better to send it and let Notion say what is wrong than to mangle it.
        assert notion._dashed("not-an-id") == "not-an-id"


class TestNotionBlocks:
    def test_each_line_becomes_a_paragraph(self):
        blocks = notion._blocks("one\ntwo\nthree")
        assert len(blocks) == 3
        assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "one"

    def test_a_long_line_is_split_rather_than_rejected(self):
        # Notion caps rich text at 2000 characters per block.
        blocks = notion._blocks("x" * 5000)
        assert len(blocks) > 1
        assert all(
            len(b["paragraph"]["rich_text"][0]["text"]["content"]) <= 2000 for b in blocks
        )

    def test_a_blank_line_survives_as_an_empty_paragraph(self):
        blocks = notion._blocks("a\n\nb")
        assert len(blocks) == 3
        assert blocks[1]["paragraph"]["rich_text"] == []

    def test_never_exceeds_the_hundred_child_limit(self):
        assert len(notion._blocks("\n".join(str(i) for i in range(500)))) == 100


class TestNotionErrors:
    def test_object_not_found_explains_the_real_cause(self):
        class Response:
            status_code = 404
            text = ""

            @staticmethod
            def json():
                return {"code": "object_not_found", "message": "Could not find page."}

        message = notion._error(Response())
        # A valid key plus an un-shared page is the common first failure, and
        # "object_not_found" alone sends people to check the key instead.
        assert "invited" in message
        assert "Connections" in message

    def test_other_errors_are_passed_through_verbatim(self):
        class Response:
            status_code = 401
            text = ""

            @staticmethod
            def json():
                return {"code": "unauthorized", "message": "API token is invalid."}

        assert notion._error(Response()) == "API token is invalid."


class TestNotionGuards:
    def test_refuses_without_a_key(self, monkeypatch):
        monkeypatch.setattr(config, "NOTION_API_KEY", "")
        assert notion.create_page("x")["ok"] is False

    def test_refuses_without_a_destination(self, monkeypatch):
        monkeypatch.setattr(config, "NOTION_API_KEY", "ntn_test")
        monkeypatch.setattr(config, "NOTION_DATABASE_ID", "")
        monkeypatch.setattr(config, "NOTION_PARENT_PAGE_ID", "")
        result = notion.create_page("x")
        assert result["ok"] is False
        assert "NOTION_DATABASE_ID" in result["error"]


class TestTelegramMessages:
    def test_not_configured_without_both_values(self, monkeypatch):
        monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:abc")
        monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "")
        assert telegram.configured() is False

    def test_refuses_to_send_without_a_recipient(self, monkeypatch):
        monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:abc")
        monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "")
        assert telegram.send("hi")["ok"] is False

    def test_a_message_is_truncated_to_the_api_limit(self, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:abc")
        monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "42")
        monkeypatch.setattr(
            telegram, "_call", lambda m, p: captured.update(p) or {"ok": True, "result": {}}
        )
        telegram.send("x" * 9000)
        assert len(captured["text"]) == telegram.MESSAGE_LIMIT

    def test_buttons_become_one_per_row(self, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:abc")
        monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "42")
        monkeypatch.setattr(
            telegram, "_call", lambda m, p: captured.update(p) or {"ok": True, "result": {}}
        )
        telegram.send("pick", buttons=[("File a ticket", "i1:file_ticket"), ("Archive", "i1:archive")])
        keyboard = captured["reply_markup"]["inline_keyboard"]
        # Sentence-length labels get truncated side by side on a phone.
        assert [len(row) for row in keyboard] == [1, 1]
        assert keyboard[0][0]["callback_data"] == "i1:file_ticket"

    def test_callback_data_is_clipped_to_the_sixty_four_byte_limit(self, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:abc")
        monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "42")
        monkeypatch.setattr(
            telegram, "_call", lambda m, p: captured.update(p) or {"ok": True, "result": {}}
        )
        telegram.send("pick", buttons=[("Go", "y" * 200)])
        assert len(captured["reply_markup"]["inline_keyboard"][0][0]["callback_data"]) == 64


class TestDecisionButtons:
    def test_every_option_becomes_a_button_carrying_its_interrupt(self):
        from handoff.models import AgentAnalysis, InterruptItem, InterruptPayload
        from handoff.tools.notify import _decision_buttons

        payload = InterruptPayload(
            interrupt_id="int_abc",
            item=InterruptItem(subject="Contract renewal"),
            agent_analysis=AgentAnalysis(confidence=0.4),
            options=["file_ticket", "archive", "skip"],
        )
        buttons = _decision_buttons(payload)
        assert [b[1] for b in buttons] == ["int_abc:file_ticket", "int_abc:archive", "int_abc:skip"]
        # Labels are what a human reads, not the internal action key.
        assert buttons[0][0] == "File a ticket"


class TestTelegramCallbacks:
    def test_splits_an_interrupt_id_from_its_action(self):
        assert listener.parse_callback("int_abc:file_ticket") == ("int_abc", "file_ticket")

    def test_survives_malformed_callback_data(self):
        assert listener.parse_callback("") == ("", "")
        assert listener.parse_callback("garbage") == ("garbage", "")

    def test_a_tap_with_no_decision_is_refused(self):
        assert listener.handle_tap("", "archive")["ok"] is False

    def test_an_unknown_interrupt_is_refused(self):
        assert listener.handle_tap("int_missing", "archive")["ok"] is False

    def test_a_resolved_decision_is_acknowledged_but_not_reapplied(self):
        from handoff.models import InterruptPayload
        from handoff.store import get_store

        payload = InterruptPayload(interrupt_id="int_done", resolved=True)
        get_store().save_interrupt(payload)

        result = listener.handle_tap("int_done", "archive")
        # Telegram replays updates; answering twice must not run the resume
        # path twice, and must still acknowledge the tap so it stops retrying.
        assert result == {"ok": True, "already_resolved": True, "interrupt_id": "int_done"}


class TestTelegramOffsets:
    def test_offset_round_trips_through_state(self):
        listener.write_offset(4242)
        assert listener.read_offset() == 4242

    def test_missing_state_reads_as_zero(self):
        assert listener.read_offset() == 0

    def test_every_update_advances_the_offset_even_when_unhandled(self, monkeypatch):
        monkeypatch.setattr(
            telegram,
            "poll_updates",
            lambda offset=0, timeout=0: {
                "ok": True,
                # A plain message, not a tap — nothing to apply, but it must
                # still not be replayed forever.
                "updates": [{"update_id": 17, "message": {"text": "hello"}}],
            },
        )
        offset, handled = listener.poll_once(0, timeout=0)
        assert offset == 18
        assert handled == []


class TestAirtableRows:
    def test_needs_all_three_values(self, monkeypatch):
        monkeypatch.setattr(config, "AIRTABLE_API_KEY", "pat123")
        monkeypatch.setattr(config, "AIRTABLE_BASE_ID", "")
        monkeypatch.setattr(config, "AIRTABLE_TABLE", "Decisions")
        assert airtable.configured() is False
        assert airtable.append_rows([{"Item": "x"}])["ok"] is False

    def test_no_rows_is_a_success_not_a_call(self, monkeypatch):
        monkeypatch.setattr(config, "AIRTABLE_API_KEY", "pat123")
        monkeypatch.setattr(config, "AIRTABLE_BASE_ID", "app123")
        monkeypatch.setattr(config, "AIRTABLE_TABLE", "Decisions")
        assert airtable.append_rows([]) == {"ok": True, "created": 0}

    def test_unknown_columns_are_dropped_rather_than_failing_the_row(self, monkeypatch):
        sent: dict = {}

        monkeypatch.setattr(config, "AIRTABLE_API_KEY", "pat123")
        monkeypatch.setattr(config, "AIRTABLE_BASE_ID", "app123")
        monkeypatch.setattr(config, "AIRTABLE_TABLE", "Decisions")
        monkeypatch.setattr(airtable, "_field_names", lambda: {"Item", "Action"})

        class Response:
            status_code = 200

            @staticmethod
            def json():
                return {"records": [{"id": "rec1"}]}

        class Client:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def post(self, url, headers=None, json=None):
                sent.update(json)
                return Response()

        monkeypatch.setattr(airtable, "_client", lambda: Client())

        result = airtable.append_rows([{"Item": "x", "Action": "archive", "Ghost": "gone"}])
        assert result["ok"] is True
        # A renamed column should cost one field, not the whole run.
        assert result["dropped_fields"] == ["Ghost"]
        assert set(sent["records"][0]["fields"]) == {"Item", "Action"}

    def test_not_found_names_the_two_settings_to_check(self):
        class Response:
            status_code = 404
            text = ""

            @staticmethod
            def json():
                return {"error": {"type": "NOT_FOUND", "message": "Table not found"}}

        message = airtable._error(Response())
        assert "AIRTABLE_BASE_ID" in message and "AIRTABLE_TABLE" in message


class TestCalendarSlots:
    def _events(self, monkeypatch, events):
        monkeypatch.setattr(
            gcal, "list_events", lambda hours_ahead=24, max_results=20: {"ok": True, "events": events}
        )

    def test_an_empty_calendar_offers_the_next_slot(self, monkeypatch):
        self._events(monkeypatch, [])
        slot = gcal.find_free_slot(30)
        assert slot["ok"] is True
        start = datetime.fromisoformat(slot["start"])
        end = datetime.fromisoformat(slot["end"])
        assert (end - start) == timedelta(minutes=30)

    def test_a_gap_before_the_first_meeting_is_used(self, monkeypatch):
        soon = datetime.now(UTC) + timedelta(hours=3)
        self._events(
            monkeypatch,
            [{"start": soon.isoformat(), "end": (soon + timedelta(hours=1)).isoformat(), "all_day": False}],
        )
        slot = gcal.find_free_slot(30)
        assert slot["ok"] is True
        assert datetime.fromisoformat(slot["start"]) < soon

    def test_a_wall_of_meetings_reports_no_gap(self, monkeypatch):
        now = datetime.now(UTC)
        self._events(
            monkeypatch,
            [
                {
                    "start": now.isoformat(),
                    "end": (now + timedelta(hours=6)).isoformat(),
                    "all_day": False,
                }
            ],
        )
        assert gcal.find_free_slot(30, within_hours=5)["ok"] is False

    def test_all_day_events_do_not_block_the_day(self, monkeypatch):
        # An all-day "Q3 planning" marker is not six hours of busy time.
        self._events(monkeypatch, [{"start": "2026-09-15", "end": "2026-09-16", "all_day": True}])
        assert gcal.find_free_slot(30)["ok"] is True

    def test_unparseable_times_are_skipped_not_fatal(self, monkeypatch):
        self._events(monkeypatch, [{"start": "later", "end": "sometime", "all_day": False}])
        assert gcal.find_free_slot(30)["ok"] is True

    def test_a_failed_read_is_reported_not_swallowed(self, monkeypatch):
        monkeypatch.setattr(
            gcal, "list_events", lambda **kw: {"ok": False, "error": "not connected"}
        )
        assert gcal.find_free_slot(30) == {"ok": False, "error": "not connected"}

    def test_refuses_when_not_signed_in(self, monkeypatch, tmp_path):
        monkeypatch.setattr(gcal, "token_path", lambda: tmp_path / "absent.json")
        assert gcal.list_events()["ok"] is False
        assert gcal.create_event("x", "2026-09-15T10:00:00Z")["ok"] is False

    def test_a_non_rfc3339_start_is_refused_before_any_call(self, monkeypatch, tmp_path):
        token = tmp_path / "token.json"
        token.write_text("{}")
        monkeypatch.setattr(gcal, "token_path", lambda: token)
        monkeypatch.setattr(gcal, "_credentials", lambda: object())
        result = gcal.create_event("x", "tomorrow morning")
        assert result["ok"] is False
        assert "RFC3339" in result["error"]


class TestBuiltinToolWiring:
    def test_an_unconfigured_integration_contributes_nothing(self, monkeypatch):
        from handoff.tools.builtins import builtin_tools

        monkeypatch.setattr(config, "NOTION_API_KEY", "")
        assert builtin_tools(["notion"]) == []

    def test_mock_mode_never_opens_a_credentialled_integration(self, monkeypatch):
        from handoff.tools.builtins import builtin_tools

        # A demo must not post into a real Notion or a real person's phone.
        monkeypatch.setattr(config, "NOTION_API_KEY", "ntn_test")
        monkeypatch.setattr(config, "USE_MOCK_TOOLS", True)
        assert builtin_tools(["notion"]) == []

    def test_a_configured_integration_yields_its_tools(self, monkeypatch):
        from handoff.tools.builtins import builtin_tools

        monkeypatch.setattr(config, "USE_MOCK_TOOLS", False)
        monkeypatch.setenv("NOTION_API_KEY", "ntn_test")
        assert len(builtin_tools(["notion"])) == 3

    def test_unknown_names_are_ignored(self):
        from handoff.tools.builtins import builtin_tools

        assert builtin_tools(["not_a_real_integration"]) == []


class TestRegistryAndCredentials:
    @pytest.mark.parametrize("name", ["notion", "telegram", "airtable", "gcal"])
    def test_each_integration_is_registered(self, name):
        from handoff.mcp.servers import MCP_SERVERS

        assert name in MCP_SERVERS
        assert MCP_SERVERS[name].actions

    @pytest.mark.parametrize("name", ["notion", "telegram", "airtable", "gcal"])
    def test_each_integration_is_connectable_from_the_ui(self, name):
        from handoff.platform.credentials import PROVIDERS

        assert name in PROVIDERS
        assert PROVIDERS[name].doctor_check in doctor.CHECKS

    def test_the_catalogue_renders_every_provider(self):
        from handoff.platform.credentials import PROVIDERS, catalogue

        rows = {row["provider"] for row in catalogue()}
        assert set(PROVIDERS) <= rows

    def test_the_registry_snapshot_includes_the_new_servers(self):
        from handoff.mcp.servers import registry_snapshot

        names = {row["name"] for row in registry_snapshot()}
        assert {"notion", "telegram", "airtable", "gcal"} <= names


class TestDoctorChecks:
    @pytest.mark.parametrize("name", ["notion", "telegram", "airtable", "gcal"])
    def test_an_unconfigured_integration_warns_and_says_how_to_fix_it(self, name, monkeypatch):
        for var in ("NOTION_API_KEY", "TELEGRAM_BOT_TOKEN", "AIRTABLE_API_KEY"):
            monkeypatch.setattr(config, var, "")
        monkeypatch.setattr(gcal, "configured", lambda: False)

        result = doctor.CHECKS[name]()
        # Never FAIL: nothing is broken, it simply is not connected yet.
        assert result["status"] == doctor.WARN
        assert result["fix"], "a warning without a fix is just anxiety"


class TestMultiAppWorkflow:
    def test_the_morning_run_is_a_valid_config(self):
        from handoff.tools.workflow_store import load_example_workflows

        workflows = {w.workflow_id: w for w in load_example_workflows()}
        assert "morning-ops-run" in workflows

    def test_the_morning_run_spans_more_than_three_apps(self):
        from handoff.tools.workflow_store import load_example_workflows

        workflow = next(
            w for w in load_example_workflows() if w.workflow_id == "morning-ops-run"
        )
        assert len(set(workflow.mcp_tools)) >= 4

    def test_every_integration_it_names_is_registered(self):
        from handoff.mcp.servers import MCP_SERVERS
        from handoff.tools.workflow_store import load_example_workflows

        for workflow in load_example_workflows():
            unknown = set(workflow.mcp_tools) - set(MCP_SERVERS)
            assert not unknown, f"{workflow.workflow_id} names unregistered {unknown}"
