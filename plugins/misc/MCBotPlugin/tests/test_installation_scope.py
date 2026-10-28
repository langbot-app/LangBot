"""Two installations, one MCBotPlugin object: no cache or storage row is shared.

Evidence model: the real SDK ``bind_invocation``/``InstallationBinding`` drive
two distinct installation bindings through one plugin object, and a stub Host
serves plugin storage with the flat row key LangBot uses
(``[instance, workspace, owner, key]`` — no installation dimension), so any
key the plugin leaves unscoped is visibly shared between the two bindings.

Pre-fix failure (asserted below): the plugin kept one ``bindings`` dict, one
``records`` list and one ``_track_task`` on the process-wide object and wrote
them under ``mcbot_bindings``/``mcbot_records``. ``get_bound_server`` for
installation B therefore returned installation A's server, ``count_playtime``
for B returned A's playtime records, the Host saw a single storage row for both
installations, and ``on_installation_revoked`` released nothing.
"""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from langbot_plugin.api.proxies.invocation import bind_invocation, invocation_capability
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _load_main():
    spec = importlib.util.spec_from_file_location("mcbot_main", PLUGIN_ROOT / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mcbot_main = _load_main()


class FlatHost:
    """Stub Host: one flat KV namespace, exactly the Host row shape that has no
    installation dimension. Also records the request contexts it was called
    under, so a test can see which binding a storage row was written for."""

    def __init__(self):
        self.data: dict[str, bytes] = {}
        self.actions: list[str] = []

    async def call_action(self, action, data, *args, **kwargs):
        self.actions.append(str(action))
        if action == Action.GET_PLUGIN_STORAGE:
            raw = self.data.get(data["key"])
            return {"value_base64": base64.b64encode(raw).decode() if raw is not None else ""}
        if action == Action.SET_PLUGIN_STORAGE:
            self.data[data["key"]] = base64.b64decode(data["value_base64"])
            return {}
        if action == Action.GET_PLUGIN_STORAGE_KEYS:
            return {"keys": list(self.data)}
        if action == Action.DELETE_PLUGIN_STORAGE:
            self.data.pop(data["key"], None)
            return {}
        raise AssertionError(f"unexpected Host action: {action}")


def binding(installation: str, *, workspace: str = "workspace-1"):
    return InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid=workspace,
        installation_uuid=installation,
        placement_generation=1,
        runtime_revision=1,
        artifact_digest="a" * 64,
    )


def build_plugin():
    plugin = mcbot_main.MCBotPlugin()
    host = FlatHost()
    plugin.plugin_runtime_handler = host
    return plugin, host


CONFIG = {"track_interval": 60, "ping_timeout": 10}


def test_bindings_and_records_do_not_leak_between_installations():
    async def scenario():
        plugin, host = build_plugin()
        first, second = binding("installation-a"), binding("installation-b")

        async def fake_ping(server_addr, timeout=None):
            return {
                "motd": "motd",
                "version": "1.20",
                "online": 1,
                "max": 20,
                "players": ["Steve"],
            }

        plugin.ping_server = fake_ping

        with bind_invocation(host, config=CONFIG, binding=first):
            await plugin.bind_server("group_1", "a.example:25565")

        with bind_invocation(host, config=CONFIG, binding=second):
            # Pre-fix this returned "a.example:25565" from the shared bindings dict.
            assert await plugin.get_bound_server("group_1") is None
            await plugin.bind_server("group_1", "b.example:25565")

        with bind_invocation(host, config=CONFIG, binding=first):
            assert await plugin.get_bound_server("group_1") == "a.example:25565"

        # A sampling cycle for installation A must not appear as B's playtime.
        await plugin._track_once(plugin._scope(first), 60, 10)

        with bind_invocation(host, config=CONFIG, binding=first):
            first_stats = await plugin.count_playtime("a.example:25565", 60)
        with bind_invocation(host, config=CONFIG, binding=second):
            # Pre-fix this returned [("Steve", 60)] from the shared records list.
            assert await plugin.count_playtime("a.example:25565", 60) == []
        assert first_stats == [("Steve", 60)]

        # Two distinct storage rows, one per installation (pre-fix: one row
        # named "mcbot_bindings" holding whichever installation wrote last).
        binding_rows = {k: v for k, v in host.data.items() if k.startswith("mcbot_bindings")}
        assert set(binding_rows) == {
            f"mcbot_bindings:{plugin._scope(first)}",
            f"mcbot_bindings:{plugin._scope(second)}",
        }
        assert json.loads(binding_rows[f"mcbot_bindings:{plugin._scope(first)}"].decode()) == {
            "group_1": "a.example:25565"
        }
        assert json.loads(binding_rows[f"mcbot_bindings:{plugin._scope(second)}"].decode()) == {
            "group_1": "b.example:25565"
        }

    asyncio.run(scenario())


def test_records_flush_to_the_owning_installation_row():
    async def scenario():
        plugin, host = build_plugin()
        first, second = binding("installation-a"), binding("installation-b")

        async def fake_ping(server_addr, timeout=None):
            return {"motd": "", "version": "1", "online": 1, "max": 2, "players": ["Alex"]}

        plugin.ping_server = fake_ping
        with bind_invocation(host, config=CONFIG, binding=first):
            await plugin.bind_server("group_1", "a.example:25565")

        # The detached tracker performs no Host call, so nothing is written yet.
        await plugin._track_once(plugin._scope(first), 60, 10)
        assert host.data.get(f"mcbot_records:{plugin._scope(first)}") is None

        # The next invocation of the owning installation writes the samples.
        with bind_invocation(host, config=CONFIG, binding=first):
            await plugin.get_bound_server("group_1")
        records = json.loads(host.data[f"mcbot_records:{plugin._scope(first)}"].decode())
        assert [r["players"] for r in records] == [["Alex"]]
        assert f"mcbot_records:{plugin._scope(second)}" not in host.data

    asyncio.run(scenario())


def test_tracker_is_registered_per_binding_and_stopped_on_revocation():
    async def scenario():
        plugin, host = build_plugin()
        first, second = binding("installation-a"), binding("installation-b")
        started: list[tuple[str, int, float]] = []

        async def fake_loop(scope, interval, timeout):
            started.append((scope, interval, timeout))
            await asyncio.sleep(3600)

        plugin._track_loop = fake_loop
        config = {"track_interval": 45, "ping_timeout": 7}

        with bind_invocation(host, config=config, binding=first):
            await plugin.bind_server("group_1", "a.example:25565")
        with bind_invocation(host, config=config, binding=second):
            await plugin.bind_server("group_2", "b.example:25565")

        await asyncio.sleep(0)
        assert set(plugin._track_tasks) == {plugin._scope(first), plugin._scope(second)}
        assert started == [
            (plugin._scope(first), 45, 7.0),
            (plugin._scope(second), 45, 7.0),
        ]
        first_task = plugin._track_tasks[plugin._scope(first)]

        await plugin.on_installation_revoked(first)
        assert first_task.cancelled() or first_task.done()
        assert set(plugin._track_tasks) == {plugin._scope(second)}
        assert plugin._scope(first) not in plugin._states
        # Release is per installation: the sibling tracker keeps running.
        assert not plugin._track_tasks[plugin._scope(second)].done()

        await plugin.on_installation_revoked(second)

    asyncio.run(scenario())


def test_two_installations_write_two_storage_rows():
    """Pre-fix failure, asserted through pre-fix-compatible APIs only.

    Both installations bound a server through ``bind_server`` and the stub Host
    keeps the flat row namespace LangBot uses. Pre-fix the second bind
    overwrote the first one's single ``mcbot_bindings`` row, so the Host held
    one row and installation A's server was gone.
    """
    async def scenario():
        plugin, host = build_plugin()
        first, second = binding("installation-a"), binding("installation-b")

        async def sleeper(scope, interval, timeout):
            await asyncio.sleep(3600)

        plugin._track_loop = sleeper

        with bind_invocation(host, config=CONFIG, binding=first):
            await plugin.bind_server("group_1", "a.example:25565")
        with bind_invocation(host, config=CONFIG, binding=second):
            await plugin.bind_server("group_1", "b.example:25565")

        assert len(host.data) == 2, host.data
        assert sorted(json.loads(v.decode())["group_1"] for v in host.data.values()) == [
            "a.example:25565",
            "b.example:25565",
        ]

        await plugin.on_installation_revoked(first)
        await plugin.on_installation_revoked(second)

    asyncio.run(scenario())


def test_dedicated_scope_keeps_the_legacy_storage_key():
    async def scenario():
        plugin, host = build_plugin()
        with bind_invocation(host, config=CONFIG):  # no installation binding
            await plugin.bind_server("group_1", "srv.example:25565")
        assert list(host.data) == ["mcbot_bindings"]
        assert plugin._scope() == mcbot_main.LEGACY_SCOPE

    asyncio.run(scenario())


def test_tracker_task_holds_no_invocation_authority():
    """The tracker must not inherit a finished invocation's (dead) authority.

    SDK rule verified here: a task started inside an invocation inherits the
    invocation context, and ``invocation_capability`` then raises
    "Plugin invocation has ended" once the invocation returns — so every Host
    call from such a task fails. ``_start_detached`` runs the tracker in a fresh
    context instead, which is why the samples it collects are flushed to storage
    by the next invocation rather than written from the loop.
    """
    async def scenario():
        plugin, host = build_plugin()
        first = binding("installation-a")
        seen: list[object] = []
        loop_gate = asyncio.Event()

        async def probe():
            seen.append(plugin._scope(first))
            result = invocation_capability(host)
            seen.append(result)
            return result

        async def fake_loop(scope, interval, timeout):
            try:
                await probe()
            except BaseException as exc:  # noqa: BLE001
                seen.append(exc)
            await loop_gate.wait()

        plugin._track_loop = fake_loop
        with bind_invocation(host, config=CONFIG, binding=first):
            await plugin.bind_server("group_1", "a.example:25565")
        await asyncio.sleep(0)

        # Fresh context: the loop sees neither an invocation nor any capability.
        assert seen == [plugin._scope(first), None]

        # The pre-fix shape: a plain task created in the invocation context.
        with bind_invocation(host, config=CONFIG, binding=first):
            inherited = asyncio.create_task(probe())
        with pytest.raises(RuntimeError, match="invocation has ended"):
            await inherited

        await plugin.on_installation_revoked(first)

    asyncio.run(scenario())


def test_scope_key_is_the_full_binding():
    plugin, _host = build_plugin()
    same_installation_other_workspace = binding("installation-a", workspace="workspace-2")
    assert plugin._scope(binding("installation-a")) != plugin._scope(same_installation_other_workspace)
    assert plugin._scope(binding("installation-a")) == plugin._scope(binding("installation-a"))
    assert plugin._scope(binding("installation-a")) == "instance-1:workspace-1:installation-a"
    assert plugin._scope(SimpleNamespace(instance_uuid="i", workspace_uuid="w", installation_uuid="x")) == "i:w:x"
