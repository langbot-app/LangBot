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


class PipelineID(Arguments):
    pipeline_uuid: UUID


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


TOOLS = {
    'list_resources': (ListResources, 'List existing Workspace resources. Discover IDs before using them.', False),
    'get_pipeline': (PipelineID, 'Read a Pipeline configuration with secrets redacted.', False),
    'get_knowledge_schema': (EngineID, 'Get the engine creation and retrieval configuration schemas.', False),
    'create_pipeline': (CreatePipeline, 'Create an unconnected Pipeline draft. Requires user confirmation.', True),
    'configure_pipeline': (
        ConfigurePipeline,
        'Set the local-agent model, system prompt and complete knowledge-base binding list. Requires confirmation.',
        True,
    ),
    'create_knowledge_base': (
        CreateKnowledgeBase,
        'Create a knowledge base using an installed engine. Read its schema first. Requires confirmation.',
        True,
    ),
}


def validate_call(context, name: str, arguments: dict) -> Arguments:
    if name not in TOOLS:
        raise ValueError('Unknown management tool')
    schema, _, writes = TOOLS[name]
    require_permission(context, Permission.RESOURCE_MANAGE if writes else Permission.RESOURCE_VIEW)
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
        for name, (schema, description, writes) in TOOLS.items()
        if not writes or Permission.RESOURCE_MANAGE in context.workspace.permissions
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
    if name == 'get_pipeline':
        return await ap.pipeline_service.get_pipeline(context, args['pipeline_uuid'])
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
