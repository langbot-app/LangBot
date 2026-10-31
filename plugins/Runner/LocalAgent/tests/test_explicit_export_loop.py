"""Explicit export uses ordinary tool messages and the existing run controls."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langbot_plugin.api.entities.builtin.provider.message import FunctionCall, Message, MessageChunk, ToolCall
from langbot_plugin.api.entities.builtin.runner.box import BoxFile

from components.runner.default import RunDeadline, RunInterruptChecker, _iterate_with_run_controls
from pkg.agent_core import AgentLoop, AgentLoopEventType, LangBotModelAdapter, LangBotToolExecutor
from pkg.box import LocalAgentBox
from tests.test_box import context
from tests.test_box_lazy import api as box_api
from tests.test_runner import make_context


class ScriptedAPI:
    def __init__(self, turns):
        self.turns = iter(turns)
        self.histories = []

    def next_turn(self, messages):
        self.histories.append([m.model_copy(deep=True) for m in messages])
        return next(self.turns)

    async def invoke_llm_with_usage(self, messages, **kwargs):
        return {"message": self.next_turn(messages), "usage": {"total_tokens": 5}}

    async def invoke_llm_stream_events(self, messages, **kwargs):
        turn = self.next_turn(messages)
        yield MessageChunk(role="assistant", content=turn.content, tool_calls=turn.tool_calls, is_final=True)
        yield {"usage": {"total_tokens": 5}}


def export_turn(identifier, content=""):
    return Message(
        role="assistant",
        content=content,
        tool_calls=[
            ToolCall(
                id=identifier,
                type="function",
                function=FunctionCall(name="export_box_files", arguments='{"paths":["/out/a"]}'),
            )
        ],
    )


def setup_loop(streaming, *, budget=10, automatic=True):
    api = ScriptedAPI(
        [export_turn("first", "Draft."), export_turn("retry"), Message(role="assistant", content="Done.")]
    )
    ctx = context()
    ctx.delivery.automatic_reply = automatic
    ctx.export_box_files = AsyncMock(
        side_effect=[RuntimeError("file missing: /out/a"), [BoxFile(id="file", name="a", type="File", size=1)]]
    )
    box = LocalAgentBox(ctx, box_api())
    executor = LangBotToolExecutor(api, set())
    assembly = SimpleNamespace(tools=[], tool_executor=executor)
    box.install_tool(assembly)
    loop = AgentLoop(
        model_adapter=LangBotModelAdapter(api),
        tool_executor=executor,
        model_ids=["model"],
        messages=[Message(role="user", content="Create an attachment")],
        tools=assembly.tools,
        streaming=streaming,
        max_tool_iterations=budget,
    )
    return loop, api, box, ctx


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_export_retry_uses_paired_tool_messages_and_original_usage(streaming):
    loop, api, box, ctx = setup_loop(streaming)
    events = [event async for event in loop.run()]
    assert sum(e.type == AgentLoopEventType.AGENT_END for e in events) == 1
    assert events[-1].usage["total_tokens"] == 15
    assert events[-1].usage["model_calls"] == 3
    assert [m.role for m in api.histories[1]] == ["user", "assistant", "tool"]
    assert api.histories[1][-1].tool_call_id == "first"
    assert "file missing" in api.histories[1][-1].content
    assert api.histories[2][-1].tool_call_id == "retry"
    assert box.file_ids == ["file"] and ctx.export_box_files.await_count == 2
    box.api.get_box_status.assert_awaited_once()
    box.api.acquire_box.assert_awaited_once_with("group_room")
    ctx.bind_box.assert_awaited_once_with("box")
    ctx.import_box_attachments.assert_not_awaited()
    if streaming:
        deltas = [e.chunk.content for e in events if e.type == AgentLoopEventType.MESSAGE_UPDATE]
        assert deltas[0] == "Draft." and deltas[-1] == "Draft.Done."


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_export_retry_cannot_reset_tool_budget(streaming):
    loop, api, box, ctx = setup_loop(streaming, budget=1)
    events = [event async for event in loop.run()]
    ctx.export_box_files.assert_awaited_once()
    assert box.file_ids == [] and len(api.histories) == 2
    assert "limit" in events[-1].messages[-1].content.lower()


@pytest.mark.asyncio
async def test_no_tool_call_means_no_implicit_export():
    loop, api, box, ctx = setup_loop(False)
    api.turns = iter([Message(role="assistant", content="Created a file, not exported.")])
    events = [event async for event in loop.run()]
    assert events[-1].type == AgentLoopEventType.AGENT_END
    ctx.export_box_files.assert_not_called()
    box.api.get_box_status.assert_not_awaited()
    box.api.acquire_box.assert_not_awaited()
    ctx.bind_box.assert_not_awaited()
    assert box.file_ids == []


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("result", [{"output": "done"}, "done"])
async def test_lazy_sandbox_instructions_reach_followup_model(streaming, result):
    loop, api, box, ctx = setup_loop(streaming)
    turn = export_turn("sandbox")
    turn.tool_calls[0].function.name = "exec"
    turn.tool_calls[0].function.arguments = '{"command":"echo done"}'
    api.turns = iter([turn, Message(role="assistant", content="Done.")])
    box.api.call_tool.return_value = result
    loop.tool_executor.api = box
    loop.tool_executor.allowed_tools.add("exec")
    assert ctx.input.contents == []
    events = [event async for event in loop.run()]
    assert events[-1].type == AgentLoopEventType.AGENT_END
    assert "/out/run-1" not in str(api.histories[0])
    followup = api.histories[1][-1]
    assert followup.role == "tool" and followup.tool_call_id == "sandbox"
    assert "/out/run-1/" in followup.content
    assert "explicitly call export_box_files" in followup.content
    assert "no automatic export occurs" in followup.content
    box.api.acquire_box.assert_awaited_once()
    ctx.export_box_files.assert_not_awaited()


@pytest.mark.asyncio
async def test_platform_failure_stops_loop_without_regeneration_or_completion():
    loop, api, box, ctx = setup_loop(False, automatic=False)
    ctx.export_box_files.side_effect = None
    ctx.export_box_files.return_value = [BoxFile(id="file", name="a", type="File", size=1)]
    ctx.reply_files.side_effect = RuntimeError("platform down")
    events = [event async for event in loop.run()]
    assert events[-1].type == AgentLoopEventType.RUN_FAILED
    assert len(api.histories) == 1 and events[-1].usage["total_tokens"] == 5
    assert not any(e.type == AgentLoopEventType.AGENT_END for e in events)


@pytest.mark.asyncio
@pytest.mark.parametrize("control", ["timeout", "cancel"])
async def test_original_run_controls_interrupt_export_tool(control):
    loop, api, box, ctx = setup_loop(False)
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def export(paths):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    ctx.export_box_files.side_effect = export
    checker = RunInterruptChecker(None, make_context())
    deadline = RunDeadline(0.1) if control == "timeout" else None
    events = []

    async def consume():
        async for event in _iterate_with_run_controls(loop.run(), checker, deadline):
            events.append(event)

    task = asyncio.create_task(consume())
    await asyncio.wait_for(started.wait(), timeout=1)
    if control == "cancel":
        task.cancel()
    with pytest.raises(asyncio.TimeoutError if control == "timeout" else asyncio.CancelledError):
        await task
    assert cancelled.is_set() and ctx.export_box_files.await_count == 1
    assert not any(e.type == AgentLoopEventType.AGENT_END for e in events)
