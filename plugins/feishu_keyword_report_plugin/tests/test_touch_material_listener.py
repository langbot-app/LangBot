from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import langbot_plugin.api.entities.builtin.platform.message as platform_message

from components.event_listeners.keyword_bitable_report import KeywordBitableReportListener


class DummyPlugin:
    def __init__(self, config: dict[str, object]):
        self._config = config
        self.sent_messages: list[platform_message.MessageChain] = []

    def get_config(self) -> dict[str, object]:
        return self._config

    async def send_message(self, **kwargs) -> None:
        message_chain = kwargs.get("message_chain")
        if isinstance(message_chain, platform_message.MessageChain):
            self.sent_messages.append(message_chain)


class DummyEvent:
    model_fields = {"reply_message_chain": object()}

    def __init__(self, text: str, launcher_type: str = "group"):
        self.launcher_type = launcher_type
        self.launcher_id = "launcher-id"
        self.query = SimpleNamespace(bot_uuid="bot-uuid")
        self.message_chain = platform_message.MessageChain([platform_message.Plain(text=text)])
        self.reply_message_chain: platform_message.MessageChain | None = None


class DummyEventContext:
    def __init__(self, event: DummyEvent):
        self.event = event
        self.default_prevented = False
        self.postorder_prevented = False

    def prevent_default(self) -> None:
        self.default_prevented = True

    def prevent_postorder(self) -> None:
        self.postorder_prevented = True


class TouchMaterialListenerTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _build_listener() -> KeywordBitableReportListener:
        listener = KeywordBitableReportListener()
        listener.plugin = DummyPlugin(
            {
                "keyword_commands": "日报",
                "touch_material_commands": "摸料",
                "reply_in_group": True,
                "reply_in_person": True,
            }
        )
        return listener

    @staticmethod
    def _extract_reply_text(event: DummyEvent) -> str:
        if event.reply_message_chain and len(event.reply_message_chain) > 0:
            first = event.reply_message_chain[0]
            if isinstance(first, platform_message.Plain):
                return str(first.text)
        return ""

    @staticmethod
    def _extract_plain_texts(event: DummyEvent) -> list[str]:
        if not event.reply_message_chain:
            return []
        out: list[str] = []
        for item in event.reply_message_chain:
            if isinstance(item, platform_message.Plain):
                out.append(str(item.text))
        return out

    @staticmethod
    def _has_reply_image(event: DummyEvent) -> bool:
        if not event.reply_message_chain:
            return False
        return any(isinstance(item, platform_message.Image) for item in event.reply_message_chain)

    async def test_touch_command_has_higher_priority_than_report(self) -> None:
        listener = self._build_listener()
        listener._run_touch_material_report = AsyncMock(return_value="touch-ok")  # type: ignore[method-assign]
        listener._dispatch_report = AsyncMock(return_value={"text": "report-ok"})  # type: ignore[method-assign]

        ctx = DummyEventContext(DummyEvent("摸料 A2"))
        await listener._handle_command(ctx)

        self.assertTrue(ctx.default_prevented)
        self.assertTrue(ctx.postorder_prevented)
        listener._run_touch_material_report.assert_awaited_once_with(segment="A2")  # type: ignore[attr-defined]
        listener._dispatch_report.assert_not_called()  # type: ignore[attr-defined]
        self.assertEqual(self._extract_reply_text(ctx.event), "touch-ok")

    async def test_touch_command_accepts_configured_segment(self) -> None:
        listener = self._build_listener()
        listener.plugin = DummyPlugin(
            {
                "keyword_commands": "日报",
                "touch_material_commands": "摸料",
                "touch_material_segments": "A1,C1",
                "reply_in_group": True,
                "reply_in_person": True,
            }
        )
        listener._run_touch_material_report = AsyncMock(return_value="touch-c1")  # type: ignore[method-assign]

        ctx = DummyEventContext(DummyEvent("摸料 C1"))
        await listener._handle_command(ctx)

        listener._run_touch_material_report.assert_awaited_once_with(segment="C1")  # type: ignore[attr-defined]
        self.assertEqual(self._extract_reply_text(ctx.event), "touch-c1")

    async def test_report_command_keeps_original_flow(self) -> None:
        listener = self._build_listener()
        listener._run_touch_material_report = AsyncMock(return_value="touch-ok")  # type: ignore[method-assign]
        listener._dispatch_report = AsyncMock(  # type: ignore[method-assign]
            return_value={"text": "report-ok", "used_sheets": [], "source": "bitable"}
        )

        ctx = DummyEventContext(DummyEvent("日报"))
        await listener._handle_command(ctx)

        self.assertTrue(ctx.default_prevented)
        self.assertTrue(ctx.postorder_prevented)
        listener._run_touch_material_report.assert_not_called()  # type: ignore[attr-defined]
        listener._dispatch_report.assert_awaited_once()  # type: ignore[attr-defined]
        self.assertEqual(self._extract_reply_text(ctx.event), "report-ok")
        self.assertFalse(self._has_reply_image(ctx.event))

    async def test_report_command_reply_sheet_snapshots_before_text(self) -> None:
        listener = self._build_listener()
        listener._run_touch_material_report = AsyncMock(return_value="touch-ok")  # type: ignore[method-assign]
        listener._dispatch_report = AsyncMock(  # type: ignore[method-assign]
            return_value={"text": "report-ok", "used_sheets": ["S18-A线"], "source": "sheets"}
        )
        listener._build_sheet_snapshot_components = AsyncMock(  # type: ignore[method-assign]
            return_value=[
                platform_message.Image(base64="data:image/png;base64,ZmFrZQ=="),
            ]
        )

        ctx = DummyEventContext(DummyEvent("日报"))
        await listener._handle_command(ctx)

        self.assertTrue(ctx.default_prevented)
        self.assertTrue(ctx.postorder_prevented)
        listener._dispatch_report.assert_awaited_once()  # type: ignore[attr-defined]
        listener._build_sheet_snapshot_components.assert_awaited_once_with(["S18-A线"], strict=False)  # type: ignore[attr-defined]
        plain_texts = self._extract_plain_texts(ctx.event)
        self.assertEqual(plain_texts, ["report-ok"])
        self.assertTrue(self._has_reply_image(ctx.event))

    async def test_image_command_reply_image(self) -> None:
        listener = self._build_listener()
        listener._run_touch_material_report = AsyncMock(return_value="touch-ok")  # type: ignore[method-assign]
        listener._dispatch_report = AsyncMock(return_value={"text": "report-ok"})  # type: ignore[method-assign]
        listener._run_sheet_snapshot_reply = AsyncMock(  # type: ignore[method-assign]
            return_value=platform_message.MessageChain(
                [
                    platform_message.Image(base64="data:image/png;base64,ZmFrZQ=="),
                ]
            )
        )

        ctx = DummyEventContext(DummyEvent("图片 S18-A线"))
        await listener._handle_command(ctx)

        self.assertTrue(ctx.default_prevented)
        self.assertTrue(ctx.postorder_prevented)
        listener._run_touch_material_report.assert_not_called()  # type: ignore[attr-defined]
        listener._dispatch_report.assert_not_called()  # type: ignore[attr-defined]
        listener._run_sheet_snapshot_reply.assert_awaited_once_with(sheet_name="S18-A线")  # type: ignore[attr-defined]
        self.assertEqual(self._extract_plain_texts(ctx.event), [])
        self.assertTrue(self._has_reply_image(ctx.event))

    async def test_dispatch_report_bitable_mode_returns_payload(self) -> None:
        listener = self._build_listener()
        listener.plugin = DummyPlugin({"data_source_mode": "bitable"})
        listener._run_bitable_brief_report = AsyncMock(return_value="bitable-ok")  # type: ignore[method-assign]

        payload = await listener._dispatch_report(date_arg=None, command_sheets=[])

        self.assertEqual(
            payload,
            {
                "text": "bitable-ok",
                "used_sheets": [],
                "source": "bitable",
            },
        )
        listener._run_bitable_brief_report.assert_awaited_once()  # type: ignore[attr-defined]

    async def test_run_sheet_snapshot_reply_uses_shared_builder(self) -> None:
        listener = self._build_listener()
        expected_components = [platform_message.Image(base64="data:image/png;base64,ZmFrZQ==")]
        listener._build_sheet_snapshot_components = AsyncMock(return_value=expected_components)  # type: ignore[method-assign]

        reply_chain = await listener._run_sheet_snapshot_reply("S18-A线")

        listener._build_sheet_snapshot_components.assert_awaited_once_with(["S18-A线"], strict=True)  # type: ignore[attr-defined]
        self.assertEqual(len(reply_chain), 1)
        self.assertIs(reply_chain[0], expected_components[0])

    async def test_run_sheets_report_auto_discovers_new_line_sheets(self) -> None:
        listener = self._build_listener()
        listener.plugin = DummyPlugin(
            {
                "sheets_spreadsheet_token": "sp_token",
                "sheets_sheet_names": "S18-A线",
            }
        )
        listener._build_auth_headers = AsyncMock(return_value={"Authorization": "Bearer test"})  # type: ignore[method-assign]
        listener._sheets_source.list_sheet_titles = AsyncMock(  # type: ignore[method-assign]
            return_value=["S18-A线", "S006-A线", "S006-B线", "说明", "S18-A线成品数据源"]
        )
        listener._sheets_source.fetch_line_matrices = AsyncMock(  # type: ignore[method-assign]
            return_value=(
                {
                    "S18-A线": [["批次", "投料日期"], ["DA2603-001", "2026-03-03"]],
                    "S006-A线": [["批次", "投料日期"], ["DB2603-001", "2026-03-03"]],
                    "S006-B线": [["批次", "投料日期"], ["DB2603-002", "2026-03-03"]],
                },
                ["S18-A线", "S006-A线", "S006-B线", "说明", "S18-A线成品数据源"],
                [],
            )
        )

        with patch(
            "components.event_listeners.keyword_bitable_report.day_metrics.build_standard_report_from_matrices",
            return_value={
                "text": "report-ok",
                "line_errors": [],
                "used_sheets": ["S18-A线", "S006-A线", "S006-B线"],
            },
        ) as mock_build:
            payload = await listener._run_sheets_report(date_arg=None, command_sheets=[])

        listener._sheets_source.fetch_line_matrices.assert_awaited_once_with(  # type: ignore[attr-defined]
            spreadsheet_token="sp_token",
            headers={"Authorization": "Bearer test"},
            target_sheet_names=["S18-A线", "S006-A线", "S006-B线"],
            cell_range="A1:ZZ2000",
        )
        mock_build.assert_called_once()
        self.assertEqual(payload["used_sheets"], ["S18-A线", "S006-A线", "S006-B线"])

    async def test_touch_material_report_recipe_uses_auto_discovered_sheets(self) -> None:
        listener = self._build_listener()
        listener.plugin = DummyPlugin(
            {
                "bitable_app_token": "app_token",
                "batch_field": "批次号",
                "route_field": "路由",
                "message_time_field": "消息时间",
                "scan_limit": "1000",
                "sheets_spreadsheet_token": "sp_token",
                "sheets_sheet_names": "S006-B线",
            }
        )

        listener._build_auth_headers = AsyncMock(return_value={"Authorization": "Bearer test"})  # type: ignore[method-assign]
        listener._bitable_source.query_latest_kiln_batch_by_segment = AsyncMock(  # type: ignore[method-assign]
            return_value={"batch_raw": "DB2603-005", "batch_core": "DB2603-005", "slots": ["1"], "time_sort": 1.0}
        )
        listener._bitable_source.query_sintering_detail_by_batch_segment = AsyncMock(  # type: ignore[method-assign]
            return_value={"details": [], "avg": None}
        )
        listener._sheets_source.list_sheet_titles = AsyncMock(  # type: ignore[method-assign]
            return_value=["S006-A线", "S006-B线", "说明"]
        )
        listener._sheets_source.query_recipe_by_batch = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "铁磷比": "96.1",
                "锂量": "251.3",
                "酸量": "1.088",
                "钛量": "2.915",
                "糖量": "87.38",
                "peg量": "19.067",
                "窑炉温度": "813",
            }
        )

        await listener._run_touch_material_report("A2")

        listener._sheets_source.query_recipe_by_batch.assert_awaited_once()  # type: ignore[attr-defined]
        kwargs = listener._sheets_source.query_recipe_by_batch.await_args.kwargs  # type: ignore[attr-defined]
        self.assertEqual(kwargs["target_sheet_names"], ["S006-B线", "S006-A线"])
        self.assertEqual(kwargs["prefer_line"], "A")

    async def test_sheet_auto_discovery_uses_configured_patterns(self) -> None:
        listener = self._build_listener()
        listener.plugin = DummyPlugin(
            {
                "sheet_auto_discovery_patterns_json": '["S20-.+产线"]',
            }
        )
        listener._sheets_source.list_sheet_titles = AsyncMock(  # type: ignore[method-assign]
            return_value=["S20-C产线", "S18-A线", "说明"]
        )

        out = await listener._resolve_target_sheets({"Authorization": "Bearer test"}, "sp_token", [])

        self.assertEqual(out, ["S20-C产线"])

    async def test_sheet_snapshot_uses_configurable_row_settings(self) -> None:
        listener = self._build_listener()
        listener.plugin = DummyPlugin(
            {
                "sheets_spreadsheet_token": "sp_token",
                "sheets_range": "A1:ZZ2000",
                "sheet_snapshot_header_rows": "5",
                "sheet_snapshot_tail_nonempty_rows": "12",
            }
        )
        listener._build_auth_headers = AsyncMock(return_value={"Authorization": "Bearer test"})  # type: ignore[method-assign]
        listener._sheets_source.fetch_line_matrices = AsyncMock(  # type: ignore[method-assign]
            return_value=(
                {
                    "S18-A线": [
                        ["header-1", "header-2"],
                        ["desc-1", "desc-2"],
                        ["spec-1", "spec-2"],
                        ["row-1", "value-1"],
                    ]
                },
                ["S18-A线"],
                [],
            )
        )

        with patch(
            "components.event_listeners.keyword_bitable_report.render_sheet_snapshot",
            return_value=SimpleNamespace(data_url="data:image/png;base64,ZmFrZQ=="),
        ) as mock_render:
            components = await listener._build_sheet_snapshot_components(["S18-A线"], strict=True)

        self.assertEqual(len(components), 1)
        self.assertIsInstance(components[0], platform_message.Image)
        mock_render.assert_called_once_with(
            sheet_title="S18-A线",
            values=[
                ["header-1", "header-2"],
                ["desc-1", "desc-2"],
                ["spec-1", "spec-2"],
                ["row-1", "value-1"],
            ],
            header_rows=5,
            tail_nonempty_rows=12,
        )

    async def test_touch_invalid_segment_reply_usage(self) -> None:
        listener = self._build_listener()
        listener._run_touch_material_report = AsyncMock(return_value="touch-ok")  # type: ignore[method-assign]

        ctx = DummyEventContext(DummyEvent("摸料 A3"))
        await listener._handle_command(ctx)

        self.assertTrue(ctx.default_prevented)
        self.assertIn("摸料参数无效", self._extract_reply_text(ctx.event))
        listener._run_touch_material_report.assert_not_called()  # type: ignore[attr-defined]

    async def test_image_without_sheet_name_reply_usage(self) -> None:
        listener = self._build_listener()
        ctx = DummyEventContext(DummyEvent("图片"))

        await listener._handle_command(ctx)

        self.assertTrue(ctx.default_prevented)
        self.assertIn("图片参数无效", self._extract_reply_text(ctx.event))

    async def test_touch_material_report_format(self) -> None:
        listener = self._build_listener()
        listener.plugin = DummyPlugin(
            {
                "bitable_app_token": "app_token",
                "batch_field": "批次号",
                "route_field": "路由",
                "message_time_field": "消息时间",
                "scan_limit": "1000",
                "sheets_spreadsheet_token": "sp_token",
                "sheets_range": "A1:ZZ2000",
            }
        )

        listener._build_auth_headers = AsyncMock(return_value={"Authorization": "Bearer test"})  # type: ignore[method-assign]
        listener._bitable_source.query_latest_kiln_batch_by_segment = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "batch_raw": "DA2603-005",
                "batch_core": "DA2603-005",
                "slots": ["1", "2", "3"],
                "time_sort": 1.0,
            }
        )
        listener._bitable_source.query_sintering_detail_by_batch_segment = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "details": [
                    "S18-SC-DA2603-005-A2-1-60min：2.345",
                    "S18-SC-DA2603-005-A2-2-60min：2.337",
                    "S18-SC-DA2603-005-A2-3-60min：2.311",
                ],
                "avg": 2.331,
            }
        )
        listener._sheets_source.list_sheet_titles = AsyncMock(return_value=["S18-A线", "S18-B线"])  # type: ignore[method-assign]
        listener._sheets_source.query_recipe_by_batch = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "铁磷比": "97.4",
                "锂量": "253.125",
                "酸量": "3.2",
                "钛量": "40",
                "糖量": "83",
                "peg量": "80",
                "窑炉温度": "778.5",
            }
        )

        text = await listener._run_touch_material_report("A2")
        self.assertIn("DA2603-005（97.4+253.125+3.2+40+83+80）A2-1/2/3-778.5", text)
        self.assertIn("烧结压实", text)
        self.assertIn("A2-1：2.345", text)
        self.assertIn("A2-2：2.337", text)
        self.assertNotIn("S18-SC-DA2603-005-A2-1-60min", text)

    async def test_touch_material_report_explains_missing_steps(self) -> None:
        listener = self._build_listener()
        listener.plugin = DummyPlugin(
            {
                "bitable_app_token": "app_token",
                "batch_field": "批次号",
                "route_field": "路由",
                "message_time_field": "消息时间",
                "scan_limit": "1000",
                "sheets_spreadsheet_token": "sp_token",
            }
        )
        listener._build_auth_headers = AsyncMock(return_value={"Authorization": "Bearer test"})  # type: ignore[method-assign]
        listener._bitable_source.query_latest_kiln_batch_by_segment = AsyncMock(  # type: ignore[method-assign]
            return_value={"batch_raw": "DA2603-005", "batch_core": "DA2603-005", "slots": ["1"], "time_sort": 1.0}
        )
        listener._bitable_source.query_sintering_detail_by_batch_segment = AsyncMock(  # type: ignore[method-assign]
            return_value={"details": [], "avg": None}
        )
        listener._sheets_source.list_sheet_titles = AsyncMock(return_value=["S18-A线"])  # type: ignore[method-assign]
        listener._sheets_source.query_recipe_by_batch = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "铁磷比": "--",
                "锂量": "--",
                "酸量": "--",
                "钛量": "--",
                "糖量": "--",
                "peg量": "--",
                "窑炉温度": "--",
            }
        )

        text = await listener._run_touch_material_report("A2")

        self.assertIn("缺少烧结压实数据", text)
        self.assertIn("配方数据", text)


if __name__ == "__main__":
    unittest.main()
