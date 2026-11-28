"""Message-side features: id capture, recall, anti-recall, cursor pages,
voice/image extraction, and the no-deepcopy invariant.

Run from HumanTakeover: python -m pytest tests -q
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from langbot_plugin.api.definition.components.page import PageRequest
from langbot_plugin.api.entities.builtin.platform.message import (
    File,
    Image,
    MessageChain,
    Plain,
    Voice,
)

from test_storage import StorageHost, open_plugin, record

from main import HumanTakeover
from components.event_listener.default import _extract_content, _extract_message_id
from components.pages.console.console import ConsolePage


class MessageFeatureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logger_patch = patch("main.logger")
        logger_patch.start()
        self.addCleanup(logger_patch.stop)
        asyncio.get_running_loop().slow_callback_duration = 1
        self.host = StorageHost()
        self.plugin = await open_plugin(self.host)
        self.plugin.config = {}

    async def _send_with_id(self, message_id="m1"):
        sent = {"return": {"message_id": message_id}}

        async def fake_send(**kwargs):
            sent["kwargs"] = kwargs
            return sent["return"]

        self.plugin.send_message = fake_send
        return sent

    async def test_human_send_captures_message_id(self):
        await record(self.plugin)
        sent = await self._send_with_id("msg-123")
        ok, err = await self.plugin.human_send("group_1", text="hello")
        self.assertTrue(ok, err)
        self.assertEqual(sent["return"]["message_id"], "msg-123")
        entry = self.plugin.messages["group_1"][-1]
        self.assertEqual(entry["message_id"], "msg-123")
        self.assertEqual(entry["role"], "human")

    async def test_human_send_builds_voice_component_and_records_voice(self):
        await record(self.plugin)
        sent = await self._send_with_id("v1")
        ok, err = await self.plugin.human_send(
            "group_1", voice_base64="data:audio/ogg;base64,AAAA"
        )
        self.assertTrue(ok, err)
        chain = sent["kwargs"]["message_chain"]
        self.assertTrue(any(isinstance(c, Voice) for c in chain))
        entry = self.plugin.messages["group_1"][-1]
        self.assertEqual(entry["content_type"], "voice")
        self.assertEqual(entry["content"], "data:audio/ogg;base64,AAAA")
        # The preview is the localized marker, not the base64 payload.
        self.assertEqual(self.plugin.sessions["group_1"]["last_msg_preview"], "[语音]")

    async def test_human_send_quote_component(self):
        await record(self.plugin)
        sent = await self._send_with_id("q1")
        ok, err = await self.plugin.human_send(
            "group_1",
            text="follow up",
            quote_message_id="ref-9",
            quoted_content="original",
        )
        self.assertTrue(ok, err)
        from langbot_plugin.api.entities.builtin.platform.message import Quote

        chain = sent["kwargs"]["message_chain"]
        quote = next(c for c in chain if isinstance(c, Quote))
        self.assertEqual(quote.id, "ref-9")

    async def test_message_page_cursor_returns_older_window(self):
        for index in range(5):
            await record(self.plugin, content=str(index))
        bucket = self.plugin.messages["group_1"]
        self.assertEqual(len(bucket), 5)
        for index, entry in enumerate(bucket, start=1):
            entry["ts"] = float(index)
        page = self.plugin.message_page("group_1", limit=2)
        self.assertEqual([m["ts"] for m in page["messages"]], [4.0, 5.0])
        self.assertTrue(page["has_more"])
        self.assertEqual(page["next_cursor"], 4.0)

        older = self.plugin.message_page("group_1", limit=2, before_ts=4.0)
        self.assertEqual([m["ts"] for m in older["messages"]], [2.0, 3.0])
        self.assertTrue(older["has_more"])

        oldest = self.plugin.message_page("group_1", before_ts=2.0)
        self.assertEqual([m["ts"] for m in oldest["messages"]], [1.0])
        self.assertFalse(oldest["has_more"])

    async def test_recall_calls_standard_delete_and_marks_entry(self):
        await record(self.plugin)
        await self._send_with_id("m-recall")
        ok, err = await self.plugin.human_send("group_1", text="recall me")
        self.assertTrue(ok, err)
        entry = self.plugin.messages["group_1"][-1]
        self.assertEqual(entry["message_id"], "m-recall")

        calls = []

        async def fake_platform(bot_uuid, action, params=None):
            calls.append((bot_uuid, action, params))
            return {"ok": True}

        self.plugin.call_platform_api = fake_platform
        ok, err = await self.plugin.recall_message("group_1", "m-recall", actor="op")
        self.assertTrue(ok, err)
        self.assertEqual(
            calls,
            [
                (
                    "fixture-bot",
                    "delete_message",
                    {
                        "chat_type": "group",
                        "chat_id": "group_1",
                        "message_id": "m-recall",
                    },
                )
            ],
        )
        self.assertTrue(entry["recalled"])
        self.assertEqual(entry["recalled_by"], "op")
        self.assertEqual(self.plugin.sessions["group_1"]["recalled_messages"][0]["message_id"], "m-recall")

    async def test_recall_missing_session_fails(self):
        ok, err = await self.plugin.recall_message("nope", "x")
        self.assertFalse(ok)
        self.assertEqual(err, "session not found")

    async def test_anti_recall_marks_retained_message_without_new_session(self):
        await record(self.plugin)
        await self._send_with_id("anti-1")
        await self.plugin.human_send("group_1", text="deleted by peer")
        entry = self.plugin.messages["group_1"][-1]
        self.assertFalse(entry.get("recalled"))
        changed = self.plugin._mark_recalled(
            self.plugin._current_state(), "group_1", "anti-1", actor="u2"
        )
        self.assertTrue(changed)
        self.assertTrue(entry["recalled"])
        self.assertEqual(entry["recalled_by"], "u2")
        # Re-marking the same id is a no-op.
        self.assertFalse(
            self.plugin._mark_recalled(
                self.plugin._current_state(), "group_1", "anti-1", actor="u3"
            )
        )

    async def test_message_page_via_console_endpoint(self):
        for index in range(5):
            await record(self.plugin, content=str(index))
        bucket = self.plugin.messages["group_1"]
        for index, entry in enumerate(bucket, start=1):
            entry["ts"] = float(index)
        page = ConsolePage()
        page.plugin = self.plugin
        response = await page.handle_api(
            PageRequest(
                endpoint="/messages",
                method="GET",
                body={"session_key": "group_1", "limit": "2"},
            )
        )
        self.assertEqual([m["ts"] for m in response.data["messages"]], [4.0, 5.0])
        self.assertTrue(response.data["has_more"])
        self.assertEqual(response.data["next_cursor"], 4.0)

    async def test_record_message_whitelists_extra_fields(self):
        await record(self.plugin)
        await self.plugin.record_message(
            session_key="group_1",
            session_type="group",
            target_id="group_1",
            bot_uuid="fixture-bot",
            session_name="g",
            role="user",
            sender_id="u1",
            sender_name="u",
            content_type="text",
            content="hi",
            extra={
                "avatar": "http://example.com/a.png",
                "remark": "备注",
                "username": "@u",
                "source_im": "onebot",
                "platform": "nick",
                "evil": "must not persist",
                "nested": {"x": 1},
            },
        )
        entry = self.plugin.messages["group_1"][-1]
        self.assertEqual(entry["avatar"], "http://example.com/a.png")
        self.assertEqual(entry["remark"], "备注")
        self.assertEqual(entry["username"], "@u")
        self.assertEqual(entry["source_im"], "onebot")
        self.assertNotIn("evil", entry)
        self.assertNotIn("nested", entry)
        # Persisted JSON contains no arbitrary keys.
        raw = self.host.writes[-1][1]
        self.assertNotIn(b"must not persist", raw)
        self.assertNotIn(b"nested", raw)

    async def test_message_update_does_not_deepcopy_message_buckets(self):
        import main as main_module

        copied_types = []
        real_deepcopy = main_module.deepcopy

        def spy(obj, *args, **kwargs):
            copied_types.append(type(obj).__name__)
            return real_deepcopy(obj, *args, **kwargs)

        with patch.object(main_module, "deepcopy", spy):
            await record(self.plugin)
        self.assertNotIn("list", copied_types, "message buckets must not be deep copied")

    async def test_extract_message_id_prefers_event_then_platform_source(self):
        class _PlatformEvent:
            source_platform_object = {"id": "src-1"}

        class _Event:
            message_event = _PlatformEvent()

        self.assertEqual(_extract_message_id(_Event()), "src-1")

        class _Event2:
            message_id = "direct-1"

            class _PlatformEvent:  # type: ignore[no-redef]
                source_platform_object = {"id": "src-1"}

            message_event = _PlatformEvent()

        self.assertEqual(_extract_message_id(_Event2()), "direct-1")


class ImagePluginContractTests(unittest.IsolatedAsyncioTestCase):
    """Lock the reserved image-plugin (StickerHub) integration contract."""

    async def asyncSetUp(self):
        logger_patch = patch("main.logger")
        logger_patch.start()
        self.addCleanup(logger_patch.stop)
        asyncio.get_running_loop().slow_callback_duration = 1
        self.host = StorageHost()
        self.plugin = await open_plugin(self.host)
        self.plugin.config = {"image_plugin_upload_url": "http://host/plugins/stickerhub/add"}

    async def test_config_and_console_endpoint(self):
        self.assertEqual(
            self.plugin.image_plugin_upload_url(), "http://host/plugins/stickerhub/add"
        )
        page = ConsolePage()
        page.plugin = self.plugin
        response = await page.handle_api(
            PageRequest(endpoint="/image_plugin_upload", method="GET", body={})
        )
        self.assertTrue(response.data["enabled"])
        self.assertEqual(response.data["url"], "http://host/plugins/stickerhub/add")

    async def test_unset_url_reports_disabled(self):
        self.plugin.config = {}
        self.assertEqual(self.plugin.image_plugin_upload_url(), "")
        page = ConsolePage()
        page.plugin = self.plugin
        response = await page.handle_api(
            PageRequest(endpoint="/image_plugin_upload", method="GET", body={})
        )
        self.assertFalse(response.data["enabled"])
        self.assertEqual(response.data["url"], "")

    def test_console_script_uses_stickerhub_add_contract(self):
        from pathlib import Path

        html = (
            Path(__file__).resolve().parents[1]
            / "components"
            / "pages"
            / "console"
            / "index.html"
        ).read_text(encoding="utf-8")
        # The console must POST name/data_url and adopt the stable url field,
        # matching StickerHub's Page `/add` contract.
        self.assertIn("data_url", html)
        self.assertIn("image_base64", html)
        self.assertIn("data.url", html)


class ContentExtractionTests(unittest.TestCase):
    def test_text_preferred_over_image(self):
        chain = MessageChain([Plain(text="hello"), Image(base64="data:image/png;base64,AA")])
        self.assertEqual(_extract_content(chain), ("text", "hello"))

    def test_image_only(self):
        chain = MessageChain([Image(url="http://img/x.png")])
        self.assertEqual(_extract_content(chain), ("image", "http://img/x.png"))

    def test_voice_only(self):
        chain = MessageChain([Voice(base64="data:audio/ogg;base64,AAAA")])
        content_type, content = _extract_content(chain)
        self.assertEqual(content_type, "voice")
        self.assertEqual(content, "data:audio/ogg;base64,AAAA")

    def test_file_only(self):
        chain = MessageChain([File(name="doc.txt", base64="data:text/plain;base64,QQ==")])
        content_type, content = _extract_content(chain)
        self.assertEqual(content_type, "file")
        self.assertEqual(content, "[文件] doc.txt")

    def test_voice_fallback_marker(self):
        chain = MessageChain([Voice()])
        self.assertEqual(_extract_content(chain), ("voice", "[语音]"))


if __name__ == "__main__":
    unittest.main()
