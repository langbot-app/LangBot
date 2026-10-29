"""Real SDK stdio round trip; synthetic in-memory Host sink, not LangBot DB."""

import asyncio
import base64
import importlib.metadata
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from langbot_plugin.entities.io.actions.enums import (
    ActionType,
    CommonAction,
    PluginToRuntimeAction,
)
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.io.controllers.stdio.client import StdioClientController
from langbot_plugin.runtime.io.controllers.stdio.server import StdioServerController
from langbot_plugin.runtime.io.handler import Handler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import HumanTakeover


class ProbeAction(ActionType):
    RECORD = "human_storage_regression_probe"


async def child():
    async def connected(conn):
        handler = Handler(conn)

        @handler.action(CommonAction.PING)
        async def ping(data):
            return ActionResponse.success({"alive": True})

        @handler.action(ProbeAction.RECORD)
        async def probe(data):
            plugin = HumanTakeover()
            plugin.config = {}
            plugin.plugin_runtime_handler = handler
            # Shared placement loads state on demand; load before seeding caches.
            await plugin.load_state()
            for i in range(1200):
                key = f"group_fixture-{i}"
                plugin._ensure_session(key, "group", key, "fixture-bot", "fixture")
                plugin.messages[key] = [
                    {"role": "user", "content": "x" * 1024, "ts": 0} for _ in range(10)
                ]
            raw_total = len(json.dumps(plugin.messages).encode())
            params = {
                "session_key": "group_fixture-0",
                "session_type": "group",
                "target_id": "fixture-0",
                "bot_uuid": "fixture-bot",
                "session_name": "fixture",
                "role": "user",
                "sender_id": "1",
                "sender_name": "fixture",
                "content_type": "text",
            }
            await plugin.record_message(**params, content="new-message")
            expected = plugin.messages["group_fixture-0"][:]
            # Large but accepted record exercises a nontrivial response frame on readback.
            await plugin.record_message(**params, content="x" * (6 * 1024 * 1024))
            expected_large = plugin.messages["group_fixture-0"][:]
            rejected = False
            try:
                await plugin.record_message(**params, content="界" * (4 * 1024 * 1024))
            except ValueError as exc:
                rejected = "storage limit" in str(exc)
            memory_preserved = plugin.messages["group_fixture-0"] == expected_large
            # Force a real read-back from storage to prove the write landed.
            await plugin.reconcile()
            return ActionResponse.success(
                {
                    "aggregate_json_bytes": raw_total,
                    "small_history_messages": len(expected),
                    "readback_equal": plugin.messages["group_fixture-0"]
                    == expected_large,
                    "oversize_rejected": rejected,
                    "memory_preserved": memory_preserved,
                    "sdk": importlib.metadata.version("langbot-plugin"),
                }
            )

        await handler.run()

    await StdioServerController().run(connected)


class StdioStorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_large_aggregate_writes_readback_and_oversize_error_over_real_stdio(
        self,
    ):
        storage, writes = {}, []
        result = {}
        with tempfile.TemporaryDirectory() as home:
            controller = StdioClientController(
                sys.executable,
                [str(Path(__file__).resolve()), "child"],
                {
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "HOME": home,
                    "PYTHONUNBUFFERED": "1",
                },
                working_dir=home,
            )

            async def connected(conn):
                handler = Handler(conn)

                @handler.action(PluginToRuntimeAction.GET_PLUGIN_STORAGE_KEYS)
                async def keys(data):
                    return ActionResponse.success({"keys": list(storage)})

                @handler.action(PluginToRuntimeAction.SET_PLUGIN_STORAGE)
                async def put(data):
                    value = base64.b64decode(data["value_base64"])
                    storage[data["key"]] = value
                    writes.append((data["key"], len(value)))
                    return ActionResponse.success({})

                @handler.action(PluginToRuntimeAction.GET_PLUGIN_STORAGE)
                async def get(data):
                    return ActionResponse.success(
                        {
                            "value_base64": base64.b64encode(
                                storage[data["key"]]
                            ).decode(),
                        }
                    )

                task = asyncio.create_task(handler.run())
                try:
                    await handler.call_action(CommonAction.PING, {}, timeout=10)
                    result.update(
                        await handler.call_action(ProbeAction.RECORD, {}, timeout=30)
                    )
                    self.assertTrue(
                        (await handler.call_action(CommonAction.PING, {}, timeout=3))[
                            "alive"
                        ]
                    )
                finally:
                    await handler.close()
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

            await controller.run(connected)
        self.assertGreater(result["aggregate_json_bytes"], 12 * 1024 * 1024)
        self.assertTrue(result["readback_equal"])
        self.assertTrue(result["oversize_rejected"])
        self.assertTrue(result["memory_preserved"])
        self.assertEqual(len(writes), 3)  # schema marker + two session writes
        self.assertLess(writes[1][1], 32 * 1024)
        self.assertLess(writes[2][1], 8 * 1024 * 1024)
        self.assertNotIn("ht_messages", storage)
        self.assertNotIn("ht_sessions", storage)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "child":
        asyncio.run(child())
    else:
        unittest.main()
