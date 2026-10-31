"""Single-turn diagnostic execution through the normal Pipeline scheduler."""

from __future__ import annotations

import asyncio
import time
import uuid

from langbot_plugin.api.entities.builtin.platform import entities, events, message
from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes

from ..authz import Permission, require_permission
from ..context import ExecutionContext, RequestContext
from ....workspace.errors import WorkspaceNotFoundError


async def run_pipeline(ap, context: RequestContext, pipeline_uuid: str, text: str, *, timeout: float = 60) -> dict:
    """Run in a fresh session; a timed-out request is never submitted again."""
    require_permission(context, Permission.RUNTIME_OPERATE)
    if not isinstance(text, str) or not text.strip() or len(text) > 100_000:
        raise ValueError('message must contain 1..100000 characters')
    if await ap.pipeline_service.get_pipeline(context, pipeline_uuid) is None:
        raise WorkspaceNotFoundError('Pipeline not found')

    bot = await ap.platform_mgr.get_websocket_proxy_bot(context)
    adapter = bot.adapter
    session_id = str(uuid.uuid4())
    launcher_id = f'websocket_{pipeline_uuid}:{session_id}'
    chain = message.MessageChain([message.Plain(text=text)])
    event = events.FriendMessage(
        sender=entities.Friend(id=launcher_id, nickname='CLI', remark='CLI'),
        message_chain=chain,
        time=time.time(),
    )
    execution = ExecutionContext.from_request(context, bot_uuid='websocket-proxy-bot', pipeline_uuid=pipeline_uuid)
    query = await ap.query_pool.add_query(
        bot_uuid='websocket-proxy-bot',
        launcher_type=LauncherTypes.PERSON,
        launcher_id=launcher_id,
        sender_id=launcher_id,
        message_event=event,
        message_chain=chain,
        adapter=adapter,
        pipeline_uuid=pipeline_uuid,
        variables={'_cli_run_status': 'failed'},
        execution_context=execution,
    )
    completed = asyncio.Event()
    # add_query returns without yielding after enqueueing, so the scheduler
    # cannot remove this query before its completion notification is attached.
    object.__setattr__(query, '_completion_event', completed)
    data = {'pipeline_uuid': pipeline_uuid, 'session_id': f'person_{launcher_id}', 'query_id': query.query_uuid}
    try:
        await asyncio.wait_for(completed.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        return {**data, 'status': 'unknown', 'error': 'Execution status unknown; do not automatically retry.'}

    replies = adapter.get_websocket_messages(pipeline_uuid, 'person', session_id)
    replies = [reply for reply in replies if reply.get('role') == 'assistant']
    data.update(
        status=query.variables['_cli_run_status'],
        replies=replies,
        reply='\n'.join(reply.get('content', '') for reply in replies),
        message_id=query.variables.get('_monitoring_message_id'),
    )
    if data['status'] != 'completed':
        data['error'] = 'Pipeline failed or was dropped; inspect the message and call records.'
    return data
