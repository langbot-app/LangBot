"""Standalone HTTP service exposing BoxRuntime as a REST API.

Usage:
    python -m langbot.pkg.box.server [--host 0.0.0.0] [--port 5410]
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging

import pydantic
from aiohttp import web

from .errors import (
    BoxBackendUnavailableError,
    BoxError,
    BoxManagedProcessConflictError,
    BoxManagedProcessNotFoundError,
    BoxSessionConflictError,
    BoxSessionNotFoundError,
    BoxValidationError,
)
from .models import BoxExecutionResult, BoxManagedProcessSpec, BoxSpec
from .runtime import BoxRuntime

logger = logging.getLogger('langbot.box.server')

_ERROR_MAP: dict[type, tuple[int, str]] = {
    BoxValidationError: (400, 'validation_error'),
    BoxSessionNotFoundError: (404, 'session_not_found'),
    BoxSessionConflictError: (409, 'session_conflict'),
    BoxManagedProcessNotFoundError: (404, 'managed_process_not_found'),
    BoxManagedProcessConflictError: (409, 'managed_process_conflict'),
    BoxBackendUnavailableError: (503, 'backend_unavailable'),
}


def _error_response(exc: Exception) -> web.Response:
    for exc_type, (status, code) in _ERROR_MAP.items():
        if isinstance(exc, exc_type):
            return web.json_response(
                {'error': {'code': code, 'message': str(exc)}},
                status=status,
            )
    return web.json_response(
        {'error': {'code': 'internal_error', 'message': str(exc)}},
        status=500,
    )


def _result_to_dict(result: BoxExecutionResult) -> dict:
    return {
        'session_id': result.session_id,
        'backend_name': result.backend_name,
        'status': result.status.value,
        'exit_code': result.exit_code,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'duration_ms': result.duration_ms,
    }


async def handle_exec(request: web.Request) -> web.Response:
    runtime: BoxRuntime = request.app['runtime']
    try:
        body = await request.json()
        session_id = request.match_info['session_id']
        body['session_id'] = session_id
        spec = BoxSpec.model_validate(body)
        result = await runtime.execute(spec)
        return web.json_response(_result_to_dict(result))
    except pydantic.ValidationError as exc:
        return web.json_response(
            {'error': {'code': 'validation_error', 'message': str(exc)}},
            status=400,
        )
    except BoxError as exc:
        return _error_response(exc)


async def handle_create_session(request: web.Request) -> web.Response:
    runtime: BoxRuntime = request.app['runtime']
    try:
        body = await request.json()
        session_id = request.match_info['session_id']
        body['session_id'] = session_id
        spec = BoxSpec.model_validate(body)
        session_info = await runtime.create_session(spec)
        return web.json_response(session_info, status=201)
    except pydantic.ValidationError as exc:
        return web.json_response(
            {'error': {'code': 'validation_error', 'message': str(exc)}},
            status=400,
        )
    except BoxError as exc:
        return _error_response(exc)


async def handle_get_sessions(request: web.Request) -> web.Response:
    runtime: BoxRuntime = request.app['runtime']
    try:
        return web.json_response(runtime.get_sessions())
    except BoxError as exc:
        return _error_response(exc)


async def handle_delete_session(request: web.Request) -> web.Response:
    runtime: BoxRuntime = request.app['runtime']
    session_id = request.match_info['session_id']
    try:
        await runtime.delete_session(session_id)
        return web.json_response({'deleted': session_id})
    except BoxError as exc:
        return _error_response(exc)


async def handle_status(request: web.Request) -> web.Response:
    runtime: BoxRuntime = request.app['runtime']
    try:
        status = await runtime.get_status()
        return web.json_response(status)
    except BoxError as exc:
        return _error_response(exc)


async def handle_health(request: web.Request) -> web.Response:
    runtime: BoxRuntime = request.app['runtime']
    try:
        info = await runtime.get_backend_info()
        return web.json_response(info)
    except BoxError as exc:
        return _error_response(exc)


async def handle_start_managed_process(request: web.Request) -> web.Response:
    runtime: BoxRuntime = request.app['runtime']
    session_id = request.match_info['session_id']
    try:
        body = await request.json()
        spec = BoxManagedProcessSpec.model_validate(body)
        process_info = await runtime.start_managed_process(session_id, spec)
        return web.json_response(process_info, status=201)
    except pydantic.ValidationError as exc:
        return web.json_response(
            {'error': {'code': 'validation_error', 'message': str(exc)}},
            status=400,
        )
    except BoxError as exc:
        return _error_response(exc)


async def handle_get_managed_process(request: web.Request) -> web.Response:
    runtime: BoxRuntime = request.app['runtime']
    session_id = request.match_info['session_id']
    try:
        return web.json_response(runtime.get_managed_process(session_id))
    except BoxError as exc:
        return _error_response(exc)


async def handle_managed_process_ws(request: web.Request) -> web.StreamResponse:
    runtime: BoxRuntime = request.app['runtime']
    session_id = request.match_info['session_id']

    runtime_session = runtime._sessions.get(session_id)
    if runtime_session is None:
        return _error_response(BoxSessionNotFoundError(f'session {session_id} not found'))

    managed_process = runtime_session.managed_process
    if managed_process is None:
        return _error_response(BoxManagedProcessNotFoundError(f'session {session_id} has no managed process'))
    if not managed_process.is_running:
        return _error_response(BoxManagedProcessConflictError(f'managed process in session {session_id} is not running'))

    ws = web.WebSocketResponse(protocols=('mcp',))
    await ws.prepare(request)

    async with managed_process.attach_lock:
        process = managed_process.process
        stdout = process.stdout
        stdin = process.stdin
        if stdout is None or stdin is None:
            await ws.close(message=b'managed process stdio unavailable')
            return ws

        async def _stdout_to_ws() -> None:
            while True:
                line = await stdout.readline()
                if not line:
                    break
                await ws.send_str(line.decode('utf-8', errors='replace').rstrip('\n'))
                runtime_session.info.last_used_at = dt.datetime.now(dt.timezone.utc)

        async def _ws_to_stdin() -> None:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    stdin.write((msg.data + '\n').encode('utf-8'))
                    await stdin.drain()
                    runtime_session.info.last_used_at = dt.datetime.now(dt.timezone.utc)
                elif msg.type in (web.WSMsgType.CLOSE, web.WSMsgType.CLOSING, web.WSMsgType.CLOSED, web.WSMsgType.ERROR):
                    break

        stdout_task = asyncio.create_task(_stdout_to_ws())
        stdin_task = asyncio.create_task(_ws_to_stdin())
        try:
            done, pending = await asyncio.wait(
                [stdout_task, stdin_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                task.result()
        finally:
            await ws.close()

    return ws


def create_app(runtime: BoxRuntime | None = None) -> web.Application:
    """Create the aiohttp Application with all routes.

    If *runtime* is ``None`` a new ``BoxRuntime`` is created using the module
    logger.
    """
    if runtime is None:
        runtime = BoxRuntime(logger=logger)

    app = web.Application()
    app['runtime'] = runtime

    app.router.add_post('/v1/sessions/{session_id}/exec', handle_exec)
    app.router.add_post('/v1/sessions/{session_id}', handle_create_session)
    app.router.add_get('/v1/sessions', handle_get_sessions)
    app.router.add_delete('/v1/sessions/{session_id}', handle_delete_session)
    app.router.add_post('/v1/sessions/{session_id}/managed-process', handle_start_managed_process)
    app.router.add_get('/v1/sessions/{session_id}/managed-process', handle_get_managed_process)
    app.router.add_get('/v1/sessions/{session_id}/managed-process/ws', handle_managed_process_ws)
    app.router.add_get('/v1/status', handle_status)
    app.router.add_get('/v1/health', handle_health)

    async def on_startup(_app: web.Application) -> None:
        await _app['runtime'].initialize()

    async def on_shutdown(_app: web.Application) -> None:
        await _app['runtime'].shutdown()

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description='LangBot Box Runtime HTTP Service')
    parser.add_argument('--host', default='0.0.0.0', help='Bind address')
    parser.add_argument('--port', type=int, default=5410, help='Bind port')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    app = create_app()
    web.run_app(app, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
