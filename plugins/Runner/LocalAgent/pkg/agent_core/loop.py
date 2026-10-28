"""Pi-style agent loop implemented with LangBot-native adapters."""

from __future__ import annotations

import asyncio
import typing
from contextlib import aclosing

from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
from langbot_plugin.api.entities.builtin.resource.tool import LLMTool

from pkg.model_calling import ModelCallError, is_deadline_exceeded_error

from .langbot import LangBotModelAdapter, LangBotToolExecutor
from .types import (
    AgentLoopEvent,
    AgentLoopEventType,
    AgentLoopHooks,
    ModelTurnEventType,
    ModelTurnResult,
    PreparedToolCall,
    ToolCallRequest,
    ToolExecutionMode,
    ToolExecutionOutcome,
)

TOOL_LOOP_LIMIT_MESSAGE = "Tool call iteration limit reached. I stopped before calling more tools."
TOOL_LOOP_LIMIT_TOOL_RESULT = "Tool call was not executed because the runner tool iteration limit was reached."


class AgentLoop:
    """Turn/message/tool lifecycle loop for local-agent.

    The loop is deliberately independent from RunnerResult so the runner can
    keep LangBot protocol adaptation at the boundary.
    """

    def __init__(
        self,
        *,
        model_adapter: LangBotModelAdapter,
        tool_executor: LangBotToolExecutor,
        model_ids: list[str],
        messages: list[Message],
        tools: list[LLMTool],
        streaming: bool,
        max_tool_iterations: int,
        tool_execution_mode: ToolExecutionMode | str = ToolExecutionMode.PARALLEL,
        hooks: AgentLoopHooks | None = None,
    ):
        self.model_adapter = model_adapter
        self.tool_executor = tool_executor
        self.model_ids = list(model_ids)
        self.messages = [message.model_copy(deep=True) for message in messages]
        self.tools = list(tools)
        self.streaming = streaming
        self.max_tool_iterations = max_tool_iterations
        self.tool_execution_mode = self._normalize_tool_execution_mode(tool_execution_mode)
        self.hooks = hooks or AgentLoopHooks()
        self._last_tool_batch_terminates = False
        self._usage: dict[str, typing.Any] | None = None

    @staticmethod
    def _normalize_tool_execution_mode(mode: ToolExecutionMode | str) -> ToolExecutionMode:
        if isinstance(mode, ToolExecutionMode):
            return mode
        try:
            return ToolExecutionMode(str(mode))
        except ValueError:
            return ToolExecutionMode.PARALLEL

    async def run(self) -> typing.AsyncGenerator[AgentLoopEvent, None]:
        if self.streaming:
            async with aclosing(self._run_streaming()) as owned_stream:
                async for event in owned_stream:
                    yield event
            return

        async with aclosing(self._run_non_streaming()) as owned_stream:
            async for event in owned_stream:
                yield event

    async def _execute_prepared_tool_call(
        self,
        index: int,
        prepared: PreparedToolCall,
    ) -> tuple[int, ToolExecutionOutcome]:
        outcome = await self.tool_executor.execute(prepared)
        outcome = await self.hooks.after_tool_call(outcome)
        return index, outcome

    async def _prepare_model_turn(self) -> None:
        messages = await self.hooks.prepare_model_turn(self.messages)
        self.messages = [message.model_copy(deep=True) for message in messages]

    async def _recover_context_overflow(self, error: ModelCallError) -> bool:
        messages = await self.hooks.recover_context_overflow(self.messages, error)
        if messages is None:
            return False
        self.messages = [message.model_copy(deep=True) for message in messages]
        return True

    def _should_execute_serially(self) -> bool:
        return self.tool_execution_mode == ToolExecutionMode.SERIAL

    def _record_usage(self, usage: dict[str, typing.Any] | None) -> None:
        if not usage:
            return
        self._usage = _merge_usage(self._usage, usage)

    def _current_usage(self) -> dict[str, typing.Any] | None:
        return dict(self._usage) if self._usage else None

    async def _execute_prepared_tool_calls_parallel(
        self,
        prepared_calls: list[PreparedToolCall],
    ) -> typing.AsyncGenerator[tuple[int, ToolExecutionOutcome], None]:
        tasks = [
            asyncio.create_task(self._execute_prepared_tool_call(index, prepared))
            for index, prepared in enumerate(prepared_calls)
        ]

        try:
            for completed in asyncio.as_completed(tasks):
                yield await completed
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_tool_batch(
        self,
        pending_tool_calls: typing.Iterable[typing.Any],
        last_model_turn: ModelTurnResult | None,
    ) -> typing.AsyncGenerator[AgentLoopEvent, None]:
        self._last_tool_batch_terminates = False
        prepared_calls: list[PreparedToolCall] = []
        for tool_call in pending_tool_calls:
            prepared = self.tool_executor.prepare(tool_call)
            prepared = await self.hooks.before_tool_call(prepared)
            prepared_calls.append(prepared)

        outcomes_by_source_order: list[ToolExecutionOutcome | None] = [None] * len(prepared_calls)
        if self._should_execute_serially():
            for index, prepared in enumerate(prepared_calls):
                yield AgentLoopEvent.tool_execution_start(prepared.request, prepared.parameters)
                _, outcome = await self._execute_prepared_tool_call(index, prepared)
                outcomes_by_source_order[index] = outcome
                yield AgentLoopEvent.tool_execution_end(outcome)
        else:
            for prepared in prepared_calls:
                yield AgentLoopEvent.tool_execution_start(prepared.request, prepared.parameters)
            async with aclosing(self._execute_prepared_tool_calls_parallel(prepared_calls)) as owned_batch:
                async for index, outcome in owned_batch:
                    outcomes_by_source_order[index] = outcome
                    yield AgentLoopEvent.tool_execution_end(outcome)

        tool_results: list[Message] = []
        for outcome in outcomes_by_source_order:
            if outcome is None or outcome.message is None:
                continue
            self.messages.append(outcome.message)
            tool_results.append(outcome.message)
            yield AgentLoopEvent.message_start(outcome.message)
            yield AgentLoopEvent.message_end(outcome.message)

        if last_model_turn is not None:
            yield AgentLoopEvent.turn_end(last_model_turn.message, tool_results, usage=self._current_usage())
            messages = await self.hooks.prepare_next_turn(self.messages, last_model_turn, tool_results)
            self.messages = [message.model_copy(deep=True) for message in messages]

        outcomes = [outcome for outcome in outcomes_by_source_order if outcome is not None]
        self._last_tool_batch_terminates = bool(outcomes) and all(outcome.terminate for outcome in outcomes)

    async def _complete_tool_loop_limit(
        self,
        pending_tool_calls: typing.Iterable[typing.Any],
        last_model_turn: ModelTurnResult | None,
        *,
        streaming: bool,
    ) -> typing.AsyncGenerator[AgentLoopEvent, None]:
        tool_results: list[Message] = []
        for raw_call in pending_tool_calls:
            request = ToolCallRequest.from_raw(raw_call)
            tool_result = Message(
                role="tool",
                tool_call_id=request.id,
                content=TOOL_LOOP_LIMIT_TOOL_RESULT,
            )
            self.messages.append(tool_result)
            tool_results.append(tool_result)
            yield AgentLoopEvent.message_start(tool_result)
            yield AgentLoopEvent.message_end(tool_result)

        if last_model_turn is not None:
            yield AgentLoopEvent.turn_end(last_model_turn.message, tool_results, usage=self._current_usage())

        final_message = Message(role="assistant", content=TOOL_LOOP_LIMIT_MESSAGE)
        self.messages.append(final_message)
        yield AgentLoopEvent.turn_start()
        yield AgentLoopEvent.message_start(final_message)
        if streaming:
            yield AgentLoopEvent.message_update(
                MessageChunk(role="assistant", content=TOOL_LOOP_LIMIT_MESSAGE, is_final=True)
            )
        yield AgentLoopEvent.message_end(final_message)
        yield AgentLoopEvent.turn_end(final_message, [], usage=self._current_usage())
        yield AgentLoopEvent.agent_end(self.messages, usage=self._current_usage())

    async def _run_streaming(self) -> typing.AsyncGenerator[AgentLoopEvent, None]:
        yield AgentLoopEvent.agent_start()

        committed_model_id: str | None = None
        pending_tool_calls = None
        visible_content_prefix = ""
        tool_iterations = 0
        last_model_turn: ModelTurnResult | None = None

        while True:
            if pending_tool_calls is not None:
                if tool_iterations >= self.max_tool_iterations:
                    async for event in self._complete_tool_loop_limit(
                        pending_tool_calls,
                        last_model_turn,
                        streaming=True,
                    ):
                        yield event
                    return

                tool_iterations += 1
                try:
                    async with aclosing(self._execute_tool_batch(pending_tool_calls, last_model_turn)) as owned_batch:
                        async for event in owned_batch:
                            yield event
                except BaseException as e:
                    if isinstance(e, (asyncio.CancelledError, GeneratorExit)) or not isinstance(e, Exception):
                        raise
                    yield self._tool_batch_failed_event(e)
                    return
                if self._last_tool_batch_terminates:
                    yield AgentLoopEvent.agent_end(self.messages, usage=self._current_usage())
                    return

            if committed_model_id is None:
                turn_model_ids = self.model_ids
            else:
                turn_model_ids = [committed_model_id]

            yield AgentLoopEvent.turn_start()
            yield AgentLoopEvent.message_start(Message(role="assistant", content=""))

            context_retry_used = False
            while True:
                stream_started = False
                try:
                    await self._prepare_model_turn()
                    model_turn: ModelTurnResult | None = None
                    async with aclosing(
                        self.model_adapter.stream_turn(
                            model_ids=turn_model_ids,
                            messages=self.messages,
                            tools=self.tools,
                            visible_prefix=visible_content_prefix,
                        )
                    ) as owned_stream:
                        async for model_event in owned_stream:
                            if model_event.type == ModelTurnEventType.MESSAGE_DELTA and model_event.chunk is not None:
                                stream_started = True
                                yield AgentLoopEvent.message_update(model_event.chunk)
                            elif model_event.type == ModelTurnEventType.MESSAGE_END and model_event.result is not None:
                                model_turn = model_event.result
                    break
                except ModelCallError as e:
                    if not stream_started and not context_retry_used and await self._recover_context_overflow(e):
                        context_retry_used = True
                        continue
                    code = "runner.timeout" if e.is_deadline_exceeded else "runner.llm_error"
                    yield AgentLoopEvent.run_failed(
                        str(e),
                        code=code,
                        retryable=True if code == "runner.timeout" else e.retryable,
                        usage=self._current_usage(),
                    )
                    return
                except Exception as e:
                    yield AgentLoopEvent.run_failed(str(e), code="runner.error", usage=self._current_usage())
                    return

            if model_turn is None:
                yield AgentLoopEvent.run_failed(
                    "Model stream ended without a final message",
                    code="runner.llm_error",
                    usage=self._current_usage(),
                )
                return

            committed_model_id = model_turn.committed_model_id or committed_model_id
            self._record_usage(model_turn.usage)
            self.messages.append(model_turn.message)
            last_model_turn = model_turn
            yield AgentLoopEvent(
                type=AgentLoopEventType.MESSAGE_END,
                message=model_turn.message,
                usage=self._current_usage(),
            )

            try:
                if await self.hooks.should_stop_after_turn(model_turn, self.messages):
                    yield AgentLoopEvent.turn_end(model_turn.message, [], usage=self._current_usage())
                    yield AgentLoopEvent.agent_end(self.messages, usage=self._current_usage())
                    return
                messages_after_turn = await self.hooks.after_model_turn(model_turn, self.messages)
            except Exception as e:
                yield AgentLoopEvent.run_failed(str(e), code="runner.error", usage=self._current_usage())
                return
            has_follow_up_messages = len(messages_after_turn) > len(self.messages)
            self.messages = [message.model_copy(deep=True) for message in messages_after_turn]

            pending_tool_calls = model_turn.tool_calls
            if not pending_tool_calls:
                yield AgentLoopEvent.turn_end(model_turn.message, [], usage=self._current_usage())
                if has_follow_up_messages:
                    pending_tool_calls = None
                    continue
                yield AgentLoopEvent.agent_end(self.messages, usage=self._current_usage())
                return

            visible_content_prefix += model_turn.visible_content

    async def _run_non_streaming(self) -> typing.AsyncGenerator[AgentLoopEvent, None]:
        yield AgentLoopEvent.agent_start()

        committed_model_id: str | None = None
        pending_tool_calls = None
        tool_iterations = 0
        last_model_turn: ModelTurnResult | None = None

        while True:
            if pending_tool_calls is not None:
                if tool_iterations >= self.max_tool_iterations:
                    async for event in self._complete_tool_loop_limit(
                        pending_tool_calls,
                        last_model_turn,
                        streaming=False,
                    ):
                        yield event
                    return

                tool_iterations += 1
                try:
                    async with aclosing(self._execute_tool_batch(pending_tool_calls, last_model_turn)) as owned_batch:
                        async for event in owned_batch:
                            yield event
                except BaseException as e:
                    if isinstance(e, (asyncio.CancelledError, GeneratorExit)) or not isinstance(e, Exception):
                        raise
                    yield self._tool_batch_failed_event(e)
                    return
                if self._last_tool_batch_terminates:
                    yield AgentLoopEvent.agent_end(self.messages, usage=self._current_usage())
                    return

            yield AgentLoopEvent.turn_start()
            yield AgentLoopEvent.message_start(Message(role="assistant", content=""))

            context_retry_used = False
            while True:
                try:
                    await self._prepare_model_turn()
                    if committed_model_id is None:
                        model_turn = await self.model_adapter.invoke_turn(
                            model_ids=self.model_ids,
                            messages=self.messages,
                            tools=self.tools,
                        )
                    else:
                        model_turn = await self.model_adapter.invoke_committed_turn(
                            committed_model_id=committed_model_id,
                            messages=self.messages,
                            tools=self.tools,
                        )
                    break
                except ModelCallError as e:
                    if not context_retry_used and await self._recover_context_overflow(e):
                        context_retry_used = True
                        continue
                    code = "runner.timeout" if e.is_deadline_exceeded else "runner.llm_error"
                    yield AgentLoopEvent.run_failed(
                        str(e),
                        code=code,
                        retryable=True if code == "runner.timeout" else e.retryable,
                        usage=self._current_usage(),
                    )
                    return
                except Exception as e:
                    yield AgentLoopEvent.run_failed(str(e), code="runner.error", usage=self._current_usage())
                    return

            committed_model_id = model_turn.committed_model_id or committed_model_id
            self._record_usage(model_turn.usage)
            self.messages.append(model_turn.message)
            last_model_turn = model_turn
            yield AgentLoopEvent(
                type=AgentLoopEventType.MESSAGE_END,
                message=model_turn.message,
                usage=self._current_usage(),
            )

            try:
                if await self.hooks.should_stop_after_turn(model_turn, self.messages):
                    yield AgentLoopEvent.turn_end(model_turn.message, [], usage=self._current_usage())
                    yield AgentLoopEvent.agent_end(self.messages, usage=self._current_usage())
                    return
                messages_after_turn = await self.hooks.after_model_turn(model_turn, self.messages)
            except Exception as e:
                yield AgentLoopEvent.run_failed(str(e), code="runner.error", usage=self._current_usage())
                return
            has_follow_up_messages = len(messages_after_turn) > len(self.messages)
            self.messages = [message.model_copy(deep=True) for message in messages_after_turn]

            pending_tool_calls = model_turn.tool_calls
            if not pending_tool_calls:
                yield AgentLoopEvent.turn_end(model_turn.message, [], usage=self._current_usage())
                if has_follow_up_messages:
                    pending_tool_calls = None
                    continue
                yield AgentLoopEvent.agent_end(self.messages, usage=self._current_usage())
                return

    def _tool_batch_failed_event(self, error: BaseException) -> AgentLoopEvent:
        code = "runner.timeout" if is_deadline_exceeded_error(error) else "runner.tool_error"
        return AgentLoopEvent.run_failed(
            str(error),
            code=code,
            retryable=code == "runner.timeout",
            usage=self._current_usage(),
        )


def _merge_usage(
    current: dict[str, typing.Any] | None,
    usage: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    merged = dict(current or {})
    calls = int(merged.get("model_calls") or 0) + 1
    merged["model_calls"] = calls

    turns = merged.get("turns")
    if not isinstance(turns, list):
        turns = []
    turns.append(dict(usage))
    merged["turns"] = turns

    for key, value in usage.items():
        if key in {"model_calls", "turns"}:
            continue
        if not _is_number(value):
            if key not in merged:
                merged[key] = value
            continue
        existing = merged.get(key)
        merged[key] = (existing if _is_number(existing) else 0) + value

    return merged


def _is_number(value: typing.Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))
