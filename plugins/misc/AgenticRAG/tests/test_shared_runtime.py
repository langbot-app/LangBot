"""Two installations drive one AgenticRAG object graph under shared-runtime-v1.

AgenticRAG relies on the stateless component model: the ``QueryKnowledge`` tool
builds its ``QueryBasedAPIProxy`` from the current invocation's query id, and the
``DisableNaiveRAG`` listener only mutates the per-event context (plus resolving
the active LLM capability from the invocation). These tests drive the same
component objects across two distinct ``InstallationBinding`` values.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from langbot_plugin.api.entities import events
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

import components.event_listener.disable_naive_rag as listener_mod  # noqa: E402
import components.tools.query_knowledge as query_mod  # noqa: E402
from main import AgenticRAG  # noqa: E402


def _binding(
    installation: str,
    *,
    workspace: str = "workspace-1",
    instance: str = "instance-1",
    revision: int = 1,
) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid=instance,
        workspace_uuid=workspace,
        installation_uuid=installation,
        runtime_revision=revision,
        artifact_digest="a" * 64,
    )


def _wire(component):
    """Mimic the runtime object graph: one plugin and one shared component."""
    plugin = AgenticRAG()
    handler = SimpleNamespace()
    plugin.plugin_runtime_handler = handler
    component.plugin = plugin
    return plugin, handler, component


def test_tool_builds_a_fresh_proxy_from_the_invocation_query_id(monkeypatch):
    _plugin, handler, tool = _wire(query_mod.QueryKnowledge())
    built: list["_RecordingProxy"] = []

    class _RecordingProxy:
        def __init__(self, *, query_id, plugin_runtime_handler):
            self.query_id = query_id
            self.plugin_runtime_handler = plugin_runtime_handler
            built.append(self)

        async def list_pipeline_knowledge_bases(self):
            return [{"uuid": f"kb-{self.query_id}"}]

    monkeypatch.setattr(query_mod, "QueryBasedAPIProxy", _RecordingProxy)

    async def call(query_id: int, binding: InstallationBinding) -> str:
        with bind_invocation(handler, config={}, binding=binding):
            return await tool.call({"action": "list"}, None, query_id)

    first = asyncio.run(call(11, _binding("installation-a")))
    second = asyncio.run(call(22, _binding("installation-b")))

    assert [proxy.query_id for proxy in built] == [11, 22]
    assert len({id(proxy) for proxy in built}) == 2
    assert all(proxy.plugin_runtime_handler is handler for proxy in built)
    assert json.loads(first) == [{"uuid": "kb-11"}]
    assert json.loads(second) == [{"uuid": "kb-22"}]
    # Nothing from the invocation was stored on the shared tool object.
    assert set(vars(tool)) == {"plugin"}


def _make_event_context() -> SimpleNamespace:
    store = {"_knowledge_base_uuids": ["kb-1"]}
    set_calls: list[tuple[str, object]] = []
    event = SimpleNamespace(
        default_prompt=[],
        query=SimpleNamespace(use_llm_model_uuid="model-x"),
    )
    context = SimpleNamespace(query_id=7, event=event, set_calls=set_calls)

    async def get_query_vars():
        return dict(store)

    async def set_query_var(key, value):
        store[key] = value
        set_calls.append((key, value))
        context.store = store

    context.store = store
    context.get_query_vars = get_query_vars
    context.set_query_var = set_query_var
    return context


def test_listener_resolves_model_capability_per_invocation_and_only_mutates_context(monkeypatch):
    plugin, handler, listener = _wire(listener_mod.DisableNaiveRAG())

    async def get_llm_models():
        binding = plugin.get_installation_binding()
        supported = binding.installation_uuid == "installation-a"
        return [{"uuid": "model-x", "tool_call_supported": supported}]

    monkeypatch.setattr(plugin, "get_llm_models", get_llm_models)

    async def dispatch(event_context: SimpleNamespace, binding: InstallationBinding) -> None:
        with bind_invocation(handler, config={}, binding=binding):
            for registered in listener.registered_handlers[events.PromptPreProcessing]:
                await registered(event_context)

    enabling = _make_event_context()
    disabling = _make_event_context()
    asyncio.run(dispatch(enabling, _binding("installation-a")))
    asyncio.run(dispatch(disabling, _binding("installation-b")))

    # installation-a declares tool support: naive RAG is cleared on that event only.
    assert enabling.set_calls == [("_knowledge_base_uuids", [])]
    assert enabling.store["_knowledge_base_uuids"] == []
    assert len(enabling.event.default_prompt) == 1

    # installation-b does not: its event is left untouched.
    assert disabling.set_calls == []
    assert disabling.store["_knowledge_base_uuids"] == ["kb-1"]
    assert disabling.event.default_prompt == []

    # No per-invocation or tenant value was copied onto the shared listener.
    assert set(vars(listener)) == {"registered_handlers", "plugin"}


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
