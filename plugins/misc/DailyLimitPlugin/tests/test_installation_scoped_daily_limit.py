"""Two installations of one artifact must not share daily-limit state.

The real plugin object graph is a process-wide singleton, so these tests drive
**two distinct installation bindings through one DailyLimitPlugin object** with
the installed SDK's ``bind_invocation`` + ``InstallationBinding``. The synthetic
Host mirrors LangBot's durable plugin-storage row key
``[instance_uuid, workspace_uuid, owner_type, owner, key]``: it has **no
installation dimension**, so two installations in the same Workspace share a row
unless the plugin namespaces its own key. It is a synthetic KV, not a live
LangBot DB.

Pre-fix failure (assertions marked ``PRE-FIX`` below): the single instance-level
``settings``/``sessions`` dicts were loaded once in ``initialize()`` and persisted
under the bare ``daily_limit_state`` key, so installation B's snapshot showed A's
tracked session, B's settings came from A's (empty-config) seed, and a restart
reloaded whichever installation wrote last.
"""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from langbot_plugin.api.definition.components.page import PageRequest
from langbot_plugin.api.proxies.invocation import bind_invocation, current_binding
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from langbot_plugin.entities.io.context import ActionContext, InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _load_plugin_module(module_name: str):
    """Load this plugin's ``main.py`` under a unique name.

    ``main`` is the conventional plugin module name, so a plain ``import main``
    would collide with a sibling plugin's module in a combined pytest session.
    """

    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


plugin_main = _load_plugin_module("daily_limit_plugin_under_test")
DailyLimitPlugin = plugin_main.DailyLimitPlugin

SHARED_PROFILE_ENV = "LANGBOT_PLUGIN_RUNTIME_PROFILE"

INSTANCE = "instance-1"
WORKSPACE = "workspace-1"

CONFIG_A = {
    "daily_limit": 1,
    "limit_message": "A limit reached",
    "silent_mode": False,
    "reset_timezone_offset": 8,
    "reset_hour": 0,
}
CONFIG_B = {
    "daily_limit": 5,
    "limit_message": "B limit reached",
    "silent_mode": False,
    "reset_timezone_offset": 8,
    "reset_hour": 0,
}


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
            return {"keys": [k for i, w, k in self.rows if (i, w) == (instance, workspace)]}
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


def _plugin(host: FakeHost) -> DailyLimitPlugin:
    plugin = DailyLimitPlugin()
    plugin.plugin_runtime_handler = host
    return plugin


def _load_component(relative_path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _MessageContext:
    """Minimal EventContext stand-in for the real listener's ``_check``."""

    def __init__(self, launcher_id: str, sender_id: str) -> None:
        self.event = SimpleNamespace(launcher_id=launcher_id, sender_id=sender_id)
        self.replied: list = []
        self.prevented = False

    async def reply(self, chain) -> None:
        self.replied.append(chain)

    def prevent_default(self) -> None:
        self.prevented = True

    def prevent_postorder(self) -> None:
        pass


def _message_context(launcher_id: str) -> _MessageContext:
    return _MessageContext(launcher_id, launcher_id)


def test_each_installation_gets_its_own_settings_and_sessions():
    """One object graph, two bindings: no session, setting or row crosses over."""

    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            allowed, message = await plugin.check_and_count("group:1", "group:1")
            assert (allowed, message) == (True, "")
            allowed, message = await plugin.check_and_count("group:1", "group:1")
            assert (allowed, message) == (False, "A limit reached")

        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            snapshot = await plugin.snapshot()
            # PRE-FIX: showed installation A's tracked "group:1" session.
            assert snapshot["sessions"] == []
            # PRE-FIX: seeded from the empty shared initialize() config.
            assert snapshot["settings"]["limit_message"] == "B limit reached"
            assert snapshot["settings"]["default_limit"] == 5
            allowed, _ = await plugin.check_and_count("group:9", "group:9")
            assert allowed is True

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            snapshot = await plugin.snapshot()
            assert [row["id"] for row in snapshot["sessions"]] == ["group:1"]
            assert snapshot["sessions"][0]["count"] == 1

        # A write from A after B wrote must not touch B's row or B's cache.
        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await plugin.check_and_count("group:1", "group:1")

        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            snapshot = await plugin.snapshot()
            assert [row["id"] for row in snapshot["sessions"]] == ["group:9"]
            assert snapshot["sessions"][0]["count"] == 1

        # The durable rows are namespaced by installation inside the shared Host row.
        keys = {key for key, _ in host.writes}
        assert len(keys) == 2, keys
        assert all(key.startswith("daily_limit_state:") for key in keys)
        assert not any(key == "daily_limit_state" for key in keys)

    asyncio.run(scenario())


def test_restart_of_the_loader_reloads_each_installation_from_its_own_row():
    """A fresh plugin object (worker restart) must not mix the two tenants' rows."""

    async def scenario():
        host = FakeHost()
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        first = _plugin(host)
        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await first.check_and_count("group:1", "group:1")
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            await first.check_and_count("group:9", "group:9")

        # Simulated restart: new process, new object graph, same Host rows.
        second = _plugin(host)
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            snapshot = await second.snapshot()
            # PRE-FIX: reloaded the single shared row (A's session, A's settings).
            assert [row["id"] for row in snapshot["sessions"]] == ["group:9"]
            assert snapshot["settings"]["limit_message"] == "B limit reached"
        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            snapshot = await second.snapshot()
            assert [row["id"] for row in snapshot["sessions"]] == ["group:1"]
            assert snapshot["settings"]["limit_message"] == "A limit reached"
            allowed, message = await second.check_and_count("group:1", "group:1")
            assert (allowed, message) == (False, "A limit reached")

    asyncio.run(scenario())


def test_initialize_is_process_scoped_and_keeps_tenant_state_intact():
    """initialize() runs once per worker with no config; it must not reset a tenant."""

    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        tenant = _binding("installation-a")

        with bind_invocation(host, config=CONFIG_A, binding=tenant):
            await plugin.check_and_count("group:1", "group:1")
            before = await plugin.snapshot()
        writes_before = list(host.writes)

        # The runtime calls initialize() with an empty config, outside any slot.
        await plugin.initialize()

        with bind_invocation(host, config=CONFIG_A, binding=tenant):
            after = await plugin.snapshot()
        # PRE-FIX: initialize() re-read the shared row and reseeded settings from {}
        # (default_limit back to 50, A's session gone).
        assert after == before
        assert after["settings"]["default_limit"] == 1
        assert host.writes == writes_before

    asyncio.run(scenario())


def test_real_components_serve_the_invoking_installation():
    """The real listener and management Page must stay inside the invoking binding."""

    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        listener = _load_component("components/event_listener/default.py", "daily_limit_listener").DefaultEventListener()
        listener.plugin = plugin
        await listener.initialize()

        manager = _load_component("components/pages/manage/manage.py", "daily_limit_manage_page").ManagePage()
        manager.plugin = plugin

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            context = _message_context("g1")
            await listener._check(context, "group")
            assert context.replied == []
            await listener._check(context, "group")
            assert len(context.replied) == 1 and context.prevented is True

        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            # PRE-FIX: B inherited A's counter and was blocked on its first message.
            context = _message_context("g1")
            await listener._check(context, "group")
            assert context.replied == [] and context.prevented is False

            state = await manager.handle_api(PageRequest(endpoint="/state", method="GET"))
            assert [row["id"] for row in state.data["sessions"]] == ["group:g1"]
            assert state.data["sessions"][0]["count"] == 1
            assert state.data["settings"]["limit_message"] == "B limit reached"

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            state = await manager.handle_api(PageRequest(endpoint="/state", method="GET"))
            assert [row["id"] for row in state.data["sessions"]] == ["group:g1"]
            assert state.data["sessions"][0]["count"] == 1
            assert state.data["settings"]["limit_message"] == "A limit reached"

    asyncio.run(scenario())


def test_on_installation_revoked_drops_only_that_binding():
    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await plugin.check_and_count("group:1", "group:1")
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            await plugin.check_and_count("group:9", "group:9")

        scope_a = plugin_main.installation_scope(binding_a)
        scope_b = plugin_main.installation_scope(binding_b)
        assert set(plugin._states) == {scope_a, scope_b}

        await plugin.on_installation_revoked(binding_b)
        assert scope_b not in plugin._states
        assert scope_a in plugin._states

        # A revoked installation reloads from its own durable row on the next invocation.
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            snapshot = await plugin.snapshot()
            assert [row["id"] for row in snapshot["sessions"]] == ["group:9"]

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
        await plugin.check_and_count("group:1", "group:1")
        assert {key for key, _ in host.writes} == {"daily_limit_state"}
        snapshot = await plugin.snapshot()
        assert [row["id"] for row in snapshot["sessions"]] == ["group:1"]

    asyncio.run(scenario())


def test_shared_profile_without_binding_refuses(monkeypatch):
    """A shared worker with no trusted binding must not fall back to a shared key."""

    host = FakeHost()
    plugin = _plugin(host)
    monkeypatch.setenv(SHARED_PROFILE_ENV, "shared")

    with pytest.raises(RuntimeError):
        asyncio.run(plugin.snapshot())
    assert host.writes == []
