from __future__ import annotations

import typing


class WorkspaceExecutionContext(typing.Protocol):
    @property
    def instance_uuid(self) -> str: ...

    @property
    def workspace_uuid(self) -> str: ...


def workspace_identity(execution_context: WorkspaceExecutionContext) -> dict[str, str]:
    """Build both first-class telemetry identities for one execution."""
    instance_id = execution_context.instance_uuid.strip()
    workspace_uuid = execution_context.workspace_uuid.strip()
    if not instance_id:
        raise ValueError('Telemetry execution instance ID is empty')
    if not workspace_uuid:
        raise ValueError('Telemetry execution Workspace UUID is empty')
    return {'instance_id': instance_id, 'workspace_uuid': workspace_uuid}
