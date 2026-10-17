"""Application-level operations shared by HTTP, MCP and assistant adapters.

This is intentionally a small first slice for issue #2639.  Protocol adapters
remain responsible for transport and presentation; this module owns the
workspace-scoped operation contract and the permission check at the shared
boundary.
"""

from __future__ import annotations

import dataclasses
import typing

from ..authz import Permission, require_permission
from ..context import RequestContext
from pydantic import TypeAdapter, ValidationError

from ...workspace.errors import WorkspaceNotFoundError


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
class KnowledgeBaseListInput:
    include_secret: bool = False


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
    """Permission and data types required by one operation."""

    permission: Permission
    input_type: type
    output_type: type


OPERATIONS: dict[str, OperationSpec] = {
    'pipeline.list': OperationSpec(
        Permission.RESOURCE_VIEW,
        input_type=PipelineListInput,
        output_type=PipelineListOutput,
    ),
    'pipeline.get': OperationSpec(
        Permission.RESOURCE_VIEW,
        input_type=PipelineGetInput,
        output_type=PipelineGetOutput,
    ),
    'pipeline.extensions.get': OperationSpec(
        Permission.RESOURCE_VIEW,
        input_type=PipelineExtensionsGetInput,
        output_type=PipelineExtensionsGetOutput,
    ),
    'pipeline.extensions.update': OperationSpec(
        Permission.RESOURCE_MANAGE,
        input_type=PipelineExtensionsUpdateInput,
        output_type=PipelineExtensionsUpdateOutput,
    ),
    'knowledge.base.list': OperationSpec(
        Permission.RESOURCE_VIEW,
        input_type=KnowledgeBaseListInput,
        output_type=KnowledgeBaseListOutput,
    ),
    'knowledge.base.get': OperationSpec(
        Permission.RESOURCE_VIEW,
        input_type=KnowledgeBaseGetInput,
        output_type=KnowledgeBaseGetOutput,
    ),
    'knowledge.engine.list': OperationSpec(
        Permission.RESOURCE_VIEW,
        input_type=KnowledgeEngineListInput,
        output_type=KnowledgeEngineListOutput,
    ),
    'knowledge.engine.schema.get': OperationSpec(
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
    def _validate_dto(value: typing.Any, expected_type: type, *, output: bool = False) -> None:
        code, status = ('invalid_output', 500) if output else ('invalid_input', 400)
        if type(value) is not expected_type:
            raise ApplicationAPIException(
                ApplicationAPIError(code, f'Expected {expected_type.__name__}, received {type(value).__name__}', status)
            )
        for name, annotation in typing.get_type_hints(expected_type).items():
            try:
                TypeAdapter(annotation).validate_python(getattr(value, name), strict=True)
            except ValidationError as exc:
                raise ApplicationAPIException(ApplicationAPIError(code, f'{name} has an invalid type', status)) from exc

    async def execute(
        self,
        operation_id: str,
        context: RequestContext,
        input: typing.Any,
    ) -> typing.Any:
        """Execute an operation with strict DTO and Workspace permission checks.

        Protocol adapters receive the typed output DTO and are responsible for
        unwrapping it into their wire representation.  No adapter object or
        transport-specific response is accepted at this boundary.
        """

        spec = OPERATIONS.get(operation_id)
        if spec is None:
            raise ApplicationAPIException(
                ApplicationAPIError('unknown_operation', 'Unknown application operation', 404)
            )
        self._validate_dto(input, spec.input_type)
        require_permission(context, spec.permission)
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
        except WorkspaceNotFoundError as exc:
            raise ApplicationAPIException(ApplicationAPIError('resource_not_found', 'Resource not found', 404)) from exc
        except ValueError as exc:
            raise ApplicationAPIException(ApplicationAPIError('validation_error', str(exc), 400)) from exc
        self._validate_dto(output, spec.output_type, output=True)
        return output

    async def _list_pipelines(self, context: RequestContext, input: PipelineListInput) -> PipelineListOutput:
        # Secret-bearing pipeline configuration must never be exposed merely
        # because a caller supplied ``include_secret=True``.  The operation
        # permission is intentionally stricter than the read permission.
        if input.include_secret is True:
            require_permission(context, Permission.RESOURCE_MANAGE)
        pipelines = await self.ap.pipeline_service.get_pipelines(
            context,
            input.sort_by,
            input.sort_order,
            include_secret=input.include_secret,
        )
        return PipelineListOutput(pipelines=pipelines)

    async def _get_pipeline(self, context: RequestContext, input: PipelineGetInput) -> PipelineGetOutput:
        if input.include_secret:
            require_permission(context, Permission.RESOURCE_MANAGE)
        pipeline = await self.ap.pipeline_service.get_pipeline(
            context,
            input.pipeline_uuid,
            include_secret=input.include_secret,
        )
        return PipelineGetOutput(pipeline=pipeline)

    async def _get_pipeline_extensions(
        self,
        context: RequestContext,
        input: PipelineExtensionsGetInput,
    ) -> PipelineExtensionsGetOutput:
        extensions = await self.ap.pipeline_service.get_pipeline_extensions(context, input.pipeline_uuid)
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
        bases = await self.ap.knowledge_service.get_knowledge_bases(context, include_secret=input.include_secret)
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
        return KnowledgeBaseGetOutput(base=base)

    async def _list_knowledge_engines(
        self, context: RequestContext, input: KnowledgeEngineListInput
    ) -> KnowledgeEngineListOutput:
        engines = await self.ap.knowledge_service.list_knowledge_engines(context)
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
        return KnowledgeEngineSchemaOutput(schema=schema)

    async def list_pipelines(
        self,
        context: RequestContext,
        sort_by: str = 'created_at',
        sort_order: str = 'DESC',
        *,
        include_secret: bool = False,
    ) -> list[dict]:
        """Return the unwrapped list payload."""

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
        """Return the unwrapped Pipeline payload."""

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
        """Return the unwrapped extension payload."""

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
        """Return the typed write output."""

        return await self.execute('pipeline.extensions.update', context, input)
