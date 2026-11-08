"""Streaming replies must not pile up one bubble per increment.

The platform re-pushes the *cumulative* response text while a reply streams.
Recording each push as a new message turned one answer into dozens of
ever-growing bubbles, which is what users saw. These tests pin the coalescing
rules so a real second reply is still kept separate.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from test_storage import StorageHost, open_plugin, record

from main import STREAM_COALESCE_WINDOW


class StreamingReplyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logger_patch = patch("main.logger")
        logger_patch.start()
        self.addCleanup(logger_patch.stop)
        self.host = StorageHost()
        self.plugin = await open_plugin(self.host)
        self.plugin.config = {}

    async def ai(self, content, ts=None):
        clock = ts if ts is not None else 1000.0
        with patch("main.time.time", return_value=clock):
            await self.plugin.record_message(
                session_key="group_1",
                session_type="group",
                target_id="group_1",
                bot_uuid="fixture-bot",
                session_name="group_1",
                role="ai",
                sender_id="",
                sender_name="AI",
                content_type="text",
                content=content,
            )

    async def test_increments_merge_into_single_message(self):
        await self.ai("Hi")
        await self.ai("Hi there")
        await self.ai("Hi there, friend")
        bucket = self.plugin.messages["group_1"]
        self.assertEqual(len(bucket), 1)
        self.assertEqual(bucket[0]["content"], "Hi there, friend")

    async def test_identical_resend_is_idempotent(self):
        await self.ai("same")
        await self.ai("same")
        self.assertEqual(len(self.plugin.messages["group_1"]), 1)

    async def test_shorter_repush_does_not_truncate(self):
        await self.ai("complete answer")
        await self.ai("complete")
        self.assertEqual(
            self.plugin.messages["group_1"][-1]["content"], "complete answer"
        )

    async def test_separate_replies_stay_separate_after_window(self):
        start = 1000.0
        await self.ai("first", ts=start)
        await self.ai("second", ts=start + STREAM_COALESCE_WINDOW + 1)
        self.assertEqual(len(self.plugin.messages["group_1"]), 2)

    async def test_unrelated_text_inside_window_is_its_own_message(self):
        await self.ai("aaa")
        await self.ai("zzz")
        self.assertEqual(len(self.plugin.messages["group_1"]), 2)

    async def test_user_message_breaks_the_run(self):
        await self.ai("Hi")
        await self.plugin.record_message(
            session_key="group_1", session_type="group", target_id="group_1",
            bot_uuid="fixture-bot", session_name="group_1", role="user",
            sender_id="1", sender_name="u", content_type="text", content="ok")
        await self.ai("Hi again")
        self.assertEqual(len(self.plugin.messages["group_1"]), 3)


class SendErrorTextTests(unittest.IsolatedAsyncioTestCase):
    """The operator must get a usable reason, not a bare SDK string."""

    async def asyncSetUp(self):
        logger_patch = patch("main.logger")
        logger_patch.start()
        self.addCleanup(logger_patch.stop)
        self.host = StorageHost()
        self.plugin = await open_plugin(self.host)
        self.plugin.config = {}

    async def test_missing_bot_is_explained(self):
        await record(self.plugin)

        async def boom(**kwargs):
            raise RuntimeError("ActionCallError: Bot is not available in this Workspace")

        self.plugin.send_message = boom
        ok, err = await self.plugin.human_send("group_1", text="hello")
        self.assertFalse(ok)
        self.assertIn("Bot", err)
        self.assertIn("Workspace", err)
        self.assertIn(bots_hint := "bots", err)
        self.assertTrue(bots_hint)

    async def test_proxy_bot_rejection_mentions_session_test(self):
        await record(self.plugin)

        async def boom(**kwargs):
            raise RuntimeError("ActionCallError: Bot is not available in this Workspace")

        self.plugin.send_message = boom
        ok, err = await self.plugin.human_send("group_1", text="hello")
        self.assertFalse(ok)
        self.assertIn("websocket-proxy-bot", err)

    async def test_unknown_error_still_returned_verbatim(self):
        await record(self.plugin)

        async def boom(**kwargs):
            raise RuntimeError("platform exploded")

        self.plugin.send_message = boom
        ok, err = await self.plugin.human_send("group_1", text="hello")
        self.assertFalse(ok)
        self.assertEqual(err, "platform exploded")


if __name__ == "__main__":
    unittest.main()
