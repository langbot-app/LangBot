"""Authenticated Harness ingress for processor-specific Bots."""

import uuid

import sqlalchemy

from ..agent.policy import can_use_processor
from ..api.http.service.bot_errors import BotApplyError
from ..entity.persistence.user import AccountStatus, User
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


async def handle_ws(ap, transport, ctx, *, revalidate=None) -> None:
    """Authorize each message using trusted Workspace/account context."""
    session = await transport.handshake() if hasattr(transport, 'handshake') else transport
    connection_id = uuid.uuid4().hex
    registries = set()
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
            if frame.get('workspace_uuid', ctx.workspace_uuid) != ctx.workspace_uuid:
                await session.send_payload({'type': 'error', 'code': 'workspace_forbidden'})
                continue
            if frame.get('processor_kind', 'agent') != 'agent':
                await session.send_payload({'type': 'error', 'code': 'processor_forbidden'})
                continue
            if not isinstance(processor, str) or not 0 < len(processor) <= 255:
                await session.send_payload({'type': 'error', 'code': 'processor_required'})
                continue
            if not isinstance(conversation, str) or not 0 < len(conversation) <= 255:
                await session.send_payload({'type': 'error', 'code': 'conversation_required'})
                continue
            if revalidate is not None:
                current = await revalidate(frame)
                if current is not None:
                    ctx = current
            if ctx.auth_type == 'harness-oauth' and 'runtime.operate' not in ctx.workspace.permissions:
                await session.send_payload({'type': 'error', 'code': 'processor_forbidden'})
                continue
            error, user = await _resolve_user(ap, ctx, processor)
            if error:
                await session.send_payload({'type': 'error', 'code': error})
                if error == 'account_not_found':
                    return
                continue
            try:
                if getattr(getattr(ap.persistence_mgr, 'mode', None), 'value', None) == 'cloud_runtime':
                    async with ap.persistence_mgr.tenant_scope(ctx.workspace_uuid):
                        bot = await ap.bot_service.ensure_harness_processor_bot(ctx, processor)
                else:
                    bot = await ap.bot_service.ensure_harness_processor_bot(ctx, processor)
            except (ValueError, BotApplyError):
                bot = None
            if bot is None or not bot.enable:
                await session.send_payload({'type': 'error', 'code': 'processor_not_running'})
                continue
            registry = bot.adapter.connections
            if registry not in registries:
                await registry.register(connection_id, session)
                registries.add(registry)
            event = build_event(
                frame,
                {'account_uuid': ctx.account_uuid, 'display_name': user.user, 'email': user.normalized_email},
                workspace_uuid=ctx.workspace_uuid,
                processor_uuid=processor,
                connection_id=connection_id,
            )
            await bot.dispatch_harness_message(event, processor)
    finally:
        for registry in registries:
            await registry.unregister(connection_id, session)
