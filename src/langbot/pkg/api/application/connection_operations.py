"""Workspace management of dashboard chat history and active connections."""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import Field

from .contracts import Input, Operation
from ..authz import Permission


class Pipeline(Input):
    pipeline_uuid: str = Field(min_length=1)


class Session(Pipeline):
    session_type: Literal['person', 'group']


class Broadcast(Pipeline):
    message: str = Field(min_length=1, max_length=100_000)


async def _require_pipeline(ap, context, pipeline_uuid):
    if await ap.pipeline_service.get_pipeline(context, pipeline_uuid) is None:
        raise FileNotFoundError('Pipeline not found')


async def history(ap, context, payload):
    await _require_pipeline(ap, context, payload.pipeline_uuid)
    proxy = await ap.platform_mgr.get_websocket_proxy_bot(context)
    return proxy.adapter.get_websocket_messages(payload.pipeline_uuid, payload.session_type)


async def reset(ap, context, payload):
    await _require_pipeline(ap, context, payload.pipeline_uuid)
    proxy = await ap.platform_mgr.get_websocket_proxy_bot(context)
    proxy.adapter.reset_session(payload.pipeline_uuid, payload.session_type)


async def connections(ap, context, payload):
    from ...platform.sources.websocket_manager import WebSocketScope, ws_connection_manager

    await _require_pipeline(ap, context, payload.pipeline_uuid)
    scope = WebSocketScope.from_context(context)
    rows = await ws_connection_manager.get_connections_by_pipeline(payload.pipeline_uuid, scope=scope)
    return {
        'stats': ws_connection_manager.get_stats(scope=scope),
        'connections': [
            {
                'connection_id': row.connection_id,
                'session_type': row.session_type,
                'created_at': row.created_at.isoformat(),
                'last_active': row.last_active.isoformat(),
                'is_active': row.is_active,
            }
            for row in rows
        ],
    }


async def broadcast(ap, context, payload):
    from ...platform.sources.websocket_manager import WebSocketScope, ws_connection_manager

    await _require_pipeline(ap, context, payload.pipeline_uuid)
    await ws_connection_manager.broadcast_to_pipeline(
        payload.pipeline_uuid,
        {'type': 'broadcast', 'message': payload.message, 'timestamp': datetime.datetime.now().isoformat()},
        scope=WebSocketScope.from_context(context),
    )


def operations() -> list[Operation]:
    permission = Permission.RUNTIME_OPERATE
    return [
        Operation('pipeline.chat.history', permission, history, Session, list[dict]),
        Operation('pipeline.chat.reset', permission, reset, Session, type(None), True),
        Operation('pipeline.chat.connections', permission, connections, Pipeline, dict),
        Operation('pipeline.chat.broadcast', permission, broadcast, Broadcast, type(None), True),
    ]
