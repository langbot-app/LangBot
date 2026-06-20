"""Plugin-runtime invocation for AgentRunner executions."""

from __future__ import annotations

import asyncio
import time
import traceback
import typing

from langbot_plugin.entities.io.errors import ActionCallTimeoutError

from ...core import app
from .context_builder import AgentRunContextPayload
from .descriptor import AgentRunnerDescriptor
from .errors import RunnerExecutionError


class AgentRunnerInvoker:
    """Invoke an AgentRunner through the plugin runtime.

    This keeps runtime transport, deadline enforcement, and transport error
    mapping out of the orchestration state machine.
    """

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def invoke(
        self,
        descriptor: AgentRunnerDescriptor,
        context: AgentRunContextPayload,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Invoke the runner and yield raw result dictionaries."""
        if not self.ap.plugin_connector.is_enable_plugin:
            raise RunnerExecutionError(
                descriptor.id,
                'Plugin system is disabled',
                retryable=False,
            )

        try:
            gen = self.ap.plugin_connector.run_agent(
                plugin_author=descriptor.plugin_author,
                plugin_name=descriptor.plugin_name,
                runner_name=descriptor.runner_name,
                context=context,
            )

            while True:
                try:
                    result_dict = await self._next_with_deadline(gen, descriptor, context)
                except StopAsyncIteration:
                    break
                yield result_dict

        except asyncio.TimeoutError as e:
            raise RunnerExecutionError(
                descriptor.id,
                'Runner timed out (code: runner.timeout)',
                retryable=True,
            ) from e
        except ActionCallTimeoutError as e:
            raise RunnerExecutionError(
                descriptor.id,
                f'{e} (code: runner.timeout)',
                retryable=True,
            ) from e
        except RunnerExecutionError:
            raise
        except Exception as e:
            self.ap.logger.error(
                f'Runner {descriptor.id} unexpected error: {traceback.format_exc()}'
            )
            raise RunnerExecutionError(
                descriptor.id,
                str(e),
                retryable=False,
            )

    async def _next_with_deadline(
        self,
        gen: typing.AsyncGenerator[dict[str, typing.Any], None],
        descriptor: AgentRunnerDescriptor,
        context: AgentRunContextPayload,
    ) -> dict[str, typing.Any]:
        """Read the next runner result while enforcing the run deadline."""
        remaining = self._remaining_deadline_seconds(context)
        if remaining is not None and remaining <= 0:
            await self._close_generator(gen, descriptor)
            raise asyncio.TimeoutError

        try:
            if remaining is None:
                return await anext(gen)
            return await asyncio.wait_for(anext(gen), timeout=remaining)
        except StopAsyncIteration:
            if self._is_deadline_exhausted(context):
                raise asyncio.TimeoutError
            raise
        except asyncio.TimeoutError:
            await self._close_generator(gen, descriptor)
            raise

    def _remaining_deadline_seconds(
        self,
        context: AgentRunContextPayload,
    ) -> float | None:
        runtime = context.get('runtime') or {}
        deadline_at = runtime.get('deadline_at')
        if deadline_at is None:
            return None
        try:
            return float(deadline_at) - time.time()
        except (TypeError, ValueError):
            return None

    def _is_deadline_exhausted(self, context: AgentRunContextPayload) -> bool:
        remaining = self._remaining_deadline_seconds(context)
        return remaining is not None and remaining <= 0

    async def _close_generator(
        self,
        gen: typing.AsyncGenerator[dict[str, typing.Any], None],
        descriptor: AgentRunnerDescriptor,
    ) -> None:
        try:
            await gen.aclose()
        except Exception as e:
            self.ap.logger.warning(f'Failed to close timed-out runner {descriptor.id}: {e}')
