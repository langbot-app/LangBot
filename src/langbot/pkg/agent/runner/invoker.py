"""Plugin-runtime invocation for Runner executions."""

from __future__ import annotations

import asyncio
import time
import traceback
import typing

from langbot_plugin.entities.io.errors import ActionCallTimeoutError

from ...core import app
from .context_builder import RunnerContextPayload
from .descriptor import RunnerDescriptor
from .errors import RunnerExecutionError
from .stream_receipts import RunnerStreamReceipts, current_runner_receipts


_BUFFERED_READ_TIMEOUT = 5.0


class RunnerInvoker:
    """Invoke an Runner through the plugin runtime.

    This keeps runtime transport, deadline enforcement, and transport error
    mapping out of the orchestration state machine.
    """

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def invoke(
        self,
        descriptor: RunnerDescriptor,
        context: RunnerContextPayload,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Invoke the runner and yield raw result dictionaries."""
        if not self.ap.plugin_connector.is_enable_plugin:
            raise RunnerExecutionError(
                descriptor.id,
                'Plugin system is disabled',
                retryable=False,
            )

        try:
            gen = self.ap.plugin_connector.run_runner(
                plugin_author=descriptor.plugin_author,
                plugin_name=descriptor.plugin_name,
                runner_name=descriptor.runner_name,
                context=context,
            )

            receipts = RunnerStreamReceipts(context)
            try:
                while True:
                    try:
                        result_dict = await self._next_with_deadline(gen, descriptor, context, receipts)
                    except StopAsyncIteration:
                        break
                    yield result_dict
            finally:
                await self._close_generator(gen, descriptor)

        except asyncio.TimeoutError as e:
            raise RunnerExecutionError(
                descriptor.id,
                'Runner timed out',
                retryable=True,
                error_code='runner.timeout',
            ) from e
        except ActionCallTimeoutError as e:
            raise RunnerExecutionError(
                descriptor.id,
                str(e),
                retryable=True,
                error_code='runner.timeout',
            ) from e
        except RunnerExecutionError:
            raise
        except Exception as e:
            self.ap.logger.error(f'Runner {descriptor.id} unexpected error: {traceback.format_exc()}')
            raise RunnerExecutionError(
                descriptor.id,
                str(e),
                retryable=False,
            )

    async def _next_with_deadline(
        self,
        gen: typing.AsyncGenerator[dict[str, typing.Any], None],
        descriptor: RunnerDescriptor,
        context: RunnerContextPayload,
        receipts: RunnerStreamReceipts | None = None,
    ) -> dict[str, typing.Any]:
        """Read the next runner result while enforcing the run deadline."""
        remaining = receipts.remaining() if receipts is not None else self._remaining_deadline_seconds(context)
        buffered = receipts is not None and receipts.has_pending()
        if remaining is not None and remaining <= 0 and not buffered:
            await self._close_generator(gen, descriptor)
            raise asyncio.TimeoutError

        token = current_runner_receipts.set(receipts)
        try:
            next_result = asyncio.create_task(anext(gen))
        finally:
            current_runner_receipts.reset(token)
        try:
            while True:
                try:
                    if remaining is None:
                        result = await next_result
                    else:
                        # Buffered frames may require transport ACKs before the next yield.
                        result = await asyncio.wait_for(
                            asyncio.shield(next_result),
                            timeout=max(remaining, _BUFFERED_READ_TIMEOUT) if buffered else remaining,
                        )
                except asyncio.TimeoutError:
                    renewed = (
                        receipts.remaining() if receipts is not None else self._remaining_deadline_seconds(context)
                    )
                    if receipts is not None and receipts.has_pending() and not buffered:
                        buffered = True
                        remaining = 0
                        continue
                    if renewed is None:
                        remaining = None
                        continue
                    if renewed > 0:
                        remaining = renewed
                        continue
                    if buffered and receipts.has_pending():
                        raise RunnerExecutionError(
                            descriptor.id, 'host.consume_timeout', error_code='host.consume_timeout'
                        )
                    raise
                self._check_receipt(receipts)
                return result
        except StopAsyncIteration:
            if receipts is not None and receipts.arrivals:
                self._check_receipt(receipts)
            elif self._is_deadline_exhausted(context):
                raise asyncio.TimeoutError
            raise
        except asyncio.TimeoutError:
            next_result.cancel()
            await asyncio.gather(next_result, return_exceptions=True)
            await self._close_generator(gen, descriptor)
            raise
        finally:
            if not next_result.done():
                next_result.cancel()
                await asyncio.gather(next_result, return_exceptions=True)

    def _check_receipt(self, receipts):
        if receipts is None or not receipts.arrivals:
            return
        received_at = receipts.arrivals.popleft()
        receipts.remaining()
        if receipts.deadline is not None and received_at > receipts.deadline:
            raise asyncio.TimeoutError
        delay_ms = (time.monotonic() - received_at) * 1000
        if delay_ms >= 100:
            self.ap.logger.debug(
                f'Slow runner result consumption run={receipts.context.get("run_id")} delay_ms={delay_ms:.1f}'
            )

    def _remaining_deadline_seconds(
        self,
        context: RunnerContextPayload,
    ) -> float | None:
        runtime = context.get('runtime') or {}
        deadline_at = runtime.get('deadline_at')
        if deadline_at is None:
            return None
        try:
            return float(deadline_at) - time.time()
        except (TypeError, ValueError):
            return None

    def _is_deadline_exhausted(self, context: RunnerContextPayload) -> bool:
        remaining = self._remaining_deadline_seconds(context)
        return remaining is not None and remaining <= 0

    async def _close_generator(
        self,
        gen: typing.AsyncGenerator[dict[str, typing.Any], None],
        descriptor: RunnerDescriptor,
    ) -> None:
        try:
            await gen.aclose()
        except Exception as e:
            self.ap.logger.warning(f'Failed to close runner {descriptor.id}: {e}')
