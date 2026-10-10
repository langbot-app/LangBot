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
        # Secret-bearing pipeline configuration must never be exposed merely
        # because a caller supplied ``include_secret=True``.  The HTTP route
        # derives this flag from the same permission, but MCP/assistant callers
        # can invoke the facade directly.
        if include_secret:
            require_permission(context, Permission.RESOURCE_MANAGE)
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
        if include_secret:
            require_permission(context, Permission.RESOURCE_MANAGE)
        return await self.ap.pipeline_service.get_pipeline(
            context,
            pipeline_uuid,
            include_secret=include_secret,
        )

    async def get_pipeline_extensions(self, context: RequestContext, pipeline_uuid: str) -> dict:
        self._authorize(context, 'pipeline.extensions.get')
        getter = getattr(self.ap.pipeline_service, 'get_pipeline_extensions', None)
        if callable(getter):
            return await getter(context, pipeline_uuid)

        # Compatibility path for lightweight service doubles and older service
        # graphs. The production PipelineService owns this implementation;
        # this fallback keeps the shared facade usable while a graph is being
        # assembled and preserves its fail-closed normalization semantics.
        from ...pipeline.extension_preferences import normalize_extension_preferences
        from ..http.service.secrets import redact_secrets

        pipeline = await self.ap.pipeline_service.get_pipeline(context, pipeline_uuid)
        if pipeline is None:
            return None
        connector = getattr(self.ap, 'plugin_connector', None)
        plugins = []
        if connector is not None:
            if getattr(connector, 'is_enable_plugin', False):
                require_context = getattr(connector, 'require_workspace_context', None)
                if callable(require_context):
                    await require_context(context)
            list_plugins = getattr(connector, 'list_plugins', None)
            if callable(list_plugins):
                plugins = await list_plugins(component_kinds=['Command', 'EventListener', 'Tool'])
        skill_service = getattr(self.ap, 'skill_service', None)
        available_skills = []
        if skill_service is not None:
            try:
                available_skills = await skill_service.list_skills(context)
            except Exception as exc:
                logger = getattr(self.ap, 'logger', None)
                warning = getattr(logger, 'warning', None)
                if callable(warning):
                    warning('Unable to list skills for pipeline extensions: %s', exc)
        mcp_service = getattr(self.ap, 'mcp_service', None)
        available_mcp_servers = []
        if mcp_service is not None:
            list_servers = getattr(mcp_service, 'get_mcp_servers', None)
            if callable(list_servers):
                available_mcp_servers = await list_servers(context, contain_runtime_info=True)
        prefs = normalize_extension_preferences(pipeline.get('extensions_preferences'))
        return {
            'enable_all_plugins': prefs.get('enable_all_plugins', True),
            'enable_all_mcp_servers': prefs.get('enable_all_mcp_servers', True),
            'enable_all_skills': prefs.get('enable_all_skills', True),
            'bound_plugins': prefs.get('plugins', []),
            'available_plugins': redact_secrets(plugins),
            'bound_mcp_servers': prefs.get('mcp_servers', []),
            'available_mcp_servers': available_mcp_servers,
            'bound_mcp_resources': prefs.get('mcp_resources', []),
            'mcp_resource_agent_read_enabled': prefs.get('mcp_resource_agent_read_enabled', True),
            'bound_skills': prefs.get('skills', []),
            'available_skills': available_skills,
        }


    async def update_pipeline_extensions(self, context: RequestContext, pipeline_uuid: str, **kwargs) -> None:
        self._authorize(context, 'pipeline.extensions.update')
        await self.ap.pipeline_service.update_pipeline_extensions(context, pipeline_uuid, **kwargs)
