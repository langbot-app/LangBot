"""Identity and configuration of the managed Workspace Harness Bot."""

import uuid

HARNESS_ADAPTER = 'harness-omni'
HARNESS_NAMESPACE = uuid.UUID('51b0ec5e-b015-5ad0-bd7e-41405bcd0fa5')


def workspace_bot_uuid(workspace_uuid: str) -> str:
    return str(uuid.uuid5(HARNESS_NAMESPACE, f'workspace/{workspace_uuid}'))


def workspace_bot_config(workspace_uuid: str) -> dict:
    return {
        'uuid': workspace_bot_uuid(workspace_uuid),
        'workspace_uuid': workspace_uuid,
        'name': 'LangBot Harness',
        'description': 'Managed by LangBot Harness.',
        'adapter': HARNESS_ADAPTER,
        'adapter_config': {},
        'enable': True,
        'event_bindings': [],
        'plugin_processors': [],
    }
