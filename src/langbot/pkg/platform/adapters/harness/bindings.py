"""Keep the deterministic Harness Bot projection aligned with processor access."""

import uuid
import typing

HARNESS_ADAPTER = 'harness'
HARNESS_NAMESPACE = uuid.UUID('51b0ec5e-b015-5ad0-bd7e-41405bcd0fa5')


def bot_uuid_for(workspace_uuid: str, processor_uuid: str) -> str:
    """Return the stable Bot identity for a Harness processor projection."""
    if not workspace_uuid or not processor_uuid:
        raise ValueError('workspace_uuid and processor_uuid are required')
    return str(uuid.uuid5(HARNESS_NAMESPACE, f'{workspace_uuid}:{processor_uuid}'))


def processor_bot_config(processor: dict[str, typing.Any], workspace_uuid: str) -> dict[str, typing.Any]:
    """Build the canonical one-Bot-per-processor projection."""
    processor_uuid = processor.get('uuid')
    processor_kind = processor.get('kind')
    name = processor.get('name')
    if not all(isinstance(value, str) and value for value in (processor_uuid, processor_kind, name)):
        raise ValueError('processor uuid, kind, and name are required')
    target_type = 'pipeline' if processor_kind == 'pipeline' else 'agent'
    return {
        'uuid': bot_uuid_for(workspace_uuid, processor_uuid),
        'workspace_uuid': workspace_uuid,
        'name': f'Harness · {name}',
        'description': 'Managed by LangBot Harness.',
        'adapter': HARNESS_ADAPTER,
        'adapter_config': {'processor_uuid': processor_uuid, 'processor_kind': processor_kind},
        'enable': True,
        'event_bindings': [
            {
                'id': 'harness-default',
                'event_pattern': 'message.received',
                'target_type': target_type,
                'target_uuid': processor_uuid,
                'priority': 0,
                'order': 0,
                'enabled': True,
            }
        ],
        'plugin_processors': [],
    }


async def sync_processor_bots(
    ap,
    context,
    workspace_uuid: str,
    allowed_processors: typing.Iterable[dict[str, typing.Any]],
) -> None:
    """Create/repair allowed processor Bots and disable stale projections.

    The caller supplies the authoritative allowed processor set after access
    policy evaluation. Re-running this operation converges to the same state.
    """
    desired = {
        bot_uuid_for(workspace_uuid, processor['uuid']): processor_bot_config(processor, workspace_uuid)
        for processor in allowed_processors
    }
    existing = await ap.bot_service.get_bots(context, include_secret=True)
    existing_by_uuid = {bot['uuid']: bot for bot in existing}

    for bot_uuid, payload in desired.items():
        current = existing_by_uuid.get(bot_uuid)
        if current is None:
            await ap.bot_service.create_bot(context, payload, bot_uuid=bot_uuid)
            continue
        if current.get('adapter') != HARNESS_ADAPTER:
            raise ValueError(f'Deterministic Harness Bot UUID collision: {bot_uuid}')
        changed = any(
            current.get(key) != value for key, value in payload.items() if key not in {'uuid', 'workspace_uuid'}
        )
        if changed:
            await ap.bot_service.update_bot(
                context,
                bot_uuid,
                {key: value for key, value in payload.items() if key not in {'uuid', 'workspace_uuid'}},
            )

    allowed_uuids = set(desired)
    for bot in existing:
        if bot.get('adapter') != HARNESS_ADAPTER or bot.get('workspace_uuid') != workspace_uuid:
            continue
        if bot['uuid'] in allowed_uuids or not bot.get('enable'):
            continue
        await ap.bot_service.update_bot(context, bot['uuid'], {'enable': False})
