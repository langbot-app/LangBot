"""Authenticated Harness ingress for the shared Workspace Bot."""

import uuid

import sqlalchemy

from ..agent.policy import can_use_processor
from ..entity.persistence.user import AccountStatus, User
from ..platform.adapters.harness.bindings import workspace_bot_uuid
from ..platform.adapters.harness.event_converter import build_event


async def _resolve_user(ap, ctx, processor):
    """Return a fresh authorization decision and active account identity."""

    async def load():
        if not await can_use_processor(ap, ctx, processor):
            return 'processor_forbidden', None
        result = await ap.persistence_mgr.execute_async(
            sqlalchemy.select(User.user, User.normalized_email).where(
                User.uuid == ctx.account_uuid, User.status == AccountStatus.ACTIVE.value
            )
        )
        user = result.first()
        return (None, user) if user else ('account_not_found', None)

    if getattr(getattr(ap.persistence_mgr, 'mode', None), 'value', None) == 'cloud_runtime':
        async with ap.persistence_mgr.tenant_scope(ctx.workspace_uuid):
            return await load()
    return await load()


async def handle_ws(ap, transport, ctx) -> None:
    """Authorize each message using trusted Workspace/account context."""
    session = await transport.handshake() if hasattr(transport, 'handshake') else transport
    connection_id = uuid.uuid4().hex
    registry = None
    try:
        while True:
            frame = await session.receive_payload()
            if (
                not isinstance(frame, dict)
                or frame.get('type', 'message') != 'message'
                or not isinstance(frame.get('content'), str)
            ):
                await session.send_payload({'type': 'error', 'code': 'invalid_message'})
                continue
            processor = frame.get('processor_uuid')
            conversation = frame.get('conversation_id')
            if not isinstance(processor, str) or not 0 < len(processor) <= 255:
                await session.send_payload({'type': 'error', 'code': 'processor_required'})
                continue
            if not isinstance(conversation, str) or not 0 < len(conversation) <= 255:
                await session.send_payload({'type': 'error', 'code': 'conversation_required'})
                continue
            error, user = await _resolve_user(ap, ctx, processor)
            if error:
                await session.send_payload({'type': 'error', 'code': error})
                if error == 'account_not_found':
                    return
                continue
            bot = await ap.platform_mgr.get_bot_by_uuid(ctx, workspace_bot_uuid(ctx.workspace_uuid))
            if bot is None or not bot.enable:
                await session.send_payload({'type': 'error', 'code': 'processor_not_running'})
                continue
            if registry is not bot.adapter.connections:
                if registry is not None:
                    await registry.unregister(connection_id, session)
                registry = bot.adapter.connections
                await registry.register(connection_id, session)
            event = build_event(
                frame,
                {'account_uuid': ctx.account_uuid, 'display_name': user.user, 'email': user.normalized_email},
                workspace_uuid=ctx.workspace_uuid,
                processor_uuid=processor,
                connection_id=connection_id,
            )
            await bot.dispatch_harness_message(event, processor)
    finally:
        if registry is not None:
            await registry.unregister(connection_id, session)
