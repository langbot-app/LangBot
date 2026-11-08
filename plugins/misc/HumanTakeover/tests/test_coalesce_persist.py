"""A coalesced stream increment must still reach storage.

Coalescing edits the last message in place, so the bucket length does not
change. The commit heuristic used to compare lengths only, which meant every
increment after the first was dropped on the floor.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from test_storage import StorageHost, open_plugin


class CoalescePersistTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        p = patch("main.logger")
        p.start()
        self.addCleanup(p.stop)
        self.host = StorageHost()
        self.plugin = await open_plugin(self.host)
        self.plugin.config = {}

    async def _ai(self, text, ts):
        with patch("main.time.time", return_value=ts):
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
                content=text,
            )

    async def test_increment_past_preview_cutoff_is_flushed(self):
        # last_msg_preview is capped at 50 chars, so once both the stored and the
        # incoming text exceed that, the preview stops changing and neither the
        # session metadata nor the bucket length differ — the increment would be
        # lost if the commit heuristic only looked at those.
        base = "x" * 60
        await self._ai(base, 2000.0)
        await self._ai(base + "TAIL-1", 2001.0)
        await self._ai(base + "TAIL-1-TAIL-2", 2002.0)
        await self.plugin.reconcile()
        self.assertEqual(
            self.plugin.messages["group_1"][-1]["content"], base + "TAIL-1-TAIL-2"
        )

    async def test_each_increment_is_flushed_to_storage(self):
        await self._ai("Hi", 1000.0)
        await self._ai("Hi there", 1001.0)
        await self._ai("Hi there friend", 1002.0)
        self.assertEqual(len(self.plugin.messages["group_1"]), 1)

        # force a genuine read-back from the host store
        await self.plugin.reconcile()
        self.assertEqual(
            self.plugin.messages["group_1"][-1]["content"], "Hi there friend"
        )


if __name__ == "__main__":
    unittest.main()
