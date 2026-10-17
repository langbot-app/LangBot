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
import types
import typing

from ..authz import AuthorizationError, Permission, require_permission
from ..context import RequestContext
from ..secrets import redact_secrets

APPLICATION_API_VERSION = 'v1'


class ApplicationErrorCode(enum.StrEnum):
    """Stable machine-readable errors emitted by the application boundary."""

    INVALID_INPUT = 'invalid_input'
    INVALID_OUTPUT = 'invalid_output'
    UNKNOWN_OPERATION = 'unknown_operation'
    PERMISSION_DENIED = 'permission_denied'
    INVALID_AUTHENTICATION = 'invalid_authentication'
    WORKSPACE_REQUIRED = 'workspace_required'
    RESOURCE_NOT_FOUND = 'resource_not_found'
    VALIDATION_ERROR = 'validation_error'
    APPLICATION_ERROR = 'application_error'


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


class _InvalidApplicationOutput(Exception):
    """Internal marker used when a service violates an operation contract."""


_ERROR_STATUS_BY_CODE: dict[str, int] = {
    'invalid_input': 400,
    'invalid_output': 500,
    'unknown_operation': 404,
    'permission_denied': 403,
    'invalid_authentication': 401,
    'workspace_required': 400,
    'resource_not_found': 404,
    'validation_error': 400,
    'application_error': 500,
}


@dataclasses.dataclass(frozen=True, slots=True)
class PipelineListInput:
    sort_by: str = 'created_at'
    sort_order: str = 'DESC'
    # ``None`` preserves the legacy service call shape for lightweight
    # adapters; HTTP passes an explicit bool so its redaction intent is
    # visible to service-level tests and doubles.
    include_secret: bool | None = None


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
class KnowledgeBaseListInput:
    # ``None`` preserves the legacy service call shape for lightweight
    # adapters; HTTP passes an explicit bool so its redaction intent is
    # visible to service-level tests and doubles.
    include_secret: bool | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class KnowledgeBaseListOutput:
    bases: list[dict]


@dataclasses.dataclass(frozen=True, slots=True)
class KnowledgeBaseGetInput:
    knowledge_base_uuid: str
    include_secret: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class KnowledgeBaseGetOutput:
    base: dict | None


@dataclasses.dataclass(frozen=True, slots=True)
class KnowledgeEngineListInput:
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class KnowledgeEngineListOutput:
    engines: list[dict]


@dataclasses.dataclass(frozen=True, slots=True)
class KnowledgeEngineSchemaInput:
    plugin_id: str
    kind: str


@dataclasses.dataclass(frozen=True, slots=True)
class KnowledgeEngineSchemaOutput:
    # Plugin runtimes historically returned either the newer object form or
    # the original list-of-field-definitions form. Keep both wire shapes in
    # the typed boundary while adapters preserve the payload unchanged.
    schema: dict | list[dict]


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
        }


OPERATIONS: dict[str, OperationSpec] = {
    'pipeline.list': OperationSpec(
        'pipeline.list',
        APPLICATION_API_VERSION,
        Permission.RESOURCE_VIEW,
        input_type=PipelineListInput,
        output_type=PipelineListOutput,
    ),
    'pipeline.get': OperationSpec(
        'pipeline.get',
        APPLICATION_API_VERSION,
        Permission.RESOURCE_VIEW,
        input_type=PipelineGetInput,
        output_type=PipelineGetOutput,
    ),
    'pipeline.extensions.get': OperationSpec(
        'pipeline.extensions.get',
        APPLICATION_API_VERSION,
        Permission.RESOURCE_VIEW,
        input_type=PipelineExtensionsGetInput,
        output_type=PipelineExtensionsGetOutput,
    ),
    'pipeline.extensions.update': OperationSpec(
        'pipeline.extensions.update',
        APPLICATION_API_VERSION,
        Permission.RESOURCE_MANAGE,
        side_effect=True,
        input_type=PipelineExtensionsUpdateInput,
        output_type=PipelineExtensionsUpdateOutput,
    ),
    'knowledge.base.list': OperationSpec(
        'knowledge.base.list',
        APPLICATION_API_VERSION,
        Permission.RESOURCE_VIEW,
        input_type=KnowledgeBaseListInput,
        output_type=KnowledgeBaseListOutput,
    ),
    'knowledge.base.get': OperationSpec(
        'knowledge.base.get',
        APPLICATION_API_VERSION,
        Permission.RESOURCE_VIEW,
        input_type=KnowledgeBaseGetInput,
        output_type=KnowledgeBaseGetOutput,
    ),
    'knowledge.engine.list': OperationSpec(
        'knowledge.engine.list',
        APPLICATION_API_VERSION,
        Permission.RESOURCE_VIEW,
        input_type=KnowledgeEngineListInput,
        output_type=KnowledgeEngineListOutput,
    ),
    'knowledge.engine.schema.get': OperationSpec(
        'knowledge.engine.schema.get',
        APPLICATION_API_VERSION,
        Permission.RESOURCE_VIEW,
        input_type=KnowledgeEngineSchemaInput,
        output_type=KnowledgeEngineSchemaOutput,
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

    @staticmethod
    def _type_name(value: typing.Any) -> str:
        return type(value).__name__

    @classmethod
    def _validate_value(cls, value: typing.Any, annotation: typing.Any, path: str) -> None:
        """Validate operation DTO values without coercion.

        Dataclasses are deliberately used as the public DTOs instead of
        accepting arbitrary dictionaries.  This small recursive validator
        catches the common bool/int and list-item coercions while keeping the
        application layer independent from Pydantic or any protocol adapter.
        """

        if annotation is typing.Any or annotation is None:
            return
        if isinstance(annotation, typing.TypeVar):
            return
        origin = typing.get_origin(annotation)
        args = typing.get_args(annotation)
        if origin in (typing.Union, types.UnionType):
            if value is None and type(None) in args:
                return
            for candidate in args:
                if candidate is type(None):
                    continue
                try:
                    cls._validate_value(value, candidate, path)
                    return
                except ApplicationAPIException:
                    continue
            raise ApplicationAPIException(ApplicationAPIError('invalid_input', f'{path} has an invalid type', 400))
        if origin in (list, tuple, set, frozenset):
            if not isinstance(value, origin):
                raise ApplicationAPIException(
                    ApplicationAPIError('invalid_input', f'{path} must be a {origin.__name__}', 400)
                )
            if args:
                item_type = args[0]
                for index, item in enumerate(value):
                    cls._validate_value(item, item_type, f'{path}[{index}]')
            return
        if origin is dict:
            if not isinstance(value, dict):
                raise ApplicationAPIException(ApplicationAPIError('invalid_input', f'{path} must be an object', 400))
            key_type, value_type = args or (typing.Any, typing.Any)
            for key, item in value.items():
                cls._validate_value(key, key_type, f'{path}.<key>')
                cls._validate_value(item, value_type, f'{path}[{key!r}]')
            return
        if annotation is bool:
            valid = type(value) is bool
        elif annotation is int:
            valid = type(value) is int
        elif annotation is float:
            valid = type(value) in (int, float) and type(value) is not bool
        elif annotation is str:
            valid = type(value) is str
        elif isinstance(annotation, type):
            valid = isinstance(value, annotation)
        else:
            valid = True
        if not valid:
            raise ApplicationAPIException(ApplicationAPIError('invalid_input', f'{path} has an invalid type', 400))

    @classmethod
    def _validate_input(cls, value: typing.Any, expected_type: type) -> None:
        if type(value) is not expected_type or not dataclasses.is_dataclass(value):
            raise ApplicationAPIException(
                ApplicationAPIError(
                    'invalid_input',
                    f'Expected {expected_type.__name__}, received {cls._type_name(value)}',
                    400,
                )
            )
        hints = typing.get_type_hints(expected_type)
        for field in dataclasses.fields(expected_type):
            cls._validate_value(getattr(value, field.name), hints.get(field.name, field.type), field.name)

    @classmethod
    def _validate_output(cls, value: typing.Any, expected_type: type) -> None:
        if type(value) is not expected_type or not dataclasses.is_dataclass(value):
            raise ApplicationAPIException(
                ApplicationAPIError(
                    'invalid_output',
                    f'Application operation returned {cls._type_name(value)}; expected {expected_type.__name__}',
                    500,
                )
            )
        # Output DTOs are just as strict as input DTOs, but report a server
        # contract error rather than blaming the caller.
        try:
            hints = typing.get_type_hints(expected_type)
            for field in dataclasses.fields(expected_type):
                cls._validate_value(getattr(value, field.name), hints.get(field.name, field.type), field.name)
        except ApplicationAPIException as exc:
            raise ApplicationAPIException(ApplicationAPIError('invalid_output', exc.error.message, 500)) from exc

    @staticmethod
    def _error_from_exception(exc: BaseException) -> ApplicationAPIError:
        if isinstance(exc, ApplicationAPIException):
            return exc.error
        code = getattr(exc, 'error_code', None)
        status = getattr(exc, 'status_code', None)
        if isinstance(code, str) and code:
            resolved_status = int(status) if isinstance(status, int) else _ERROR_STATUS_BY_CODE.get(code, 400)
            return ApplicationAPIError(code, str(exc), resolved_status)
        if exc.__class__.__name__ in {'WorkspaceNotFoundError', 'ResourceNotFoundError'}:
            return ApplicationAPIError('resource_not_found', 'Resource not found', 404)
        if isinstance(exc, ValueError):
            return ApplicationAPIError('validation_error', str(exc), 400)
        return ApplicationAPIError('application_error', 'Application operation failed', 500)

    async def execute(
        self,
        operation_id: str,
        context: RequestContext,
        input: typing.Any,
    ) -> typing.Any:
        """Execute a versioned operation with strict DTO and Workspace permission checks.

        Protocol adapters receive the typed output DTO and are responsible for
        unwrapping it into their wire representation.  No adapter object or
        transport-specific response is accepted at this boundary.
        """

        spec = OPERATIONS.get(operation_id)
        if spec is None:
            raise ApplicationAPIException(
                ApplicationAPIError('unknown_operation', 'Unknown application operation', 404)
            )
        self._validate_input(input, spec.input_type)
        # Keep authorization errors as AuthorizationError instances for the
        # HTTP compatibility layer; their error_code/status_code are already
        # stable and callers historically catch PermissionDeniedError.
        self._authorize(context, operation_id)
        try:
            if operation_id == 'pipeline.list':
                output = await self._list_pipelines(context, input)
            elif operation_id == 'pipeline.get':
                output = await self._get_pipeline(context, input)
            elif operation_id == 'pipeline.extensions.get':
                output = await self._get_pipeline_extensions(context, input)
            elif operation_id == 'pipeline.extensions.update':
                output = await self._update_pipeline_extensions(context, input)
            elif operation_id == 'knowledge.base.list':
                output = await self._list_knowledge_bases(context, input)
            elif operation_id == 'knowledge.base.get':
                output = await self._get_knowledge_base(context, input)
            elif operation_id == 'knowledge.engine.list':
                output = await self._list_knowledge_engines(context, input)
            elif operation_id == 'knowledge.engine.schema.get':
                output = await self._get_knowledge_engine_schema(context, input)
            else:  # pragma: no cover - guarded by catalog lookup
                raise ApplicationAPIException(
                    ApplicationAPIError('unknown_operation', 'Unknown application operation', 404)
                )
        except AuthorizationError:
            raise
        except _InvalidApplicationOutput as exc:
            raise ApplicationAPIException(ApplicationAPIError('invalid_output', str(exc), 500)) from exc
        except ApplicationAPIException:
            raise
        except Exception as exc:
            raise ApplicationAPIException(self._error_from_exception(exc)) from exc
        self._validate_output(output, spec.output_type)
        return output

    async def invoke(
        self,
        operation_id: str,
        context: RequestContext,
        input: typing.Any,
    ) -> typing.Any:
        """Alias for :meth:`execute` used by adapters that prefer verb syntax."""

        return await self.execute(operation_id, context, input)

    async def _list_pipelines(self, context: RequestContext, input: PipelineListInput) -> PipelineListOutput:
        # Secret-bearing pipeline configuration must never be exposed merely
        # because a caller supplied ``include_secret=True``.  The operation
        # permission is intentionally stricter than the read permission.
        if input.include_secret is True:
            require_permission(context, Permission.RESOURCE_MANAGE)
        if input.include_secret is None and input.sort_by == 'created_at' and input.sort_order == 'DESC':
            pipelines = await self.ap.pipeline_service.get_pipelines(context)
        else:
            pipelines = await self.ap.pipeline_service.get_pipelines(
                context,
                input.sort_by,
                input.sort_order,
                include_secret=input.include_secret is True,
            )
        if not isinstance(pipelines, list):
            raise _InvalidApplicationOutput('pipeline.list returned a non-list value')
        return PipelineListOutput(pipelines=pipelines)

    async def _get_pipeline(self, context: RequestContext, input: PipelineGetInput) -> PipelineGetOutput:
        if input.include_secret:
            require_permission(context, Permission.RESOURCE_MANAGE)
        pipeline = await self.ap.pipeline_service.get_pipeline(
            context,
            input.pipeline_uuid,
            include_secret=input.include_secret,
        )
        if pipeline is not None and not isinstance(pipeline, dict):
            raise _InvalidApplicationOutput('pipeline.get returned a non-object value')
        return PipelineGetOutput(pipeline=pipeline)

    async def _get_pipeline_extensions(
        self,
        context: RequestContext,
        input: PipelineExtensionsGetInput,
    ) -> PipelineExtensionsGetOutput:
        getter = getattr(self.ap.pipeline_service, 'get_pipeline_extensions', None)
        if callable(getter):
            getter_is_async = inspect.iscoroutinefunction(getter)
            extensions = getter(context, input.pipeline_uuid)
            if inspect.isawaitable(extensions):
                extensions = await extensions
            if not isinstance(extensions, dict):
                # A few isolated HTTP graphs expose a bare ``Mock`` for
                # optional service methods. Treat that as an absent method so
                # the compatibility implementation below can run; a real
                # async service method returning the wrong DTO is a contract
                # violation and remains a hard failure.
                if getter_is_async:
                    raise _InvalidApplicationOutput('pipeline.extensions.get returned a non-object value')
            else:
                return PipelineExtensionsGetOutput(extensions=extensions)

        # Compatibility path for lightweight service doubles and older service
        # graphs. The production PipelineService owns this implementation;
        # this fallback keeps the shared facade usable while a graph is being
        # assembled and preserves its fail-closed normalization semantics.
        from ...pipeline.extension_preferences import normalize_extension_preferences

        pipeline = await self.ap.pipeline_service.get_pipeline(context, input.pipeline_uuid)
        if pipeline is None:
            return PipelineExtensionsGetOutput(extensions={})
        connector = getattr(self.ap, 'plugin_connector', None)
        plugins = []
        if connector is not None:
            if getattr(connector, 'is_enable_plugin', False) is True:
                require_context = getattr(connector, 'require_workspace_context', None)
                if callable(require_context):
                    require_context_result = require_context(context)
                    if inspect.isawaitable(require_context_result):
                        await require_context_result
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
        extensions = {
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
        return PipelineExtensionsGetOutput(extensions=extensions)

    async def _update_pipeline_extensions(
        self,
        context: RequestContext,
        input: PipelineExtensionsUpdateInput,
    ) -> PipelineExtensionsUpdateOutput:
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

    async def _list_knowledge_bases(
        self, context: RequestContext, input: KnowledgeBaseListInput
    ) -> KnowledgeBaseListOutput:
        if input.include_secret is True:
            require_permission(context, Permission.RESOURCE_MANAGE)
        if input.include_secret is None:
            bases = await self.ap.knowledge_service.get_knowledge_bases(context)
        else:
            bases = await self.ap.knowledge_service.get_knowledge_bases(
                context,
                include_secret=input.include_secret,
            )
        if not isinstance(bases, list):
            raise _InvalidApplicationOutput('knowledge_base.list returned a non-list value')
        return KnowledgeBaseListOutput(bases=bases)

    async def _get_knowledge_base(
        self, context: RequestContext, input: KnowledgeBaseGetInput
    ) -> KnowledgeBaseGetOutput:
        if input.include_secret:
            require_permission(context, Permission.RESOURCE_MANAGE)
        base = await self.ap.knowledge_service.get_knowledge_base(
            context,
            input.knowledge_base_uuid,
            include_secret=input.include_secret,
        )
        if base is not None and not isinstance(base, dict):
            raise _InvalidApplicationOutput('knowledge_base.get returned a non-object value')
        return KnowledgeBaseGetOutput(base=base)

    async def _list_knowledge_engines(
        self, context: RequestContext, input: KnowledgeEngineListInput
    ) -> KnowledgeEngineListOutput:
        engines = await self.ap.knowledge_service.list_knowledge_engines(context)
        if not isinstance(engines, list):
            raise _InvalidApplicationOutput('knowledge_engine.list returned a non-list value')
        return KnowledgeEngineListOutput(engines=engines)

    async def _get_knowledge_engine_schema(
        self, context: RequestContext, input: KnowledgeEngineSchemaInput
    ) -> KnowledgeEngineSchemaOutput:
        if input.kind not in {'creation', 'retrieval'}:
            raise ApplicationAPIException(
                ApplicationAPIError('invalid_input', 'kind must be creation or retrieval', 400)
            )
        getter = (
            self.ap.knowledge_service.get_engine_creation_schema
            if input.kind == 'creation'
            else self.ap.knowledge_service.get_engine_retrieval_schema
        )
        schema = await getter(context, input.plugin_id)
        if not isinstance(schema, (dict, list)):
            raise _InvalidApplicationOutput('knowledge.engine.schema.get returned a non-object value')
        if isinstance(schema, list) and not all(isinstance(item, dict) for item in schema):
            raise _InvalidApplicationOutput('knowledge.engine.schema.get returned invalid field definitions')
        return KnowledgeEngineSchemaOutput(schema=schema)

    async def list_pipelines(
        self,
        context: RequestContext,
        sort_by: str = 'created_at',
        sort_order: str = 'DESC',
        *,
        include_secret: bool | None = None,
    ) -> list[dict]:
        """Compatibility helper returning the unwrapped list payload."""

        output = await self.execute(
            'pipeline.list',
            context,
            PipelineListInput(sort_by=sort_by, sort_order=sort_order, include_secret=include_secret),
        )
        return output.pipelines

    async def get_pipeline(
        self,
        context: RequestContext,
        pipeline_uuid: str,
        *,
        include_secret: bool = False,
    ) -> dict | None:
        """Compatibility helper returning the unwrapped Pipeline payload."""

        output = await self.execute(
            'pipeline.get',
            context,
            PipelineGetInput(pipeline_uuid=pipeline_uuid, include_secret=include_secret),
        )
        return output.pipeline

    async def get_pipeline_extensions(
        self,
        context: RequestContext,
        pipeline_uuid: str,
    ) -> dict:
        """Compatibility helper returning the unwrapped extension payload."""

        output = await self.execute(
            'pipeline.extensions.get',
            context,
            PipelineExtensionsGetInput(pipeline_uuid=pipeline_uuid),
        )
        return output.extensions

    async def update_pipeline_extensions(
        self,
        context: RequestContext,
        input: PipelineExtensionsUpdateInput,
    ) -> PipelineExtensionsUpdateOutput:
        """Compatibility helper preserving the typed write output."""

        return await self.execute('pipeline.extensions.update', context, input)
