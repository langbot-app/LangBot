"""One installation, several bots: conversations must never share a session.

A session key is derived from the trusted bot uuid resolved from the event query,
so two bots/adapters with the same launcher id keep separate history, takeover
state and reply targets. Real SDK event models + synthetic Host KV sink.

Run from HumanTakeover: python -m pytest tests
"""

from __future__ import annotations

import base64
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from langbot_plugin.api.entities import events
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from components.event_listener.default import DefaultEventListener  # noqa: E402
from main import HumanTakeover  # noqa: E402


class FakeHost:
    """Synthetic Host KV sink; keys/values mimic the real plugin_storage row."""

    def __init__(self):
        self.data = {}
        self.writes = []

    async def call_action(self, action, data):
        key = data.get("key")
        if action == Action.GET_PLUGIN_STORAGE_KEYS:
            return {"keys": list(self.data)}
        if action == Action.GET_PLUGIN_STORAGE:
            return {"value_base64": base64.b64encode(self.data[key]).decode()}
        if action == Action.SET_PLUGIN_STORAGE:
            value = base64.b64decode(data["value_base64"])
            self.writes.append((key, value))
            self.data[key] = value
            return {}
        if action == Action.DELETE_PLUGIN_STORAGE:
            del self.data[key]
            return {}
        raise AssertionError(action)


class FakeEventContext:
    """Only the surface the EventListener uses; identity comes from the Host."""

    def __init__(self, event, bot_uuid):
        self.event = event
        self._bot_uuid = bot_uuid
        self.prevented_default = False
        self.prevented_postorder = False

    async def get_bot_uuid(self):
        if isinstance(self._bot_uuid, Exception):
            raise self._bot_uuid
        return self._bot_uuid

    def prevent_default(self):
        self.prevented_default = True

    def prevent_postorder(self):
        self.prevented_postorder = True


def person_event(launcher_id: str, text: str) -> events.PersonMessageReceived:
    chain = platform_message.MessageChain([platform_message.Plain(text=text)])
    friend = platform_entities.Friend(id=launcher_id, nickname="Alice", remark=None)
    message_event = platform_events.FriendMessage(
        type="FriendMessage", sender=friend, message_chain=chain
    )
    return events.PersonMessageReceived(
        launcher_type="person",
        launcher_id=launcher_id,
        sender_id=launcher_id,
        message_event=message_event,
        message_chain=chain,
    )


class SessionIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Failure paths are asserted through exceptions, not test stderr.
        for target in ("main.logger", "components.event_listener.default.logger"):
            logger_patch = patch(target)
            logger_patch.start()
            self.addCleanup(logger_patch.stop)
        self.host = FakeHost()

    async def _open(self, host=None):
        host = host if host is not None else self.host
        plugin = HumanTakeover()
        plugin.config = {}
        plugin.plugin_runtime_handler = host
        await plugin.initialize()
        await plugin.load_state()
        return plugin

    async def _record(self, plugin, session_key, bot_uuid, content, adapter=""):
        await plugin.record_message(
            session_key=session_key,
            session_type="person",
            target_id="42",
            bot_uuid=bot_uuid,
            session_name=bot_uuid,
            role="user",
            sender_id="42",
            sender_name="user",
            content_type="text",
            content=content,
            adapter=adapter,
        )

    async def _listener(self, plugin, adapter_by_bot=None):
        async def get_bot_info(bot_uuid):
            return {"adapter": (adapter_by_bot or {}).get(bot_uuid, "")}

        plugin.get_bot_info = get_bot_info
        listener = DefaultEventListener()
        listener.plugin = plugin
        await listener.initialize()
        return listener.registered_handlers[events.PersonMessageReceived][0]

    async def test_session_key_includes_the_trusted_bot_identity(self):
        self.assertNotEqual(
            HumanTakeover.make_session_key("person", "42", "bot-a"),
            HumanTakeover.make_session_key("person", "42", "bot-b"),
        )
        # An unscoped key would collide across bots; it must not be producible.
        with self.assertRaises(ValueError):
            HumanTakeover.make_session_key("person", "42", "")

    async def test_two_bots_with_the_same_launcher_id_keep_separate_history(self):
        plugin = await self._open()
        key_a = HumanTakeover.make_session_key("person", "42", "bot-a")
        key_b = HumanTakeover.make_session_key("person", "42", "bot-b")
        await self._record(plugin, key_a, "bot-a", "from A", adapter="qq")
        await self._record(plugin, key_b, "bot-b", "from B", adapter="telegram")

        self.assertEqual([m["content"] for m in plugin.messages[key_a]], ["from A"])
        self.assertEqual([m["content"] for m in plugin.messages[key_b]], ["from B"])
        self.assertEqual(plugin.sessions[key_a]["bot_uuid"], "bot-a")
        self.assertEqual(plugin.sessions[key_a]["adapter"], "qq")
        self.assertEqual(plugin.sessions[key_b]["bot_uuid"], "bot-b")
        self.assertEqual(plugin.sessions[key_b]["adapter"], "telegram")

        # A reply from the console must reach the bot that owns the opened session.
        sent = []

        async def send_message(**kwargs):
            sent.append(kwargs)

        plugin.send_message = send_message
        ok, error = await plugin.human_send(key_b, text="manual")
        self.assertTrue(ok, error)
        self.assertEqual(
            [(m["bot_uuid"], m["target_type"], m["target_id"]) for m in sent],
            [("bot-b", "person", "42")],
        )

        restarted = await self._open()
        self.assertEqual(restarted.messages, plugin.messages)
        self.assertEqual(restarted.sessions, plugin.sessions)
        self.assertEqual([m["content"] for m in restarted.messages[key_a]], ["from A"])

    async def test_foreign_bot_event_cannot_overwrite_an_existing_session(self):
        plugin = await self._open()
        key_a = HumanTakeover.make_session_key("person", "42", "bot-a")
        await self._record(plugin, key_a, "bot-a", "from A", adapter="qq")
        before = copy.deepcopy((plugin.sessions, plugin.messages))

        # Same key, another bot: the reply target must not be rewritten.
        with self.assertRaisesRegex(RuntimeError, "identity"):
            await self._record(plugin, key_a, "bot-b", "spoofed", adapter="telegram")
        self.assertEqual((plugin.sessions, plugin.messages), before)

        with self.assertRaisesRegex(RuntimeError, "identity"):
            await self._record(plugin, key_a, "bot-a", "spoofed adapter", adapter="tg")
        self.assertEqual((plugin.sessions, plugin.messages), before)

    async def test_listener_scopes_events_by_bot_identity(self):
        plugin = await self._open()
        handler = await self._listener(plugin, {"bot-a": "qq", "bot-b": "telegram"})

        # Same launcher id, two bots: the key must be resolved from the Host identity.
        await handler(FakeEventContext(person_event("42", "from A"), "bot-a"))
        await handler(FakeEventContext(person_event("42", "from B"), "bot-b"))

        # Keys are looked up through the recorded identity, so this assertion is
        # about behaviour: one shared record shows up as a single bot.
        by_bot = {sess["bot_uuid"]: key for key, sess in plugin.sessions.items()}
        self.assertEqual(sorted(by_bot), ["bot-a", "bot-b"])
        key_a, key_b = by_bot["bot-a"], by_bot["bot-b"]
        self.assertNotEqual(key_a, key_b)
        self.assertEqual(plugin.sessions[key_a]["adapter"], "qq")
        self.assertEqual(plugin.sessions[key_b]["adapter"], "telegram")
        self.assertEqual([m["content"] for m in plugin.messages[key_a]], ["from A"])
        self.assertEqual([m["content"] for m in plugin.messages[key_b]], ["from B"])

        sent = []

        async def send_message(**kwargs):
            sent.append(kwargs)

        plugin.send_message = send_message
        for session_key, text in ((key_a, "reply A"), (key_b, "reply B")):
            ok, error = await plugin.human_send(session_key, text=text)
            self.assertTrue(ok, error)
        self.assertEqual(
            [(m["bot_uuid"], m["target_id"]) for m in sent],
            [("bot-a", "42"), ("bot-b", "42")],
        )

    async def test_event_without_trusted_bot_identity_is_not_keyed(self):
        plugin = await self._open()
        handler = await self._listener(plugin)

        context = FakeEventContext(
            person_event("42", "anonymous"), RuntimeError("host unavailable")
        )
        await handler(context)

        self.assertEqual(plugin.sessions, {})
        self.assertEqual(plugin.messages, {})
        self.assertFalse(context.prevented_default)

    async def test_unscoped_legacy_session_is_not_merged_with_bot_scoped_events(self):
        plugin = await self._open()
        legacy_key = "person_42"
        await self._record(plugin, legacy_key, "bot-a", "legacy history", adapter="qq")

        restarted = await self._open()
        handler = await self._listener(restarted, {"bot-b": "telegram"})
        await handler(FakeEventContext(person_event("42", "from B"), "bot-b"))

        # Behaviour first: the older row must keep its owner and history, and the
        # bot-b event must land in its own record instead of rewriting it.
        self.assertEqual(restarted.sessions[legacy_key]["bot_uuid"], "bot-a")
        self.assertEqual(
            [m["content"] for m in restarted.messages[legacy_key]], ["legacy history"]
        )
        by_bot = {sess["bot_uuid"]: key for key, sess in restarted.sessions.items()}
        self.assertEqual(sorted(by_bot), ["bot-a", "bot-b"])
        key_b = by_bot["bot-b"]
        self.assertEqual([m["content"] for m in restarted.messages[key_b]], ["from B"])

        self.assertFalse(
            HumanTakeover.session_key_has_bot_identity(
                legacy_key, restarted.sessions[legacy_key]
            )
        )
        self.assertTrue(
            HumanTakeover.session_key_has_bot_identity(key_b, restarted.sessions[key_b])
        )


if __name__ == "__main__":
    unittest.main()
