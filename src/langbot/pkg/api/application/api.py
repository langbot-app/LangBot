"""Application-level operations shared by HTTP, MCP and assistant adapters.

This is intentionally a small first slice for issue #2639.  Protocol adapters
remain responsible for transport and presentation; this module owns the
workspace-scoped operation contract and the permission check at the shared
boundary.
"""

from __future__ import annotations

import dataclasses
import typing

from ..http.authz import Permission, require_permission
from ..http.context import RequestContext

APPLICATION_API_VERSION = 'v1'


@dataclasses.dataclass(frozen=True, slots=True)
class OperationSpec:
    """Stable metadata for one public workspace operation."""

    operation_id: str
    version: str
    permission: Permission
    scope: str = 'workspace'
    side_effect: bool = False


OPERATIONS: dict[str, OperationSpec] = {
    'pipeline.list': OperationSpec('pipeline.list', APPLICATION_API_VERSION, Permission.RESOURCE_VIEW),
    'pipeline.get': OperationSpec('pipeline.get', APPLICATION_API_VERSION, Permission.RESOURCE_VIEW),
    'pipeline.extensions.get': OperationSpec(
        'pipeline.extensions.get', APPLICATION_API_VERSION, Permission.RESOURCE_VIEW
    ),
    'pipeline.extensions.update': OperationSpec(
        'pipeline.extensions.update',
        APPLICATION_API_VERSION,
        Permission.RESOURCE_MANAGE,
        side_effect=True,
    ),
}


class ApplicationAPI:
    """Workspace-scoped application operations.

    The first version delegates persistence and runtime details to existing
    services. That keeps the experiment low-risk while giving each adapter one
    stable boundary to call and one place to enforce authorization.
    """

    def __init__(self, ap) -> None:
        self.ap = ap

    @staticmethod
    def operation_catalog() -> list[dict[str, typing.Any]]:
        """Return serializable operation metadata for capability discovery."""

        return [
            {
                'id': spec.operation_id,
                'version': spec.version,
                'scope': spec.scope,
                'permission': spec.permission.value,
                'side_effect': spec.side_effect,
            }
            for spec in OPERATIONS.values()
        ]

    @staticmethod
    def _authorize(context: RequestContext, operation_id: str) -> None:
        spec = OPERATIONS[operation_id]
        require_permission(context, spec.permission)

    async def list_pipelines(
        self,
        context: RequestContext,
        sort_by: str = 'created_at',
        sort_order: str = 'DESC',
        *,
        include_secret: bool = False,
    ) -> list[dict]:
        self._authorize(context, 'pipeline.list')
        return await self.ap.pipeline_service.get_pipelines(
            context,
            sort_by,
            sort_order,
            include_secret=include_secret,
        )

    async def get_pipeline(
        self,
        context: RequestContext,
        pipeline_uuid: str,
        *,
        include_secret: bool = False,
    ) -> dict | None:
        self._authorize(context, 'pipeline.get')
        return await self.ap.pipeline_service.get_pipeline(
            context,
            pipeline_uuid,
            include_secret=include_secret,
        )

    async def get_pipeline_extensions(self, context: RequestContext, pipeline_uuid: str) -> dict:
        self._authorize(context, 'pipeline.extensions.get')
        return await self.ap.pipeline_service.get_pipeline_extensions(context, pipeline_uuid)

    async def update_pipeline_extensions(self, context: RequestContext, pipeline_uuid: str, **kwargs) -> None:
        self._authorize(context, 'pipeline.extensions.update')
        await self.ap.pipeline_service.update_pipeline_extensions(context, pipeline_uuid, **kwargs)
