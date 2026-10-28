"""Tests for the LangBot-native agent core loop."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from langbot_plugin.api.entities.builtin.provider.message import FunctionCall, Message, MessageChunk, ToolCall
from langbot_plugin.api.entities.builtin.runner.errors import AgentAPIError, AgentAPIException
from langbot_plugin.api.entities.builtin.runner.steering import SteeringPullResult
from langbot_plugin.api.proxies.runner import PermissionDeniedError

from pkg.agent_core import (
    AgentLoop,
    AgentLoopEventType,
    AgentLoopHooks,
    LangBotContextHooks,
    LangBotModelAdapter,
    LangBotToolExecutor,
    ModelTurnEvent,
    ModelTurnResult,
    ToolCallRequest,
    ToolExecutionMode,
)
from pkg.agent_core.langbot import LangBotSteeringPuller
from pkg.context_pipeline import ContextBudget
from pkg.model_calling import ModelCallError, StreamingModelCaller


async def _collect_events(loop: AgentLoop):
    return [event async for event in loop.run()]


@pytest.mark.asyncio
async def test_steering_puller_accepts_sdk_result_models():
    """Host steering_pull returns SDK DTOs, not plain dicts."""

    class SteeringAPI:
        async def steering_pull(self, mode="all"):
            assert mode == "all"
            return SteeringPullResult.model_validate(
                {
                    "items": [
                        {
                            "claimed_run_id": "run-1",
                            "runner_id": "plugin:langbot-team/LocalAgent/default",
                            "event": {
                                "event_id": "evt-follow-up",
                                "event_type": "message.received",
                                "source": "host_adapter",
                            },
                            "input": {
                                "text": "follow-up sentinel",
                                "contents": [],
                                "attachments": [],
                            },
                        }
                    ]
                }
            )

    messages = await LangBotSteeringPuller(SteeringAPI()).pull_messages(mode="all")

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "follow-up sentinel"


@pytest.mark.asyncio
async def test_steering_puller_treats_permission_denied_as_authoritative():
    """The public proxy authorization gate is authoritative for steering."""

    class SteeringAPI:
        run_id = "run-1"

        async def steering_pull(self, mode="all"):
            raise PermissionDeniedError("steering_pull is not available locally")

    messages = await LangBotSteeringPuller(SteeringAPI()).pull_messages(mode="all")

    assert messages == []


@pytest.mark.asyncio
async def test_steering_puller_noops_when_sdk_method_missing():
    """Older SDK proxies without steering_pull degrade to no-op."""

    class SteeringAPI:
        run_id = "run-1"

    messages = await LangBotSteeringPuller(SteeringAPI()).pull_messages(mode="all")

    assert messages == []


def test_tool_call_request_generates_uuid_ids_for_raw_calls_without_id():
    request = ToolCallRequest.from_raw({"function": {"name": "search", "arguments": "{}"}})

    assert request.id.startswith("call_")
    assert request.id != ToolCallRequest.from_raw({"function": {"name": "search", "arguments": "{}"}}).id


@pytest.mark.asyncio
async def test_streaming_loop_emits_turn_message_and_tool_events():
    """The core loop exposes a Pi-style lifecycle independent from RunnerResult."""

    class FakeAPI:
        def __init__(self):
            self.call_tool = AsyncMock(return_value={"value": "tool-result"})
            self.stream_calls = 0

        def invoke_llm_stream(self, *args, **kwargs):
            self.stream_calls += 1

            async def stream():
                if self.stream_calls == 1:
                    yield MessageChunk(
                        role="assistant",
                        content="Checking",
                        is_final=True,
                        tool_calls=[
                            ToolCall(
                                id="call-1",
                                type="function",
                                function=FunctionCall(name="allowed_tool", arguments='{"arg": "value"}'),
                            )
                        ],
                    )
                else:
                    yield MessageChunk(role="assistant", content="Done", is_final=True)

            return stream()

    api = FakeAPI()
    loop = AgentLoop(
        model_adapter=LangBotModelAdapter(api),
        tool_executor=LangBotToolExecutor(api, {"allowed_tool"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Use the tool")],
        tools=[],
        streaming=True,
        max_tool_iterations=10,
    )

    events = [event async for event in loop.run()]
    event_types = [event.type for event in events]

    assert event_types == [
        AgentLoopEventType.AGENT_START,
        AgentLoopEventType.TURN_START,
        AgentLoopEventType.MESSAGE_START,
        AgentLoopEventType.MESSAGE_UPDATE,
        AgentLoopEventType.MESSAGE_END,
        AgentLoopEventType.TOOL_EXECUTION_START,
        AgentLoopEventType.TOOL_EXECUTION_END,
        AgentLoopEventType.MESSAGE_START,
        AgentLoopEventType.MESSAGE_END,
        AgentLoopEventType.TURN_END,
        AgentLoopEventType.TURN_START,
        AgentLoopEventType.MESSAGE_START,
        AgentLoopEventType.MESSAGE_UPDATE,
        AgentLoopEventType.MESSAGE_END,
        AgentLoopEventType.TURN_END,
        AgentLoopEventType.AGENT_END,
    ]

    deltas = [
        event.chunk.content
        for event in events
        if event.type == AgentLoopEventType.MESSAGE_UPDATE and event.chunk is not None
    ]
    assert deltas == ["Checking", "CheckingDone"]
    api.call_tool.assert_awaited_once_with(tool_name="allowed_tool", parameters={"arg": "value"})


@pytest.mark.asyncio
async def test_loop_aggregates_usage_across_tool_turns():
    """The loop carries aggregate model usage to the terminal event."""

    class UsageAPI:
        def __init__(self):
            self.call_tool = AsyncMock(return_value={"value": "tool-result"})
            self.stream_calls = 0

        def invoke_llm_stream_events(self, *args, **kwargs):
            self.stream_calls += 1

            async def stream():
                if self.stream_calls == 1:
                    yield MessageChunk(
                        role="assistant",
                        content="Checking",
                        is_final=True,
                        tool_calls=[
                            ToolCall(
                                id="call-1",
                                type="function",
                                function=FunctionCall(name="allowed_tool", arguments='{"arg": "value"}'),
                            )
                        ],
                    )
                    yield {"usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}}
                else:
                    yield MessageChunk(role="assistant", content="Done", is_final=True)
                    yield {"usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}}

            return stream()

    api = UsageAPI()
    loop = AgentLoop(
        model_adapter=LangBotModelAdapter(api),
        tool_executor=LangBotToolExecutor(api, {"allowed_tool"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Use the tool")],
        tools=[],
        streaming=True,
        max_tool_iterations=10,
    )

    events = [event async for event in loop.run()]
    assert events[-1].type == AgentLoopEventType.AGENT_END
    assert events[-1].usage == {
        "model_calls": 2,
        "turns": [
            {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
        ],
        "prompt_tokens": 12,
        "completion_tokens": 5,
        "total_tokens": 17,
    }


@pytest.mark.asyncio
async def test_streaming_model_empty_final_chunk_falls_back():
    class StreamingAPI:
        def __init__(self):
            self.model_ids: list[str] = []

        def invoke_llm_stream(self, *, llm_model_uuid, messages, funcs, remove_think, reasoning_level):
            self.model_ids.append(llm_model_uuid)

            async def stream():
                if llm_model_uuid == "model-1":
                    yield MessageChunk(role="assistant", content="", is_final=True)
                    return
                yield MessageChunk(role="assistant", content="fallback response", is_final=True)

            return stream()

    api = StreamingAPI()
    caller = StreamingModelCaller(
        api,
        model_ids=["model-1", "model-2"],
        messages=[Message(role="user", content="hello")],
    )

    chunks = [chunk async for chunk, _ in caller.stream()]

    assert api.model_ids == ["model-1", "model-2"]
    assert chunks[-1].content == "fallback response"
    assert caller.get_committed_model_id() == "model-2"


@pytest.mark.asyncio
async def test_streaming_model_empty_normal_stop_commits_and_preserves_usage():
    class StreamingAPI:
        def __init__(self):
            self.model_ids = []

        async def invoke_llm_stream_events(self, *, llm_model_uuid, **kwargs):
            self.model_ids.append(llm_model_uuid)
            yield {"chunk": MessageChunk(role="assistant", content=" ", is_final=False)}
            yield {
                "chunk": MessageChunk(
                    role="assistant", content="", is_final=True, provider_specific_fields={"finish_reason": "stop"}
                )
            }
            yield {"usage": {"prompt_tokens": 20, "completion_tokens": 1, "total_tokens": 21}}

    api = StreamingAPI()
    caller = StreamingModelCaller(
        api, model_ids=["model-1", "model-2"], messages=[Message(role="user", content="hello")]
    )

    chunks = [chunk async for chunk, _ in caller.stream()]

    assert api.model_ids == ["model-1"]
    assert caller.get_committed_model_id() == "model-1"
    assert chunks[-1].is_final
    assert not caller.get_tool_calls()
    assert caller.get_usage()["total_tokens"] == 21


@pytest.mark.asyncio
async def test_streaming_model_all_empty_final_chunks_fail():
    class StreamingAPI:
        def invoke_llm_stream(self, *, llm_model_uuid, messages, funcs, remove_think, reasoning_level):
            async def stream():
                yield MessageChunk(role="assistant", content="", is_final=True)

            return stream()

    caller = StreamingModelCaller(
        StreamingAPI(),
        model_ids=["model-1", "model-2"],
        messages=[Message(role="user", content="hello")],
    )

    with pytest.raises(ModelCallError, match="All models failed"):
        async for _chunk, _ in caller.stream():
            pass


@pytest.mark.asyncio
async def test_streaming_loop_pulls_steering_after_tool_batch():
    class RecordingModelAdapter:
        def __init__(self):
            self.turns = 0
            self.messages_by_turn: list[list[Message]] = []

        async def stream_turn(self, *, model_ids, messages, tools, visible_prefix=""):
            self.messages_by_turn.append([message.model_copy(deep=True) for message in messages])
            self.turns += 1

            if self.turns == 1:
                result = ModelTurnResult(
                    message=Message(
                        role="assistant",
                        content="Need tool",
                        tool_calls=[
                            ToolCallRequest(
                                id="call-sleep",
                                name="sleep_tool",
                                arguments="{}",
                            ).to_tool_call()
                        ],
                    ),
                    tool_calls=[
                        ToolCallRequest(
                            id="call-sleep",
                            name="sleep_tool",
                            arguments="{}",
                        )
                    ],
                    committed_model_id="model-1",
                    visible_content="Need tool",
                )
                yield ModelTurnEvent.message_delta(MessageChunk(role="assistant", content="Need tool", is_final=True))
                yield ModelTurnEvent.message_end(result)
                return

            saw_followup = any(
                message.role == "user" and message.content == "steering follow-up" for message in messages
            )
            content = "saw steering follow-up" if saw_followup else "missing steering follow-up"
            yield ModelTurnEvent.message_delta(MessageChunk(role="assistant", content=content, is_final=True))
            yield ModelTurnEvent.message_end(
                ModelTurnResult(
                    message=Message(role="assistant", content=content),
                    tool_calls=[],
                    committed_model_id="model-1",
                    visible_content=content,
                )
            )

    class ToolAPI:
        async def call_tool(self, *, tool_name, parameters):
            return {"value": "done"}

    class SteeringPuller:
        def __init__(self):
            self.calls = 0

        async def pull_messages(self, *, mode="all"):
            self.calls += 1
            if self.calls == 1:
                return [Message(role="user", content="steering follow-up")]
            return []

    class NoopTokenCounter:
        async def count(self, messages: list[Message]) -> int:
            return 0

    model_adapter = RecordingModelAdapter()
    steering_puller = SteeringPuller()
    loop = AgentLoop(
        model_adapter=model_adapter,
        tool_executor=LangBotToolExecutor(ToolAPI(), {"sleep_tool"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Use the tool")],
        tools=[],
        streaming=True,
        max_tool_iterations=10,
        hooks=LangBotContextHooks(
            ContextBudget(window_tokens=0, reserve_tokens=0),
            token_counter=NoopTokenCounter(),
            steering_puller=steering_puller,
        ),
    )

    events = await _collect_events(loop)

    assert steering_puller.calls == 2
    assert len(model_adapter.messages_by_turn) == 2
    assert any(
        message.role == "user" and message.content == "steering follow-up"
        for message in model_adapter.messages_by_turn[1]
    )
    assert any(
        event.type == AgentLoopEventType.MESSAGE_END
        and event.message is not None
        and event.message.content == "saw steering follow-up"
        for event in events
    )


@pytest.mark.asyncio
async def test_streaming_tool_follow_up_strips_thinking_from_model_context():
    class FakeAPI:
        def __init__(self):
            self.call_tool = AsyncMock(return_value={"value": "tool-result"})
            self.stream_calls: list[list[Message]] = []

        def invoke_llm_stream(self, *args, **kwargs):
            self.stream_calls.append([message.model_copy(deep=True) for message in kwargs["messages"]])

            async def stream():
                if len(self.stream_calls) == 1:
                    yield MessageChunk(
                        role="assistant",
                        content="<think>private reasoning</think>\nNeed tool",
                        is_final=True,
                        tool_calls=[
                            ToolCall(
                                id="call-1",
                                type="function",
                                function=FunctionCall(name="allowed_tool", arguments='{"arg": "value"}'),
                            )
                        ],
                    )
                else:
                    yield MessageChunk(role="assistant", content="Done", is_final=True)

            return stream()

    api = FakeAPI()
    loop = AgentLoop(
        model_adapter=LangBotModelAdapter(api),
        tool_executor=LangBotToolExecutor(api, {"allowed_tool"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Use the tool")],
        tools=[],
        streaming=True,
        max_tool_iterations=10,
    )

    events = await _collect_events(loop)

    deltas = [
        event.chunk.content
        for event in events
        if event.type == AgentLoopEventType.MESSAGE_UPDATE and event.chunk is not None
    ]
    assert any("<think>private reasoning</think>" in delta for delta in deltas)
    follow_up_messages = api.stream_calls[1]
    assistant_with_tool = next(message for message in follow_up_messages if message.role == "assistant")
    assert assistant_with_tool.content == "Need tool"
    assert assistant_with_tool.tool_calls is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_loop_executes_same_batch_tools_in_parallel_and_preserves_source_order(streaming):
    class BatchModelAdapter:
        def __init__(self):
            self.turns = 0
            self.messages_by_turn: list[list[Message]] = []
            self.tool_calls = [
                ToolCallRequest(id="call-slow", name="slow_tool", arguments='{"value": "slow"}'),
                ToolCallRequest(id="call-fast", name="fast_tool", arguments='{"value": "fast"}'),
            ]

        def _next_turn(self, messages: list[Message]) -> ModelTurnResult:
            self.messages_by_turn.append(list(messages))
            self.turns += 1
            if self.turns == 1:
                return ModelTurnResult(
                    message=Message(
                        role="assistant",
                        content="Need tools",
                        tool_calls=[tool_call.to_tool_call() for tool_call in self.tool_calls],
                    ),
                    tool_calls=self.tool_calls,
                    committed_model_id="model-1",
                    visible_content="Need tools",
                )

            return ModelTurnResult(
                message=Message(role="assistant", content="Done"),
                tool_calls=[],
                committed_model_id="model-1",
                visible_content="Done",
            )

        async def invoke_turn(self, *, model_ids, messages, tools):
            return self._next_turn(messages)

        async def invoke_committed_turn(self, *, committed_model_id, messages, tools):
            return self._next_turn(messages)

        async def stream_turn(self, *, model_ids, messages, tools, visible_prefix=""):
            result = self._next_turn(messages)
            yield ModelTurnEvent.message_delta(
                MessageChunk(role="assistant", content=result.visible_content, is_final=True)
            )
            yield ModelTurnEvent.message_end(result)

    class ConcurrentToolAPI:
        def __init__(self):
            self.active_calls = 0
            self.max_active_calls = 0
            self.both_started = asyncio.Event()

        async def call_tool(self, *, tool_name, parameters):
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
            if self.active_calls == 2:
                self.both_started.set()

            try:
                await self.both_started.wait()
                if tool_name == "slow_tool":
                    await asyncio.sleep(0.05)
                else:
                    await asyncio.sleep(0.001)
                return {"tool": tool_name, "value": parameters["value"]}
            finally:
                self.active_calls -= 1

    model_adapter = BatchModelAdapter()
    api = ConcurrentToolAPI()
    loop = AgentLoop(
        model_adapter=model_adapter,
        tool_executor=LangBotToolExecutor(api, {"slow_tool", "fast_tool"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Use both tools")],
        tools=[],
        streaming=streaming,
        max_tool_iterations=10,
    )

    events = await asyncio.wait_for(_collect_events(loop), timeout=1)

    assert api.max_active_calls == 2

    started_tool_call_ids = [
        event.tool_call_id for event in events if event.type == AgentLoopEventType.TOOL_EXECUTION_START
    ]
    assert started_tool_call_ids == ["call-slow", "call-fast"]

    ended_tool_call_ids = [
        event.tool_call_id for event in events if event.type == AgentLoopEventType.TOOL_EXECUTION_END
    ]
    assert ended_tool_call_ids == ["call-fast", "call-slow"]

    result_message_ids = [
        event.message.tool_call_id
        for event in events
        if event.type == AgentLoopEventType.MESSAGE_END and event.message is not None and event.message.role == "tool"
    ]
    assert result_message_ids == ["call-slow", "call-fast"]

    tool_result_turns = [event for event in events if event.type == AgentLoopEventType.TURN_END and event.tool_results]
    assert len(tool_result_turns) == 1
    assert [message.tool_call_id for message in tool_result_turns[0].tool_results] == ["call-slow", "call-fast"]

    second_model_turn_tool_results = [
        message.tool_call_id for message in model_adapter.messages_by_turn[1] if message.role == "tool"
    ]
    assert second_model_turn_tool_results == ["call-slow", "call-fast"]


@pytest.mark.asyncio
async def test_loop_cancels_parallel_tool_tasks_when_generator_closes():
    class ToolBatchModelAdapter:
        async def invoke_turn(self, *, model_ids, messages, tools):
            return ModelTurnResult(
                message=Message(
                    role="assistant",
                    content="Need tools",
                    tool_calls=[
                        ToolCallRequest(id="call-a", name="tool_a", arguments="{}").to_tool_call(),
                        ToolCallRequest(id="call-b", name="tool_b", arguments="{}").to_tool_call(),
                    ],
                ),
                tool_calls=[
                    ToolCallRequest(id="call-a", name="tool_a", arguments="{}"),
                    ToolCallRequest(id="call-b", name="tool_b", arguments="{}"),
                ],
                committed_model_id="model-1",
            )

    class SleepingToolAPI:
        def __init__(self):
            self.started = asyncio.Event()
            self.cancelled: set[str] = set()
            self.active = 0

        async def call_tool(self, *, tool_name, parameters):
            self.active += 1
            if self.active == 2:
                self.started.set()
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                self.cancelled.add(tool_name)
                raise
            finally:
                self.active -= 1

    api = SleepingToolAPI()
    loop = AgentLoop(
        model_adapter=ToolBatchModelAdapter(),
        tool_executor=LangBotToolExecutor(api, {"tool_a", "tool_b"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Use tools")],
        tools=[],
        streaming=False,
        max_tool_iterations=10,
    )

    collected: list[AgentLoopEventType] = []
    keep_open = asyncio.Event()

    async def consume_until_tools_started():
        async for event in loop.run():
            collected.append(event.type)
            if api.started.is_set():
                await keep_open.wait()

    task = asyncio.create_task(consume_until_tools_started())
    await asyncio.wait_for(api.started.wait(), timeout=1)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert AgentLoopEventType.TOOL_EXECUTION_START in collected
    assert api.cancelled == {"tool_a", "tool_b"}
    assert api.active == 0


@pytest.mark.asyncio
async def test_tool_deadline_exceeded_maps_to_timeout_with_prior_usage():
    class ToolDeadlineModelAdapter:
        def __init__(self):
            self.turns = 0

        async def invoke_turn(self, *, model_ids, messages, tools):
            self.turns += 1
            return ModelTurnResult(
                message=Message(
                    role="assistant",
                    content="Need tool",
                    tool_calls=[ToolCallRequest(id="call-a", name="tool_a", arguments="{}").to_tool_call()],
                ),
                tool_calls=[ToolCallRequest(id="call-a", name="tool_a", arguments="{}")],
                committed_model_id="model-1",
                usage={"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
            )

    class DeadlineToolAPI:
        async def call_tool(self, *, tool_name, parameters):
            raise AgentAPIException(
                AgentAPIError(
                    code="deadline_exceeded",
                    message="Agent run deadline has expired",
                    retryable=True,
                )
            )

    loop = AgentLoop(
        model_adapter=ToolDeadlineModelAdapter(),
        tool_executor=LangBotToolExecutor(DeadlineToolAPI(), {"tool_a"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Use tool")],
        tools=[],
        streaming=False,
        max_tool_iterations=10,
    )

    events = await _collect_events(loop)

    assert events[-1].type == AgentLoopEventType.RUN_FAILED
    assert events[-1].code == "runner.timeout"
    assert events[-1].retryable is True
    assert events[-1].usage == {
        "model_calls": 1,
        "turns": [{"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}],
        "prompt_tokens": 4,
        "completion_tokens": 2,
        "total_tokens": 6,
    }


@pytest.mark.asyncio
async def test_loop_stops_after_tool_batch_when_all_results_terminate():
    class TerminatingModelAdapter:
        def __init__(self):
            self.turns = 0

        async def invoke_turn(self, *, model_ids, messages, tools):
            self.turns += 1
            return ModelTurnResult(
                message=Message(
                    role="assistant",
                    content="Sending now",
                    tool_calls=[ToolCallRequest(id="call-1", name="send_message", arguments="{}").to_tool_call()],
                ),
                tool_calls=[ToolCallRequest(id="call-1", name="send_message", arguments="{}")],
                committed_model_id="model-1",
                visible_content="Sending now",
            )

        async def invoke_committed_turn(self, *, committed_model_id, messages, tools):
            self.turns += 1
            raise AssertionError("terminating tool batch should skip the follow-up model turn")

    class TerminatingAPI:
        async def call_tool(self, *, tool_name, parameters):
            return {"content": "sent", "terminate": True}

    adapter = TerminatingModelAdapter()
    loop = AgentLoop(
        model_adapter=adapter,
        tool_executor=LangBotToolExecutor(TerminatingAPI(), {"send_message"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Send it")],
        tools=[],
        streaming=False,
        max_tool_iterations=10,
    )

    events = await _collect_events(loop)

    assert adapter.turns == 1
    assert events[-1].type == AgentLoopEventType.AGENT_END
    tool_messages = [
        event.message
        for event in events
        if event.type == AgentLoopEventType.MESSAGE_END and event.message is not None and event.message.role == "tool"
    ]
    assert len(tool_messages) == 1
    assert "sent" in tool_messages[0].content
    assert "terminate" not in tool_messages[0].content


@pytest.mark.asyncio
async def test_loop_continues_after_mixed_terminate_tool_batch():
    class MixedModelAdapter:
        def __init__(self):
            self.turns = 0

        async def invoke_turn(self, *, model_ids, messages, tools):
            self.turns += 1
            return ModelTurnResult(
                message=Message(
                    role="assistant",
                    content="Need tools",
                    tool_calls=[
                        ToolCallRequest(id="call-a", name="tool_a", arguments="{}").to_tool_call(),
                        ToolCallRequest(id="call-b", name="tool_b", arguments="{}").to_tool_call(),
                    ],
                ),
                tool_calls=[
                    ToolCallRequest(id="call-a", name="tool_a", arguments="{}"),
                    ToolCallRequest(id="call-b", name="tool_b", arguments="{}"),
                ],
                committed_model_id="model-1",
            )

        async def invoke_committed_turn(self, *, committed_model_id, messages, tools):
            self.turns += 1
            return ModelTurnResult(
                message=Message(role="assistant", content="Done"),
                tool_calls=[],
                committed_model_id=committed_model_id,
                visible_content="Done",
            )

    class MixedAPI:
        async def call_tool(self, *, tool_name, parameters):
            return {"content": tool_name, "terminate": tool_name == "tool_a"}

    adapter = MixedModelAdapter()
    loop = AgentLoop(
        model_adapter=adapter,
        tool_executor=LangBotToolExecutor(MixedAPI(), {"tool_a", "tool_b"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Use tools")],
        tools=[],
        streaming=False,
        max_tool_iterations=10,
    )

    events = await _collect_events(loop)

    assert adapter.turns == 2
    assert events[-1].type == AgentLoopEventType.AGENT_END
    assert any(
        event.type == AgentLoopEventType.MESSAGE_END
        and event.message is not None
        and event.message.role == "assistant"
        and event.message.content == "Done"
        for event in events
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_loop_defaults_to_parallel_without_tool_name_heuristics(streaming):
    class StatefulBatchModelAdapter:
        def __init__(self):
            self.turns = 0
            self.tool_calls = [
                ToolCallRequest(id="call-activate", name="activate", arguments='{"skill_name": "pdf"}'),
                ToolCallRequest(id="call-read", name="read_tool", arguments='{"path": "/workspace/a.txt"}'),
            ]

        def _next_turn(self, messages: list[Message]) -> ModelTurnResult:
            self.turns += 1
            if self.turns == 1:
                return ModelTurnResult(
                    message=Message(
                        role="assistant",
                        content="Need skill",
                        tool_calls=[tool_call.to_tool_call() for tool_call in self.tool_calls],
                    ),
                    tool_calls=self.tool_calls,
                    committed_model_id="model-1",
                    visible_content="Need skill",
                )

            return ModelTurnResult(
                message=Message(role="assistant", content="Done"),
                tool_calls=[],
                committed_model_id="model-1",
                visible_content="Done",
            )

        async def invoke_turn(self, *, model_ids, messages, tools):
            return self._next_turn(messages)

        async def invoke_committed_turn(self, *, committed_model_id, messages, tools):
            return self._next_turn(messages)

        async def stream_turn(self, *, model_ids, messages, tools, visible_prefix=""):
            result = self._next_turn(messages)
            yield ModelTurnEvent.message_delta(
                MessageChunk(role="assistant", content=result.visible_content, is_final=True)
            )
            yield ModelTurnEvent.message_end(result)

    class RecordingToolAPI:
        def __init__(self):
            self.active_calls = 0
            self.max_active_calls = 0
            self.both_started = asyncio.Event()
            self.call_order: list[str] = []

        async def call_tool(self, *, tool_name, parameters):
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
            if self.active_calls == 2:
                self.both_started.set()
            self.call_order.append(tool_name)
            try:
                await self.both_started.wait()
                if tool_name == "activate":
                    await asyncio.sleep(0.05)
                else:
                    await asyncio.sleep(0.001)
                return {"tool": tool_name, "parameters": parameters}
            finally:
                self.active_calls -= 1

    api = RecordingToolAPI()
    loop = AgentLoop(
        model_adapter=StatefulBatchModelAdapter(),
        tool_executor=LangBotToolExecutor(api, {"activate", "read_tool"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Use pdf skill")],
        tools=[],
        streaming=streaming,
        max_tool_iterations=10,
    )

    events = await asyncio.wait_for(_collect_events(loop), timeout=1)

    assert api.max_active_calls == 2
    assert api.call_order == ["activate", "read_tool"]

    started_tool_call_ids = [
        event.tool_call_id for event in events if event.type == AgentLoopEventType.TOOL_EXECUTION_START
    ]
    assert started_tool_call_ids == ["call-activate", "call-read"]

    ended_tool_call_ids = [
        event.tool_call_id for event in events if event.type == AgentLoopEventType.TOOL_EXECUTION_END
    ]
    assert ended_tool_call_ids == ["call-read", "call-activate"]

    result_message_ids = [
        event.message.tool_call_id
        for event in events
        if event.type == AgentLoopEventType.MESSAGE_END and event.message is not None and event.message.role == "tool"
    ]
    assert result_message_ids == ["call-activate", "call-read"]


@pytest.mark.asyncio
async def test_loop_serial_mode_forces_serial_execution_for_ordinary_tools():
    class OrdinaryBatchModelAdapter:
        def __init__(self):
            self.turns = 0
            self.tool_calls = [
                ToolCallRequest(id="call-a", name="tool_a", arguments="{}"),
                ToolCallRequest(id="call-b", name="tool_b", arguments="{}"),
            ]

        async def invoke_turn(self, *, model_ids, messages, tools):
            self.turns += 1
            if self.turns == 1:
                return ModelTurnResult(
                    message=Message(
                        role="assistant",
                        content="Need tools",
                        tool_calls=[tool_call.to_tool_call() for tool_call in self.tool_calls],
                    ),
                    tool_calls=self.tool_calls,
                    committed_model_id="model-1",
                    visible_content="Need tools",
                )
            return ModelTurnResult(
                message=Message(role="assistant", content="Done"),
                tool_calls=[],
                committed_model_id="model-1",
            )

        async def invoke_committed_turn(self, *, committed_model_id, messages, tools):
            return await self.invoke_turn(model_ids=[committed_model_id], messages=messages, tools=tools)

    class RecordingToolAPI:
        def __init__(self):
            self.active_calls = 0
            self.max_active_calls = 0

        async def call_tool(self, *, tool_name, parameters):
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
            try:
                await asyncio.sleep(0.001)
                return {"tool": tool_name}
            finally:
                self.active_calls -= 1

    api = RecordingToolAPI()
    loop = AgentLoop(
        model_adapter=OrdinaryBatchModelAdapter(),
        tool_executor=LangBotToolExecutor(api, {"tool_a", "tool_b"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Use tools")],
        tools=[],
        streaming=False,
        max_tool_iterations=10,
        tool_execution_mode=ToolExecutionMode.SERIAL,
    )

    await _collect_events(loop)

    assert api.max_active_calls == 1


@pytest.mark.asyncio
async def test_loop_runs_pi_style_hooks_around_turns_and_tools():
    class HookedModelAdapter:
        def __init__(self):
            self.turns = 0

        async def invoke_turn(self, *, model_ids, messages, tools):
            self.turns += 1
            return ModelTurnResult(
                message=Message(
                    role="assistant",
                    content="Need tool",
                    tool_calls=[
                        ToolCallRequest(id="call-1", name="allowed_tool", arguments='{"arg": "value"}').to_tool_call()
                    ],
                ),
                tool_calls=[ToolCallRequest(id="call-1", name="allowed_tool", arguments='{"arg": "value"}')],
                committed_model_id="model-1",
                visible_content="Need tool",
            )

        async def invoke_committed_turn(self, *, committed_model_id, messages, tools):
            self.turns += 1
            return ModelTurnResult(
                message=Message(role="assistant", content="Done"),
                tool_calls=[],
                committed_model_id=committed_model_id,
                visible_content="Done",
            )

    class HookAPI:
        async def call_tool(self, *, tool_name, parameters):
            return {"ok": True, "arg": parameters["arg"]}

    class TrackingHooks(AgentLoopHooks):
        def __init__(self):
            self.prepare_model_turn_calls = 0
            self.before_tool_ids: list[str] = []
            self.after_tool_ids: list[str] = []
            self.prepare_next_turn_tool_ids: list[str] = []
            self.stop_checks = 0

        async def prepare_model_turn(self, messages: list[Message]) -> list[Message]:
            self.prepare_model_turn_calls += 1
            return [message.model_copy(deep=True) for message in messages]

        async def before_tool_call(self, prepared):
            self.before_tool_ids.append(prepared.request.id)
            return prepared

        async def after_tool_call(self, outcome):
            self.after_tool_ids.append(outcome.request.id)
            return outcome

        async def should_stop_after_turn(self, result, messages):
            self.stop_checks += 1
            return False

        async def prepare_next_turn(self, messages, result, tool_results):
            self.prepare_next_turn_tool_ids = [message.tool_call_id for message in tool_results]
            return [message.model_copy(deep=True) for message in messages]

    hooks = TrackingHooks()
    loop = AgentLoop(
        model_adapter=HookedModelAdapter(),
        tool_executor=LangBotToolExecutor(HookAPI(), {"allowed_tool"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Use tool")],
        tools=[],
        streaming=False,
        max_tool_iterations=10,
        hooks=hooks,
    )

    events = await _collect_events(loop)

    assert AgentLoopEventType.RUN_FAILED not in [event.type for event in events]
    assert hooks.prepare_model_turn_calls == 2
    assert hooks.before_tool_ids == ["call-1"]
    assert hooks.after_tool_ids == ["call-1"]
    assert hooks.prepare_next_turn_tool_ids == ["call-1"]
    assert hooks.stop_checks == 2


@pytest.mark.asyncio
async def test_loop_converts_before_tool_hook_exception_to_run_failed():
    class ToolRequestModelAdapter:
        async def invoke_turn(self, *, model_ids, messages, tools):
            return ModelTurnResult(
                message=Message(
                    role="assistant",
                    content="",
                    tool_calls=[ToolCallRequest(id="call-1", name="allowed_tool", arguments="{}").to_tool_call()],
                ),
                tool_calls=[ToolCallRequest(id="call-1", name="allowed_tool", arguments="{}")],
                committed_model_id="model-1",
            )

        async def invoke_committed_turn(self, *, committed_model_id, messages, tools):
            raise AssertionError("tool hook failure should stop before next model turn")

    class HookAPI:
        async def call_tool(self, *, tool_name, parameters):
            return {"ok": True}

    class FailingHooks(AgentLoopHooks):
        async def before_tool_call(self, prepared):
            raise RuntimeError("before hook failed")

    loop = AgentLoop(
        model_adapter=ToolRequestModelAdapter(),
        tool_executor=LangBotToolExecutor(HookAPI(), {"allowed_tool"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Use tool")],
        tools=[],
        streaming=False,
        max_tool_iterations=10,
        hooks=FailingHooks(),
    )

    events = await _collect_events(loop)

    assert events[-1].type == AgentLoopEventType.RUN_FAILED
    assert events[-1].code == "runner.tool_error"
    assert "before hook failed" in events[-1].error


@pytest.mark.asyncio
async def test_loop_converts_prepare_next_turn_hook_exception_to_run_failed():
    class ToolRequestModelAdapter:
        async def invoke_turn(self, *, model_ids, messages, tools):
            return ModelTurnResult(
                message=Message(
                    role="assistant",
                    content="",
                    tool_calls=[ToolCallRequest(id="call-1", name="allowed_tool", arguments="{}").to_tool_call()],
                ),
                tool_calls=[ToolCallRequest(id="call-1", name="allowed_tool", arguments="{}")],
                committed_model_id="model-1",
            )

        async def invoke_committed_turn(self, *, committed_model_id, messages, tools):
            raise AssertionError("prepare_next_turn failure should stop before next model turn")

    class HookAPI:
        async def call_tool(self, *, tool_name, parameters):
            return {"ok": True}

    class FailingHooks(AgentLoopHooks):
        async def prepare_next_turn(self, messages, result, tool_results):
            raise RuntimeError("next turn preparation failed")

    loop = AgentLoop(
        model_adapter=ToolRequestModelAdapter(),
        tool_executor=LangBotToolExecutor(HookAPI(), {"allowed_tool"}),
        model_ids=["model-1"],
        messages=[Message(role="user", content="Use tool")],
        tools=[],
        streaming=False,
        max_tool_iterations=10,
        hooks=FailingHooks(),
    )

    events = await _collect_events(loop)

    assert events[-1].type == AgentLoopEventType.RUN_FAILED
    assert events[-1].code == "runner.tool_error"
    assert "next turn preparation failed" in events[-1].error


@pytest.mark.asyncio
@pytest.mark.parametrize("method_name", ["should_stop_after_turn", "after_model_turn"])
async def test_loop_converts_after_model_hook_exception_to_run_failed(method_name):
    class DoneModelAdapter:
        async def invoke_turn(self, *, model_ids, messages, tools):
            return ModelTurnResult(
                message=Message(role="assistant", content="Done"),
                tool_calls=[],
                committed_model_id="model-1",
                visible_content="Done",
            )

    class FailingHooks(AgentLoopHooks):
        async def should_stop_after_turn(self, result, messages):
            if method_name == "should_stop_after_turn":
                raise RuntimeError("stop hook failed")
            return False

        async def after_model_turn(self, result, messages):
            if method_name == "after_model_turn":
                raise RuntimeError("after model hook failed")
            return [message.model_copy(deep=True) for message in messages]

    loop = AgentLoop(
        model_adapter=DoneModelAdapter(),
        tool_executor=LangBotToolExecutor(AsyncMock(), set()),
        model_ids=["model-1"],
        messages=[Message(role="user", content="hello")],
        tools=[],
        streaming=False,
        max_tool_iterations=10,
        hooks=FailingHooks(),
    )

    events = await _collect_events(loop)

    assert events[-1].type == AgentLoopEventType.RUN_FAILED
    assert events[-1].code == "runner.error"
    assert "hook failed" in events[-1].error


@pytest.mark.asyncio
async def test_non_streaming_loop_recovers_context_overflow_before_visible_failure():
    class OverflowModelAdapter:
        def __init__(self):
            self.calls: list[list[Message]] = []

        async def invoke_turn(self, *, model_ids, messages, tools):
            self.calls.append([message.model_copy(deep=True) for message in messages])
            if len(self.calls) == 1:
                raise ModelCallError("context length exceeded", retryable=True)
            return ModelTurnResult(
                message=Message(role="assistant", content="Recovered"),
                tool_calls=[],
                committed_model_id="model-1",
                visible_content="Recovered",
            )

        async def invoke_committed_turn(self, *, committed_model_id, messages, tools):
            raise AssertionError("committed turn should not be used")

    class RecoveryHooks(AgentLoopHooks):
        def __init__(self):
            self.recover_calls = 0

        async def recover_context_overflow(self, messages: list[Message], error: Exception) -> list[Message] | None:
            self.recover_calls += 1
            return [Message(role="user", content="short retry context")]

    model_adapter = OverflowModelAdapter()
    hooks = RecoveryHooks()
    loop = AgentLoop(
        model_adapter=model_adapter,
        tool_executor=LangBotToolExecutor(AsyncMock(), set()),
        model_ids=["model-1"],
        messages=[Message(role="user", content="long context")],
        tools=[],
        streaming=False,
        max_tool_iterations=10,
        hooks=hooks,
    )

    events = await _collect_events(loop)

    assert hooks.recover_calls == 1
    assert len(model_adapter.calls) == 2
    assert model_adapter.calls[1][0].content == "short retry context"
    assert [event.type for event in events].count(AgentLoopEventType.TURN_START) == 1
    assert AgentLoopEventType.RUN_FAILED not in [event.type for event in events]
