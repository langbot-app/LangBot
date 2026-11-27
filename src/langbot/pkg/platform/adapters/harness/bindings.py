"""Stable identities for managed Harness Bots and historical projections."""

import uuid

HARNESS_ADAPTER = 'harness-omni'
HARNESS_NAMESPACE = uuid.UUID('51b0ec5e-b015-5ad0-bd7e-41405bcd0fa5')


def workspace_bot_uuid(workspace_uuid: str) -> str:
    return str(uuid.uuid5(HARNESS_NAMESPACE, f'workspace/{workspace_uuid}'))


def processor_bot_uuid(workspace_uuid: str, processor_uuid: str) -> str:
    return str(uuid.uuid5(uuid.UUID(workspace_bot_uuid(workspace_uuid)), processor_uuid))


def processor_bot_config(workspace_uuid: str, processor_uuid: str) -> dict:
    return {
        'uuid': processor_bot_uuid(workspace_uuid, processor_uuid),
        'workspace_uuid': workspace_uuid,
        'name': 'LangBot Harness',
        'description': 'Managed by LangBot Harness.',
        'adapter': HARNESS_ADAPTER,
        'adapter_config': {},
        'enable': True,
        'plugin_processors': [],
        'event_bindings': [
            {
                'id': 'harness-agent',
                'event_pattern': 'message.received',
                'target_type': 'agent',
                'target_uuid': processor_uuid,
            }
        ],
    }
