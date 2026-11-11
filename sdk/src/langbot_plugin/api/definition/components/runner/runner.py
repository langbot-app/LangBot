"""Unified plugin Runner supporting streamed execution and typed event handlers."""

from __future__ import annotations

import asyncio
import inspect
from contextlib import suppress
from typing import Any, AsyncGenerator

from langbot_plugin.api.definition.components.base import BaseComponent
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.api.entities.builtin.platform.events import EBAEvent
from langbot_plugin.api.proxies.runner.api import RunnerAPIProxy
from langbot_plugin.api.proxies.runner.tracing import _TracedRunAPI
from langbot_plugin.api.proxies.invocation import (
    bind_invocation,
    current_binding,
    current_config,
)


class Runner(BaseComponent):
    """One execution contract for Agent engines and event-driven plugin logic.

    Override run(ctx), or register typed callbacks in initialize(). Both styles
    receive the same invocation context and use the same result transport.
    """

    __kind__ = "Runner"

    def __init__(self):
        super().__init__()
        self._plugin_runtime_handler = None
        self._plugin_config: dict[str, Any] = {}
        self._plugin_identity: str | None = None
        self.registered_handlers: dict[type[EBAEvent], list] = {}

    def bind_runtime(
        self, *, plugin_runtime_handler, plugin_config=None, plugin_identity=None
    ):
        self._plugin_runtime_handler = plugin_runtime_handler
        self._plugin_config = dict(plugin_config or {})
        self._plugin_identity = plugin_identity

    def get_plugin_config(self) -> dict[str, Any]:
        scoped = current_config(self._plugin_runtime_handler)
        if scoped is not None:
            return dict(scoped)
        return dict(self._plugin_config)

    @property
    def plugin_identity(self) -> str | None:
        return self._plugin_identity

    def get_run_api(self, ctx: RunnerContext) -> RunnerAPIProxy:
        """Construct an API explicitly bound to this invocation."""
        if self._plugin_runtime_handler is None:
            raise RuntimeError("Runner runtime is not bound")
        return RunnerAPIProxy(
            ctx=ctx, plugin_runtime_handler=self._plugin_runtime_handler
        )

    @classmethod
    def get_config_schema(cls) -> list[dict[str, Any]]:
        return []

    def handler(self, event_type: type[EBAEvent]):
        """Register a typed callback; declare supported events in the manifest."""
        if not isinstance(event_type, type) or not issubclass(event_type, EBAEvent):
            raise TypeError("Runner handlers require platform event types")

        def decorator(callback):
            self.registered_handlers.setdefault(event_type, []).append(callback)
            return callback

        return decorator

    async def run(self, ctx: RunnerContext):
        """Default execution dispatches a typed event; override for custom engines."""
        event = ctx.platform_event
        callbacks = self.registered_handlers.get(
            type(event)
        ) or self.registered_handlers.get(EBAEvent)
        if not callbacks:
            raise ValueError(f"No handler registered for {ctx.event.event_type}")
        for callback in callbacks:
            await callback(ctx)

    async def invoke(self, ctx: RunnerContext) -> AsyncGenerator[RunnerResult, None]:
        """Execute with per-invocation APIs, tracing, cancellation and completion."""
        if ctx._api is not None:
            raise RuntimeError("Runner context is already active")
        results: asyncio.Queue[RunnerResult] = asyncio.Queue(maxsize=256)
        ctx._api = _TracedRunAPI(self.get_run_api(ctx), ctx.run_id, results)
        ctx._results = results

        async def execute():
            terminal = False
            execution = self.run(ctx)
            if hasattr(execution, "__aiter__"):
                try:
                    async for result in execution:
                        if not isinstance(result, RunnerResult):
                            raise TypeError("Runner must yield RunnerResult objects")
                        if result.run_id != ctx.run_id:
                            raise ValueError(
                                "Runner result belongs to a different invocation"
                            )
                        await results.put(result)
                        if result.type in {"run.completed", "run.failed"}:
                            terminal = True
                            break
                finally:
                    close = getattr(execution, "aclose", None)
                    if close is not None:
                        await close()
            elif inspect.isawaitable(execution):
                value = await execution
                if value is not None:
                    raise TypeError("Coroutine Runner.run must return None")
            else:
                raise TypeError("Runner.run must be async")
            if not terminal:
                await results.put(RunnerResult.run_completed(ctx.run_id))

        async def execute_bound():
            scoped_config = current_config(self._plugin_runtime_handler)
            with bind_invocation(
                self._plugin_runtime_handler,
                ctx.api,
                config=(
                    self._plugin_config if scoped_config is None else scoped_config
                ),
                binding=current_binding(self._plugin_runtime_handler),
            ):
                await execute()

        task = asyncio.create_task(execute_bound())
        next_result = None
        try:
            while not task.done():
                next_result = asyncio.create_task(results.get())
                done, _ = await asyncio.wait(
                    {task, next_result}, return_when=asyncio.FIRST_COMPLETED
                )
                if next_result in done:
                    yield next_result.result()
                    next_result = None
                else:
                    next_result.cancel()
                    with suppress(asyncio.CancelledError):
                        await next_result
                    next_result = None
            while not results.empty():
                yield results.get_nowait()
            await task
        finally:
            for pending in (next_result, task):
                if pending is not None:
                    pending.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await pending
            ctx._api = None
            ctx._results = None
