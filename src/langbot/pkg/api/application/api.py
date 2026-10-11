"""Application-level operations shared by HTTP, MCP and assistant adapters.

This is intentionally a small first slice for issue #2639.  Protocol adapters
remain responsible for transport and presentation; this module owns the
workspace-scoped operation contract and the permission check at the shared
boundary.
"""

from __future__ import annotations

import dataclasses
import enum
import inspect
import typing

from ..http.authz import Permission, require_permission
from ..context import RequestContext

APPLICATION_API_VERSION = 'v1'


class ApplicationSurface(enum.StrEnum):
    """Protocol surface allowed to invoke an application operation."""

    HTTP = 'http'
    MCP = 'mcp'
    ASSISTANT = 'assistant'
    CLI = 'cli'


@dataclasses.dataclass(frozen=True, slots=True)
class ApplicationAPIError:
    """Stable, serializable operation error metadata."""

    code: str
    message: str
    status_code: int = 400


class ApplicationAPIException(Exception):
    """Typed application-boundary failure for non-HTTP callers."""

    def __init__(self, error: ApplicationAPIError):
        super().__init__(error.message)
        self.error = error


@dataclasses.dataclass(frozen=True, slots=True)
class PipelineListInput:
    sort_by: str = 'created_at'
    sort_order: str = 'DESC'
    include_secret: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class PipelineListOutput:
    pipelines: list[dict]


@dataclasses.dataclass(frozen=True, slots=True)
class PipelineGetInput:
    pipeline_uuid: str
    include_secret: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class PipelineGetOutput:
    pipeline: dict | None


@dataclasses.dataclass(frozen=True, slots=True)
class PipelineExtensionsGetInput:
    pipeline_uuid: str


@dataclasses.dataclass(frozen=True, slots=True)
class PipelineExtensionsGetOutput:
    extensions: dict


@dataclasses.dataclass(frozen=True, slots=True)
class PipelineExtensionsUpdateInput:
    pipeline_uuid: str
    bound_plugins: list[dict]
    bound_mcp_servers: list[str] | None = None
    enable_all_plugins: bool = True
    enable_all_mcp_servers: bool = True
    bound_skills: list[str] | None = None
    enable_all_skills: bool = True
    bound_mcp_resources: list[dict] | None = None
    mcp_resource_agent_read_enabled: bool | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class PipelineExtensionsUpdateOutput:
    ok: bool = True


@dataclasses.dataclass(frozen=True, slots=True)
class OperationSpec:
    """Stable metadata for one public workspace operation."""

    operation_id: str
    version: str
    permission: Permission
    scope: str = 'workspace'
    side_effect: bool = False
    input_type: type = dict
    output_type: type = dict
    error_type: type = ApplicationAPIError
    allowed_surfaces: frozenset[ApplicationSurface] = frozenset()

    def as_dict(self) -> dict[str, typing.Any]:
        """Return JSON-safe metadata for capability discovery."""

        return {
            'id': self.operation_id,
            'version': self.version,
            'scope': self.scope,
            'permission': self.permission.value,
            'side_effect': self.side_effect,
            'input_type': self.input_type.__name__,
            'output_type': self.output_type.__name__,
            'error_type': self.error_type.__name__,
            'allowed_surfaces': sorted(surface.value for surface in self.allowed_surfaces),
        }


OPERATIONS: dict[str, OperationSpec] = {
    'pipeline.list': OperationSpec(
        'pipeline.list',
        APPLICATION_API_VERSION,
        Permission.RESOURCE_VIEW,
        input_type=PipelineListInput,
        output_type=PipelineListOutput,
        allowed_surfaces=frozenset(ApplicationSurface),
    ),
    'pipeline.get': OperationSpec(
        'pipeline.get',
        APPLICATION_API_VERSION,
        Permission.RESOURCE_VIEW,
        input_type=PipelineGetInput,
        output_type=PipelineGetOutput,
        allowed_surfaces=frozenset(ApplicationSurface),
    ),
    'pipeline.extensions.get': OperationSpec(
        'pipeline.extensions.get',
        APPLICATION_API_VERSION,
        Permission.RESOURCE_VIEW,
        input_type=PipelineExtensionsGetInput,
        output_type=PipelineExtensionsGetOutput,
        allowed_surfaces=frozenset(ApplicationSurface),
    ),
    'pipeline.extensions.update': OperationSpec(
        'pipeline.extensions.update',
        APPLICATION_API_VERSION,
        Permission.RESOURCE_MANAGE,
        side_effect=True,
        input_type=PipelineExtensionsUpdateInput,
        output_type=PipelineExtensionsUpdateOutput,
        allowed_surfaces=frozenset(
            {
                ApplicationSurface.HTTP,
                ApplicationSurface.MCP,
                ApplicationSurface.CLI,
            }
        ),
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

        return [spec.as_dict() for spec in OPERATIONS.values()]

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
        include_secret: bool | None = None,
    ) -> list[dict]:
        self._authorize(context, 'pipeline.list')
        # Secret-bearing pipeline configuration must never be exposed merely
        # because a caller supplied ``include_secret=True``.  The HTTP route
        # derives this flag from the same permission, but MCP/assistant callers
        # can invoke the facade directly.
        include_secret_requested = include_secret is True
        if include_secret_requested:
            require_permission(context, Permission.RESOURCE_MANAGE)
        # The assistant and MCP adapters use the ordinary defaults and keep
        # the legacy service call shape.  HTTP passes an explicit boolean so
        # the redaction intent remains visible to service-level tests and
        # lightweight doubles.
        if include_secret is None and sort_by == 'created_at' and sort_order == 'DESC':
            return await self.ap.pipeline_service.get_pipelines(context)
        return await self.ap.pipeline_service.get_pipelines(
            context,
            sort_by,
            sort_order,
            include_secret=include_secret_requested,
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
        if callable(getter) and inspect.iscoroutinefunction(getter):
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
            if getattr(connector, 'is_enable_plugin', False) is True:
                require_context = getattr(connector, 'require_workspace_context', None)
                if callable(require_context):
                    result = require_context(context)
                    if inspect.isawaitable(result):
                        await result
            list_plugins = getattr(connector, 'list_plugins', None)
            if callable(list_plugins):
                result = list_plugins(component_kinds=['Command', 'EventListener', 'Tool'])
                if inspect.isawaitable(result):
                    plugins = await result
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
                result = list_servers(context, contain_runtime_info=True)
                if inspect.isawaitable(result):
                    available_mcp_servers = await result
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

    async def update_pipeline_extensions(
        self,
        context: RequestContext,
        input: PipelineExtensionsUpdateInput,
    ) -> PipelineExtensionsUpdateOutput:
        self._authorize(context, 'pipeline.extensions.update')
        if not isinstance(input, PipelineExtensionsUpdateInput):
            raise TypeError('input must be PipelineExtensionsUpdateInput')
        await self.ap.pipeline_service.update_pipeline_extensions(
            context,
            input.pipeline_uuid,
            bound_plugins=input.bound_plugins,
            bound_mcp_servers=input.bound_mcp_servers,
            enable_all_plugins=input.enable_all_plugins,
            enable_all_mcp_servers=input.enable_all_mcp_servers,
            bound_skills=input.bound_skills,
            enable_all_skills=input.enable_all_skills,
            bound_mcp_resources=input.bound_mcp_resources,
            mcp_resource_agent_read_enabled=input.mcp_resource_agent_read_enabled,
        )
        return PipelineExtensionsUpdateOutput()
