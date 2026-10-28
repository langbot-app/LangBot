"""Real SDK discovery, initialization, Runner RPC, proxy and WebSocket tests.

Only the Host/backend responses are deterministic protocol fixtures. No SDK
classes, Runner API methods, transport or plugin implementation are mocked.
No external model/provider is contacted; sockets bind to loopback on a free port.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest
import pytest_asyncio
import websockets
from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.cli.run.controller import PluginRuntimeController
from langbot_plugin.cli.run.handler import PluginRuntimeHandler
from langbot_plugin.cli.utils.page_components import discover_plugin_components
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction, RuntimeToPluginAction
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.runtime.plugin.container import RuntimeContainerStatus
from langbot_plugin.utils.discover.engine import ComponentDiscoveryEngine

ROOT = Path(__file__).resolve().parents[1]
USAGE = {"prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10}


class BackendProtocolFixture:
    """Bounded Host responses, not a replacement Runner API or SDK handler."""

    def __init__(self, host):
        self.calls = []
        self.fail_primary = False
        self.use_tool = False
        self.opaque_provider_fields = False
        self.cancelled = False
        self.stall = False
        self.stall_started = asyncio.Event()
        self.host = host

        @host.action(PluginToRuntimeAction.GET_LANGBOT_VERSION)
        async def version(data):
            return ActionResponse.success({"version": "test", "api_features": ["llm.reasoning_level"]})

        @host.action(PluginToRuntimeAction.COUNT_TOKENS)
        async def count_tokens(data):
            self.record("count_tokens", data)
            assert isinstance(data["messages"], list)
            return ActionResponse.success({"tokens": 16})

        @host.action(PluginToRuntimeAction.STEERING_PULL)
        async def steering_pull(data):
            self.record("steering_pull", data)
            return ActionResponse.success({"items": []})

        @host.action(PluginToRuntimeAction.GET_TOOL_DETAIL)
        async def tool_detail(data):
            self.record("tool_detail", data)
            assert data["tool_name"] == "fixture_echo"
            return ActionResponse.success(
                {"tool": {"name": "fixture_echo", "description": "Fixture echo", "parameters": {"type": "object"}}}
            )

        @host.action(PluginToRuntimeAction.CALL_TOOL)
        async def call_tool(data):
            self.record("call_tool", data)
            assert data["tool_name"] == "fixture_echo"
            assert data["parameters"] == {"text": "hello"}
            return ActionResponse.success({"result": {"echo": "hello"}})

        @host.action(PluginToRuntimeAction.RUN_GET)
        async def run_get(data):
            self.record("run_get", data)
            return ActionResponse.success(
                {"run_id": data["run_id"], "status": "cancelled" if self.cancelled else "running"}
            )

        @host.action(PluginToRuntimeAction.INVOKE_LLM)
        async def invoke(data):
            self.record("invoke", data)
            if self.fail_primary and data["llm_model_uuid"] == "primary":
                return ActionResponse.error("fixture primary unavailable")
            return ActionResponse.success({"message": self.reply(data).model_dump(mode="json"), "usage": USAGE})

        @host.action(PluginToRuntimeAction.INVOKE_LLM_STREAM)
        async def stream(data):
            self.record("stream", data)
            if self.stall:
                self.stall_started.set()
                await asyncio.Event().wait()
            if self.fail_primary and data["llm_model_uuid"] == "primary":
                yield ActionResponse.error("fixture primary unavailable")
                return
            message = self.reply(data)
            chunk = MessageChunk(
                role="assistant",
                content=message.content,
                tool_calls=message.tool_calls,
                provider_specific_fields=message.provider_specific_fields,
                is_final=True,
            )
            yield ActionResponse.success({"chunk": chunk.model_dump(mode="json")})
            # Usage-only final response exercises the actual SDK stream decoder.
            yield ActionResponse.success({"usage": USAGE})

    def record(self, action, data):
        assert data["run_id"] == "sdk-fixture-run"
        self.calls.append((action, data))
        assert len(self.calls) < 100, "Unbounded fixture RPC loop"

    def reply(self, data):
        if self.use_tool and not any(message["role"] == "tool" for message in data["messages"]):
            return Message.model_validate(
                {
                    "role": "assistant",
                    "content": "",
                    "provider_specific_fields": {"opaque_state": "message-signature"}
                    if self.opaque_provider_fields
                    else None,
                    "tool_calls": [
                        {
                            "id": "fixture-call",
                            "type": "function",
                            "provider_specific_fields": {"opaque_state": "tool-signature"}
                            if self.opaque_provider_fields
                            else None,
                            "function": {"name": "fixture_echo", "arguments": '{"text":"hello"}'},
                        }
                    ],
                }
            )
        return Message(role="assistant", content="真实 SDK fixture ✓")

    async def run(self, context, runner_name="default"):
        async def collect():
            return [
                RunnerResult.model_validate(item)
                async for item in self.host.call_action_generator(
                    RuntimeToPluginAction.RUN_RUNNER,
                    {"runner_name": runner_name, "context": context.model_dump(mode="json")},
                    timeout=3,
                )
            ]

        return await asyncio.wait_for(collect(), timeout=5)


ORIGINAL_BACKEND_FIXTURE = BackendProtocolFixture


def run_context(*, streaming=True, tools=False):
    return RunnerContext.model_validate(
        {
            "run_id": "sdk-fixture-run",
            "trigger": {"type": "message.received"},
            "event": {"event_id": "fixture-event", "event_type": "message.received", "source": "pipeline_adapter"},
            "input": {"text": "Fixture question"},
            "delivery": {"surface": "pipeline", "supports_streaming": streaming},
            "context": {"conversation_id": "fixture-conversation", "available_apis": {"steering_pull": True}},
            "runtime": {"query_id": 1},
            "config": {"model": {"primary": "primary", "fallbacks": ["fallback"]}, "timeout": 2},
            "resources": {
                "models": [
                    {"model_id": name, "operations": ["invoke", "stream", "count_tokens"]}
                    for name in ["primary", "fallback"]
                ],
                "tools": [{"tool_name": "fixture_echo", "operations": ["detail", "call"]}] if tools else [],
            },
        }
    )


@pytest_asyncio.fixture
async def sdk_runtime(monkeypatch, tmp_path):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("LANGBOT_PLUGIN_FILE_STORAGE_DIR", str(tmp_path / "rpc"))
    discovery = ComponentDiscoveryEngine()
    manifest = discovery.load_component_manifest("manifest.yaml")
    assert manifest is not None
    shared = BackendProtocolFixture is not ORIGINAL_BACKEND_FIXTURE
    if shared:
        manifest.execution.shared_runtime = "shared-runtime-v1"
        manifest.execution.component_model = "stateless-v1"
    components = discover_plugin_components(manifest, discovery)
    assert [(item.kind, item.metadata.name) for item in components] == [("Runner", "default")]
    controller = PluginRuntimeController(manifest, components, stdio=False, ws_debug_url="")
    host_ready = asyncio.get_running_loop().create_future()

    async def host_connection(socket):
        host = Handler(WebSocketConnection(socket), file_storage_dir=tmp_path / "host-rpc")
        backend = BackendProtocolFixture(host)
        host_ready.set_result(backend)
        try:
            await host.run()
        finally:
            await host.close()

    async with websockets.serve(host_connection, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with websockets.connect(f"ws://127.0.0.1:{port}") as socket:
            handler = PluginRuntimeHandler(WebSocketConnection(socket), controller.initialize)
            handler.plugin_container = controller.plugin_container
            if shared:
                handler._slot_initialize_callback = controller.initialize_slot
                handler._slot_detach_callback = controller.detach_slot
                handler._slot_cancel_callback = controller.invalidate_slot
            controller.handler = handler
            task = asyncio.create_task(handler.run())
            backend = await asyncio.wait_for(host_ready, 3)
            try:
                if shared:
                    backend.host_slots = set()
                    await backend.host.call_action(
                        RuntimeToPluginAction.ATTACH_PLUGIN_SLOT,
                        {"plugin_settings": {"enabled": True, "priority": 0, "plugin_config": {}}},
                        timeout=3,
                        action_context=InstallationBinding(
                            instance_uuid="fixture",
                            workspace_uuid="workspace-a",
                            installation_uuid="installation-a",
                            runtime_revision=1,
                            artifact_digest="1" * 64,
                        ),
                    )
                    backend.host_slots.add("installation-a")
                else:
                    await backend.host.call_action(
                        RuntimeToPluginAction.INITIALIZE_PLUGIN,
                        {"plugin_settings": {"enabled": True, "priority": 0, "plugin_config": {}}},
                        timeout=3,
                    )
                container = controller.plugin_container
                assert container.status == RuntimeContainerStatus.INITIALIZED
                assert type(container.plugin_instance).__name__ == "LocalAgentPlugin"
                runner = container.components[0].component_instance
                assert isinstance(runner, Runner)
                assert type(runner).__name__ == "DefaultRunner"
                yield backend
            finally:
                await backend.host.close()
                await handler.close()
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await controller.cleanup_instances()


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("use_tool", [False, True])
@pytest.mark.parametrize("fallback", [False, True])
async def test_real_sdk_runner_round_trip(sdk_runtime, streaming, use_tool, fallback):
    sdk_runtime.fail_primary = fallback
    sdk_runtime.use_tool = use_tool
    results = await sdk_runtime.run(run_context(streaming=streaming, tools=use_tool))

    assert [item.sequence for item in results] == list(range(1, len(results) + 1))
    assert all(item.run_id == "sdk-fixture-run" for item in results)
    assert [item.type for item in results[-2:]] == ["message.completed", "run.completed"]
    assert results[-2].data["message"]["content"] == "真实 SDK fixture ✓"
    assert results[-1].usage.total_tokens == (20 if use_tool else 10)
    assert results[-1].usage.model_calls == (2 if use_tool else 1)
    assert any(item.type == "message.delta" for item in results) is streaming
    assert any(item.type == "tool.call.completed" for item in results) is use_tool
    model_calls = [data for action, data in sdk_runtime.calls if action in {"stream", "invoke"}]
    assert model_calls[0]["llm_model_uuid"] == "primary"
    assert model_calls[-1]["llm_model_uuid"] == ("fallback" if fallback else "primary")
    assert all(data["timeout"] > 0 for data in model_calls)


@pytest.mark.asyncio
async def test_real_sdk_runner_no_authorized_model(sdk_runtime):
    context = run_context()
    context.resources.models = []
    results = await sdk_runtime.run(context)
    assert len(results) == 1
    assert results[0].data["code"] == "runner.no_model"
    assert sdk_runtime.calls == []


@pytest.mark.asyncio
async def test_real_sdk_rejects_missing_count_tokens_grant(sdk_runtime):
    context = run_context()
    context.resources.models[0].operations = ["invoke", "stream"]
    results = await sdk_runtime.run(context)
    assert len(results) == 1
    assert results[0].type == "run.failed"
    assert not any(action in {"count_tokens", "invoke", "stream"} for action, _ in sdk_runtime.calls)


@pytest.mark.asyncio
async def test_real_sdk_missing_runner(sdk_runtime):
    results = await sdk_runtime.run(run_context(), runner_name="does-not-exist")
    assert len(results) == 1
    assert results[0].data["code"] == "runner.not_found"
    assert results[0].sequence == 1
    assert sdk_runtime.calls == []


@pytest.mark.asyncio
async def test_real_sdk_host_deadline_bounds_stalled_stream(sdk_runtime):
    sdk_runtime.stall = True
    context = run_context()
    context.runtime.deadline_at = time.time() + 0.25
    results = await sdk_runtime.run(context)
    assert sdk_runtime.stall_started.is_set()
    assert len(results) == 1
    assert results[0].data["code"] == "runner.timeout"
    assert results[0].sequence == 1


@pytest.mark.asyncio
async def test_real_sdk_run_get_cancellation(sdk_runtime):
    sdk_runtime.cancelled = True
    context = run_context()
    context.context.available_apis.run_get = True
    results = await sdk_runtime.run(context)
    assert len(results) == 1
    assert results[0].data["code"] == "cancelled"
    assert [action for action, _ in sdk_runtime.calls] == ["run_get"]


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_real_sdk_master_parity_request_contract(sdk_runtime, streaming):
    sdk_runtime.fail_primary = True
    sdk_runtime.use_tool = True
    sdk_runtime.opaque_provider_fields = True
    context = run_context(streaming=streaming, tools=True)
    reasoning = {"primary": "high", "fallback": "low"}
    context.config["model"]["reasoning"] = reasoning.copy()
    results = await sdk_runtime.run(context)
    assert results[-1].type == "run.completed"
    model_calls = [data for action, data in sdk_runtime.calls if action in {"stream", "invoke"}]
    assert [data["llm_model_uuid"] for data in model_calls] == ["primary", "fallback", "fallback"]
    assert context.config["model"]["reasoning"] == reasoning
    for action, payload in sdk_runtime.calls:
        if action in {"invoke", "stream", "count_tokens"}:
            assert payload["reasoning_level"] == reasoning[payload["llm_model_uuid"]]
    assert all(not data.get("extra_args") for data in model_calls)
    assert all("Current date:" in data["messages"][0]["content"] for data in model_calls)
    assistant = next(message for message in model_calls[-1]["messages"] if message["role"] == "assistant")
    assert assistant["provider_specific_fields"] == {"opaque_state": "message-signature"}
    assert assistant["tool_calls"][0]["provider_specific_fields"] == {"opaque_state": "tool-signature"}
    # This proves explicit SDK RPC parameters; Core separately proves provider translation.


@pytest.mark.asyncio
async def test_real_sdk_authorized_multikb_rerank_reaches_model(sdk_runtime):
    import json

    from langbot_plugin.api.entities.builtin.runner.resources import KnowledgeBaseResource, ModelResource

    @sdk_runtime.host.action(PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE)
    async def retrieve(data):
        sdk_runtime.record("retrieve", data)
        return ActionResponse.success({"results": [{"content": [{"type": "text", "text": data["kb_id"] + " fact"}]}]})

    @sdk_runtime.host.action(PluginToRuntimeAction.INVOKE_RERANK)
    async def rerank(data):
        sdk_runtime.record("rerank", data)
        return ActionResponse.success({"results": [{"index": 1, "relevance_score": 0.99}]})

    context = run_context(streaming=False)
    context.config.update(
        {"knowledge-bases": ["kb-a", "foreign-kb", "kb-b"], "rerank-model": "reranker", "rerank-top-k": 1}
    )
    context.resources.knowledge_bases = [
        KnowledgeBaseResource(kb_id=name, operations=["retrieve"]) for name in ["kb-a", "kb-b"]
    ]
    context.resources.models.append(ModelResource(model_id="reranker", model_type="rerank", operations=["rerank"]))
    results = await sdk_runtime.run(context)
    assert results[-1].type == "run.completed"
    retrieval_calls = [data for action, data in sdk_runtime.calls if action == "retrieve"]
    assert [data["kb_id"] for data in retrieval_calls] == ["kb-a", "kb-b"]
    assert all(data["top_k"] == 5 for data in retrieval_calls)
    rerank_call = next(data for action, data in sdk_runtime.calls if action == "rerank")
    assert rerank_call["documents"] == ["kb-a fact", "kb-b fact"]
    model_call = next(data for action, data in sdk_runtime.calls if action == "invoke")
    rag = next(
        json.loads(message["content"])
        for message in model_call["messages"]
        if isinstance(message.get("content"), str) and '"langbot_retrieved_context"' in message["content"]
    )
    assert [chunk["content"] for chunk in rag["data"]["chunks"]] == ["kb-b fact"]
    assert model_call["messages"][-1]["content"] == "Fixture question"


@pytest.mark.asyncio
async def test_real_sdk_cancels_while_waiting_for_stream(sdk_runtime):
    sdk_runtime.stall = True
    context = run_context()
    context.context.available_apis.run_get = True
    task = asyncio.create_task(sdk_runtime.run(context))
    try:
        await asyncio.wait_for(sdk_runtime.stall_started.wait(), timeout=3)
        sdk_runtime.cancelled = True
        results = await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert len(results) == 1
    assert results[0].type == "run.failed"
    assert results[0].data["code"] == "cancelled"


@pytest.mark.asyncio
async def test_real_sdk_cancels_while_waiting_for_tool(sdk_runtime):
    sdk_runtime.use_tool = True
    tool_started = asyncio.Event()

    @sdk_runtime.host.action(PluginToRuntimeAction.CALL_TOOL)
    async def stalled_tool(data):
        sdk_runtime.record("call_tool", data)
        tool_started.set()
        await asyncio.Event().wait()

    context = run_context(tools=True)
    context.context.available_apis.run_get = True
    task = asyncio.create_task(sdk_runtime.run(context))
    try:
        await asyncio.wait_for(tool_started.wait(), timeout=3)
        sdk_runtime.cancelled = True
        results = await asyncio.wait_for(task, timeout=1.5)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert results[-1].type == "run.failed"
    assert results[-1].data["code"] == "cancelled"
    assert sum(result.type in {"run.failed", "run.completed"} for result in results) == 1
