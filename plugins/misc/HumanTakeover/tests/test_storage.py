"""Real plugin/SDK API + synthetic Host KV tests (not a live LangBot DB).
Run from HumanTakeover: ../.venv/bin/python -m unittest discover -s tests -v
"""

import asyncio
import base64
import copy
import json
import unittest
from unittest.mock import patch

from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from main import HumanTakeover


class StorageHost:
    def __init__(self):
        self.data = {}
        self.writes = []
        self.reads = []
        self.failure = None
        self.write_started = None
        self.release_write = None

    async def call_action(self, action, data):
        key = data.get("key")
        if self.failure and self.failure(action, key):
            raise OSError("fixture storage unavailable")
        if action == Action.GET_PLUGIN_STORAGE_KEYS:
            return {"keys": list(self.data)}
        if action == Action.GET_PLUGIN_STORAGE:
            self.reads.append(key)
            return {"value_base64": base64.b64encode(self.data[key]).decode()}
        if action == Action.SET_PLUGIN_STORAGE:
            if len(json.dumps(data).encode()) + 1024 > 16 * 1024 * 1024:
                raise ValueError("fixture 16 MiB encoded frame limit")
            value = base64.b64decode(data["value_base64"])
            self.writes.append((key, value))
            if self.write_started is not None:
                started, release = self.write_started, self.release_write
                self.write_started = None
                started.set()
                await release.wait()
            await asyncio.sleep(0)
            self.data[key] = value
            return {}
        if action == Action.DELETE_PLUGIN_STORAGE:
            del self.data[key]
            return {}
        raise AssertionError(action)


class DetachedHost(StorageHost):
    """The host commit outlives cancellation/loss of the RPC waiter."""

    def __init__(self):
        super().__init__()
        self.pause_action = None
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.remote = None
        self.error = None

    async def call_action(self, action, data):
        if action != self.pause_action:
            return await super().call_action(action, data)
        self.pause_action = None

        async def commit():
            self.started.set()
            await self.release.wait()
            return await super(DetachedHost, self).call_action(action, data)

        self.remote = asyncio.create_task(commit())
        await self.started.wait()
        if self.error:
            raise self.error("remote outcome unknown")
        return await asyncio.shield(self.remote)


class PausableHost(StorageHost):
    """Holds one chosen action in flight, then fails it after the pause.

    Unlike ``DetachedHost`` the caller stays blocked until the test releases it,
    so another caller can be queued behind the installation lock first.
    """

    def __init__(self):
        super().__init__()
        self.pause_action = None
        self.paused = asyncio.Event()
        self.release = asyncio.Event()
        self.pause_error = None

    async def call_action(self, action, data):
        if action != self.pause_action:
            return await super().call_action(action, data)
        self.pause_action = None
        self.paused.set()
        await self.release.wait()
        if self.pause_error is not None:
            raise self.pause_error("remote outcome unknown")
        return await super().call_action(action, data)


async def open_plugin(host):
    plugin = HumanTakeover()
    plugin.config = {}
    plugin.plugin_runtime_handler = host
    await plugin.initialize()
    # Shared placement loads tenant state on demand, per invocation.
    await plugin.load_state()
    return plugin


async def record(plugin, key="group_1", content="hello"):
    await plugin.record_message(
        session_key=key,
        session_type="group",
        target_id=key,
        bot_uuid="fixture-bot",
        session_name=key,
        role="user",
        sender_id="1",
        sender_name="测试",
        content_type="text",
        content=content,
    )


def seed_legacy(host, count=2, content="历史消息"):
    sessions = {
        f"group_{i}": {
            "session_key": f"group_{i}",
            "name": f"Group {i}",
            "takeover": {"active": False},
            "custom": {"keep": True},
        }
        for i in range(count)
    }
    messages = {
        key: [{"role": "user", "content": content, "ts": 0}] for key in sessions
    }
    messages["person_orphan"] = [{"content": "do not discard"}]
    host.data["ht_sessions"] = json.dumps(sessions, ensure_ascii=False).encode()
    host.data["ht_messages"] = json.dumps(messages, ensure_ascii=False).encode()
    return sessions, messages


class StorageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Expected failure-injection logs are asserted via exceptions, not test stderr.
        logger_patch = patch("main.logger")
        logger_patch.start()
        self.addCleanup(logger_patch.stop)
        asyncio.get_running_loop().slow_callback_duration = 1
        self.host = StorageHost()
        self.plugin = await open_plugin(self.host)
        self.host.writes.clear()

    async def test_legacy_migration_preserves_exact_history_and_skips_legacy_on_restart(
        self,
    ):
        host = StorageHost()
        sessions, messages = seed_legacy(host)
        plugin = await open_plugin(host)
        self.assertEqual((plugin.sessions, plugin.messages), (sessions, messages))
        self.assertTrue(host.writes, "legacy data must migrate before normal writes")
        host.reads.clear()
        restarted = await open_plugin(host)
        self.assertEqual((restarted.sessions, restarted.messages), (sessions, messages))
        self.assertNotIn("ht_messages", host.reads)
        self.assertNotIn("ht_sessions", host.reads)

    async def test_update_writes_one_session_not_global_history(self):
        await record(self.plugin, "group_1")
        await record(self.plugin, "group_2", "unrelated")
        before = dict(self.host.data)
        self.host.writes.clear()
        await record(self.plugin, "group_1", "new")
        self.assertEqual(len(self.host.writes), 1)
        key, value = self.host.writes[0]
        self.assertNotIn(key, {"ht_messages", "ht_sessions"})
        self.assertNotIn(b"unrelated", value)
        self.assertEqual(sum(before.get(k) != v for k, v in self.host.data.items()), 1)
        restarted = await open_plugin(self.host)
        self.assertEqual(restarted.messages, self.plugin.messages)
        self.assertEqual(restarted.sessions, self.plugin.sessions)

    async def test_aggregate_history_above_frame_limit_can_record(self):
        for i in range(1200):
            key = f"group_{i}"
            self.plugin._ensure_session(key, "group", key, "fixture-bot", key)
            self.plugin.messages[key] = [{"content": "x" * 1024} for _ in range(11)]
        await record(self.plugin, "group_0", "persist-me")
        restarted = await open_plugin(self.host)
        self.assertIn(
            "group_0", restarted.messages, "successful record must survive restart"
        )
        self.assertEqual(restarted.messages["group_0"], self.plugin.messages["group_0"])
        self.assertEqual(len(self.host.writes), 1)
        self.assertLess(len(self.host.writes[0][1]), 32 * 1024)

    async def test_concurrent_same_session_updates_cannot_commit_out_of_order(self):
        await record(self.plugin)
        self.host.write_started = started = asyncio.Event()
        self.host.release_write = release = asyncio.Event()
        first = asyncio.create_task(record(self.plugin, content="first"))
        await started.wait()
        second = asyncio.create_task(record(self.plugin, content="second"))
        await asyncio.sleep(0.01)
        release.set()
        await asyncio.gather(first, second)
        restarted = await open_plugin(self.host)
        self.assertEqual(restarted.messages, self.plugin.messages)
        self.assertEqual(restarted.sessions, self.plugin.sessions)

    async def test_concurrent_sessions_and_metadata_read_back(self):
        await asyncio.gather(*(record(self.plugin, f"group_{i}") for i in range(10)))
        await asyncio.gather(
            self.plugin.set_takeover("group_1", True),
            self.plugin.mark_unread("group_1", "help"),
            self.plugin.touch_human_response("group_2"),
        )
        restarted = await open_plugin(self.host)
        self.assertEqual(restarted.sessions, self.plugin.sessions)
        self.assertEqual(restarted.messages, self.plugin.messages)

    async def test_write_failure_raises_and_rolls_back_memory(self):
        await record(self.plugin)
        before = copy.deepcopy((self.plugin.sessions, self.plugin.messages))
        self.host.failure = lambda action, key: action == Action.SET_PLUGIN_STORAGE
        with self.assertRaisesRegex(OSError, "storage unavailable"):
            await record(self.plugin, content="not saved")
        self.assertEqual((self.plugin.sessions, self.plugin.messages), before)
        self.host.failure = None
        # This fixture proves no request remains in flight; production must reconcile.
        await self.plugin.reconcile()
        await record(self.plugin, content="retry")
        restarted = await open_plugin(self.host)
        self.assertEqual(restarted.messages, self.plugin.messages)

    async def test_failed_new_session_is_not_left_in_memory(self):
        self.host.failure = lambda action, key: action == Action.SET_PLUGIN_STORAGE
        with self.assertRaises(OSError):
            await record(self.plugin)
        self.assertEqual(self.plugin.sessions, {})
        self.assertEqual(self.plugin.messages, {})

    async def test_metadata_failure_does_not_report_success(self):
        await record(self.plugin)
        before = copy.deepcopy(self.plugin.sessions)
        self.host.failure = lambda action, key: action == Action.SET_PLUGIN_STORAGE
        with self.assertRaises(OSError):
            await self.plugin.set_takeover("group_1", True)
        self.assertEqual(self.plugin.sessions, before)

    async def test_key_listing_failure_prevents_initialization(self):
        self.host.failure = lambda action, key: action == Action.GET_PLUGIN_STORAGE_KEYS
        with self.assertRaises(OSError):
            await open_plugin(self.host)

    async def test_legacy_read_failure_does_not_initialize_empty(self):
        host = StorageHost()
        seed_legacy(host)
        host.failure = lambda action, key: action == Action.GET_PLUGIN_STORAGE
        with self.assertRaises(OSError):
            await open_plugin(host)
        self.assertFalse(host.writes)

    async def test_corrupt_legacy_data_is_not_overwritten(self):
        host = StorageHost()
        seed_legacy(host)
        host.data["ht_messages"] = b"invalid json"
        with self.assertRaises(ValueError):
            await open_plugin(host)
        self.assertFalse(host.writes)

    async def test_interrupted_migration_can_retry_without_losing_history(self):
        host = StorageHost()
        expected = seed_legacy(host)
        original = dict(host.data)
        host.failure = lambda action, key: (
            action == Action.SET_PLUGIN_STORAGE and len(host.writes) == 1
        )
        with self.assertRaises(OSError):
            await open_plugin(host)
        for key, value in original.items():
            self.assertEqual(host.data[key], value)
        host.failure = None
        plugin = await open_plugin(host)
        self.assertEqual((plugin.sessions, plugin.messages), expected)
        restarted = await open_plugin(host)
        self.assertEqual((restarted.sessions, restarted.messages), expected)

    async def test_large_individual_session_rejected_without_truncating_history(self):
        await record(self.plugin, content="previous history")
        before = copy.deepcopy((self.plugin.sessions, self.plugin.messages))
        stored = dict(self.host.data)
        writes = len(self.host.writes)
        with self.assertRaisesRegex(ValueError, "session.*limit"):
            await record(self.plugin, content="界" * (4 * 1024 * 1024))
        self.assertEqual((self.plugin.sessions, self.plugin.messages), before)
        self.assertEqual(self.host.data, stored)
        self.assertEqual(len(self.host.writes), writes)

    async def test_oversized_legacy_session_fails_without_discarding_backup(self):
        host = StorageHost()
        seed_legacy(host, count=1, content="x" * (9 * 1024 * 1024))
        original = dict(host.data)
        with self.assertRaisesRegex(ValueError, "session.*limit"):
            await open_plugin(host)
        for key, value in original.items():
            self.assertEqual(host.data[key], value)

    async def test_clear_removes_legacy_and_new_data_without_resurrection(self):
        host = StorageHost()
        seed_legacy(host)
        plugin = await open_plugin(host)
        await record(plugin, "group_new")
        host.data["unrelated"] = b"keep"
        await plugin.clear_all()
        restarted = await open_plugin(host)
        self.assertEqual((restarted.sessions, restarted.messages), ({}, {}))
        self.assertEqual(host.data["unrelated"], b"keep")
        self.assertNotIn("ht_messages", host.data)
        await record(restarted, content="after clear")
        self.assertEqual((await open_plugin(host)).messages, restarted.messages)

    async def test_clear_failure_is_surfaced_and_retryable(self):
        await record(self.plugin)
        self.host.failure = lambda action, key: (
            action in {Action.DELETE_PLUGIN_STORAGE, Action.SET_PLUGIN_STORAGE}
        )
        with self.assertRaises(OSError):
            await self.plugin.clear_all()
        self.host.failure = None
        await self.plugin.reconcile()
        await self.plugin.clear_all()
        self.assertEqual((await open_plugin(self.host)).messages, {})

    async def test_null_legacy_snapshots_remain_compatible(self):
        host = StorageHost()
        host.data.update(ht_sessions=b"null", ht_messages=b"null")
        plugin = await open_plugin(host)
        self.assertEqual((plugin.sessions, plugin.messages), ({}, {}))
        await record(plugin)
        self.assertEqual((await open_plugin(host)).messages, plugin.messages)

    async def test_invalid_legacy_bucket_prevents_migration(self):
        for value in (None, "not a list", ["not a message"]):
            with self.subTest(value=value):
                host = StorageHost()
                seed_legacy(host)
                host.data["ht_messages"] = json.dumps({"group_0": value}).encode()
                with self.assertRaisesRegex(ValueError, "Invalid.*storage"):
                    await open_plugin(host)
                self.assertFalse(host.writes)

    async def test_invalid_session_record_is_not_loaded(self):
        await record(self.plugin)
        key, raw = self.host.writes[-1]
        data = json.loads(raw)
        data["messages"] = "not a list"
        self.host.data[key] = json.dumps(data).encode()
        with self.assertRaisesRegex(ValueError, "Invalid.*storage"):
            await open_plugin(self.host)

    async def test_sent_message_storage_failure_warns_against_resending(self):
        await record(self.plugin)
        sent = []

        async def send_message(**kwargs):
            sent.append(kwargs)

        self.plugin.send_message = send_message
        self.host.failure = lambda action, key: action == Action.SET_PLUGIN_STORAGE
        try:
            ok, error = await self.plugin.human_send("group_1", text="manual response")
        except OSError:
            self.fail(
                "Post-delivery storage failure must say the message was already sent"
            )
        self.assertFalse(ok)
        self.assertIn("sent", error)
        self.assertIn("storage", error)
        self.assertIn("not resend", error)
        self.assertEqual(len(sent), 1)

    async def test_existing_300_message_retention_is_unchanged(self):
        for i in range(301):
            await record(self.plugin, content=str(i))
        self.assertEqual(len(self.plugin.messages["group_1"]), 300)
        self.assertEqual(self.plugin.messages["group_1"][0]["content"], "1")
        self.assertEqual((await open_plugin(self.host)).messages, self.plugin.messages)

    async def test_migration_does_not_apply_retention_to_existing_history(self):
        host = StorageHost()
        sessions, messages = seed_legacy(host)
        messages["group_0"] = [{"content": str(i)} for i in range(400)]
        host.data["ht_messages"] = json.dumps(messages).encode()
        plugin = await open_plugin(host)
        self.assertEqual((plugin.sessions, plugin.messages), (sessions, messages))
        self.assertEqual((await open_plugin(host)).messages, messages)

    async def test_clear_waits_for_inflight_record(self):
        await record(self.plugin)
        self.host.write_started = started = asyncio.Event()
        self.host.release_write = release = asyncio.Event()
        writing = asyncio.create_task(record(self.plugin, content="in flight"))
        await started.wait()
        clearing = asyncio.create_task(self.plugin.clear_all())
        await asyncio.sleep(0.01)
        self.assertFalse(clearing.done())
        release.set()
        await asyncio.gather(writing, clearing)
        self.assertEqual((await open_plugin(self.host)).messages, {})

    async def test_cancelled_write_waits_for_remote_commit(self):
        for clear in (False, True):
            with self.subTest(clear=clear):
                host = DetachedHost()
                plugin = await open_plugin(host)
                await record(plugin, content="baseline")
                host.pause_action = Action.SET_PLUGIN_STORAGE
                writing = asyncio.create_task(record(plugin, content="cancelled"))
                await host.started.wait()
                writing.cancel()
                await asyncio.sleep(0.01)
                writing.cancel()  # Repeated cancellation must not release the lock.
                following = asyncio.create_task(
                    plugin.clear_all() if clear else record(plugin, content="next")
                )
                try:
                    await asyncio.sleep(0.01)
                    self.assertFalse(
                        following.done(), "late commit must stay serialized"
                    )
                    self.assertFalse(writing.done())
                finally:
                    host.release.set()
                    await asyncio.gather(writing, following, return_exceptions=True)
                    await host.remote
                self.assertTrue(writing.cancelled())
                following.result()
                restarted = await open_plugin(host)
                self.assertEqual(restarted.messages, plugin.messages)
                if clear:
                    self.assertEqual(restarted.messages, {})
                else:
                    self.assertEqual(
                        [m["content"] for m in restarted.messages["group_1"]],
                        ["baseline", "cancelled", "next"],
                    )

    async def test_cancelled_clear_waits_for_remote_delete(self):
        host = DetachedHost()
        plugin = await open_plugin(host)
        await record(plugin)
        host.pause_action = Action.DELETE_PLUGIN_STORAGE
        clearing = asyncio.create_task(plugin.clear_all())
        await host.started.wait()
        clearing.cancel()
        await asyncio.sleep(0.01)
        clearing.cancel()
        following = asyncio.create_task(record(plugin, content="next"))
        try:
            await asyncio.sleep(0.01)
            self.assertFalse(following.done())
        finally:
            host.release.set()
            await asyncio.gather(clearing, following, return_exceptions=True)
            await host.remote
        self.assertTrue(clearing.cancelled())
        following.result()
        self.assertEqual((await open_plugin(host)).messages, plugin.messages)
        self.assertEqual(len(plugin.messages["group_1"]), 1)

    async def test_cancelled_migration_finishes_before_reinitialize(self):
        host = DetachedHost()
        expected = seed_legacy(host)
        host.pause_action = Action.SET_PLUGIN_STORAGE
        plugin = HumanTakeover()
        plugin.config = {}
        plugin.plugin_runtime_handler = host
        loading = asyncio.create_task(plugin.load_state())
        await host.started.wait()
        loading.cancel()
        await asyncio.sleep(0.01)
        loading.cancel()
        following = asyncio.create_task(plugin.load_state())
        try:
            await asyncio.sleep(0.01)
            self.assertFalse(following.done())
        finally:
            host.release.set()
            await asyncio.gather(loading, following, return_exceptions=True)
            await host.remote
        self.assertTrue(loading.cancelled())
        following.result()
        self.assertEqual((plugin.sessions, plugin.messages), expected)

    async def test_ambiguous_mutations_fence_until_explicit_reconciliation(self):
        for error in (TimeoutError, ConnectionError):
            for operation in ("record", "clear", "migration"):
                with self.subTest(error=error, operation=operation):
                    host = DetachedHost()
                    plugin = await open_plugin(host)
                    await record(plugin)
                    if operation == "migration":
                        host.data.pop("ht_storage_schema")
                        seed_legacy(host)
                    host.pause_action = (
                        Action.DELETE_PLUGIN_STORAGE
                        if operation == "clear"
                        else Action.SET_PLUGIN_STORAGE
                    )
                    host.error = error
                    try:
                        with self.assertRaises(error):
                            if operation == "clear":
                                await plugin.clear_all()
                            elif operation == "migration":
                                # Force a reload so the migration write is attempted.
                                await plugin.reconcile()
                            else:
                                await record(plugin, content="uncertain")
                        self.assertFalse(plugin._loaded)
                        with self.assertRaises(RuntimeError):
                            await record(plugin, content="must not write")
                        with self.assertRaises(RuntimeError):
                            await plugin.clear_all()
                        with self.assertRaisesRegex(RuntimeError, "reconcil"):
                            await plugin.load_state()
                    finally:
                        host.release.set()
                        await host.remote
                    # The host is now known quiescent; an ordinary read was not proof.
                    await plugin.reconcile()
                    await record(plugin, content="after reconciliation")
                    self.assertEqual(
                        (await open_plugin(host)).messages, plugin.messages
                    )

    async def _queued_operation_cannot_cross_barrier(self, first, second, pause_action):
        """Run ``first`` so it fails only after ``second`` passed its fence check."""
        host = PausableHost()
        plugin = await open_plugin(host)
        await record(plugin, "group_1", "baseline")
        before = copy.deepcopy((plugin.sessions, plugin.messages))
        before_data = dict(host.data)
        host.pause_action = pause_action
        host.pause_error = TimeoutError
        failing = asyncio.create_task(first(plugin))
        await host.paused.wait()
        queued = asyncio.create_task(second(plugin))
        await asyncio.sleep(0.01)
        self.assertTrue(
            plugin._loaded, "the barrier only exists once the writer has failed"
        )
        self.assertFalse(queued.done(), "the second operation must wait for the lock")
        host.release.set()
        with self.assertRaises(TimeoutError):
            await failing
        # The queued caller passed the fence check before the failure; it must
        # re-check it under the lock instead of writing over an unknown outcome.
        with self.assertRaisesRegex(RuntimeError, "reconcil"):
            await queued
        self.assertFalse(plugin._loaded)
        self.assertEqual((plugin.sessions, plugin.messages), before)
        self.assertEqual(host.data, before_data)
        host.pause_error = None
        await plugin.reconcile()
        self.assertEqual((plugin.sessions, plugin.messages), before)

    async def test_queued_update_cannot_cross_storage_failure_barrier(self):
        await self._queued_operation_cannot_cross_barrier(
            lambda plugin: record(plugin, "group_1", "not saved"),
            lambda plugin: record(plugin, "group_1", "queued"),
            Action.SET_PLUGIN_STORAGE,
        )

    async def test_queued_clear_cannot_cross_storage_failure_barrier(self):
        await self._queued_operation_cannot_cross_barrier(
            lambda plugin: plugin.clear_all(),
            lambda plugin: record(plugin, "group_1", "queued"),
            Action.DELETE_PLUGIN_STORAGE,
        )

    async def test_queued_update_cannot_clear_after_failed_clear(self):
        await self._queued_operation_cannot_cross_barrier(
            lambda plugin: plugin.clear_all(),
            lambda plugin: plugin.clear_all(),
            Action.DELETE_PLUGIN_STORAGE,
        )

    async def test_queued_loader_cannot_clear_failed_load_barrier(self):
        host = PausableHost()
        plugin = HumanTakeover()
        plugin.config = {}
        plugin.plugin_runtime_handler = host
        host.pause_action = Action.GET_PLUGIN_STORAGE_KEYS
        host.pause_error = ConnectionError
        failing = asyncio.create_task(plugin.load_state())
        await host.paused.wait()
        queued = asyncio.create_task(plugin.load_state())
        await asyncio.sleep(0.01)
        self.assertFalse(queued.done())
        host.release.set()
        with self.assertRaises(ConnectionError):
            await failing
        # A plain load must never lift the barrier an earlier load raised, even
        # though it passed the fence check before that failure.
        with self.assertRaisesRegex(RuntimeError, "not initialized"):
            await queued
        self.assertFalse(plugin._loaded)
        self.assertEqual(host.data, {})
        host.pause_error = None
        await plugin.reconcile()
        self.assertTrue(plugin._loaded)

    async def test_v2_read_failure_blocks_writes_after_failed_initialize(self):
        await record(self.plugin)
        self.host.failure = lambda action, key: action == Action.GET_PLUGIN_STORAGE
        plugin = HumanTakeover()
        plugin.config = {}
        plugin.plugin_runtime_handler = self.host
        with self.assertRaises(OSError):
            await plugin.load_state()
        self.host.failure = None
        with self.assertRaisesRegex(RuntimeError, "not initialized"):
            await record(plugin)

    async def test_page_returns_storage_failure_not_success(self):
        from components.pages.console.console import ConsolePage
        from langbot_plugin.api.definition.components.page import PageRequest

        await record(self.plugin)
        page = ConsolePage()
        page.plugin = self.plugin
        self.host.failure = lambda action, key: action == Action.SET_PLUGIN_STORAGE
        with patch("components.pages.console.console.logger"):
            response = await page.handle_api(
                PageRequest(
                    endpoint="/takeover", method="POST", body={"session_key": "group_1"}
                )
            )
        self.assertIn("storage unavailable", response.error)

    async def test_timeout_sweep_persists_only_changed_session(self):
        await record(self.plugin, "group_1")
        await record(self.plugin, "group_2")
        with patch("main.time.time", return_value=1000):
            await self.plugin.set_takeover("group_1", True)
        self.host.writes.clear()
        with patch("main.time.time", return_value=2000):
            await self.plugin.expire_timeouts()
        self.assertEqual(len(self.host.writes), 1)
        self.assertNotIn(b"group_2", self.host.writes[0][1])
        self.assertFalse(
            (await open_plugin(self.host)).sessions["group_1"]["takeover"]["active"]
        )


if __name__ == "__main__":
    unittest.main()
