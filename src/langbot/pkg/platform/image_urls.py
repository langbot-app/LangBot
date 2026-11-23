"""Refresh image references at authorized read/use boundaries."""

import copy
import json

from .adapters.aiocqhttp.image_urls import image_nodes


async def refresh_image_payload(ap, workspace_uuid, bot_id, payload):
    """Return a refreshed copy, resolving bot ownership exclusively from trusted scope."""
    if not workspace_uuid or not bot_id or not list(image_nodes(payload)):
        return payload
    manager = getattr(ap, 'platform_mgr', None)
    if manager is None:
        return payload
    bot = await manager.resolve_public_bot(bot_id)
    if bot is None or bot.workspace_uuid != workspace_uuid or not bot.enable or bot.bot_entity.adapter != 'onebot-v11':
        return payload
    connection = bot.adapter.bot.connection
    if connection is None or connection.closed:
        return payload
    result = copy.deepcopy(payload)
    try:
        from ..persistence.resource_urls import refresh_images

        await refresh_images(
            ap.persistence_mgr.get_db_engine(),
            connection,
            result,
            is_current=lambda: bot.adapter.bot.connection is connection,
        )
        if bot.adapter.bot.connection is not connection or connection.closed:
            return payload
        return result
    except Exception as exc:
        # Do not log signed URLs, credentials, or arbitrary upstream response bodies.
        ap.logger.warning(f'OneBot image URL refresh failed ({type(exc).__name__})')
        return payload


async def refresh_message_rows(ap, workspace_uuid, rows):
    """Refresh bounded, already-authorized monitoring response rows in place."""
    groups = {}
    for row in rows:
        raw = row.get('message_content')
        if not isinstance(raw, str):
            continue
        try:
            payload = json.loads(raw)
        except ValueError:
            continue
        if list(image_nodes(payload)):
            groups.setdefault(row.get('bot_id'), []).append((row, payload))
    for bot_id, group in groups.items():
        payloads = [payload for _, payload in group]
        refreshed = await refresh_image_payload(ap, workspace_uuid, bot_id, payloads)
        if refreshed is not payloads:
            for (row, _), payload in zip(group, refreshed):
                row['message_content'] = json.dumps(payload, ensure_ascii=False)


async def refresh_model_images(ap, context, query, messages):
    """Refresh on every actual model attempt, including reused Runner message lists."""
    bot_id = (getattr(query, 'bot_uuid', None) if query is not None else None) or getattr(context, 'bot_uuid', None)
    if not bot_id:
        return messages
    payload = [message.model_dump(mode='json') for message in messages]
    if not list(image_nodes(payload)):
        return messages
    chain = getattr(query, 'message_chain', None)
    if chain is not None and hasattr(chain, 'model_dump'):
        # Keep current-message origins available when provider contents omit Source/Image IDs.
        payload = {'message_chain': chain.model_dump(), 'messages': payload}
    refreshed = await refresh_image_payload(ap, context.workspace_uuid, bot_id, payload)
    if refreshed is payload:
        return messages
    if isinstance(refreshed, dict):
        refreshed = refreshed['messages']
    return [
        message.model_copy(update={'content': type(message).model_validate(data).content})
        for message, data in zip(messages, refreshed)
    ]


async def refresh_history_items(ap, workspace_uuid, bot_id, items):
    """Recover original image identities from scoped event facts before returning history."""
    if not items or not workspace_uuid or not bot_id or not any(list(image_nodes(item)) for item in items):
        return
    import sqlalchemy as sa
    from ..entity.persistence.event_log import EventLog

    event_ids = [item['event_id'] for item in items if item.get('event_id')]
    result = await ap.persistence_mgr.execute_async(
        sa.select(EventLog.event_id, EventLog.metadata_json, EventLog.subject_type, EventLog.subject_id).where(
            EventLog.workspace_id == workspace_uuid,
            EventLog.bot_id == bot_id,
            EventLog.event_id.in_(event_ids),
        )
    )
    origins = {}
    for event_id, raw, subject_type, subject_id in result.all():
        try:
            metadata = json.loads(raw) if raw else {}
        except ValueError:
            continue
        if not isinstance(metadata, dict):
            continue
        event = metadata.get('input_event', {})
        if isinstance(event, dict):
            message_id = event.get('message_id')
            if message_id is None and subject_type == 'message' and str(subject_id).lstrip('-').isdigit():
                message_id = subject_id
            origins[event_id] = {'message_id': message_id, 'message_chain': event.get('message_chain', [])}
    scoped_items = []
    payloads = []
    for item in items:
        if item.get('workspace_id') != workspace_uuid or item.get('bot_id') != bot_id:
            continue
        scoped_items.append(item)
        payloads.append(
            {
                **origins.get(item.get('event_id'), {}),
                'content_json': item.get('content_json'),
                'attachment_refs': item.get('attachment_refs', []),
            }
        )
    refreshed = await refresh_image_payload(ap, workspace_uuid, bot_id, payloads)
    for item, payload in zip(scoped_items, refreshed):
        item['content_json'] = payload['content_json']
        item['attachment_refs'] = payload['attachment_refs']
