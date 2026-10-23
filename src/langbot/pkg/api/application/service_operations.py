"""Explicit service-backed operations; schemas follow their business signatures."""

from __future__ import annotations

import importlib
import inspect
import typing
from functools import lru_cache

from pydantic import Field, create_model

from ..authz import Permission, require_permission
from ..context import PrincipalType
from ...workspace.errors import WorkspaceNotFoundError
from .contracts import Input, Operation

# Only these service methods are public. Adding a service method never exposes it.
_BINDINGS = (
    (
        'monitoring.session.reset',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'reset_session_context',
        'RESOURCE_MANAGE',
        True,
    ),
    ('pipeline.list', 'pipeline_service', 'pipeline', 'PipelineService', 'get_pipelines', 'RESOURCE_VIEW', False),
    ('pipeline.get', 'pipeline_service', 'pipeline', 'PipelineService', 'get_pipeline', 'RESOURCE_VIEW', False),
    ('pipeline.create', 'pipeline_service', 'pipeline', 'PipelineService', 'create_pipeline', 'RESOURCE_MANAGE', True),
    ('pipeline.update', 'pipeline_service', 'pipeline', 'PipelineService', 'update_pipeline', 'RESOURCE_MANAGE', True),
    ('pipeline.delete', 'pipeline_service', 'pipeline', 'PipelineService', 'delete_pipeline', 'RESOURCE_MANAGE', True),
    ('pipeline.copy', 'pipeline_service', 'pipeline', 'PipelineService', 'copy_pipeline', 'RESOURCE_MANAGE', True),
    (
        'pipeline.metadata',
        'pipeline_service',
        'pipeline',
        'PipelineService',
        'get_pipeline_metadata',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'pipeline.defaults',
        'pipeline_service',
        'pipeline',
        'PipelineService',
        'get_default_pipeline_config',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'pipeline.extensions.get',
        'pipeline_service',
        'pipeline',
        'PipelineService',
        'get_pipeline_extensions',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'pipeline.extensions.update',
        'pipeline_service',
        'pipeline',
        'PipelineService',
        'update_pipeline_extensions',
        'RESOURCE_MANAGE',
        True,
    ),
    ('model.llm.list', 'llm_model_service', 'model', 'LLMModelsService', 'get_llm_models', 'RESOURCE_VIEW', False),
    (
        'model.llm.list_by_provider',
        'llm_model_service',
        'model',
        'LLMModelsService',
        'get_llm_models_by_provider',
        'RESOURCE_VIEW',
        False,
    ),
    ('model.llm.get', 'llm_model_service', 'model', 'LLMModelsService', 'get_llm_model', 'RESOURCE_VIEW', False),
    (
        'model.llm.create',
        'llm_model_service',
        'model',
        'LLMModelsService',
        'create_llm_model',
        'PROVIDER_SECRET_MANAGE',
        True,
    ),
    (
        'model.llm.update',
        'llm_model_service',
        'model',
        'LLMModelsService',
        'update_llm_model',
        'PROVIDER_SECRET_MANAGE',
        True,
    ),
    ('model.llm.delete', 'llm_model_service', 'model', 'LLMModelsService', 'delete_llm_model', 'RESOURCE_MANAGE', True),
    (
        'model.llm.test',
        'llm_model_service',
        'model',
        'LLMModelsService',
        'test_llm_model',
        'PROVIDER_SECRET_MANAGE',
        True,
    ),
    (
        'model.llm.starred.get',
        'llm_model_service',
        'model',
        'LLMModelsService',
        'get_starred_model',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'model.llm.starred.set',
        'llm_model_service',
        'model',
        'LLMModelsService',
        'set_starred_model',
        'PROVIDER_SECRET_MANAGE',
        True,
    ),
    (
        'model.llm.default.get',
        'llm_model_service',
        'model',
        'LLMModelsService',
        'get_default_model',
        'RESOURCE_MANAGE',
        False,
    ),
    (
        'model.embedding.list',
        'embedding_models_service',
        'model',
        'EmbeddingModelsService',
        'get_embedding_models',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'model.embedding.list_by_provider',
        'embedding_models_service',
        'model',
        'EmbeddingModelsService',
        'get_embedding_models_by_provider',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'model.embedding.get',
        'embedding_models_service',
        'model',
        'EmbeddingModelsService',
        'get_embedding_model',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'model.embedding.create',
        'embedding_models_service',
        'model',
        'EmbeddingModelsService',
        'create_embedding_model',
        'PROVIDER_SECRET_MANAGE',
        True,
    ),
    (
        'model.embedding.update',
        'embedding_models_service',
        'model',
        'EmbeddingModelsService',
        'update_embedding_model',
        'PROVIDER_SECRET_MANAGE',
        True,
    ),
    (
        'model.embedding.delete',
        'embedding_models_service',
        'model',
        'EmbeddingModelsService',
        'delete_embedding_model',
        'RESOURCE_MANAGE',
        True,
    ),
    (
        'model.embedding.test',
        'embedding_models_service',
        'model',
        'EmbeddingModelsService',
        'test_embedding_model',
        'PROVIDER_SECRET_MANAGE',
        True,
    ),
    (
        'model.rerank.list',
        'rerank_models_service',
        'model',
        'RerankModelsService',
        'get_rerank_models',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'model.rerank.list_by_provider',
        'rerank_models_service',
        'model',
        'RerankModelsService',
        'get_rerank_models_by_provider',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'model.rerank.get',
        'rerank_models_service',
        'model',
        'RerankModelsService',
        'get_rerank_model',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'model.rerank.create',
        'rerank_models_service',
        'model',
        'RerankModelsService',
        'create_rerank_model',
        'PROVIDER_SECRET_MANAGE',
        True,
    ),
    (
        'model.rerank.update',
        'rerank_models_service',
        'model',
        'RerankModelsService',
        'update_rerank_model',
        'PROVIDER_SECRET_MANAGE',
        True,
    ),
    (
        'model.rerank.delete',
        'rerank_models_service',
        'model',
        'RerankModelsService',
        'delete_rerank_model',
        'RESOURCE_MANAGE',
        True,
    ),
    (
        'model.rerank.test',
        'rerank_models_service',
        'model',
        'RerankModelsService',
        'test_rerank_model',
        'PROVIDER_SECRET_MANAGE',
        True,
    ),
    ('provider.list', 'provider_service', 'provider', 'ModelProviderService', 'get_providers', 'RESOURCE_VIEW', False),
    ('provider.get', 'provider_service', 'provider', 'ModelProviderService', 'get_provider', 'RESOURCE_VIEW', False),
    (
        'provider.create',
        'provider_service',
        'provider',
        'ModelProviderService',
        'create_provider',
        'PROVIDER_SECRET_MANAGE',
        True,
    ),
    (
        'provider.update',
        'provider_service',
        'provider',
        'ModelProviderService',
        'update_provider',
        'PROVIDER_SECRET_MANAGE',
        True,
    ),
    (
        'provider.delete',
        'provider_service',
        'provider',
        'ModelProviderService',
        'delete_provider',
        'RESOURCE_MANAGE',
        True,
    ),
    (
        'provider.models.scan',
        'provider_service',
        'provider',
        'ModelProviderService',
        'scan_provider_models',
        'PROVIDER_SECRET_MANAGE',
        True,
    ),
    (
        'provider.models.count',
        'provider_service',
        'provider',
        'ModelProviderService',
        'get_provider_model_counts',
        'RESOURCE_VIEW',
        False,
    ),
    ('agent.list', 'agent_service', 'agent', 'AgentService', 'get_agents', 'RESOURCE_VIEW', False),
    ('agent.get', 'agent_service', 'agent', 'AgentService', 'get_agent', 'RESOURCE_VIEW', False),
    ('agent.create', 'agent_service', 'agent', 'AgentService', 'create_agent', 'RESOURCE_MANAGE', True),
    ('agent.update', 'agent_service', 'agent', 'AgentService', 'update_agent', 'RESOURCE_MANAGE', True),
    ('agent.delete', 'agent_service', 'agent', 'AgentService', 'delete_agent', 'RESOURCE_MANAGE', True),
    ('agent.metadata', 'agent_service', 'agent', 'AgentService', 'get_agent_metadata', 'RESOURCE_VIEW', False),
    ('agent.debug', 'agent_service', 'agent', 'AgentService', 'debug_agent', 'RUNTIME_OPERATE', True),
    ('agent.runs.list', 'agent_service', 'agent', 'AgentService', 'get_processor_runs', 'RESOURCE_VIEW', False),
    ('agent.runs.events', 'agent_service', 'agent', 'AgentService', 'get_processor_run_events', 'RESOURCE_VIEW', False),
    ('bot.list', 'bot_service', 'bot', 'BotService', 'get_bots', 'RESOURCE_VIEW', False),
    ('bot.get', 'bot_service', 'bot', 'BotService', 'get_bot', 'RESOURCE_VIEW', False),
    ('bot.runtime.get', 'bot_service', 'bot', 'BotService', 'get_runtime_bot_info', 'RESOURCE_VIEW', False),
    ('bot.create', 'bot_service', 'bot', 'BotService', 'create_bot', 'RESOURCE_MANAGE', True),
    ('bot.update', 'bot_service', 'bot', 'BotService', 'update_bot', 'RESOURCE_MANAGE', True),
    ('bot.delete', 'bot_service', 'bot', 'BotService', 'delete_bot', 'RESOURCE_MANAGE', True),
    ('bot.logs', 'bot_service', 'bot', 'BotService', 'list_event_logs', 'RESOURCE_VIEW', False),
    ('bot.routes.status', 'bot_service', 'bot', 'BotService', 'list_event_route_statuses', 'RESOURCE_VIEW', False),
    (
        'bot.group_filter.preview',
        'bot_service',
        'bot',
        'BotService',
        'preview_group_filter_migration',
        'RESOURCE_MANAGE',
        False,
    ),
    (
        'bot.group_filter.apply',
        'bot_service',
        'bot',
        'BotService',
        'apply_group_filter_migration',
        'RESOURCE_MANAGE',
        True,
    ),
    ('bot.message.send', 'bot_service', 'bot', 'BotService', 'send_message', 'RUNTIME_OPERATE', True),
    ('bot.message.test', 'bot_service', 'bot', 'BotService', 'send_http_bot_test_message', 'RESOURCE_MANAGE', True),
    ('bot.admins.list', 'bot_service', 'bot', 'BotService', 'get_bot_admins', 'RESOURCE_VIEW', False),
    ('bot.admins.add', 'bot_service', 'bot', 'BotService', 'add_bot_admin', 'RESOURCE_MANAGE', True),
    ('bot.admins.delete', 'bot_service', 'bot', 'BotService', 'delete_bot_admin', 'RESOURCE_MANAGE', True),
    (
        'knowledge.base.list',
        'knowledge_service',
        'knowledge',
        'KnowledgeService',
        'get_knowledge_bases',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'knowledge.base.get',
        'knowledge_service',
        'knowledge',
        'KnowledgeService',
        'get_knowledge_base',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'knowledge.base.create',
        'knowledge_service',
        'knowledge',
        'KnowledgeService',
        'create_knowledge_base',
        'RESOURCE_MANAGE',
        True,
    ),
    (
        'knowledge.base.update',
        'knowledge_service',
        'knowledge',
        'KnowledgeService',
        'update_knowledge_base',
        'RESOURCE_MANAGE',
        True,
    ),
    (
        'knowledge.base.delete',
        'knowledge_service',
        'knowledge',
        'KnowledgeService',
        'delete_knowledge_base',
        'RESOURCE_MANAGE',
        True,
    ),
    (
        'knowledge.base.retrieve',
        'knowledge_service',
        'knowledge',
        'KnowledgeService',
        'retrieve_knowledge_base',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'knowledge.file.list',
        'knowledge_service',
        'knowledge',
        'KnowledgeService',
        'get_files_by_knowledge_base',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'knowledge.file.store',
        'knowledge_service',
        'knowledge',
        'KnowledgeService',
        'store_file',
        'RESOURCE_MANAGE',
        True,
    ),
    (
        'knowledge.file.delete',
        'knowledge_service',
        'knowledge',
        'KnowledgeService',
        'delete_file',
        'RESOURCE_MANAGE',
        True,
    ),
    (
        'knowledge.engine.list',
        'knowledge_service',
        'knowledge',
        'KnowledgeService',
        'list_knowledge_engines',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'knowledge.engine.creation_schema',
        'knowledge_service',
        'knowledge',
        'KnowledgeService',
        'get_engine_creation_schema',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'knowledge.engine.retrieval_schema',
        'knowledge_service',
        'knowledge',
        'KnowledgeService',
        'get_engine_retrieval_schema',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'knowledge.parser.list',
        'knowledge_service',
        'knowledge',
        'KnowledgeService',
        'list_parsers',
        'RESOURCE_VIEW',
        False,
    ),
    ('mcp.server.list', 'mcp_service', 'mcp', 'MCPService', 'get_mcp_servers', 'RESOURCE_VIEW', False),
    ('mcp.server.get', 'mcp_service', 'mcp', 'MCPService', 'get_mcp_server_by_name', 'RESOURCE_VIEW', False),
    ('mcp.server.create', 'mcp_service', 'mcp', 'MCPService', 'create_mcp_server', 'RESOURCE_MANAGE', True),
    ('mcp.server.update', 'mcp_service', 'mcp', 'MCPService', 'update_mcp_server', 'RESOURCE_MANAGE', True),
    ('mcp.server.delete', 'mcp_service', 'mcp', 'MCPService', 'delete_mcp_server', 'RESOURCE_MANAGE', True),
    ('mcp.server.test', 'mcp_service', 'mcp', 'MCPService', 'test_mcp_server', 'RESOURCE_MANAGE', True),
    ('mcp.server.logs', 'mcp_service', 'mcp', 'MCPService', 'get_mcp_server_logs', 'AUDIT_VIEW', False),
    ('mcp.server.runtime', 'mcp_service', 'mcp', 'MCPService', 'get_runtime_info', 'RESOURCE_VIEW', False),
    ('mcp.resource.list', 'mcp_service', 'mcp', 'MCPService', 'get_mcp_server_resources', 'RESOURCE_VIEW', False),
    (
        'mcp.resource.templates',
        'mcp_service',
        'mcp',
        'MCPService',
        'get_mcp_server_resource_templates',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'mcp.resource.read',
        'mcp_service',
        'mcp',
        'MCPService',
        'read_mcp_server_resource_envelope',
        'RESOURCE_VIEW',
        False,
    ),
    ('skill.list', 'skill_service', 'skill', 'SkillService', 'list_skills', 'RESOURCE_VIEW', False),
    ('skill.get', 'skill_service', 'skill', 'SkillService', 'get_skill', 'RESOURCE_VIEW', False),
    ('skill.create', 'skill_service', 'skill', 'SkillService', 'create_skill', 'RESOURCE_MANAGE', True),
    ('skill.update', 'skill_service', 'skill', 'SkillService', 'update_skill', 'RESOURCE_MANAGE', True),
    ('skill.delete', 'skill_service', 'skill', 'SkillService', 'delete_skill', 'RESOURCE_MANAGE', True),
    ('skill.file.list', 'skill_service', 'skill', 'SkillService', 'list_skill_files', 'RESOURCE_VIEW', False),
    ('skill.file.read', 'skill_service', 'skill', 'SkillService', 'read_skill_file', 'RESOURCE_VIEW', False),
    ('skill.file.write', 'skill_service', 'skill', 'SkillService', 'write_skill_file', 'RESOURCE_MANAGE', True),
    ('skill.github.install', 'skill_service', 'skill', 'SkillService', 'install_from_github', 'RESOURCE_MANAGE', True),
    (
        'skill.github.preview',
        'skill_service',
        'skill',
        'SkillService',
        'preview_install_from_github',
        'RESOURCE_MANAGE',
        False,
    ),
    ('skill.zip.install', 'skill_service', 'skill', 'SkillService', 'install_from_zip_upload', 'RESOURCE_MANAGE', True),
    (
        'skill.zip.preview',
        'skill_service',
        'skill',
        'SkillService',
        'preview_install_from_zip_upload',
        'RESOURCE_MANAGE',
        False,
    ),
    (
        'skill.directory.scan',
        'skill_service',
        'skill',
        'SkillService',
        'scan_directory_async',
        'RESOURCE_MANAGE',
        False,
    ),
    (
        'skill.directory.import',
        'skill_service',
        'skill',
        'SkillService',
        'import_skill_directory',
        'RESOURCE_MANAGE',
        True,
    ),
    ('skill.reload', 'skill_service', 'skill', 'SkillService', 'reload_skills', 'RESOURCE_MANAGE', True),
    ('api_key.list', 'apikey_service', 'apikey', 'ApiKeyService', 'get_api_keys', 'API_KEY_MANAGE', False),
    ('api_key.get', 'apikey_service', 'apikey', 'ApiKeyService', 'get_api_key', 'API_KEY_MANAGE', False),
    ('api_key.create', 'apikey_service', 'apikey', 'ApiKeyService', 'create_api_key', 'API_KEY_MANAGE', True),
    ('api_key.update', 'apikey_service', 'apikey', 'ApiKeyService', 'update_api_key', 'API_KEY_MANAGE', True),
    ('api_key.delete', 'apikey_service', 'apikey', 'ApiKeyService', 'delete_api_key', 'API_KEY_MANAGE', True),
    ('webhook.list', 'webhook_service', 'webhook', 'WebhookService', 'get_webhooks', 'RESOURCE_VIEW', False),
    ('webhook.get', 'webhook_service', 'webhook', 'WebhookService', 'get_webhook', 'RESOURCE_VIEW', False),
    ('webhook.create', 'webhook_service', 'webhook', 'WebhookService', 'create_webhook', 'RESOURCE_MANAGE', True),
    ('webhook.update', 'webhook_service', 'webhook', 'WebhookService', 'update_webhook', 'RESOURCE_MANAGE', True),
    ('webhook.delete', 'webhook_service', 'webhook', 'WebhookService', 'delete_webhook', 'RESOURCE_MANAGE', True),
    (
        'monitoring.overview',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_overview_metrics',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.executions',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_executions',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.inflight',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_inflight_snapshot',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.tokens',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_token_statistics',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.messages',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_messages',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.llm_calls',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_llm_calls',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.tool_calls',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_tool_calls',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.embedding_calls',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_embedding_calls',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.sessions',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_sessions',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.errors',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_errors',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.session.analysis',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_session_analysis',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.message.detail',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_message_details',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.feedback.stats',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_feedback_stats',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.feedback.list',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'get_feedback_list',
        'RESOURCE_VIEW',
        False,
    ),
    (
        'monitoring.export.messages',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'export_messages',
        'DATA_EXPORT',
        False,
    ),
    (
        'monitoring.export.llm_calls',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'export_llm_calls',
        'DATA_EXPORT',
        False,
    ),
    (
        'monitoring.export.embedding_calls',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'export_embedding_calls',
        'DATA_EXPORT',
        False,
    ),
    (
        'monitoring.export.errors',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'export_errors',
        'DATA_EXPORT',
        False,
    ),
    (
        'monitoring.export.sessions',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'export_sessions',
        'DATA_EXPORT',
        False,
    ),
    (
        'monitoring.export.feedback',
        'monitoring_service',
        'monitoring',
        'MonitoringService',
        'export_feedback',
        'DATA_EXPORT',
        False,
    ),
    (
        'monitoring.execution.detail',
        'monitoring_service',
        'monitoring_execution_details',
        'ExecutionDetailsMixin',
        'get_execution_detail',
        'RESOURCE_VIEW',
        False,
    ),
)

# These methods predate annotated service contracts. Specify their public types explicitly.
_FIELD_TYPES = {
    'processor_id': str,
    'run_id': str,
    'before_id': int | None,
    'after_sequence': int | None,
    'source': str,
    'execution_id': str,
    'section': str | None,
    'scopes': list[str] | None,
}
_OUTPUT_TYPES = {
    'get_processor_runs': dict,
    'get_processor_run_events': dict,
    'get_execution_detail': dict,
    'get_engine_creation_schema': dict | list[dict],
    'get_engine_retrieval_schema': dict | list[dict],
}
_INTERNAL_PARAMETERS = {'preserve_uuid', 'default', 'on_result', 'for_inflight'}


def _contract(operation_id, method):
    signature = inspect.signature(method)
    hints = typing.get_type_hints(method)
    fields = {}
    for name, parameter in signature.parameters.items():
        if name in {'self', 'context', 'ctx'} | _INTERNAL_PARAMETERS:
            continue
        annotation = _FIELD_TYPES.get(name, hints.get(name))
        default = parameter.default
        if annotation is None:
            if default is inspect.Parameter.empty or default is None:
                raise TypeError(f'Missing application input type: {operation_id}.{name}')
            annotation = type(default)
        if default is None:
            annotation = annotation | None
        default = ... if default is inspect.Parameter.empty else default
        constraints = {}
        if name in {'limit', 'max_count', 'max_entries'}:
            constraints = {'ge': 1, 'le': 100_000 if '.export.' in operation_id else 1000}
        elif name in {'offset', 'from_index', 'after_sequence', 'before_id'}:
            constraints = {'ge': 0}
        elif annotation is str and (name.endswith(('_uuid', '_id')) or name in {'query', 'uri'}):
            constraints = {'min_length': 1}
        fields[name] = (annotation, Field(default=default, **constraints))
    model_name = ''.join(part.title() for part in operation_id.split('.')) + 'Input'
    model = create_model(model_name, __base__=Input, **fields)
    output = _OUTPUT_TYPES.get(method.__name__, hints.get('return', inspect.Parameter.empty))
    if output is inspect.Parameter.empty:
        raise TypeError(f'Missing application output type: {operation_id}')
    return model, output


def _operation(operation_id, service_name, method, permission, side_effect):
    input_type, output_type = _contract(operation_id, method)

    async def invoke(ap, context, payload):
        arguments = payload.model_dump()
        if arguments.get('include_secret'):
            secret_permission = (
                Permission.PROVIDER_SECRET_MANAGE
                if operation_id.startswith(('model.', 'provider.'))
                else Permission.RESOURCE_MANAGE
            )
            require_permission(context, secret_permission)
        service = getattr(ap, service_name)
        result = await getattr(service, method.__name__)(context, **arguments)
        if result is None and operation_id.endswith('.get') and output_type != type(None):
            # Optional defaults (e.g. starred model) are intentionally nullable.
            if operation_id not in {'model.llm.starred.get', 'model.llm.default.get'}:
                raise WorkspaceNotFoundError('Resource not found')
        return result

    return Operation(operation_id, Permission[permission], invoke, input_type, output_type, side_effect)


@lru_cache(maxsize=1)
def operations() -> tuple[Operation, ...]:
    result = []
    for operation_id, service_name, module, cls, method_name, permission, side_effect in _BINDINGS:
        service_module = importlib.import_module('langbot.pkg.api.http.service.' + module)
        method = getattr(getattr(service_module, cls), method_name)
        result.append(_operation(operation_id, service_name, method, permission, side_effect))
    result.extend(_special_operations())
    return tuple(result)


class PipelineRunInput(Input):
    pipeline_uuid: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=100_000)
    timeout: float = Field(default=60.0, gt=0, le=300)


async def _pipeline_run(ap, context, payload):
    from ..http.service.pipeline_run import run_pipeline

    return await run_pipeline(ap, context, **payload.model_dump())


class CodexProviderInput(Input):
    provider: str = Field(min_length=1)


class CodexAttemptInput(CodexProviderInput):
    authorization_id: str = Field(min_length=1)


class ConversationInput(Input):
    conversation_id: str = Field(min_length=1)


class StopInput(ConversationInput):
    revision: int = Field(ge=0)


class TurnInput(StopInput):
    text: str | None = Field(default=None, min_length=1, max_length=8000)
    approved: bool | None = None
    model_uuid: str | None = None


def _assistant_service(ap):
    from ..http.service.assistant import AssistantService

    service = getattr(ap, '_application_assistant_service', None)
    if service is None:
        service = ap._application_assistant_service = AssistantService(ap)
    return service


def _validate_turn(payload):
    if (payload.text is None) == (payload.approved is None) or (payload.text is not None and not payload.text.strip()):
        raise ValueError('Provide text or an approval decision')


async def _assistant(ap, context, payload, method):
    service = _assistant_service(ap)
    arguments = payload.model_dump()
    if method == 'turn':
        _validate_turn(payload)
    result = await getattr(service, method)(context, **arguments)
    return service.public_view(result) if method in {'create', 'turn'} else result


class RoutePreviewInput(Input):
    bot_uuid: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    event_data: dict | None = None
    event_context: dict | None = None
    event_bindings: list[dict] | None = None


async def _route_preview(ap, context, payload):
    return await ap.bot_service.dry_run_event_route(
        context,
        payload.bot_uuid,
        payload.event_type,
        event_data=payload.event_data,
        context=payload.event_context,
        event_bindings=payload.event_bindings,
    )


class MigrationInput(Input):
    body: dict


def _migration_service(ap):
    from ..http.service.pipeline_migration import PipelineMigrationService

    service = getattr(ap, '_application_pipeline_migration_service', None)
    if service is None:
        service = ap._application_pipeline_migration_service = PipelineMigrationService(ap)
    return service


async def _migration_preview(ap, context, payload):
    return await _migration_service(ap).preview(context)


async def _migration_execute(ap, context, payload):
    return await _migration_service(ap).execute(context, payload.body)


async def _assistant_start(ap, context, payload):
    _validate_turn(payload)
    service = _assistant_service(ap)
    await service.get(context, payload.conversation_id)
    service.start_run(context, payload.conversation_id, payload)
    return {'conversation_id': payload.conversation_id, 'revision': payload.revision + 1}


def _special_operations():
    account = frozenset({PrincipalType.ACCOUNT})
    result = [
        Operation('pipeline.run', Permission.RUNTIME_OPERATE, _pipeline_run, PipelineRunInput, dict, True),
        Operation('bot.routes.preview', Permission.RESOURCE_MANAGE, _route_preview, RoutePreviewInput, dict),
        Operation(
            'pipeline.migration.preview', Permission.RESOURCE_VIEW, _migration_preview, Input, dict, principals=account
        ),
        Operation(
            'pipeline.migration.execute',
            Permission.RESOURCE_MANAGE,
            _migration_execute,
            MigrationInput,
            dict,
            True,
            principals=account,
        ),
        Operation(
            'assistant.run.start',
            Permission.RUNTIME_OPERATE,
            _assistant_start,
            TurnInput,
            dict,
            True,
            principals=account,
        ),
    ]
    for method in ('status', 'start', 'poll', 'disconnect', 'cancel'):

        async def invoke(ap, context, payload, method=method):
            return await getattr(ap.provider_service.codex_auth, method)(context, **payload.model_dump())

        result.append(
            Operation(
                'provider.codex.' + method,
                Permission.PROVIDER_SECRET_MANAGE,
                invoke,
                CodexAttemptInput if method in {'poll', 'cancel'} else CodexProviderInput,
                type(None) if method in {'disconnect', 'cancel'} else dict,
                method != 'status',
                principals=frozenset({PrincipalType.ACCOUNT}),
            )
        )
    for name, method, model, output, permission, write in (
        ('list', 'list_conversations', Input, list[dict], Permission.RESOURCE_VIEW, False),
        ('get', 'progress', ConversationInput, dict, Permission.RESOURCE_VIEW, False),
        ('create', 'create', Input, dict, Permission.RUNTIME_OPERATE, True),
        ('stop', 'stop', StopInput, dict, Permission.RUNTIME_OPERATE, True),
        ('turn', 'turn', TurnInput, dict, Permission.RUNTIME_OPERATE, True),
        ('recommended_model', 'recommended_model', Input, dict, Permission.RUNTIME_OPERATE, False),
    ):

        async def invoke(ap, context, payload, method=method):
            return await _assistant(ap, context, payload, method)

        result.append(
            Operation(
                'assistant.' + name,
                permission,
                invoke,
                model,
                output,
                write,
                principals=frozenset({PrincipalType.ACCOUNT}),
            )
        )
    return result
