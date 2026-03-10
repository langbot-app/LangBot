from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

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
        self.assertIn("压实", text)
        self.assertIn("S18-SC-DA2603-005-A2-1-60min：2.345", text)


if __name__ == "__main__":
    unittest.main()
