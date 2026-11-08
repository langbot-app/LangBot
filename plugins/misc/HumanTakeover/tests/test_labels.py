"""User-label store: CRUD, persistence, filtering and profile surface.

Run from HumanTakeover: python -m pytest tests -q
"""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch

from langbot_plugin.api.definition.components.page import PageRequest
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action

from test_storage import StorageHost, open_plugin, record

from main import STORAGE_KEY_LABELS, normalize_label_store
from components.pages.console.console import ConsolePage


def labels_key(host: StorageHost, scope: str = "dedicated") -> str:
    return scope if scope == "dedicated" else f"{scope}:{STORAGE_KEY_LABELS}"


class LabelStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logger_patch = patch("main.logger")
        logger_patch.start()
        self.addCleanup(logger_patch.stop)
        asyncio.get_running_loop().slow_callback_duration = 1
        self.host = StorageHost()
        self.plugin = await open_plugin(self.host)
        self.plugin.config = {
            "label_colors": ["#111111", "#222222"],
            "max_labels_per_user": 3,
        }

    async def test_assign_list_and_persist_across_restart(self):
        ok, err = await self.plugin.assign_label("u1", "VIP", name="小明")
        self.assertTrue(ok, err)
        ok, err = await self.plugin.assign_label("u1", "投诉")
        self.assertTrue(ok, err)
        ok, err = await self.plugin.assign_label("u2", "VIP", name="小红")
        self.assertTrue(ok, err)

        users = {u["id"]: u for u in await self.plugin.list_labeled_users()}
        self.assertEqual(sorted(users), ["u1", "u2"])
        self.assertEqual([lb["name"] for lb in users["u1"]["labels"]], ["VIP", "投诉"])
        # Colors cycle through the configured palette.
        self.assertEqual(users["u1"]["labels"][0]["color"], "#111111")
        self.assertEqual(users["u1"]["labels"][1]["color"], "#222222")

        restarted = await open_plugin(self.host)
        restarted.config = {
            "label_colors": ["#111111", "#222222"],
            "max_labels_per_user": 3,
        }
        users2 = {u["id"]: u for u in await restarted.list_labeled_users()}
        self.assertEqual(users2, users)

    async def test_remove_label_and_empty_user_is_dropped(self):
        await self.plugin.assign_label("u1", "VIP")
        await self.plugin.assign_label("u1", "投诉")
        ok, err = await self.plugin.unassign_label("u1", "VIP")
        self.assertTrue(ok, err)
        users = {u["id"]: u for u in await self.plugin.list_labeled_users()}
        self.assertEqual([lb["name"] for lb in users["u1"]["labels"]], ["投诉"])

        ok, err = await self.plugin.unassign_label("u1", "投诉")
        self.assertTrue(ok, err)
        self.assertEqual(await self.plugin.list_labeled_users(), [])
        self.assertEqual(await self.plugin.get_user_labels("u1"), {"id": "u1", "name": "", "labels": []})

    async def test_remove_missing_label_reports_error(self):
        await self.plugin.assign_label("u1", "VIP")
        ok, err = await self.plugin.unassign_label("u1", "不存在")
        self.assertFalse(ok)
        self.assertEqual([u["id"] for u in await self.plugin.list_labeled_users()], ["u1"])

    async def test_max_labels_per_user_enforced(self):
        await self.plugin.assign_label("u1", "a")
        await self.plugin.assign_label("u1", "b")
        await self.plugin.assign_label("u1", "c")
        ok, err = await self.plugin.assign_label("u1", "d")
        self.assertFalse(ok)
        self.assertIn("labels per user", err)
        self.assertEqual(len((await self.plugin.get_user_labels("u1"))["labels"]), 3)

    async def test_empty_and_overlong_labels_rejected(self):
        ok, err = await self.plugin.assign_label("u1", "   ")
        self.assertFalse(ok)
        ok, err = await self.plugin.assign_label("u1", "x" * 65)
        self.assertFalse(ok)

    async def test_rename_label_for_one_user_keeps_other_users(self):
        await self.plugin.assign_label("u1", "VIP")
        await self.plugin.assign_label("u2", "VIP")
        ok, err = await self.plugin.rename_label("u1", "VIP", "黄金客户", color="#abcdef")
        self.assertTrue(ok, err)
        users = {u["id"]: u for u in await self.plugin.list_labeled_users()}
        self.assertEqual(users["u1"]["labels"][0]["name"], "黄金客户")
        self.assertEqual(users["u1"]["labels"][0]["color"], "#abcdef")
        self.assertEqual(users["u2"]["labels"][0]["name"], "VIP")

    async def test_delete_label_everywhere(self):
        await self.plugin.assign_label("u1", "VIP")
        await self.plugin.assign_label("u1", "投诉")
        await self.plugin.assign_label("u2", "VIP")
        removed = await self.plugin.delete_label_everywhere("VIP")
        self.assertEqual(removed, 2)
        users = {u["id"]: u for u in await self.plugin.list_labeled_users()}
        self.assertEqual([lb["name"] for lb in users["u1"]["labels"]], ["投诉"])
        self.assertEqual(users["u1"]["labels"][0]["color"], "#222222")
        self.assertNotIn("u2", users)

    async def test_sessions_filter_uses_member_labels(self):
        await record(self.plugin, "group_1", "hello")  # member "1"
        await self.plugin.record_message(
            session_key="group_2",
            session_type="group",
            target_id="group_2",
            bot_uuid="fixture-bot",
            session_name="g2",
            role="user",
            sender_id="2",
            sender_name="u2",
            content_type="text",
            content="hi",
        )
        await self.plugin.assign_label("1", "VIP")
        keys = await self.plugin.sessions_with_label("VIP")
        self.assertEqual(keys, ["group_1"])

    async def test_console_sessions_filter_and_user_info(self):
        await record(self.plugin, "group_1", "hello")
        await self.plugin.assign_label("1", "VIP", name="小明")

        page = ConsolePage()
        page.plugin = self.plugin
        filtered = await page.handle_api(
            PageRequest(endpoint="/sessions", method="GET", body={"label": "VIP"})
        )
        self.assertEqual(
            [s["session_key"] for s in filtered.data["sessions"]], ["group_1"]
        )
        all_sessions = await page.handle_api(
            PageRequest(endpoint="/sessions", method="GET", body={})
        )
        self.assertTrue(all_sessions.data["sessions"][0]["has_labels"])
        self.assertEqual(all_sessions.data["sessions"][0]["labels"][0]["name"], "VIP")

        info = await page.handle_api(
            PageRequest(
                endpoint="/user_info",
                method="GET",
                body={"session_key": "group_1", "member_id": "1"},
            )
        )
        self.assertEqual(info.data["labels"][0]["name"], "VIP")
        self.assertEqual(info.data["id"], "1")

    async def test_clear_all_removes_labels(self):
        await self.plugin.assign_label("u1", "VIP")
        await record(self.plugin, "group_1")
        await self.plugin.clear_all()
        self.assertEqual(await self.plugin.list_labeled_users(), [])
        self.assertNotIn(
            "ht_user_labels_v2", self.host.data, "labels row must be deleted"
        )

    async def test_corrupt_labels_payload_degrades_to_empty(self):
        self.host.data["ht_user_labels_v2"] = b"not-json"
        plugin = await open_plugin(self.host)
        plugin.config = {"label_colors": [], "max_labels_per_user": 3}
        self.assertEqual(await plugin.list_labeled_users(), [])
        # A subsequent write still works after a bad payload was tolerated.
        ok, err = await plugin.assign_label("u1", "VIP")
        self.assertTrue(ok, err)

    async def test_labels_read_failure_does_not_block_messages(self):
        await record(self.plugin, "group_1")
        self.host.failure = (
            lambda action, key: action == Action.GET_PLUGIN_STORAGE
            and key == "ht_user_labels_v2"
        )
        await record(self.plugin, "group_1", "still works")
        self.assertEqual(len(self.plugin.messages["group_1"]), 2)


class LabelNormalizationTests(unittest.TestCase):
    def test_normalize_skips_bad_rows_and_duplicates(self):
        raw = {
            "version": 1,
            "users": {
                "ok": {"name": "A", "labels": [{"name": "VIP", "color": "#f00"}, "VIP", "x"]},
                "bad": "not a dict",
                "empty": {"name": "B", "labels": []},
                "list": {"name": "C", "labels": "VIP"},
                "": {"name": "", "labels": [{"name": "VIP"}]},
            },
        }
        store = normalize_label_store(raw)
        self.assertEqual(set(store), {"ok", "list"})
        self.assertEqual([lb["name"] for lb in store["ok"]["labels"]], ["VIP", "x"])
        self.assertEqual(store["list"]["labels"], [{"name": "VIP", "color": None}])

    def test_normalize_rejects_non_dict(self):
        self.assertEqual(normalize_label_store(None), {})
        self.assertEqual(normalize_label_store("nope"), {})

    def test_normalize_accepts_flat_shape(self):
        store = normalize_label_store({"labels": {"u1": ["VIP"]}})
        self.assertEqual(store["u1"]["labels"], [{"name": "VIP", "color": None}])

    def test_store_payload_round_trip(self):
        payload = {"version": 1, "users": {"u1": {"name": "A", "labels": []}}}
        encoded = json.dumps(payload).encode("utf-8")
        self.assertEqual(json.loads(encoded)["version"], 1)


if __name__ == "__main__":
    unittest.main()
