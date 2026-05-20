from __future__ import annotations

import datetime
from pathlib import Path
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
        images: list[platform_message.Image] | None = None,
        message_event_time: datetime.datetime | None = None,
        query_variables: dict[str, object] | None = None,
    ):
        self.launcher_type = launcher_type
        self.launcher_id = "launcher-id"
        self.sender_id = "sender-id"
        self.query = SimpleNamespace(bot_uuid="bot-uuid")
        if query_variables is not None:
            self.query.variables = query_variables

        components: list[object] = [platform_message.Source(id=message_id, time=source_time)]
        if text:
            components.append(platform_message.Plain(text=text))
        components.extend(images or [])
        chain = platform_message.MessageChain(components)
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

    async def test_parse_particle_size_supports_c_line_batch_id(self) -> None:
        listener = self._build_listener()

        records = listener._parse_particle_size(
            "S20-CM-DC2604-001 D10:1.1 D50:2.2 D90:3.3",
            "2026-04-24 09:00:00",
        )

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.line, "C")
        self.assertEqual(record.batch_id, "S20-DC2604-001")
        self.assertEqual(record.route_key, "wet_process.C")
        self.assertEqual(record.fields["最后更新工序"], "粗磨工序")
        self.assertEqual(record.fields["粗磨D50"], 2.2)

    async def test_parse_feeding_supports_c_line_batch_id(self) -> None:
        listener = self._build_listener()

        records = listener._parse_feeding(
            "批次号：S20-DC2604-001\n磷酸铁需补：12.5kg\nBL总量：88.8kg",
            "2026-04-24 10:00:00",
        )

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.line, "C")
        self.assertEqual(record.batch_id, "S20-DC2604-001")
        self.assertEqual(record.route_key, "feeding.C")
        self.assertEqual(record.fields["磷酸铁需补(kg)"], 12.5)
        self.assertEqual(record.fields["BL总量(kg)"], 88.8)

    async def test_parse_product_supports_group_text_samples(self) -> None:
        listener = self._build_listener()

        records = listener._parse_product(
            "S20-CP-DA2605-101-A1\nB2下的料\n"
            "S18-CP-DA2605-105-A2\n\n"
            "S18-CP-DA2605-104-A1\n"
            "S18-CP-DB2605-102-B1\n铜锌颗粒、大颗粒\n全检已送检",
            "2026-05-20 14:29:00",
        )

        self.assertEqual(len(records), 4)
        self.assertEqual(records[0].scenario, "product")
        self.assertEqual(records[0].line, "A")
        self.assertEqual(records[0].route_key, "product.S20")
        self.assertEqual(records[0].batch_id, "S20-CP-DA2605-101-A1")
        self.assertEqual(records[0].fields["产线"], "A")
        self.assertEqual(records[0].fields["下料段位"], "B2")
        self.assertEqual(records[-1].route_key, "product.S18")
        self.assertEqual(records[-1].fields["关注项"], "铜锌颗粒、大颗粒")
        self.assertEqual(records[-1].fields["送检项目"], "全检")
        self.assertEqual(records[-1].fields["送检状态"], "已送检")

    async def test_parse_product_supports_html_post_text_and_legacy_batch(self) -> None:
        listener = self._build_listener()

        records = listener._parse_product(
            "<p>S18--DA2605-085-Cs-A1</p><p>A1下14包B1 下20包</p><p>全检已送</p>",
            "2026-05-20 06:39:00",
        )

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.batch_id, "S18-CP-DA2605-085-A1")
        self.assertEqual(record.route_key, "product.S18")
        self.assertEqual(record.fields["成品后缀"], "CS")
        self.assertEqual(record.fields["下料说明"], "A1下14包；B1下20包")
        self.assertEqual(record.fields["送检状态"], "已送检")

    async def test_parse_product_extracts_ocr_metrics_for_statistics(self) -> None:
        listener = self._build_listener()

        records = listener._parse_product(
            "S18-CP-DA2605-103-A2\n"
            "成品压实 2.384\n"
            "0.1C充电：160.2\n"
            "0.1C放电 156.8\n"
            "0.1C首效 9688\n"
            "3.2V平台效率 82.1\n"
            "Li+含量 316\n"
            "碳含量 1.22\n"
            "粉末电阻 34.5\n"
            "麦克比表 10.8",
            "2026-05-20 00:27:00",
        )

        self.assertEqual(len(records), 1)
        fields = records[0].fields
        self.assertEqual(records[0].route_key, "product.S18")
        self.assertEqual(fields["成品压实"], 2.384)
        self.assertEqual(fields["0.1C充电"], 160.2)
        self.assertEqual(fields["0.1C放电"], 156.8)
        self.assertEqual(fields["首效"], 96.88)
        self.assertEqual(fields["平台效率"], 82.1)
        self.assertEqual(fields["残碱(Li+)"], 316.0)
        self.assertEqual(fields["碳含量"], 1.22)
        self.assertEqual(fields["粉阻(粉末电阻)"], 34.5)
        self.assertEqual(fields["比表(麦克比表)"], 10.8)

    async def test_parse_product_supports_feishu_ocr_table_sample_without_segment(self) -> None:
        listener = self._build_listener()

        records = listener._parse_product(
            "A\nB\nE\n样品批号\nHp\n9.15\n2026.05.20\nS18-DA2605-085-CS",
            "2026-05-20 10:00:00",
        )

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.route_key, "product.S18")
        self.assertEqual(record.batch_id, "S18-CP-DA2605-085-CS")
        self.assertEqual(record.fields["样品批号"], "S18-DA2605-085-CS")
        self.assertEqual(record.fields["成品后缀"], "CS")
        self.assertEqual(record.fields["产线"], "A")
        self.assertEqual(record.fields["段位"], "")
        self.assertEqual(record.fields["pH"], 9.15)
        self.assertEqual(record.fields["检测日期"], "2026.05.20")

    async def test_parse_product_extracts_ocr_table_metrics_by_header_order(self) -> None:
        listener = self._build_listener()

        records = listener._parse_product(
            "样品批号\n"
            "成品压实\n"
            "0.1C充电\n"
            "0.1C放电\n"
            "首效\n"
            "平台效率\n"
            "残碱(Li+)\n"
            "碳含量\n"
            "粉阻\n"
            "比表\n"
            "Hp\n"
            "S18-DA2605-085-CS\n"
            "2.384\n"
            "160.2\n"
            "156.8\n"
            "9688\n"
            "82.1\n"
            "316\n"
            "1.22\n"
            "34.5\n"
            "10.8\n"
            "9.15\n"
            "2026.05.20",
            "2026-05-20 10:00:00",
        )

        self.assertEqual(len(records), 1)
        fields = records[0].fields
        self.assertEqual(fields["样品批号"], "S18-DA2605-085-CS")
        self.assertEqual(fields["成品压实"], 2.384)
        self.assertEqual(fields["0.1C充电"], 160.2)
        self.assertEqual(fields["0.1C放电"], 156.8)
        self.assertEqual(fields["首效"], 96.88)
        self.assertEqual(fields["平台效率"], 82.1)
        self.assertEqual(fields["残碱(Li+)"], 316.0)
        self.assertEqual(fields["碳含量"], 1.22)
        self.assertEqual(fields["粉阻(粉末电阻)"], 34.5)
        self.assertEqual(fields["比表(麦克比表)"], 10.8)
        self.assertEqual(fields["pH"], 9.15)
        self.assertEqual(fields["检测日期"], "2026.05.20")

    async def test_parse_records_with_text_priority_uses_ocr_for_product_images(self) -> None:
        listener = self._build_listener()

        records = listener._parse_records_with_text_priority(
            "",
            "S18-CP-DA2605-103-A2\n三倍水分，扣电已送检",
            "2026-05-20 00:27:00",
        )

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.scenario, "product")
        self.assertEqual(record.batch_id, "S18-CP-DA2605-103-A2")
        self.assertEqual(record.fields["检测倍率"], "三倍")
        self.assertEqual(record.fields["送检项目"], "水分、扣电")

    async def test_image_ocr_product_text_writes_product_record(self) -> None:
        listener = self._build_listener({"enable_ocr_for_images": True})
        source_time = datetime.datetime(2026, 5, 20, 14, 42, tzinfo=ZoneInfo("Asia/Shanghai"))
        image_path = Path(__file__)
        ctx = DummyEventContext(
            DummyEvent(
                "",
                message_id="msg-product-image",
                source_time=source_time,
                images=[platform_message.Image(path=str(image_path))],
            )
        )
        upsert_result = UpsertResult(
            ok=True,
            detail="rec-product",
            record_id="rec-product",
            operation="create",
            before_fields={},
            after_fields={},
        )

        listener._extract_recall_meta = AsyncMock(return_value=None)  # type: ignore[method-assign]
        listener._recognize_image_bytes = AsyncMock(  # type: ignore[method-assign]
            return_value="S20-CP-DA2605-100-A2\n全检已送检"
        )
        listener._resolve_or_create_table_id = AsyncMock(return_value="tbl-product")  # type: ignore[method-assign]
        listener._ensure_table_fields = AsyncMock(return_value=(True, "", {}))  # type: ignore[method-assign]
        listener._upsert_record_to_bitable = AsyncMock(return_value=upsert_result)  # type: ignore[method-assign]
        listener._normalize_write_fields = lambda fields, field_types: dict(fields)  # type: ignore[method-assign]
        listener._build_upsert_match_fields = lambda fields: {"批次号": str(fields.get("批次号", ""))}  # type: ignore[method-assign]

        await listener._handle_normal_message(ctx)

        listener._upsert_record_to_bitable.assert_awaited_once()  # type: ignore[attr-defined]
        args = listener._upsert_record_to_bitable.await_args.args  # type: ignore[attr-defined]
        self.assertEqual(args[0], "tbl-product")
        self.assertEqual(args[1]["业务类型"], "product")
        self.assertEqual(args[1]["路由"], "product.S20")
        self.assertEqual(args[1]["产线"], "A")
        self.assertEqual(args[1]["批次号"], "S20-CP-DA2605-100-A2")
        self.assertEqual(args[1]["OCR文本"], "S20-CP-DA2605-100-A2\n全检已送检")

    async def test_default_auto_create_fields_is_strict(self) -> None:
        listener = self._build_listener()
        listener._list_all_table_fields = AsyncMock(return_value={"批次号": 1})  # type: ignore[method-assign]

        ok, detail, field_types = await listener._ensure_table_fields(
            "tbl-process",
            {"批次号": "DA2603-001", "D50": 1.23},
        )

        self.assertFalse(ok)
        self.assertIn("missing fields", detail)
        self.assertEqual(field_types, {"批次号": 1})

    async def test_default_auto_create_table_by_route_is_disabled(self) -> None:
        listener = self._build_listener()
        listener._list_all_bitable_tables = AsyncMock(return_value=[])  # type: ignore[method-assign]
        listener._create_bitable_table = AsyncMock(return_value="tbl-created")  # type: ignore[method-assign]

        table_id = await listener._get_or_create_table_id_by_name("新表")

        self.assertEqual(table_id, "")
        listener._create_bitable_table.assert_not_called()  # type: ignore[attr-defined]

    async def test_find_existing_record_uses_server_search_first(self) -> None:
        listener = self._build_listener({"bitable_app_token": "app_token"})
        listener._get_tenant_access_token = AsyncMock(return_value="token")  # type: ignore[method-assign]
        listener._call_feishu_json_api = AsyncMock(  # type: ignore[method-assign]
            return_value={"items": [{"record_id": "rec-1", "fields": {"批次号": "DA2603-001"}}]}
        )

        record_id = await listener._find_existing_record_id("tbl-process", {"批次号": "DA2603-001"})

        self.assertEqual(record_id, "rec-1")
        listener._call_feishu_json_api.assert_awaited_once()  # type: ignore[attr-defined]
        args = listener._call_feishu_json_api.await_args.args  # type: ignore[attr-defined]
        kwargs = listener._call_feishu_json_api.await_args.kwargs  # type: ignore[attr-defined]
        self.assertEqual(args[0], "POST")
        self.assertIn("/records/search", args[1])
        self.assertEqual(kwargs["params"], {"page_size": 1})
