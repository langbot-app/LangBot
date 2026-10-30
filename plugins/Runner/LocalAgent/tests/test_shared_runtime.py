"""Real SDK/loopback RPC and one component, with simulated scoped Host/model.

No live credentials, Core database, worker supervisor/nsjail, or upstream model.
The fixture deliberately reuses model, conversation, actor, state-key and tool IDs
across installations. Only the trusted RPC envelope selects simulated authority.
"""

from __future__ import annotations

import asyncio
import copy
import json

import pytest
from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as P
from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction as R
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.entities.io.resp import ActionResponse

from tests import test_sdk_runtime as base

sdk_runtime = base.sdk_runtime


class ScopedHost(base.BackendProtocolFixture):
    def __init__(self, host):
        super().__init__(host)
        self.owners = {}
        self.storage = {}
        self.cancel_runs = set()
        self.fail_runs = set()
        self.stall_runs = set()
        self.history_failure = set()
        self.model_started = {}
        self.release = asyncio.Event()
        self.model_owners = set()
        self.credentials_used = []
        self.active = 0
        self.peak = 0
        self.compact = False
        self.barrier = False
        self.host_slots = set()

        @host.action(P.RUN_GET)
        async def run_get(data):
            self.record("run_get", data)
            return ActionResponse.success(
                {"run_id": data["run_id"], "status": "cancelled" if data["run_id"] in self.cancel_runs else "running"}
            )

        @host.action(P.STATE_GET)
        async def state_get(data):
            owner = self.record("state_get", data)
            assert data["scope"] == "conversation"
            return ActionResponse.success({"value": copy.deepcopy(self.storage.get((owner, data["key"])))})

        @host.action(P.STATE_SET)
        async def state_set(data):
            owner = self.record("state_set", data)
            assert data["scope"] == "conversation"
            self.storage[owner, data["key"]] = copy.deepcopy(data["value"])
            return ActionResponse.success({"success": True})

        @host.action(P.HISTORY_PAGE)
        async def history(data):
            owner = self.record("history", data)
            if data["run_id"] in self.history_failure:
                return ActionResponse.error("fixture history unavailable")
            return ActionResponse.success(
                {
                    "items": [
                        {
                            "transcript_id": f"t-{i}",
                            "event_id": f"old-{i}",
                            "conversation_id": "same-conversation",
                            "cursor": str(i),
                            "role": "user" if i % 2 else "assistant",
                            "item_type": "message",
                            "content": f"history-private-{owner} " * (100 if self.compact else 1),
                        }
                        for i in range(1, 6)
                    ],
                    "has_more": False,
                    "next_cursor": None,
                    "prev_cursor": None,
                }
            )

        @host.action(P.COUNT_TOKENS)
        async def count(data):
            self.record("count_tokens", data)
            return ActionResponse.success({"tokens": max(1, len(json.dumps(data["messages"])) // 4)})

        @host.action(P.CALL_TOOL)
        async def tool(data):
            owner = self.record("call_tool", data)
            assert data["tool_name"] == "fixture_echo"
            assert data["parameters"] == {"text": "hello"}
            return ActionResponse.success({"result": {"text": f"tool-private-{owner}"}})

        @host.action(P.RETRIEVE_KNOWLEDGE_BASE)
        async def retrieve(data):
            owner = self.record("retrieve", data)
            assert data["kb_id"] == "same-kb"
            return ActionResponse.success(
                {"results": [{"content": [{"type": "text", "text": f"rag-private-{owner}"}]}]}
            )

        @host.action(P.INVOKE_LLM)
        async def invoke(data):
            answer = await self.model(data)
            if answer is None:
                return ActionResponse.error("fixture model unavailable")
            return ActionResponse.success({"message": answer.model_dump(mode="json"), "usage": base.USAGE})

        @host.action(P.INVOKE_LLM_STREAM)
        async def stream(data):
            answer = await self.model(data)
            if answer is None:
                yield ActionResponse.error("fixture model unavailable")
                return
            chunk = MessageChunk(role="assistant", content=answer.content, tool_calls=answer.tool_calls, is_final=True)
            yield ActionResponse.success({"chunk": chunk.model_dump(mode="json")})
            yield ActionResponse.success({"usage": base.USAGE})

    def record(self, action, data):
        binding = self.host.current_action_context
        assert isinstance(binding, InstallationBinding), "Host callback lost trusted installation envelope"
        owner = self.owners[data["run_id"]]
        assert binding.workspace_uuid == f"workspace-{owner}"
        assert binding.installation_uuid == f"installation-{owner}"
        assert binding.runtime_revision == 1
        self.calls.append((action, copy.deepcopy(data)))
        assert len(self.calls) < 500
        return owner

    async def model(self, data):
        owner = self.record("model", data)
        rid = data["run_id"]
        assert data["llm_model_uuid"] == "primary"
        assert data["reasoning_level"] == ("high" if owner == "a" else "low")
        payload = json.dumps(data)
        foreign = "b" if owner == "a" else "a"
        for prefix in ("config-private-", "history-private-", "summary-private-", "tool-private-", "rag-private-"):
            assert prefix + foreign not in payload
        assert "fixture-credential-" not in payload
        # Credential selection is simulated Host behavior, never plugin-side keys.
        self.credentials_used.append((rid, f"fixture-credential-{owner}"))
        self.model_owners.add(owner)
        self.model_started.setdefault(rid, asyncio.Event()).set()
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            if self.barrier and len(self.model_owners) < 2:
                await asyncio.wait_for(self.release.wait(), 2)
            elif self.barrier:
                self.release.set()
            if rid in self.stall_runs:
                await asyncio.wait_for(self.release.wait(), 3)
            if rid in self.fail_runs:
                return None
            await asyncio.sleep(0)
            if self.use_tool and not any(m["role"] == "tool" for m in data["messages"]):
                return super().reply(data)
            return Message(role="assistant", content=f"summary-private-{owner}")
        finally:
            self.active -= 1

    async def run(self, context, owner="a", runner_name="default"):
        self.owners[context.run_id] = owner
        binding = InstallationBinding(
            instance_uuid="fixture",
            workspace_uuid=f"workspace-{owner}",
            installation_uuid=f"installation-{owner}",
            runtime_revision=1,
            artifact_digest="1" * 64,
        )
        if binding.installation_uuid not in self.host_slots:
            await self.host.call_action(
                R.ATTACH_PLUGIN_SLOT,
                {"plugin_settings": {"enabled": True, "priority": 0, "plugin_config": {}}},
                timeout=5,
                action_context=binding,
            )
            self.host_slots.add(binding.installation_uuid)
        return [
            RunnerResult.model_validate(item)
            async for item in self.host.call_action_generator(
                R.RUN_RUNNER,
                {"runner_name": runner_name, "context": context.model_dump(mode="json")},
                timeout=5,
                action_context=binding,
            )
        ]


@pytest.fixture(autouse=True)
def scoped_backend(monkeypatch):
    monkeypatch.setattr(base, "BackendProtocolFixture", ScopedHost)


def context(owner, *, streaming=False, tools=False, rid=None):
    ctx = base.run_context(streaming=streaming, tools=tools)
    ctx.run_id = rid or f"run-{owner}"
    ctx.context.conversation_id = "same-conversation"
    ctx.context.available_apis.history_page = True
    ctx.context.available_apis.state = True
    ctx.context.available_apis.run_get = True
    ctx.config["prompt"] = [{"role": "system", "content": f"config-private-{owner}"}]
    ctx.config["model"] = {"primary": "primary", "reasoning": {"primary": "high" if owner == "a" else "low"}}
    ctx.config["timeout"] = 4
    return ctx


def assert_success(results, owner):
    assert results[-1].type == "run.completed"
    assert results[-2].data["message"]["content"] == f"summary-private-{owner}"
    assert [r.sequence for r in results] == list(range(1, len(results) + 1))
    assert len([r for r in results if r.type in {"run.completed", "run.failed"}]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_same_component_concurrent_installations(sdk_runtime, streaming):
    host = sdk_runtime
    host.barrier = True
    # A tool response and B plain response overlap, with the same primary model ID.
    host.use_tool = True
    from langbot_plugin.api.entities.builtin.runner.resources import KnowledgeBaseResource

    contexts = [context(owner, streaming=streaming, tools=True) for owner in ("a", "b")]
    for owner, ctx in zip(("a", "b"), contexts):
        ctx.config["knowledge-bases"] = ["same-kb", "foreign-kb"]
        ctx.resources.knowledge_bases = [KnowledgeBaseResource(kb_id="same-kb", operations=["retrieve"])]
    before = [c.model_dump() for c in contexts]
    results = await asyncio.gather(*(host.run(c, o) for c, o in zip(contexts, ("a", "b"))))
    for owner, output in zip(("a", "b"), results):
        assert_success(output, owner)
        assert output[-1].usage.model_calls == 2
        calls = [d for action, d in host.calls if action == "model" and host.owners[d["run_id"]] == owner]
        assert any(f"config-private-{owner}" in json.dumps(d) for d in calls)
        assert any(f"history-private-{owner}" in json.dumps(d) for d in calls)
        assert any(f"rag-private-{owner}" in json.dumps(d) for d in calls)
        assert any(f"tool-private-{owner}" in json.dumps(d) for d in calls)
    assert host.peak >= 2
    assert [c.model_dump() for c in contexts] == before
    assert {credential for _, credential in host.credentials_used} == {"fixture-credential-a", "fixture-credential-b"}


@pytest.mark.asyncio
async def test_scoped_checkpoint_compaction_and_readback(sdk_runtime):
    host = sdk_runtime
    host.compact = True
    contexts = [context(o) for o in ("a", "b")]
    for ctx in contexts:
        ctx.config.update(
            {
                "context-window-tokens": 1500,
                "context-reserve-tokens": 100,
                "context-keep-recent-tokens": 100,
                "context-summary-tokens": 300,
            }
        )
    results = await asyncio.gather(*(host.run(c, o) for c, o in zip(contexts, ("a", "b"))))
    for o, output in zip(("a", "b"), results):
        assert_success(output, o)
    writes = [(host.owners[d["run_id"]], d["key"]) for action, d in host.calls if action == "state_set"]
    assert {owner for owner, _ in writes} == {"a", "b"}
    for owner, key in writes:
        assert f"summary-private-{owner}" in host.storage[owner, key]["summary"]
    host.compact = False
    again = await asyncio.gather(*(host.run(context(o, rid=f"readback-{o}"), o) for o in ("a", "b")))
    for o, output in zip(("a", "b"), again):
        assert_success(output, o)
        model = next(d for a, d in host.calls if a == "model" and d["run_id"] == f"readback-{o}")
        assert f"summary-private-{o}" in json.dumps(model["messages"])


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["model_failure", "history_failure", "cancel", "deadline"])
async def test_failure_cancel_deadline_do_not_poison_other_installation(sdk_runtime, mode):
    host = sdk_runtime
    a, b = context("a", streaming=True), context("b", streaming=True)
    if mode == "model_failure":
        host.fail_runs.add(a.run_id)
    elif mode == "history_failure":
        host.history_failure.add(a.run_id)
    else:
        host.stall_runs.add(a.run_id)
        host.model_started[a.run_id] = asyncio.Event()
        if mode == "deadline":
            import time

            a.runtime.deadline_at = time.time() + 0.3
    task_a = asyncio.create_task(host.run(a, "a"))
    task_b = asyncio.create_task(host.run(b, "b"))
    if mode == "cancel":
        await asyncio.wait_for(host.model_started[a.run_id].wait(), 2)
        host.cancel_runs.add(a.run_id)
    try:
        output_a, output_b = await asyncio.gather(task_a, task_b)
        assert output_a[-1].type == "run.failed"
        assert_success(output_b, "b")
        if mode == "cancel":
            assert output_a[-1].data["code"] == "cancelled"
        if mode == "deadline":
            assert output_a[-1].data["code"] == "runner.timeout"
        assert_success(await host.run(context("a", rid="a-recovery"), "a"), "a")
    finally:
        # Cancelling an RPC waiter need not cancel the remote Host model action.
        # Explicitly release our bounded simulated upstream before teardown.
        host.release.set()
        await asyncio.gather(task_a, task_b, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("resource", ["model", "model_operation", "tool", "kb"])
async def test_scope_grants_not_foreign_config(sdk_runtime, resource):
    host = sdk_runtime
    ctx = context("a")
    if resource == "model":
        ctx.resources.models = []
    elif resource == "model_operation":
        ctx.resources.models[0].operations = ["count_tokens"]
    elif resource == "tool":
        host.use_tool = True
    elif resource == "kb":
        ctx.config["knowledge-bases"] = ["foreign-kb"]
    result = await host.run(ctx)
    if resource in {"model", "model_operation"}:
        assert result[-1].type == "run.failed"
        assert not any(a == "model" for a, _ in host.calls)
    elif resource == "tool":
        assert not any(a == "call_tool" for a, _ in host.calls)
    else:
        assert_success(result, "a")
        assert not any(a == "retrieve" for a, _ in host.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("denied_a", [False, True])
@pytest.mark.parametrize("automatic_reply", [False, True])
async def test_scoped_box_binding_and_exports(sdk_runtime, denied_a, automatic_reply):
    from langbot_plugin.api.entities.builtin.runner.resources import ToolResource

    host = sdk_runtime

    @host.host.action(P.GET_BOX_STATUS)
    async def status(data):
        owner = host.record("box_status", data)
        return ActionResponse.success(
            {"enabled": True, "available": not (denied_a and owner == "a"), "reason": "fixture denial"}
        )

    @host.host.action(P.ACQUIRE_BOX)
    async def acquire(data):
        owner = host.record("box_acquire", data)
        assert data["reuse_key"] == "global"  # deliberately identical across installations
        return ActionResponse.success({"id": f"box-{owner}", "status": "ready"})

    @host.host.action(P.BIND_BOX)
    async def bind(data):
        owner = host.record("box_bind", data)
        assert data["box_id"] == f"box-{owner}"
        return ActionResponse.success({"box_id": f"box-{owner}", "inbox": f"/in/{owner}", "outbox": f"/out/{owner}"})

    @host.host.action(P.EXPORT_BOX_FILES)
    async def export(data):
        owner = host.record("box_export", data)
        assert data["paths"] == [f"/out/{owner}/result.txt"]
        return ActionResponse.success(
            {"items": [{"id": f"file-{owner}", "name": "result.txt", "type": "File", "size": 1}]}
        )

    @host.host.action(P.GET_TOOL_DETAIL)
    async def detail(data):
        host.record("tool_detail", data)
        return ActionResponse.success(
            {"tool": {"name": "exec", "description": "fixture", "parameters": {"type": "object"}}}
        )

    @host.host.action(P.CALL_PLATFORM_API)
    async def reply_files(data):
        owner = host.record("reply_files", data)
        assert data["file_ids"] == [f"file-{owner}"]
        return ActionResponse.success({"result": {"ok": True}})

    original_model = host.model

    async def export_model(data):
        answer = await original_model(data)
        if not any(m["role"] == "tool" for m in data["messages"]):
            owner = host.owners[data["run_id"]]
            return Message(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "export",
                        "type": "function",
                        "function": {
                            "name": "export_box_files",
                            "arguments": json.dumps({"paths": [f"/out/{owner}/result.txt"]}),
                        },
                    }
                ],
            )
        return answer

    host.model = export_model
    contexts = [context(o) for o in ("a", "b")]
    for ctx in contexts:
        ctx.delivery.automatic_reply = automatic_reply
        ctx.context.available_apis.box = True
        ctx.config["box-session-id-template"] = "{global}"
        ctx.resources.tools = [ToolResource(tool_name="exec", operations=["detail", "call"])]
    results = await asyncio.gather(*(host.run(c, o) for c, o in zip(contexts, ("a", "b"))))
    for owner, output in zip(("a", "b"), results):
        if denied_a and owner == "a":
            assert_success(output, owner)
            assert not output[-2].data.get("file_ids")
            assert not any(
                action in {"box_acquire", "box_bind", "box_export"} and host.owners[d["run_id"]] == owner
                for action, d in host.calls
            )
            assert any(
                result.type == "tool.call.completed" and "fixture denial" in json.dumps(result.data)
                for result in output
            )
        else:
            assert_success(output, owner)
            assert output[-2].data["file_ids"] == ([f"file-{owner}"] if automatic_reply else [])
            assert (
                any(action == "reply_files" and host.owners[d["run_id"]] == owner for action, d in host.calls)
                is not automatic_reply
            )
            model = next(d for action, d in host.calls if action == "model" and host.owners[d["run_id"]] == owner)
            assert f"/out/{owner}/" not in json.dumps(model["messages"])
            assert f"/out/{'b' if owner == 'a' else 'a'}/" not in json.dumps(model["messages"])


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_text_only_with_sandbox_tools_does_not_acquire_box(sdk_runtime, streaming):
    from langbot_plugin.api.entities.builtin.runner.resources import ToolResource

    host = sdk_runtime

    @host.host.action(P.GET_BOX_STATUS)
    async def status(data):
        host.record("unexpected_box_status", data)
        raise AssertionError("text-only run must not contact Box")

    @host.host.action(P.GET_TOOL_DETAIL)
    async def detail(data):
        host.record("tool_detail", data)
        return ActionResponse.success(
            {"tool": {"name": "exec", "description": "fixture", "parameters": {"type": "object"}}}
        )

    ctx = context("a", streaming=streaming)
    ctx.context.available_apis.box = True
    ctx.resources.tools = [ToolResource(tool_name="exec", operations=["detail", "call"])]
    output = await host.run(ctx, "a")
    assert_success(output, "a")
    assert not any("box" in action for action, _ in host.calls)
    assert not output[-2].data.get("file_ids")
