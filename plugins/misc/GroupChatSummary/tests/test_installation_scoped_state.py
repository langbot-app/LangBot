"""Two installations of one artifact must not share group-chat buffers.

The real plugin object graph is a process-wide singleton, so these tests drive
**two distinct installation bindings through one GroupChatSummary object** with
the installed SDK's ``bind_invocation`` + ``InstallationBinding``. The synthetic
Host mirrors LangBot's durable plugin-storage row key
``[instance_uuid, workspace_uuid, owner_type, owner, key]``: it has **no
installation dimension**, so two installations in the same Workspace share a row
unless the plugin namespaces its own key. It is a synthetic KV, not a live
LangBot DB.

Pre-fix failure (assertions marked ``PRE-FIX`` below): one instance-level
``message_buffer``/``auto_summary_watermark`` pair was loaded once in
``initialize()`` and persisted under the bare ``message_buffers`` key, and the
auto-summary task was detached with no registry. Installation B therefore saw
A's buffered group and A's persisted row, and revoking A left its task running.
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
from main import GroupChatSummary  # noqa: E402

SHARED_PROFILE_ENV = "LANGBOT_PLUGIN_RUNTIME_PROFILE"

INSTANCE = "instance-1"
WORKSPACE = "workspace-1"

CONFIG_A = {
    "max_messages": 500,
    "default_summary_count": 100,
    "auto_summary_enabled": False,
    "auto_summary_threshold": 200,
    "language": "zh_Hans",
}
CONFIG_B = {**CONFIG_A, "language": "en_US"}


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
        key = data["key"]
        row = (instance, workspace, key)
        if action == Action.GET_PLUGIN_STORAGE_KEYS:
            return {
                "keys": [k for i, w, k in self.rows if (i, w) == (instance, workspace)]
            }
        if action == Action.GET_PLUGIN_STORAGE:
            return {"value_base64": base64.b64encode(self.rows[row]).decode()}
        if action == Action.SET_PLUGIN_STORAGE:
            value = base64.b64decode(data["value_base64"])
            self.writes.append((key, value))
            self.rows[row] = value
            return {}
        if action == Action.DELETE_PLUGIN_STORAGE:
            del self.rows[row]
            return {}
        raise AssertionError(action)


def _plugin(host: FakeHost) -> GroupChatSummary:
    plugin = GroupChatSummary()
    plugin.plugin_runtime_handler = host
    return plugin


async def _record(
    plugin: GroupChatSummary, launcher_id: str, text: str, *, bot_uuid: str | None = None
) -> None:
    await plugin.record_message(
        launcher_type="group",
        launcher_id=launcher_id,
        sender_id="1",
        sender_name="tester",
        text=text,
        bot_uuid=bot_uuid,
    )


def test_each_installation_sees_only_its_own_buffers():
    """One object graph, two bindings: no buffered group or row crosses over."""

    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            for i in range(10):
                await _record(plugin, "group-1", f"a-{i}")
            assert plugin.get_message_count("group", "group-1") == 10

        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            await plugin.ensure_loaded()
            # PRE-FIX: showed installation A's 10 buffered group-1 messages.
            assert plugin.get_message_count("group", "group-1") == 0
            await _record(plugin, "group-9", "b-only")
            assert plugin.get_message_count("group", "group-9") == 1

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await plugin.ensure_loaded()
            assert plugin.get_message_count("group", "group-1") == 10
            assert plugin.get_message_count("group", "group-9") == 0

        # Durable rows are namespaced by installation inside the shared Host row.
        keys = {key for key, _ in host.writes}
        assert keys, "buffers must be persisted"
        assert all(key.startswith("message_buffers:") for key in keys), keys
        # PRE-FIX: the single bare "message_buffers" row was shared by both.
        assert "message_buffers" not in keys

    asyncio.run(scenario())


def test_restart_of_the_loader_reloads_each_installation_from_its_own_row():
    """A fresh plugin object (worker restart) must not mix the two tenants' rows."""

    async def scenario():
        host = FakeHost()
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        first = _plugin(host)
        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            for i in range(10):
                await _record(first, "group-1", f"a-{i}")
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            for i in range(10):
                await _record(first, "group-9", f"b-{i}")

        second = _plugin(host)
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            await second.ensure_loaded()
            # PRE-FIX: reloaded whichever installation wrote last into the single dict.
            assert second.get_message_count("group", "group-9") == 10
            assert second.get_message_count("group", "group-1") == 0
        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await second.ensure_loaded()
            assert second.get_message_count("group", "group-1") == 10
            assert second.get_message_count("group", "group-9") == 0

    asyncio.run(scenario())


def test_initialize_is_process_scoped_and_keeps_tenant_buffers_intact():
    """initialize() runs once per worker with no config; it must not reset a tenant."""

    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        tenant = _binding("installation-a")

        with bind_invocation(host, config=CONFIG_A, binding=tenant):
            await _record(plugin, "group-1", "hello")
            before = plugin.get_message_count("group", "group-1")
        writes_before = list(host.writes)

        # The runtime calls initialize() with an empty config, outside any slot.
        await plugin.initialize()

        with bind_invocation(host, config=CONFIG_A, binding=tenant):
            # PRE-FIX: initialize() re-read the shared row into the single dict.
            assert plugin.get_message_count("group", "group-1") == before == 1
        assert host.writes == writes_before

    asyncio.run(scenario())


def test_on_installation_revoked_drops_state_and_stops_that_binding():
    """Revocation releases only the revoked installation's cache and tasks."""

    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            for i in range(10):
                await _record(plugin, "group-1", f"a-{i}")
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            for i in range(10):
                await _record(plugin, "group-9", f"b-{i}")

        scope_a = plugin_main.installation_scope(binding_a)
        scope_b = plugin_main.installation_scope(binding_b)
        assert set(plugin._states) == {scope_a, scope_b}

        await plugin.on_installation_revoked(binding_b)
        assert scope_b not in plugin._states
        assert scope_a in plugin._states

        # A revoked installation reloads from its own durable row on the next invocation.
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            await plugin.ensure_loaded()
            assert plugin.get_message_count("group", "group-9") == 10
        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            assert plugin.get_message_count("group", "group-1") == 10

    asyncio.run(scenario())


def test_auto_summary_tasks_are_binding_keyed_and_cancelled_on_revocation():
    """Detached auto-summaries carry their own binding and die with it."""

    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")
        config = {**CONFIG_A, "auto_summary_enabled": True, "auto_summary_threshold": 1}

        seen: list[tuple[str, str]] = []
        hold = asyncio.Event()

        async def fake_generate_summary(**kwargs):
            # Runs inside the detached task: report which tenant/config it sees.
            binding = plugin.get_installation_binding()
            seen.append((binding.installation_uuid, plugin.get_config()["language"]))
            await hold.wait()
            return "summary"

        plugin.generate_summary = fake_generate_summary  # type: ignore[assignment]

        with bind_invocation(host, config=config, binding=binding_a):
            await _record(plugin, "group-1", "a", bot_uuid="bot-a")
        with bind_invocation(host, config={**config, "language": "en_US"}, binding=binding_b):
            await _record(plugin, "group-9", "b", bot_uuid="bot-b")

        scope_a = plugin_main.installation_scope(binding_a)
        scope_b = plugin_main.installation_scope(binding_b)
        for _ in range(100):
            if len(seen) == 2:
                break
            await asyncio.sleep(0)
        assert set(plugin._tasks) == {scope_a, scope_b}
        task_a = next(iter(plugin._tasks[scope_a]))
        task_b = next(iter(plugin._tasks[scope_b]))
        assert not task_a.done() and not task_b.done()

        await plugin.on_installation_revoked(binding_a)
        assert scope_a not in plugin._tasks
        assert task_a.cancelled()
        assert scope_b in plugin._tasks
        # PRE-FIX: the task was detached with no registry, so revoking A left it
        # running and any later Host call could escape to another installation.
        assert not task_b.done()

        await plugin.on_installation_revoked(binding_b)
        assert plugin._tasks == {}
        assert task_b.cancelled()
        # Each task re-entered an invocation scope with its own captured binding.
        assert sorted(uuid for uuid, _ in seen) == ["installation-a", "installation-b"]
        assert {lang for _, lang in seen} == {"zh_Hans", "en_US"}

    asyncio.run(scenario())


def test_dedicated_binding_less_worker_keeps_the_legacy_key(monkeypatch):
    """Dedicated placement has no invocation binding and must keep its stored rows."""

    async def scenario():
        host = FakeHost()
        host.bound_action_context = ActionContext(
            instance_uuid=INSTANCE,
            workspace_uuid=WORKSPACE,
            placement_generation=1,
        )
        plugin = _plugin(host)

        monkeypatch.delenv(SHARED_PROFILE_ENV, raising=False)
        with bind_invocation(host, config=CONFIG_A):
            for i in range(10):
                await _record(plugin, "group-1", f"m-{i}")
        assert {key for key, _ in host.writes} == {"message_buffers"}

        restarted = _plugin(host)
        with bind_invocation(host, config=CONFIG_A):
            await restarted.ensure_loaded()
            assert restarted.get_message_count("group", "group-1") == 10

    asyncio.run(scenario())


def test_shared_profile_without_binding_refuses(monkeypatch):
    """A shared worker with no trusted binding must not fall back to a shared key."""

    host = FakeHost()
    plugin = _plugin(host)
    monkeypatch.setenv(SHARED_PROFILE_ENV, "shared")

    with pytest.raises(RuntimeError):
        asyncio.run(plugin.ensure_loaded())
    with pytest.raises(RuntimeError):
        _ = plugin.message_buffer
    assert host.writes == []
