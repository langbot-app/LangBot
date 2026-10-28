"""Two installations, one KeywordAlert object graph: alerts never cross cooldowns.

Evidence model: one real plugin object plus one real ``KeywordMonitor``
component object are driven through the real SDK
``bind_invocation``/``InstallationBinding`` with two distinct installation
bindings; the stub Host records every ``SEND_MESSAGE`` relay, so a suppressed
alert is observable as a smaller relay list.

Pre-fix failure (asserted below): ``_cooldowns`` was one process-global dict
keyed by ``(group_id, keyword)`` only. Installation A's first alert therefore
suppressed installation B's alert for the same group/keyword, and
``on_installation_revoked`` had nothing to release. The identical message below
produced one relay instead of two.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from langbot_plugin.api.entities import events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


alert_main = _load(PLUGIN_ROOT / "main.py", "keyword_alert_main")
monitor_module = _load(PLUGIN_ROOT / "components" / "event_listener" / "monitor.py", "keyword_monitor")


class FlatHost:
    """Stub Host that records alert relays (no live platform call)."""

    def __init__(self):
        self.sent: list[dict] = []

    async def call_action(self, action, data, *args, **kwargs):
        if action == Action.SEND_MESSAGE:
            self.sent.append(data)
            return {"result": "ok"}
        if action == Action.GET_BOTS:
            return {"bots": ["fallback-bot"]}
        raise AssertionError(f"unexpected Host action: {action}")


CONFIG = {
    "keywords": "urgent",
    "group_ids": "",
    "admin_id": "admin-1",
    "bot": "bot-1",
    "case_sensitive": False,
    "cooldown_seconds": 3600,
}


def binding(installation: str, *, workspace: str = "workspace-1"):
    return InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid=workspace,
        installation_uuid=installation,
        placement_generation=1,
        runtime_revision=1,
        artifact_digest="a" * 64,
    )


def build_graph():
    plugin = alert_main.KeywordAlert()
    host = FlatHost()
    plugin.plugin_runtime_handler = host
    monitor = monitor_module.KeywordMonitor()
    monitor.plugin = plugin
    handler = monitor.registered_handlers[events.GroupMessageReceived][0]
    return plugin, host, handler


def group_message(text: str, *, group_id: str = "group-1", sender_id: str = "user-1"):
    event = SimpleNamespace(
        launcher_id=group_id,
        sender_id=sender_id,
        message_chain=platform_message.MessageChain([platform_message.Plain(text=text)]),
    )
    return SimpleNamespace(event=event)


def _texts(payloads: list[dict]) -> list[str]:
    return [
        "".join(
            part.get("text", "")
            for part in payload["message_chain"]
            if part.get("type") == "Plain"
        )
        for payload in payloads
    ]


def test_one_installation_cooldown_does_not_suppress_another():
    async def scenario():
        plugin, host, handler = build_graph()
        first, second = binding("installation-a"), binding("installation-b")

        with bind_invocation(host, config=CONFIG, binding=first):
            await handler(group_message("this is urgent"))
        with bind_invocation(host, config=CONFIG, binding=second):
            await handler(group_message("this is urgent"))

        # Pre-fix: only one relay, because the shared (group, keyword) key was
        # already in cooldown from installation A.
        assert len(host.sent) == 2
        assert all(payload["target_id"] == "admin-1" for payload in host.sent)
        assert _texts(host.sent)[0] == _texts(host.sent)[1]
        assert "urgent" in _texts(host.sent)[1]

        # Each installation keeps its own cooldown table.
        assert set(plugin._cooldowns) == {plugin._scope(first), plugin._scope(second)}

        # The cooldown still works inside one installation.
        with bind_invocation(host, config=CONFIG, binding=first):
            await handler(group_message("urgent again"))
        assert len(host.sent) == 2

    asyncio.run(scenario())


def test_cooldown_is_released_on_revocation():
    async def scenario():
        plugin, host, handler = build_graph()
        first = binding("installation-a")

        with bind_invocation(host, config=CONFIG, binding=first):
            await handler(group_message("this is urgent"))
        assert len(host.sent) == 1

        await plugin.on_installation_revoked(first)
        assert plugin._scope(first) not in plugin._cooldowns

        with bind_invocation(host, config=CONFIG, binding=first):
            await handler(group_message("this is urgent"))
        assert len(host.sent) == 2

    asyncio.run(scenario())


def test_cooldown_key_includes_the_full_binding():
    plugin = alert_main.KeywordAlert()
    same_installation_other_workspace = binding("installation-a", workspace="workspace-2")
    assert plugin._scope(binding("installation-a")) != plugin._scope(same_installation_other_workspace)
    assert plugin._scope(binding("installation-a")) == "instance-1:workspace-1:installation-a"
    assert plugin._scope() == alert_main.LEGACY_SCOPE


def test_revocation_of_an_unknown_binding_is_a_no_op():
    async def scenario():
        plugin, _host, _handler = build_graph()
        await plugin.on_installation_revoked(binding("installation-never-seen"))
        assert plugin._cooldowns == {}

    asyncio.run(scenario())


def test_dedicated_binding_less_invocation_keeps_its_cooldown():
    """A dedicated worker's invocation carries no binding; it keeps its own scope."""

    async def scenario():
        plugin, host, handler = build_graph()
        with bind_invocation(host, config=CONFIG):  # no installation binding
            await handler(group_message("this is urgent"))
        assert len(host.sent) == 1
        assert set(plugin._cooldowns) == {alert_main.LEGACY_SCOPE}

        with bind_invocation(host, config=CONFIG):
            await handler(group_message("urgent again"))
        assert len(host.sent) == 1  # the legacy cooldown still suppresses the repeat

    asyncio.run(scenario())
