"""Local Agent default runner implementation.

Supports:
- Model fallback (primary + fallbacks)
- Streaming and non-streaming
- Tool calling loop with max iterations
- Knowledge retrieval with permission validation
- Protocol v1 RunnerResult output
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import aclosing
from typing import Any, AsyncGenerator

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.runner import (
    RunnerContext,
    RunnerResult,
)

from pkg.agent_core import (
    AgentLoop,
    AgentLoopEvent,
    AgentLoopEventType,
    LangBotModelAdapter,
)
from pkg.box import LocalAgentBox
from pkg.config import get_run_timeout_seconds, model_reasoning_levels
from pkg.run_assembly import AgentRunAssembler, AgentRunAssembly, NoAuthorizedModelError

logger = logging.getLogger(__name__)

CANCELLED_ERROR = "Run cancellation requested"
CANCELLED_CODE = "cancelled"
TIMEOUT_ERROR = "Agent run timed out"
TIMEOUT_CODE = "runner.timeout"
INTERRUPT_CHECK_INTERVAL_SECONDS = 0.5


class RunCancelledError(Exception):
    """Raised internally when Host marks the run cancelled."""


class RunDeadline:
    """Wall-clock deadline shared by assembly, model calls, and tool calls."""

    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = max(0.001, float(timeout_seconds))
        self._deadline = time.monotonic() + self.timeout_seconds

    def remaining(self) -> float:
        return max(0.0, self._deadline - time.monotonic())


class RunInterruptChecker:
    """Poll Host run ledger for cooperative cancellation requests."""

    def __init__(
        self,
        api: Any,
        ctx: RunnerContext,
        *,
        interval_seconds: float = INTERRUPT_CHECK_INTERVAL_SECONDS,
    ):
        self.api = api
        self.ctx = ctx
        self.interval_seconds = max(0.1, interval_seconds)
        self._check_generation = 0
        self._cancelled = asyncio.Event()
        self._check_lock = asyncio.Lock()
        self._watch_lock = asyncio.Lock()
        self._watcher: asyncio.Task | None = None
        available_apis = getattr(getattr(ctx, "context", None), "available_apis", None)
        self.available = bool(getattr(available_apis, "run_get", False)) and callable(getattr(api, "run_get", None))

    async def is_cancelled(self, *, force: bool = False, coalesce: bool = False) -> bool:
        if self._cancelled.is_set():
            return True
        if not self.available:
            return False
        # Hot-path checks never wait for a ledger RPC already in flight.
        if not force:
            return self._cancelled.is_set()
        if coalesce:
            async with self._watch_lock:
                if self._check_lock.locked():
                    # The watcher can await a fresh boundary without issuing another RPC.
                    generation = self._check_generation
                    async with self._check_lock:
                        if generation != self._check_generation:
                            return self._cancelled.is_set()
                if self._cancelled.is_set():
                    return True
                return await self._poll()
        async with self._check_lock:
            if self._cancelled.is_set():
                return True
            # A fresh boundary must not wait for an older background snapshot.
            return await self._poll()

    async def _poll(self) -> bool:
        request = asyncio.ensure_future(self.api.run_get(self.ctx.run_id))
        try:
            # wait_for can swallow cancellation when the RPC completes at
            # the same instant on Python 3.11. Keep task ownership explicit.
            done, _ = await asyncio.wait({request}, timeout=1.0)
            if not done:
                return self._cancelled.is_set()
            run = request.result()
            self._check_generation += 1
            if _run_cancel_requested(run):
                self._cancelled.set()
        except Exception:
            logger.debug("Failed to check AgentRun cancellation state", exc_info=True)
        finally:
            if not request.done():
                request.cancel()
            await asyncio.gather(request, return_exceptions=True)
        return self._cancelled.is_set()

    async def _watch(self):
        while not self._cancelled.is_set():
            await self.is_cancelled(force=True, coalesce=True)
            await asyncio.sleep(self.interval_seconds)

    async def __aenter__(self):
        if self.available:
            self._watcher = asyncio.create_task(self._watch())
        return self

    async def __aexit__(self, *args):
        if self._watcher is not None:
            self._watcher.cancel()
            await asyncio.gather(self._watcher, return_exceptions=True)
            self._watcher = None

    async def wait_for(self, awaitable: Any, *, deadline: RunDeadline | None = None) -> Any:
        """Wait for an awaitable while polling Host cancellation and run timeout."""
        if not self.available and deadline is None:
            return await awaitable

        task = asyncio.ensure_future(awaitable)
        cancellation = asyncio.create_task(self._cancelled.wait())
        temporary_watcher = asyncio.create_task(self._watch()) if self.available and self._watcher is None else None
        try:
            await asyncio.wait(
                {task, cancellation},
                timeout=deadline.remaining() if deadline else None,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if self._cancelled.is_set():
                raise RunCancelledError(CANCELLED_ERROR)
            if not task.done():
                raise asyncio.TimeoutError(TIMEOUT_ERROR)
            return task.result()
        finally:
            pending = [task, cancellation] + ([temporary_watcher] if temporary_watcher else [])
            for future in pending:
                if not future.done():
                    future.cancel()
            await asyncio.gather(*pending, return_exceptions=True)


class RunUsageTracker:
    """Share already observed model usage across run-control cancellation paths."""

    def __init__(self):
        self._usage: dict[str, Any] | None = None

    def update(self, usage: dict[str, Any] | None) -> None:
        if usage is not None:
            self._usage = usage

    def current(self) -> dict[str, Any] | None:
        return dict(self._usage) if self._usage is not None else None


def _run_cancel_requested(run: Any) -> bool:
    if run is None:
        return False
    if isinstance(run, dict):
        return run.get("cancel_requested_at") is not None or run.get("status") == "cancelled"
    return getattr(run, "cancel_requested_at", None) is not None or getattr(run, "status", None) == "cancelled"


class DefaultRunner(Runner):
    """Default Runner for Local Agent.

    Full-featured LLM runner with:
    - Model primary/fallback selection
    - Streaming and non-streaming output
    - Tool calling loop
    - Knowledge retrieval (RAG)

    All resource access goes through RunnerAPIProxy for authorization.
    """

    async def run(self, ctx: RunnerContext) -> AsyncGenerator[RunnerResult, None]:
        async with RunInterruptChecker(self.get_run_api(ctx), ctx) as interrupt_checker:
            async with aclosing(self._run_controlled(ctx, interrupt_checker)) as results:
                async for result in results:
                    yield result

    async def _run_controlled(
        self, ctx: RunnerContext, interrupt_checker: RunInterruptChecker
    ) -> AsyncGenerator[RunnerResult, None]:
        """Run the agent with full LLM capabilities.

        Implementation:
        1. Get authorized models and parse model config
        2. Retrieve knowledge base context (if configured)
        3. Build messages from prompt + history + input
        4. Stream/Invoke LLM with fallback support
        5. Handle tool calling loop
        6. Yield RunnerResult events
        """
        api = self.get_run_api(ctx)
        config = ctx.config if isinstance(ctx.config, dict) else {}
        timeout_seconds = get_run_timeout_seconds(config)
        deadline = RunDeadline(timeout_seconds) if timeout_seconds is not None else None
        usage_tracker = RunUsageTracker()

        if await interrupt_checker.is_cancelled(force=True):
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=CANCELLED_ERROR,
                code=CANCELLED_CODE,
                retryable=False,
            )
            return

        box = LocalAgentBox(ctx, api)
        try:
            needs_box = box.needed()
            if needs_box and ctx.input.attachments:
                await interrupt_checker.wait_for(box.prepare(), deadline=deadline)
            assembly = await interrupt_checker.wait_for(
                AgentRunAssembler(api, ctx).assemble(),
                deadline=deadline,
            )
            if needs_box:
                box.install_tool(assembly)
                assembly.tool_executor.api = box
        except NoAuthorizedModelError:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error="No authorized model for local-agent",
                code="runner.no_model",
            )
            return
        except RunCancelledError:
            yield _cancelled_result(ctx.run_id)
            return
        except asyncio.TimeoutError:
            yield _timeout_result(ctx.run_id)
            return
        except Exception as e:
            logger.exception("Agent run assembly failed")
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=str(e) or "Agent run assembly failed",
                code="runner.error",
                retryable=False,
            )
            return

        if await interrupt_checker.is_cancelled(force=True):
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=CANCELLED_ERROR,
                code=CANCELLED_CODE,
                retryable=False,
            )
            return

        try:
            results = self._run_runner_loop(
                run_id=ctx.run_id,
                api=api,
                assembly=assembly,
                interrupt_checker=interrupt_checker,
                usage_tracker=usage_tracker,
                reasoning_levels=model_reasoning_levels(config),
            )
            async with aclosing(_iterate_with_run_controls(results, interrupt_checker, deadline)) as owned_stream:
                async for result in owned_stream:
                    if box.binding is not None and getattr(result.type, "value", result.type) == "message.completed":
                        result.data["file_ids"] = box.file_ids
                    yield result
                    if _is_terminal_result(result):
                        return
        except RunCancelledError:
            yield _cancelled_result(ctx.run_id, usage=usage_tracker.current())
        except asyncio.TimeoutError:
            yield _timeout_result(ctx.run_id, usage=usage_tracker.current())
        except Exception as e:
            logger.exception("Agent run failed")
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=str(e) or "Agent run failed",
                code="runner.error",
                retryable=False,
                usage=usage_tracker.current(),
            )

    async def _run_runner_loop(
        self,
        run_id: str,
        api: Any,
        assembly: AgentRunAssembly,
        interrupt_checker: RunInterruptChecker | None = None,
        usage_tracker: RunUsageTracker | None = None,
        reasoning_levels: dict[str, str] | None = None,
    ) -> AsyncGenerator[RunnerResult, None]:
        """Run the LangBot-native Pi-style agent loop."""
        loop = AgentLoop(
            model_adapter=LangBotModelAdapter(
                api, remove_think=assembly.remove_think, reasoning_levels=reasoning_levels
            ),
            tool_executor=assembly.tool_executor,
            model_ids=assembly.model_ids,
            messages=assembly.messages,
            tools=assembly.tools,
            streaming=assembly.streaming,
            max_tool_iterations=assembly.max_tool_iterations,
            tool_execution_mode=assembly.tool_execution_mode,
            hooks=assembly.hooks,
        )

        final_message: Message | None = None
        terminal_usage: dict[str, Any] | None = None
        async with aclosing(loop.run()) as owned_stream:
            async for event in owned_stream:
                if event.usage is not None:
                    terminal_usage = event.usage
                    if usage_tracker is not None:
                        usage_tracker.update(event.usage)

                if interrupt_checker is not None and await interrupt_checker.is_cancelled():
                    yield RunnerResult.run_failed(
                        run_id,
                        error=CANCELLED_ERROR,
                        code=CANCELLED_CODE,
                        retryable=False,
                        usage=terminal_usage,
                    )
                    return

                result = self._loop_event_to_result(run_id, event, streaming=assembly.streaming)
                if result is not None:
                    yield result
                    if getattr(result.type, "value", result.type) == "run.failed":
                        return

                    if interrupt_checker is not None and await interrupt_checker.is_cancelled():
                        yield RunnerResult.run_failed(
                            run_id,
                            error=CANCELLED_ERROR,
                            code=CANCELLED_CODE,
                            retryable=False,
                            usage=terminal_usage,
                        )
                        return

                if (
                    event.type == AgentLoopEventType.MESSAGE_END
                    and event.message is not None
                    and event.message.role == "assistant"
                    and not event.message.tool_calls
                ):
                    final_message = event.message

                if event.type == AgentLoopEventType.AGENT_END:
                    if interrupt_checker is not None and await interrupt_checker.is_cancelled(force=True):
                        yield RunnerResult.run_failed(
                            run_id,
                            error=CANCELLED_ERROR,
                            code=CANCELLED_CODE,
                            retryable=False,
                            usage=terminal_usage,
                        )
                        return
                    if final_message is not None:
                        yield RunnerResult.message_completed(run_id, final_message)
                    yield RunnerResult.run_completed(
                        run_id,
                        finish_reason="stop",
                        usage=event.usage or terminal_usage,
                    )

    def _loop_event_to_result(
        self,
        run_id: str,
        event: AgentLoopEvent,
        *,
        streaming: bool,
    ) -> RunnerResult | None:
        if event.type == AgentLoopEventType.MESSAGE_UPDATE and streaming and event.chunk is not None:
            return RunnerResult.message_delta(run_id, event.chunk)

        if event.type == AgentLoopEventType.TOOL_EXECUTION_START and event.tool_call_id and event.tool_name:
            return RunnerResult.tool_call_started(
                run_id,
                tool_call_id=event.tool_call_id,
                tool_name=event.tool_name,
                parameters=event.parameters,
            )

        if event.type == AgentLoopEventType.TOOL_EXECUTION_END and event.tool_call_id and event.tool_name:
            return RunnerResult.tool_call_completed(
                run_id,
                tool_call_id=event.tool_call_id,
                tool_name=event.tool_name,
                result=_tool_event_result_payload(event.result),
                error=event.error,
            )

        if event.type == AgentLoopEventType.RUN_FAILED:
            return RunnerResult.run_failed(
                run_id,
                error=event.error or "Agent loop failed",
                code=event.code or "runner.error",
                retryable=event.retryable,
                usage=event.usage,
            )

        return None


def _tool_event_result_payload(result: Any) -> dict[str, Any] | None:
    if result is None or isinstance(result, dict):
        return result
    return {"value": result}


async def _iterate_with_run_controls(
    results: AsyncGenerator[RunnerResult, None],
    interrupt_checker: RunInterruptChecker,
    deadline: RunDeadline | None,
) -> AsyncGenerator[RunnerResult, None]:
    iterator = results.__aiter__()
    try:
        while True:
            try:
                yield await interrupt_checker.wait_for(iterator.__anext__(), deadline=deadline)
            except StopAsyncIteration:
                return
    except BaseException:
        await iterator.aclose()
        raise


def _cancelled_result(run_id: str, usage: dict[str, Any] | None = None) -> RunnerResult:
    return RunnerResult.run_failed(
        run_id,
        error=CANCELLED_ERROR,
        code=CANCELLED_CODE,
        retryable=False,
        usage=usage,
    )


def _timeout_result(run_id: str, usage: dict[str, Any] | None = None) -> RunnerResult:
    return RunnerResult.run_failed(
        run_id,
        error=TIMEOUT_ERROR,
        code=TIMEOUT_CODE,
        retryable=True,
        usage=usage,
    )


def _is_terminal_result(result: RunnerResult) -> bool:
    result_type = getattr(result.type, "value", result.type)
    return result_type in {"run.failed", "run.completed"}
