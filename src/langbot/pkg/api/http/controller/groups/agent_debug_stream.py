"""Bounded, cancellable NDJSON transport for Agent debug execution."""

from __future__ import annotations

from .....i18n import t

import asyncio
import contextlib
import json

import quart

from .....agent.runner.errors import (
    RunnerError,
    RunnerExecutionError,
    RunnerNotAuthorizedError,
    RunnerNotFoundError,
    RunnerProtocolError,
)


def debug_stream_response(router, context, agent_uuid: str, payload: dict) -> quart.Response:
    async def stream():
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=32)

        async def execute() -> None:
            application = router.ap
            try:
                async with contextlib.aclosing(
                    router.stream_application(
                        'agent.debug.stream', context, {'agent_uuid': agent_uuid, 'payload': payload}
                    )
                ) as frames:
                    async for frame in frames:
                        await queue.put(frame)
            except Exception as exc:
                if isinstance(exc, RunnerExecutionError):
                    code, message = exc.error_code or 'runner_execution_failed', exc.message
                elif isinstance(exc, RunnerNotFoundError):
                    code, message = 'runner_not_found', t('Agent runner temporarily unavailable. Please try again.')
                elif isinstance(exc, RunnerNotAuthorizedError):
                    code, message = 'runner_not_authorized', t('Agent runner not authorized for this pipeline.')
                elif isinstance(exc, RunnerProtocolError):
                    code, message = 'runner_protocol_error', t('The Agent runner returned an invalid response.')
                elif isinstance(exc, ValueError):
                    code, message = 'invalid_request', str(exc)
                elif isinstance(exc, RunnerError):
                    code, message = 'runner_error', t('Agent runner execution failed.')
                else:
                    logger = getattr(application, 'logger', None)
                    if logger is not None:
                        logger.exception('Agent debug stream execution failed')
                    code, message = 'runner_error', t('Agent runner execution failed.')
                await queue.put({'kind': 'error', 'code': code, 'msg': message})

        task = asyncio.create_task(execute())
        try:
            while True:
                try:
                    frame = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield '\n'
                    continue
                yield json.dumps(frame, ensure_ascii=False) + '\n'
                if frame['kind'] in {'completed', 'error'}:
                    break
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    response = quart.Response(stream(), content_type='application/x-ndjson; charset=utf-8')
    response.timeout = None
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Accel-Buffering'] = 'no'
    return response
