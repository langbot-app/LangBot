"""A deliberately small allowlist of management operations; no shell or arbitrary HTTP."""

import copy
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from langbot_plugin.api.entities.builtin.resource.tool import LLMTool

from ..authz import Permission, require_permission
from ..context import ExecutionContext
from .secrets import redact_secrets


class Arguments(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ListResources(Arguments):
    kind: Literal['models', 'embedding_models', 'pipelines', 'knowledge_bases', 'knowledge_engines']


#: Canonical resource types, mirrored from the trace service action table. The
#: enum lets the model pick a value that exists instead of guessing a string
#: that matches nothing.
_RESOURCE_TYPES = (
    'bot',
    'adapter',
    'model_provider',
    'llm_model',
    'pipeline',
    'user',
    'workspace',
    'monitoring',
    'webhook',
    'api_key',
    'workspace_settings',
    'member',
    'member_invitation',
    'operation_log',
    'plugin',
    'plugin_page',
    'skill',
    'knowledge_base',
    'mcp_server',
    'runtime',
    'system',
    'resource',
)


class ListOperationLogs(Arguments):
    """Read the Workspace operation trace (owner / admin only)."""

    #: Optional free-text filter is mapped to a substring match so the caller
    #: can name a plugin, an account or a verb ("install") without knowing the
    #: stored action key. Prefer this over ``action`` when unsure of the key.
    search: str | None = Field(default=None, max_length=100)
    #: Exact stored action key, e.g. ``plugin_install`` (see the action list in
    #: the tool description). Only use it when the exact key is known.
    action: str | None = Field(default=None, max_length=64)
    resource_type: str | None = Field(
        default=None,
        max_length=64,
        description='Optional resource type filter. Valid values: ' + ', '.join(_RESOURCE_TYPES) + '.',
    )
    actor: str | None = Field(
        default=None,
        max_length=64,
        description='Optional actor filter: an account UUID or part of the actor name.',
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=50,
        description='Maximum records to return. Keep it small (10-20) for a targeted answer.',
    )


#: Forensics fields the settings panel needs but an answer does not; dropping
#: them keeps a page of records far below the assistant's per-result budget.
_COMPACT_CHANGE_FIELDS = 6
_COMPACT_CHANGE_CHARS = 160


def _brief(value, limit: int = _COMPACT_CHANGE_CHARS):
    """Render a diff value as a bounded string (mirrors the trace service)."""

    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = value if isinstance(value, str) else str(value)
    return text if len(text) <= limit else text[: max(limit - 1, 0)] + '…'


def _compact_operation_records(result: dict) -> dict:
    """Project operation records onto the fields a "who did what" answer needs.

    ``query_logs`` returns the full panel payload -- hash chain, user agent,
    payload details -- which is roughly a kilobyte per row. A whole page of
    those overflows the assistant's per-result budget and arrives as a raw
    truncated preview the model cannot read, which is why an answer can end up
    claiming the data is unavailable. Only the actor, the action, the target,
    the timestamp and the verification verdicts are kept here; the heavy
    forensic columns stay available through the settings panel export.
    """

    def record(row: dict) -> dict:
        changes = [
            {
                'field': change.get('field'),
                'before': _brief(change.get('before')),
                'after': _brief(change.get('after')),
            }
            for change in (row.get('changes') or [])[:_COMPACT_CHANGE_FIELDS]
        ]
        return {
            'id': row.get('id'),
            'created_at': row.get('created_at'),
            'actor': row.get('actor_name') or row.get('actor_account_uuid'),
            'actor_role': row.get('actor_role'),
            'action': row.get('action'),
            'action_i18n_key': row.get('action_i18n_key'),
            'resource_type': row.get('resource_type'),
            'resource_id': row.get('resource_id'),
            'summary': row.get('summary'),
            'changes': changes,
            'outcome': row.get('outcome'),
            'http_method': row.get('http_method'),
            'route': row.get('route'),
            'integrity_ok': row.get('integrity_ok'),
            'chain_ok': row.get('chain_ok'),
            'tampered': row.get('tampered'),
        }

    records = result.get('records') or []
    return {
        'total': result.get('total', len(records)),
        'returned': len(records),
        'tampered_count': result.get('tampered_count', 0),
        'integrity_failed_count': result.get('integrity_failed_count', 0),
        'chain_failed_count': result.get('chain_failed_count', 0),
        'records': [record(row) for row in records],
    }


class PipelineID(Arguments):
    pipeline_uuid: UUID


class PipelineExtensionsID(PipelineID):
    pass


class EngineID(Arguments):
    plugin_id: str = Field(min_length=3, max_length=255)


class CreatePipeline(Arguments):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=1000)


class ConfigurePipeline(PipelineID):
    model_uuid: UUID
    system_prompt: str = Field(min_length=1, max_length=8000)
    knowledge_base_uuids: list[UUID] = Field(max_length=8)


class CreateKnowledgeBase(CreatePipeline):
    knowledge_engine_plugin_id: str = Field(min_length=3, max_length=255)
    creation_settings: dict = Field(default_factory=dict)
    retrieval_settings: dict = Field(default_factory=dict)


#: Each entry is ``(schema, description, writes, extra_permission)``. ``writes``
#: selects resource.manage vs resource.view; ``extra_permission`` narrows a tool
#: further (e.g. the audit surface needs ``audit.view``, which only the owner
#: and admin hold) and both are enforced identically when listing and calling.
TOOLS = {
    'list_resources': (
        ListResources,
        'List existing Workspace resources. Discover IDs before using them.',
        False,
        None,
    ),
    'get_pipeline': (PipelineID, 'Read a Pipeline configuration with secrets redacted.', False, None),
    'get_pipeline_extensions': (
        PipelineExtensionsID,
        'Read Pipeline extension bindings and available Workspace extensions.',
        False,
        None,
    ),
    'get_knowledge_schema': (EngineID, 'Get the engine creation and retrieval configuration schemas.', False, None),
    'list_operation_logs': (
        ListOperationLogs,
        'Search the Workspace operation trace (who changed or viewed what, with before/after fields). '
        'Owner and admin only. Always pass a narrow filter instead of dumping everything: use "search" '
        'for a substring such as a plugin name, an account or a verb (e.g. search="LangTARS" or '
        'search="install"); use the exact "action" key only when known - valid keys include '
        'plugin_install, plugin_uninstall, plugin_config, plugin_view, plugin_upgrade, skill_install, '
        'skill_uninstall, create, update, delete, view, export, execute, debug, publish, member_invite, '
        'member_role_update, member_remove, member_view, settings_update, settings_view, audit_log_view, '
        'pipeline_extensions_update, knowledge_base_update, knowledge_base_delete, mcp_config, mcp_delete. '
        'Combine resource_type and actor to answer "who installed X".',
        False,
        Permission.AUDIT_VIEW,
    ),
    'create_pipeline': (
        CreatePipeline,
        'Create an unconnected Pipeline draft. Requires user confirmation.',
        True,
        None,
    ),
    'configure_pipeline': (
        ConfigurePipeline,
        'Set the local-agent model, system prompt and complete knowledge-base binding list. Requires confirmation.',
        True,
        None,
    ),
    'create_knowledge_base': (
        CreateKnowledgeBase,
        'Create a knowledge base using an installed engine. Read its schema first. Requires confirmation.',
        True,
        None,
    ),
}


def _required_permission(writes: bool, extra: Permission | None) -> Permission:
    """Return the permission a tool needs beyond the base resource verbs."""

    if extra is not None:
        return extra
    return Permission.RESOURCE_MANAGE if writes else Permission.RESOURCE_VIEW


def _authorized(context, name: str) -> bool:
    _schema, _description, writes, extra = TOOLS[name]
    return _required_permission(writes, extra).value in context.workspace.permissions


def validate_call(context, name: str, arguments: dict) -> Arguments:
    if name not in TOOLS:
        raise ValueError('Unknown management tool')
    schema, _, writes, extra = TOOLS[name]
    require_permission(context, _required_permission(writes, extra))
    return schema.model_validate(arguments)


def tool_definitions(context) -> list[LLMTool]:
    return [
        LLMTool(
            name=name,
            human_desc=description,
            description=description,
            parameters=schema.model_json_schema(),
            func=execute_tool,
        )
        for name, (schema, description, _writes, _extra) in TOOLS.items()
        if _authorized(context, name)
    ]


async def execute_tool(ap, context, name: str, arguments: dict):
    args = validate_call(context, name, arguments).model_dump(mode='json')
    if name == 'list_resources':
        readers = {
            'models': ap.llm_model_service.get_llm_models,
            'embedding_models': ap.embedding_models_service.get_embedding_models,
            'pipelines': ap.pipeline_service.get_pipelines,
            'knowledge_bases': ap.knowledge_service.get_knowledge_bases,
            'knowledge_engines': ap.knowledge_service.list_knowledge_engines,
        }
        resources = await readers[args['kind']](context)
        if args['kind'] != 'knowledge_engines':
            # Lists discover resources; get_pipeline / get_knowledge_schema supply configuration details.
            fields = ('uuid', 'name', 'description', 'abilities', 'knowledge_engine_plugin_id')
            resources = [{key: item[key] for key in fields if key in item} for item in resources]
        return {'total': len(resources), 'items': redact_secrets(resources)}
    if name == 'list_operation_logs':
        # Delegates to the operation-trace service, so the assistant shows the
        # same records and tamper verification as the settings panel, then
        # compacts them so a full page still fits the per-result budget.
        result = await ap.workspace_settings_service.query_logs(
            context.workspace_uuid,
            limit=args['limit'],
            search=args['search'],
            action=args['action'],
            resource_type=args['resource_type'],
            actor_account_uuid=args['actor'],
        )
        compact = _compact_operation_records(result)
        # Echo the applied filters so the model can see why a result is empty
        # and widen a filter instead of repeating an empty targeted query.
        compact['query'] = {key: args[key] for key in ('search', 'action', 'resource_type', 'actor') if args.get(key)}
        return compact
    if name == 'get_pipeline':
        return await getattr(ap, 'application_api', ap.pipeline_service).get_pipeline(context, args['pipeline_uuid'])
    if name == 'get_pipeline_extensions':
        return await getattr(ap, 'application_api', ap.pipeline_service).get_pipeline_extensions(
            context, args['pipeline_uuid']
        )
    if name == 'get_knowledge_schema':
        return {
            'creation': await ap.knowledge_service.get_engine_creation_schema(context, args['plugin_id']),
            'retrieval': await ap.knowledge_service.get_engine_retrieval_schema(context, args['plugin_id']),
        }
    if name == 'create_pipeline':
        args['extensions_preferences'] = {
            'enable_all_plugins': False,
            'enable_all_mcp_servers': False,
            'enable_all_skills': False,
            'plugins': [],
            'mcp_servers': [],
            'skills': [],
            'mcp_resources': [],
        }
        resource_id = await ap.pipeline_service.create_pipeline(context, args)
        return {'uuid': resource_id, 'url': f'/home/pipelines?id={resource_id}', 'configured': False}
    if name == 'configure_pipeline':
        pipeline = await ap.pipeline_service.get_pipeline(context, args['pipeline_uuid'], include_secret=True)
        if pipeline is None:
            raise ValueError('Pipeline not found')
        await ap.model_mgr.get_model_by_uuid(ExecutionContext.from_request(context), args['model_uuid'])
        for kb_id in args['knowledge_base_uuids']:
            if await ap.knowledge_service.get_knowledge_base(context, kb_id) is None:
                raise ValueError('Knowledge base not found')
        config = copy.deepcopy(pipeline['config'])
        config['ai']['runner']['runner'] = 'local-agent'
        local = config['ai']['local-agent']
        local['model']['primary'] = args['model_uuid']
        local['prompt'] = [{'role': 'system', 'content': args['system_prompt']}]
        local['knowledge-bases'] = args['knowledge_base_uuids']
        await ap.pipeline_service.update_pipeline(context, args['pipeline_uuid'], {'config': config})
        return {'uuid': args['pipeline_uuid'], 'url': f'/home/pipelines?id={args["pipeline_uuid"]}'}
    resource_id = await ap.knowledge_service.create_knowledge_base(context, args)
    return {'uuid': resource_id, 'url': f'/home/knowledge?id={resource_id}'}
