"""Authenticated Harness WebSocket dispatch over a negotiated secure session.

The transport is responsible for HTS1 handshake and envelope encryption. It
must expose ``receive_payload`` and ``send_payload`` for decoded inner objects.
"""

import sqlalchemy

from ..agent.policy import can_use_processor
from ..entity.persistence import user as persistence_user
from ..platform.adapters.harness.bindings import bot_uuid_for


async def handle_ws(ap, transport, ctx) -> None:
    """Validate the first frame, bind the conversation and dispatch messages.

    ``transport.handshake`` authenticates the peer and returns an encrypted
    session facade. This boundary deliberately accepts only trusted request
    context supplied by the HTTP/OAuth layer.
    """
    session = await transport.handshake()
    first = await session.receive_payload()
    if not isinstance(first, dict):
        await session.send_payload({'type': 'error', 'code': 'invalid_first_frame'})
        return
    processor_uuid = first.get('processor_uuid')
    conversation_id = first.get('conversation_id')
    if not isinstance(processor_uuid, str) or not processor_uuid:
        await session.send_payload({'type': 'error', 'code': 'processor_required'})
        return
    if not isinstance(conversation_id, str) or not conversation_id:
        await session.send_payload({'type': 'error', 'code': 'conversation_required'})
        return
    if not await can_use_processor(ap, ctx, processor_uuid):
        await session.send_payload({'type': 'error', 'code': 'processor_forbidden'})
        return

    bot = await ap.platform_mgr.get_bot_by_uuid(ctx, bot_uuid_for(ctx.workspace_uuid, processor_uuid))
    adapter = getattr(bot, 'adapter', None) if bot is not None else None
    if adapter is None:
        await session.send_payload({'type': 'error', 'code': 'processor_not_running'})
        return

    await adapter.connections.register(conversation_id, session)
    user_result = await ap.persistence_mgr.execute_async(
        sqlalchemy.select(persistence_user.User.user, persistence_user.User.normalized_email).where(
            persistence_user.User.uuid == ctx.account_uuid
        )
    )
    user = user_result.first()
    if user is None:
        await adapter.connections.unregister(conversation_id, session)
        await session.send_payload({'type': 'error', 'code': 'account_not_found'})
        return
    identity = {'account_uuid': ctx.account_uuid, 'display_name': user.user, 'email': user.normalized_email}

    try:
        frame = first
        while True:
            if frame.get('type', 'message') == 'message':
                await adapter.ingest_frame(frame, identity)
            frame = await session.receive_payload()
    finally:
        await adapter.connections.unregister(conversation_id, session)
