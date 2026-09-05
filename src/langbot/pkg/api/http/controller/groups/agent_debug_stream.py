"""Bounded, cancellable NDJSON transport for Agent debug execution."""

from __future__ import annotations

import asyncio
import contextlib
import json

import quart

from .....agent.runner.errors import (
    AgentRunnerError,
    RunnerExecutionError,
    RunnerNotAuthorizedError,
    RunnerNotFoundError,
    RunnerProtocolError,
)


def debug_stream_response(service, context, agent_uuid: str, payload: dict) -> quart.Response:
    async def stream():
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=32)

        async def on_result(result: dict) -> None:
            await queue.put({'kind': 'result', 'data': result})

        async def execute() -> None:
            try:
                result = await service.debug_agent(context, agent_uuid, payload, on_result=on_result)
                await queue.put({'kind': 'completed', 'data': result})
            except Exception as exc:
                if isinstance(exc, RunnerExecutionError):
                    code, message = exc.error_code or 'runner_execution_failed', exc.message
                elif isinstance(exc, RunnerNotFoundError):
                    code, message = 'runner_not_found', 'The configured Agent runner is unavailable'
                elif isinstance(exc, RunnerNotAuthorizedError):
                    code, message = 'runner_not_authorized', 'The configured Agent runner is not authorized'
                elif isinstance(exc, RunnerProtocolError):
                    code, message = 'runner_protocol_error', 'The Agent runner returned an invalid response'
                elif isinstance(exc, ValueError):
                    code, message = 'invalid_request', str(exc)
                elif isinstance(exc, AgentRunnerError):
                    code, message = 'runner_error', 'The Agent runner could not complete this test'
                else:
                    code, message = 'runner_error', 'The Agent debug execution failed'
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
