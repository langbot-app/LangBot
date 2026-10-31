"""Two installations of one artifact must not share FAQ entries.

The real plugin object graph is a process-wide singleton, so these tests drive
**two distinct installation bindings through one FAQManagerPlugin object** with
the installed SDK's ``bind_invocation`` + ``InstallationBinding``. The synthetic
Host mirrors LangBot's durable plugin-storage row key
``[instance_uuid, workspace_uuid, owner_type, owner, key]``: it has **no
installation dimension**, so two installations in the same Workspace share a row
unless the plugin namespaces its own key. It is a synthetic KV, not a live
LangBot DB.

Pre-fix failure (assertions marked ``PRE-FIX`` below): ``entries`` was a single
instance list loaded in ``initialize()`` from the bare ``faq_entries`` key, so
installation B listed A's questions, A's search returned B's answers, and a
restart reloaded whichever installation wrote last.
"""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import sys
from pathlib import Path

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


plugin_main = _load_plugin_module("faq_manager_plugin_under_test")
FAQManagerPlugin = plugin_main.FAQManagerPlugin

SHARED_PROFILE_ENV = "LANGBOT_PLUGIN_RUNTIME_PROFILE"

INSTANCE = "instance-1"
WORKSPACE = "workspace-1"
DIGEST = "a" * 64


def _load_component(relative_path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _binding(installation: str, *, workspace: str = WORKSPACE) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid=INSTANCE,
        workspace_uuid=workspace,
        installation_uuid=installation,
        runtime_revision=1,
        artifact_digest=DIGEST,
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


def _plugin(host: FakeHost) -> FAQManagerPlugin:
    plugin = FAQManagerPlugin()
    plugin.plugin_runtime_handler = host
    return plugin


def _manager_page(plugin: FAQManagerPlugin):
    module = _load_component("components/pages/manager/manager.py", "faq_manager_page")
    page = module.ManagerPage()
    page.plugin = plugin
    return page


def _dashboard_page(plugin: FAQManagerPlugin):
    module = _load_component("components/pages/dashboard/dashboard.py", "faq_dashboard_page")
    page = module.DashboardPage()
    page.plugin = plugin
    return page


def _search_tool(plugin: FAQManagerPlugin):
    module = _load_component("components/tools/search_faq.py", "faq_search_tool")
    tool = module.SearchFAQ()
    tool.plugin = plugin
    return tool


def test_two_installations_keep_separate_entries():
    """One object graph, two bindings: neither the list, the search nor the row crosses over."""

    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        with bind_invocation(host, binding=binding_a):
            entry = await plugin.add_entry("a-question", "a-answer")
            await plugin.persist()
            assert entry["question"] == "a-question"

        with bind_invocation(host, binding=binding_b):
            # PRE-FIX: B listed A's "a-question".
            assert await plugin.get_entries() == []
            # PRE-FIX: A's entry matched B's search.
            assert await plugin.search("a-question") == []
            await plugin.add_entry("b-question", "b-answer")
            await plugin.persist()

        with bind_invocation(host, binding=binding_a):
            questions = [e["question"] for e in await plugin.get_entries()]
            assert questions == ["a-question"]
            # A write from B after A wrote must not alter A's data.
            assert [e["question"] for e in await plugin.search("b-question")] == []
            assert [e["question"] for e in await plugin.search("a-question")] == ["a-question"]

        with bind_invocation(host, binding=binding_b):
            questions = [e["question"] for e in await plugin.get_entries()]
            assert questions == ["b-question"]

        keys = {key for key, _ in host.writes}
        assert len(keys) == 2, keys
        assert all(key.startswith("faq_entries:") for key in keys)
        assert "faq_entries" not in {key for key, _ in host.writes}

    asyncio.run(scenario())


def test_restart_of_the_loader_reloads_each_installation_from_its_own_row():
    """A fresh plugin object (worker restart) must not mix the two tenants' rows."""

    async def scenario():
        host = FakeHost()
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        first = _plugin(host)
        with bind_invocation(host, binding=binding_a):
            await first.add_entry("a-question", "a-answer")
            await first.persist()
        with bind_invocation(host, binding=binding_b):
            await first.add_entry("b-question", "b-answer")
            await first.persist()

        # Simulated restart: new process, new object graph, same Host rows.
        second = _plugin(host)
        with bind_invocation(host, binding=binding_b):
            entries = await second.get_entries()
            # PRE-FIX: reloaded the single shared row (A's entry, or both).
            assert [e["question"] for e in entries] == ["b-question"]
        with bind_invocation(host, binding=binding_a):
            entries = await second.get_entries()
            assert [e["question"] for e in entries] == ["a-question"]

    asyncio.run(scenario())


def test_page_and_tool_components_read_the_invoking_installation():
    """The Page and Tool components share the plugin object; both must stay scoped."""

    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")
        page = _manager_page(plugin)
        dashboard = _dashboard_page(plugin)
        tool = _search_tool(plugin)

        with bind_invocation(host, binding=binding_a):
            created = await page.handle_api(
                PageRequest(endpoint="/entries", method="POST", body={"question": "a-question", "answer": "a-answer"})
            )
            assert created.error is None

        with bind_invocation(host, binding=binding_b):
            listed = await page.handle_api(PageRequest(endpoint="/entries", method="GET"))
            # PRE-FIX: the management page showed installation A's entries.
            assert listed.data == {"entries": []}
            stats = await dashboard.handle_api(PageRequest(endpoint="/stats", method="GET"))
            assert stats.data == {"total_entries": 0, "avg_answer_length": 0}
            found = await tool.call({"query": "a-question"})
            assert found["results"] == []
            await page.handle_api(
                PageRequest(endpoint="/entries", method="POST", body={"question": "b-question", "answer": "b-answer"})
            )

        with bind_invocation(host, binding=binding_a):
            found = await tool.call({"query": "b-question"})
            assert found["results"] == []
            found = await tool.call({"query": "a-question"})
            assert found["results"] == [{"question": "a-question", "answer": "a-answer"}]
            stats = await dashboard.handle_api(PageRequest(endpoint="/stats", method="GET"))
            assert stats.data == {"total_entries": 1, "avg_answer_length": len("a-answer")}

    asyncio.run(scenario())


def test_on_installation_revoked_drops_only_that_binding():
    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        with bind_invocation(host, binding=binding_a):
            await plugin.get_entries()
        with bind_invocation(host, binding=binding_b):
            await plugin.get_entries()

        scope_a = plugin_main.installation_scope(binding_a)
        scope_b = plugin_main.installation_scope(binding_b)
        assert set(plugin._states) == {scope_a, scope_b}

        await plugin.on_installation_revoked(binding_b)
        assert scope_b not in plugin._states
        assert scope_a in plugin._states

        # A revoked installation reloads from its own durable row on the next invocation.
        with bind_invocation(host, binding=binding_b):
            await plugin.add_entry("b-question", "b-answer")
            await plugin.persist()
        with bind_invocation(host, binding=binding_b):
            state = plugin._states[scope_b]
            assert [e["question"] for e in state.entries] == ["b-question"]

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
        await plugin.add_entry("legacy-question", "legacy-answer")
        await plugin.persist()
        assert {key for key, _ in host.writes} == {"faq_entries"}
        stored = json.loads(host.rows[(INSTANCE, WORKSPACE, "faq_entries")].decode("utf-8"))
        assert [e["question"] for e in stored] == ["legacy-question"]

    asyncio.run(scenario())


def test_shared_profile_without_binding_refuses(monkeypatch):
    """A shared worker with no trusted binding must not fall back to a shared key."""

    host = FakeHost()
    plugin = _plugin(host)
    monkeypatch.setenv(SHARED_PROFILE_ENV, "shared")

    with pytest.raises(RuntimeError):
        asyncio.run(plugin.get_entries())
    assert host.writes == []
