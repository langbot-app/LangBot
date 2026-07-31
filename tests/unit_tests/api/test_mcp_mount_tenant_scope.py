from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.service.apikey import ApiKeyIdentity
from langbot.pkg.api.mcp.context import get_request_context
from langbot.pkg.api.mcp.mount import MCPMount
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.persistence.tenant_uow import PersistenceScopeKind


@pytest.mark.asyncio
async def test_mcp_mount_keeps_request_context_but_no_session_during_stream_wait(tmp_path) -> None:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "mcp-short-scope.db"}')
    table = sa.Table('mcp_scope_probe', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    checked_out = 0

    def on_checkout(*_args):
        nonlocal checked_out
        checked_out += 1

    def on_checkin(*_args):
        nonlocal checked_out
        checked_out -= 1

    sa.event.listen(engine.sync_engine, 'checkout', on_checkout)
    sa.event.listen(engine.sync_engine, 'checkin', on_checkin)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        identity = ApiKeyIdentity(
            instance_uuid='instance-1',
            workspace_uuid='workspace-1',
            placement_generation=7,
            api_key_uuid='key-1',
            permissions=frozenset({'pipelines:read'}),
        )
        app = SimpleNamespace(
            apikey_service=SimpleNamespace(authenticate_api_key=AsyncMock(return_value=identity)),
            persistence_mgr=manager,
            deployment_admission=None,
            deployment=None,
        )
        stream_waiting = asyncio.Event()
        release_stream = asyncio.Event()
        observations: list[tuple[str, str, bool]] = []

        async def fake_mcp_asgi(scope, receive, send):
            del scope, receive
            context = get_request_context()
            assert manager.current_scope().kind is PersistenceScopeKind.WORKSPACE
            assert manager.current_session() is None
            await manager.execute_async(sa.select(table.c.id))
            assert manager.current_session() is None
            observations.append((context.request_id, context.workspace_uuid, manager.current_session() is None))
            stream_waiting.set()
            await release_stream.wait()
            preserved_context = get_request_context()
            observations.append(
                (
                    preserved_context.request_id,
                    preserved_context.workspace_uuid,
                    manager.current_session() is None,
                )
            )
            await manager.execute_async(sa.select(table.c.id))
            assert manager.current_session() is None
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'{}'})

        async def unused_quart_asgi(scope, receive, send):
            del scope, receive, send
            raise AssertionError('MCP request was routed to Quart')

        mount = MCPMount.__new__(MCPMount)
        mount.ap = app
        mount._mcp_asgi = fake_mcp_asgi
        sent_messages: list[dict] = []

        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': False}

        async def send(message):
            sent_messages.append(message)

        async def release_after_observation() -> None:
            await asyncio.wait_for(stream_waiting.wait(), timeout=2)
            assert checked_out == 0
            release_stream.set()

        release_task = asyncio.create_task(release_after_observation())
        await mount.wrap(unused_quart_asgi)(
            {
                'type': 'http',
                'path': '/mcp',
                'headers': [(b'x-api-key', b'secret')],
            },
            receive,
            send,
        )
        await release_task

        assert sent_messages[0]['status'] == 200
        assert len(observations) == 2
        assert observations[0] == observations[1]
        assert observations[0][1:] == ('workspace-1', True)
        assert checked_out == 0
        assert manager.current_scope() is None
        with pytest.raises(RuntimeError, match='context is unavailable'):
            get_request_context()
    finally:
        await engine.dispose()
