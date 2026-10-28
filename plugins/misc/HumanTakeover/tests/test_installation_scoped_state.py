"""Two installations of one artifact must not share takeover sessions.

The real plugin object graph is a process-wide singleton, so these tests drive
**two distinct installation bindings through one HumanTakeover object** with the
installed SDK's ``bind_invocation`` + ``InstallationBinding``. The synthetic Host
mirrors LangBot's durable plugin-storage row key
``[instance_uuid, workspace_uuid, owner_type, owner, key]``: it has **no
installation dimension**, so two installations in the same Workspace share a row
unless the plugin namespaces its own key. It is a synthetic KV, not a live
LangBot DB.

Pre-fix failure (assertions marked ``PRE-FIX`` below): the instance-level
``sessions``/``messages`` dicts were loaded once in ``initialize()`` and persisted
under the bare ``ht_session_v2_*``/``ht_storage_schema`` keys, so installation B
saw A's sessions, message history and takeover flags, and revocation dropped
nothing.
"""

from __future__ import annotations

import asyncio
import base64
import sys
from pathlib import Path

import pytest
from langbot_plugin.api.proxies.invocation import bind_invocation, current_binding
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from langbot_plugin.entities.io.context import ActionContext, InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

import main as plugin_main  # noqa: E402
from main import HumanTakeover  # noqa: E402

SHARED_PROFILE_ENV = "LANGBOT_PLUGIN_RUNTIME_PROFILE"

INSTANCE = "instance-1"
WORKSPACE = "workspace-1"

CONFIG_A = {"takeover_timeout": 600, "trigger_words": ["human"], "auto_takeover_on_trigger": True}
CONFIG_B = {"takeover_timeout": 60, "trigger_words": ["manual"], "auto_takeover_on_trigger": False}


def _binding(installation: str, *, workspace: str = WORKSPACE) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid=INSTANCE,
        workspace_uuid=workspace,
        installation_uuid=installation,
        runtime_revision=1,
        artifact_digest="a" * 64,
    )


class FakeHost:
    """Synthetic Host worker carrying durable plugin rows, keyed like the real one."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, str], bytes] = {}
        self.writes: list[tuple[str, bytes]] = []
        self.bound_action_context = None
        self.fail = False
        self.fail_write_after = 0
        self.write_count = 0

    def _scope(self) -> tuple[str, str]:
        """Resolve the trusted execution scope exactly like the Host envelope does."""

        binding = current_binding(self)
        if binding is not None:
            return binding.instance_uuid, binding.workspace_uuid
        assert self.bound_action_context is not None, "no execution scope bound"
        return (
            self.bound_action_context.instance_uuid,
            self.bound_action_context.workspace_uuid,
        )

    async def call_action(self, action, data):
        instance, workspace = self._scope()
        if action == Action.GET_PLUGIN_STORAGE_KEYS:
            return {
                "keys": [k for i, w, k in self.rows if (i, w) == (instance, workspace)]
            }
        key = data["key"]
        row = (instance, workspace, key)
        if action == Action.GET_PLUGIN_STORAGE:
            if self.fail:
                raise OSError("fixture storage unavailable")
            return {"value_base64": base64.b64encode(self.rows[row]).decode()}
        if action == Action.SET_PLUGIN_STORAGE:
            if self.fail:
                raise OSError("fixture storage unavailable")
            value = base64.b64decode(data["value_base64"])
            self.write_count += 1
            if self.fail_write_after and self.write_count > self.fail_write_after:
                raise OSError("fixture storage unavailable")
            self.writes.append((key, value))
            self.rows[row] = value
            return {}
        if action == Action.DELETE_PLUGIN_STORAGE:
            if self.fail:
                raise OSError("fixture storage unavailable")
            del self.rows[row]
            return {}
        raise AssertionError(action)


async def _open(host: FakeHost) -> HumanTakeover:
    """Construct the shared object graph; tenant state loads per invocation."""
    plugin = HumanTakeover()
    plugin.plugin_runtime_handler = host
    await plugin.initialize()
    return plugin


async def _record(plugin: HumanTakeover, key: str, content: str) -> None:
    await plugin.record_message(
        session_key=key,
        session_type="group",
        target_id=key,
        bot_uuid="fixture-bot",
        session_name=key,
        role="user",
        sender_id="1",
        sender_name="tester",
        content_type="text",
        content=content,
    )


def test_each_installation_sees_only_its_own_sessions_and_messages():
    """One object graph, two bindings: no session, message or row crosses over."""

    async def scenario():
        host = FakeHost()
        plugin = await _open(host)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await _record(plugin, "group_1", "a-message")
            await plugin.set_takeover("group_1", True)
            assert plugin.is_taken_over("group_1") is True

        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            await plugin.load_state()
            # PRE-FIX: B saw A's session, history and takeover flag.
            assert plugin.sessions == {}
            assert plugin.messages == {}
            assert plugin.is_taken_over("group_1") is False
            assert plugin.get_takeover_timeout() == 60
            await _record(plugin, "group_9", "b-message")

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await plugin.load_state()
            assert list(plugin.sessions) == ["group_1"]
            assert [m["content"] for m in plugin.messages["group_1"]] == ["a-message"]
            # PRE-FIX: A saw B's session too.
            assert "group_9" not in plugin.sessions
            assert plugin.get_takeover_timeout() == 600

        # Durable rows are namespaced by installation inside the shared Host row.
        keys = {key for key, _ in host.writes}
        assert keys
        scope_a = plugin_main.installation_scope(binding_a)
        scope_b = plugin_main.installation_scope(binding_b)
        assert f"{scope_a}:{plugin_main.STORAGE_KEY_SCHEMA}" in keys
        assert f"{scope_b}:{plugin_main.STORAGE_KEY_SCHEMA}" in keys
        assert any(
            key.startswith(f"{scope_a}:{plugin_main.STORAGE_SESSION_PREFIX}")
            for key in keys
        )
        assert any(
            key.startswith(f"{scope_b}:{plugin_main.STORAGE_SESSION_PREFIX}")
            for key in keys
        )
        # PRE-FIX: the bare "ht_session_v2_*" rows were shared by both tenants.
        assert not any(key.startswith(plugin_main.STORAGE_SESSION_PREFIX) for key in keys)

    asyncio.run(scenario())


def test_restart_of_the_loader_reloads_each_installation_from_its_own_row():
    """A fresh plugin object (worker restart) must not mix the two tenants' rows."""

    async def scenario():
        host = FakeHost()
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        first = await _open(host)
        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await _record(first, "group_1", "a-message")
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            await _record(first, "group_9", "b-message")

        second = await _open(host)
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            await second.load_state()
            # PRE-FIX: reloaded whichever tenant wrote last into the single cache.
            assert list(second.sessions) == ["group_9"]
            assert list(second.messages) == ["group_9"]
        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await second.load_state()
            assert list(second.sessions) == ["group_1"]
            assert list(second.messages) == ["group_1"]

    asyncio.run(scenario())


def test_initialize_is_process_scoped_and_keeps_tenant_state_intact():
    """initialize() runs once per worker with no config; it must not reset a tenant."""

    async def scenario():
        host = FakeHost()
        plugin = await _open(host)
        tenant = _binding("installation-a")

        with bind_invocation(host, config=CONFIG_A, binding=tenant):
            await _record(plugin, "group_1", "a-message")
            before = (dict(plugin.sessions), dict(plugin.messages))
        writes_before = list(host.writes)

        # The runtime calls initialize() with an empty config, outside any slot.
        await plugin.initialize()

        with bind_invocation(host, config=CONFIG_A, binding=tenant):
            # PRE-FIX: initialize() reset and re-read the shared row.
            assert (plugin.sessions, plugin.messages) == before
        assert host.writes == writes_before

    asyncio.run(scenario())


def test_on_installation_revoked_drops_only_that_binding():
    async def scenario():
        host = FakeHost()
        plugin = await _open(host)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await _record(plugin, "group_1", "a-message")
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            await _record(plugin, "group_9", "b-message")

        scope_a = plugin_main.installation_scope(binding_a)
        scope_b = plugin_main.installation_scope(binding_b)
        assert set(plugin._states) == {scope_a, scope_b}

        await plugin.on_installation_revoked(binding_b)
        # PRE-FIX: nothing was released, so A's and B's caches both stayed resident.
        assert scope_b not in plugin._states
        assert scope_a in plugin._states

        # A revoked installation reloads from its own durable row on the next invocation.
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            await plugin.load_state()
            assert list(plugin.sessions) == ["group_9"]
        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await plugin.load_state()
            assert list(plugin.sessions) == ["group_1"]

    asyncio.run(scenario())


def test_dedicated_binding_less_worker_keeps_the_legacy_keys(monkeypatch):
    """Dedicated placement has no invocation binding and must keep its stored rows."""

    async def scenario():
        host = FakeHost()
        host.bound_action_context = ActionContext(
            instance_uuid=INSTANCE,
            workspace_uuid=WORKSPACE,
            placement_generation=1,
        )
        plugin = HumanTakeover()
        plugin.plugin_runtime_handler = host

        monkeypatch.delenv(SHARED_PROFILE_ENV, raising=False)
        await plugin.initialize()
        await plugin.load_state()
        await _record(plugin, "group_1", "dedicated")

        keys = {key for key, _ in host.writes}
        assert plugin_main.STORAGE_KEY_SCHEMA in keys
        assert any(key.startswith(plugin_main.STORAGE_SESSION_PREFIX) for key in keys)

        restarted = HumanTakeover()
        restarted.plugin_runtime_handler = host
        await restarted.initialize()
        await restarted.load_state()
        assert list(restarted.sessions) == ["group_1"]

    asyncio.run(scenario())


def test_shared_profile_without_binding_refuses(monkeypatch):
    """A shared worker with no trusted binding must not fall back to a shared key."""

    host = FakeHost()
    plugin = HumanTakeover()
    plugin.plugin_runtime_handler = host
    monkeypatch.setenv(SHARED_PROFILE_ENV, "shared")

    with pytest.raises(RuntimeError):
        asyncio.run(plugin.load_state())
    with pytest.raises(RuntimeError):
        _ = plugin.sessions
    assert host.writes == []


def test_ambiguous_write_fence_is_per_installation():
    """A failed write must fence only the installation whose row was uncertain."""

    async def scenario():
        host = FakeHost()
        plugin = await _open(host)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await _record(plugin, "group_1", "a-message")
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            await _record(plugin, "group_9", "b-message")

        # The next SET for A fails; B must remain fully usable.
        host.fail_write_after = host.write_count
        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            with pytest.raises(OSError):
                await _record(plugin, "group_1", "a-fails")
        host.fail_write_after = 0
        host.fail = False

        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            # PRE-FIX: the process-global fence blocked every installation.
            await _record(plugin, "group_9", "b-still-works")
            assert [m["content"] for m in plugin.messages["group_9"]] == [
                "b-message",
                "b-still-works",
            ]

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            with pytest.raises(RuntimeError):
                await _record(plugin, "group_1", "a-blocked")
            await plugin.reconcile()
            await _record(plugin, "group_1", "a-recovered")

    asyncio.run(scenario())
