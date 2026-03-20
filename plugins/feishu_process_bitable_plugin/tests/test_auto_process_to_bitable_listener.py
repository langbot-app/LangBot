from __future__ import annotations

import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

import langbot_plugin.api.entities.builtin.platform.message as platform_message

from components.event_listeners.auto_process_to_bitable import (
    AutoProcessToBitableListener,
    ParsedRecord,
    UpsertResult,
)


class DummyPlugin:
    def __init__(self, config: dict[str, object]):
        self._config = config

    def get_config(self) -> dict[str, object]:
        return self._config

    async def send_message(self, **kwargs) -> None:
        return None


class DummyEvent:
    model_fields = {"reply_message_chain": object()}

    def __init__(
        self,
        text: str,
        *,
        message_id: str,
        source_time: datetime.datetime,
        launcher_type: str = "person",
        message_event_time: datetime.datetime | None = None,
        query_variables: dict[str, object] | None = None,
    ):
        self.launcher_type = launcher_type
        self.launcher_id = "launcher-id"
        self.sender_id = "sender-id"
        self.query = SimpleNamespace(bot_uuid="bot-uuid")
        if query_variables is not None:
            self.query.variables = query_variables

        chain = platform_message.MessageChain(
            [
                platform_message.Source(id=message_id, time=source_time),
                platform_message.Plain(text=text),
            ]
        )
        self.message_chain = chain
        self.reply_message_chain: platform_message.MessageChain | None = None
        if message_event_time is not None:
            self.message_event = SimpleNamespace(time=message_event_time)


class DummyEventContext:
    def __init__(self, event: DummyEvent):
        self.event = event
        self.default_prevented = False
        self.postorder_prevented = False

    def prevent_default(self) -> None:
        self.default_prevented = True

    def prevent_postorder(self) -> None:
        self.postorder_prevented = True


class AutoProcessToBitableListenerTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _build_listener(config: dict[str, object] | None = None) -> AutoProcessToBitableListener:
        listener = AutoProcessToBitableListener()
        listener.plugin = DummyPlugin(
            {
                "reply_in_person": True,
                "reply_in_group": False,
                "reply_on_write": False,
                "reply_on_error": False,
                "prevent_default_on_match": True,
                "enable_recall_restore_previous": False,
                "time_zone": "Asia/Shanghai",
                "time_format": "%Y-%m-%d %H:%M:%S",
                **(config or {}),
            }
        )
        return listener

    @staticmethod
    def _build_record() -> ParsedRecord:
        return ParsedRecord(
            scenario="particle_size",
            line="A1",
            batch_id="DA2603-001",
            route_key="particle_size.A",
            fields={"D50": "1.23"},
        )

    async def test_resolve_message_time_prefers_message_event_time(self) -> None:
        listener = self._build_listener()
        source_time = datetime.datetime(2026, 3, 19, 7, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
        message_event_time = datetime.datetime(2026, 3, 20, 8, 45, tzinfo=ZoneInfo("Asia/Shanghai"))
        ctx = DummyEventContext(
            DummyEvent(
                "S18-FS-DA2603-001-A1-60min:1.23",
                message_id="msg-1",
                source_time=source_time,
                message_event_time=message_event_time,
            )
        )

        message_time = listener._resolve_message_time(ctx)

        self.assertEqual(message_time, "2026-03-20 08:45:00")

    async def test_resolve_message_time_falls_back_to_message_chain_source_time(self) -> None:
        listener = self._build_listener()
        source_time = datetime.datetime(2026, 3, 19, 23, 50, tzinfo=ZoneInfo("Asia/Shanghai"))
        ctx = DummyEventContext(
            DummyEvent(
                "DA2603-021批次结束出窑\nA2-1--06:23",
                message_id="msg-2",
                source_time=source_time,
            )
        )

        message_time = listener._resolve_message_time(ctx)

        self.assertEqual(message_time, "2026-03-19 23:50:00")

    async def test_duplicate_message_id_is_only_processed_once_without_query_variables(self) -> None:
        listener = self._build_listener()
        record = self._build_record()
        upsert_result = UpsertResult(
            ok=True,
            detail="rec-1",
            record_id="rec-1",
            operation="create",
            before_fields={},
            after_fields=dict(record.fields),
        )
        source_time = datetime.datetime(2026, 3, 19, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

        listener._extract_recall_meta = AsyncMock(return_value=None)  # type: ignore[method-assign]
        listener._parse_records_with_text_priority = Mock(return_value=[record])  # type: ignore[method-assign]
        listener._resolve_or_create_table_id = AsyncMock(return_value="tbl-process")  # type: ignore[method-assign]
        listener._ensure_table_fields = AsyncMock(return_value=(True, "", {}))  # type: ignore[method-assign]
        listener._upsert_record_to_bitable = AsyncMock(return_value=upsert_result)  # type: ignore[method-assign]
        listener._normalize_write_fields = lambda fields, field_types: dict(fields)  # type: ignore[method-assign]
        listener._build_upsert_match_fields = lambda fields: {"批次号": str(fields.get("批次号", ""))}  # type: ignore[method-assign]

        first_ctx = DummyEventContext(
            DummyEvent(
                "S18-FS-DA2603-001-A1-60min:1.23",
                message_id="msg-dup-1",
                source_time=source_time,
            )
        )
        second_ctx = DummyEventContext(
            DummyEvent(
                "S18-FS-DA2603-001-A1-60min:1.23",
                message_id="msg-dup-1",
                source_time=source_time,
            )
        )

        await listener._handle_normal_message(first_ctx)
        await listener._handle_normal_message(second_ctx)

        self.assertEqual(listener._upsert_record_to_bitable.await_count, 1)  # type: ignore[attr-defined]

    async def test_history_write_failure_blocks_successful_write_result(self) -> None:
        listener = self._build_listener(
            {
                "enable_recall_restore_previous": True,
                "reply_on_write": True,
                "reply_on_error": True,
            }
        )
        record = self._build_record()
        upsert_result = UpsertResult(
            ok=True,
            detail="rec-2",
            record_id="rec-2",
            operation="update",
            before_fields={"D50": "1.11"},
            after_fields=dict(record.fields),
        )
        source_time = datetime.datetime(2026, 3, 19, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        ctx = DummyEventContext(
            DummyEvent(
                "S18-FS-DA2603-001-A1-60min:1.23",
                message_id="msg-history-1",
                source_time=source_time,
                query_variables={},
            )
        )

        listener._extract_recall_meta = AsyncMock(return_value=None)  # type: ignore[method-assign]
        listener._parse_records_with_text_priority = Mock(return_value=[record])  # type: ignore[method-assign]
        listener._resolve_or_create_table_id = AsyncMock(return_value="tbl-process")  # type: ignore[method-assign]
        listener._ensure_table_fields = AsyncMock(return_value=(True, "", {}))  # type: ignore[method-assign]
        listener._upsert_record_to_bitable = AsyncMock(return_value=upsert_result)  # type: ignore[method-assign]
        listener._record_history_entry = AsyncMock(return_value=(False, "history write failed"))  # type: ignore[method-assign]
        listener._send_feedback = AsyncMock()  # type: ignore[method-assign]
        listener._normalize_write_fields = lambda fields, field_types: dict(fields)  # type: ignore[method-assign]
        listener._build_upsert_match_fields = lambda fields: {"批次号": str(fields.get("批次号", ""))}  # type: ignore[method-assign]

        await listener._handle_normal_message(ctx)

        self.assertEqual(listener._send_feedback.await_count, 1)  # type: ignore[attr-defined]
        self.assertTrue(listener._send_feedback.await_args.kwargs["is_error"])  # type: ignore[attr-defined]
        self.assertIn("history write failed", listener._send_feedback.await_args.args[1])  # type: ignore[attr-defined]
