from __future__ import annotations

import typing


class WorkspaceExecutionContext(typing.Protocol):
    @property
    def workspace_uuid(self) -> str: ...


def workspace_identity(execution_context: WorkspaceExecutionContext) -> dict[str, str]:
    """Build the canonical telemetry identity for one Workspace execution."""
    workspace_uuid = execution_context.workspace_uuid.strip()
    if not workspace_uuid:
        raise ValueError('Telemetry execution Workspace UUID is empty')
    return {'workspace_uuid': workspace_uuid}
