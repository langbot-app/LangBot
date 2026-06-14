from __future__ import annotations

import typing
from typing import Any, Union
import base64
import traceback

import sqlalchemy

from langbot_plugin.runtime.io import handler
from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.entities.io.actions.enums import (
    CommonAction,
    RuntimeToLangBotAction,
    LangBotToRuntimeAction,
    PluginToRuntimeAction,
)
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

from ..entity.persistence import plugin as persistence_plugin
from ..entity.persistence import bstorage as persistence_bstorage
from ..provider.modelmgr import requester as model_requester

from ..core import app
from ..utils import constants
from ..agent.runner.session_registry import get_session_registry
from ..agent.runner.config_migration import ConfigMigration
from ..agent.runner import config_schema


def _make_rag_error_response(error: Exception, error_type: str, **extra_context) -> handler.ActionResponse:
    """Create a clean error response for RAG operations.

    Args:
        error: The caught exception.
        error_type: A category string like 'EmbeddingError', 'VectorStoreError'.
        **extra_context: Additional context fields for the error message.
    """
    context_parts = [f'{k}={v}' for k, v in extra_context.items()]
    context_str = f' [{", ".join(context_parts)}]' if context_parts else ''
    message = f'[{error_type}/{type(error).__name__}]{context_str} {str(error)}'
    return handler.ActionResponse.error(message=message)


def _pop_query_llm_usage(query: Any) -> dict[str, Any] | None:
    """Read provider usage stashed on a query by RuntimeProvider."""
    if query is None or not getattr(query, 'variables', None):
        return None
    usage = query.variables.pop(model_requester.LLM_USAGE_QUERY_VARIABLE, None)
    if usage is None:
        return None
    if isinstance(usage, dict):
        return dict(usage)
    return None


def _i18n_to_dict(value: Any) -> dict[str, Any]:
    """Convert SDK i18n values to plain dictionaries."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, 'to_dict'):
        return value.to_dict()
    if hasattr(value, 'model_dump'):
        return value.model_dump()
    return {'en_US': str(value)}


def _i18n_to_text(value: Any) -> str:
    """Return a stable human-readable text from SDK i18n values."""
    data = _i18n_to_dict(value)
    for key in ('en_US', 'zh_Hans', 'zh_Hant'):
        text = data.get(key)
        if text:
            return str(text)
    for text in data.values():
        if text:
            return str(text)
    return ''


def _build_tool_detail(tool: Any, requested_tool_name: str | None = None) -> dict[str, Any]:
    """Normalize LLMTool and plugin ComponentManifest objects for tool detail APIs."""
    # TODO(litellm): This handler-local adapter is temporary. Once LiteLLM-backed
    # tool schema normalization owns tool detail generation, simplify GET_TOOL_DETAIL
    # and make ToolManager return one host-level tool detail shape.
    if hasattr(tool, 'metadata') and hasattr(tool, 'spec'):
        metadata = tool.metadata
        spec = tool.spec or {}
        description = spec.get('llm_prompt') or _i18n_to_text(getattr(metadata, 'description', None))
        parameters = spec.get('parameters') or {}

        return {
            'name': requested_tool_name or getattr(metadata, 'name', ''),
            'label': _i18n_to_dict(getattr(metadata, 'label', None)),
            'description': description,
            'human_desc': description,
            'parameters': parameters,
            'spec': spec,
        }

    name = getattr(tool, 'name', requested_tool_name or '')
    description = getattr(tool, 'description', None) or getattr(tool, 'human_desc', '') or ''
    parameters = getattr(tool, 'parameters', None) or {}

    return {
        'name': name,
        'label': {},
        'description': description,
        'human_desc': getattr(tool, 'human_desc', description) or description,
        'parameters': parameters,
        'spec': {'parameters': parameters},
    }


def _validate_artifact_access(
    session: dict[str, Any],
    artifact_metadata: dict[str, Any],
    operation: str,
) -> tuple[bool, str | None]:
    """Validate artifact access for a run session.

    Authorization rules (evaluated in order, first match wins):
    1. Artifact run_id matches session run_id → ALLOW (created by this run)
    2. Artifact has conversation_id AND matches session conversation_id → ALLOW (same conversation)
    3. Otherwise → DENY

    Note: Artifacts without conversation_id are NOT globally accessible by default.
    Without an explicit scope field, we enforce strict access control.

    Args:
        session: AgentRunSession dict with run_id and authorization snapshot
        artifact_metadata: Artifact metadata dict with conversation_id, run_id,
            and Host-only scope fields when available
        operation: Operation name for error messages ('metadata' or 'read')

    Returns:
        Tuple of (is_allowed, error_message). If is_allowed is False, error_message contains reason.
    """
    authorization = session['authorization']
    artifact_conversation_id = artifact_metadata.get('conversation_id')
    artifact_run_id = artifact_metadata.get('run_id')
    session_conversation_id = authorization.get('conversation_id')
    session_run_id = session.get('run_id')

    # Rule 1: Created by this run (allows cross-conversation access for self-created artifacts)
    if artifact_run_id and artifact_run_id == session_run_id:
        return True, None

    # Rule 2: Same conversation (requires artifact to have conversation_id)
    if artifact_conversation_id and session_conversation_id:
        if artifact_conversation_id == session_conversation_id and _artifact_matches_run_scope(session, artifact_metadata):
            return True, None

    # Rule 3: Deny - no matching authorization rule
    return False, f'Artifact {operation} access denied: artifact not in session conversation and not created by this run'


def _get_run_authorization(session: dict[str, Any]) -> dict[str, Any]:
    """Return the run-scoped authorization snapshot."""
    return session['authorization']


def _artifact_matches_run_scope(session: dict[str, Any], artifact_metadata: dict[str, Any]) -> bool:
    authorization = _get_run_authorization(session)
    for scope_key in ('bot_id', 'workspace_id', 'thread_id'):
        if authorization.get(scope_key) != artifact_metadata.get(scope_key):
            return False
    return True


def _public_artifact_metadata(artifact_metadata: dict[str, Any]) -> dict[str, Any]:
    public_metadata = dict(artifact_metadata)
    for scope_key in ('bot_id', 'workspace_id', 'thread_id'):
        public_metadata.pop(scope_key, None)
    return public_metadata


def _resolve_state_scope(
    session: dict[str, Any],
    scope: str,
) -> tuple[dict[str, Any] | None, str | None, handler.ActionResponse | None]:
    """Resolve state policy/context for an authorized run scope."""
    authorization = _get_run_authorization(session)
    state_policy = authorization['state_policy']

    if not state_policy.get('enable_state', True):
        return None, None, handler.ActionResponse.error(
            message='State access is disabled by binding policy'
        )

    state_scopes = state_policy.get('state_scopes', ['conversation', 'actor'])
    if scope not in state_scopes:
        return None, None, handler.ActionResponse.error(
            message=f'Scope "{scope}" is not enabled by binding policy'
        )

    state_context = authorization['state_context']
    scope_key = state_context.get('scope_keys', {}).get(scope)
    if not scope_key:
        return None, None, handler.ActionResponse.error(
            message=f'Scope key not available for scope "{scope}"'
        )

    return state_context, scope_key, None


async def _validate_agent_run_session(
    run_id: str,
    caller_plugin_identity: str | None,
    ap: app.Application,
    api_name: str,
    api_capability: str | None = None,
) -> Union[tuple[None, handler.ActionResponse], tuple[Any, None]]:
    """Validate an AgentRunner pull API run session and run-scoped API access."""
    session_registry = get_session_registry()
    session = await session_registry.get(run_id)
    if not session:
        return None, handler.ActionResponse.error(
            message=f'Run session {run_id} not found or expired'
        )

    session_plugin_identity = session.get('plugin_identity')
    if not isinstance(session_plugin_identity, str) or not session_plugin_identity.strip():
        ap.logger.warning(f'{api_name}: run_id {run_id} has no plugin_identity')
        return None, handler.ActionResponse.error(
            message=f'Run session {run_id} has no plugin_identity'
        )
    if not caller_plugin_identity:
        return None, handler.ActionResponse.error(
            message=f'caller_plugin_identity is required for run_id {run_id}'
        )
    if caller_plugin_identity != session_plugin_identity:
        ap.logger.warning(
            f'{api_name}: caller_plugin_identity {caller_plugin_identity} '
            f'does not match session plugin_identity {session_plugin_identity}'
        )
        return None, handler.ActionResponse.error(
            message=f'Plugin identity mismatch for run_id {run_id}'
        )

    if api_capability:
        available_apis = _get_run_authorization(session).get('available_apis', {})
        if not available_apis.get(api_capability, False):
            return None, handler.ActionResponse.error(
                message=f'{api_name} access not authorized'
            )

    return session, None


def _resolve_run_conversation(
    session: dict[str, Any],
    requested_conversation_id: str | None,
    api_name: str,
) -> tuple[str | None, handler.ActionResponse | None]:
    """Resolve and enforce current-run conversation scope."""
    session_conversation_id = _get_run_authorization(session).get('conversation_id')

    if requested_conversation_id:
        if not session_conversation_id:
            return None, handler.ActionResponse.error(
                message=f'{api_name} is not available without a run conversation'
            )
        if requested_conversation_id != session_conversation_id:
            return None, handler.ActionResponse.error(
                message=f'Conversation {requested_conversation_id} is not accessible by this run'
            )
        return requested_conversation_id, None

    return session_conversation_id, None


def _run_scope_filters(session: dict[str, Any]) -> dict[str, Any]:
    authorization = _get_run_authorization(session)
    return {
        'bot_id': authorization.get('bot_id'),
        'workspace_id': authorization.get('workspace_id'),
        'thread_id': authorization.get('thread_id'),
        'strict_thread': True,
    }


def _event_matches_run_scope(session: dict[str, Any], event: dict[str, Any]) -> bool:
    authorization = _get_run_authorization(session)
    if authorization.get('conversation_id') != event.get('conversation_id'):
        return False
    if authorization.get('bot_id') is not None and authorization.get('bot_id') != event.get('bot_id'):
        return False
    if authorization.get('workspace_id') is not None and authorization.get('workspace_id') != event.get('workspace_id'):
        return False
    if authorization.get('thread_id') != event.get('thread_id'):
        return False
    return True


def _project_event_record_for_api(event: dict[str, Any]) -> dict[str, Any]:
    """Project EventLogStore rows onto the SDK AgentEventRecord DTO."""
    seq = event.get('seq') or event.get('id')
    return {
        'event_id': event.get('event_id'),
        'event_type': event.get('event_type'),
        'event_time': event.get('event_time'),
        'source': event.get('source'),
        'bot_id': event.get('bot_id'),
        'workspace_id': event.get('workspace_id'),
        'conversation_id': event.get('conversation_id'),
        'thread_id': event.get('thread_id'),
        'actor_type': event.get('actor_type'),
        'actor_id': event.get('actor_id'),
        'actor_name': event.get('actor_name'),
        'subject_type': event.get('subject_type'),
        'subject_id': event.get('subject_id'),
        'input_summary': event.get('input_summary'),
        'input_ref': event.get('input_ref'),
        'raw_ref': event.get('raw_ref'),
        'seq': seq,
        'cursor': event.get('cursor') or (str(seq) if seq is not None else None),
        'created_at': event.get('created_at'),
        'metadata': event.get('metadata') or {},
    }


def _normalize_uuid_list(values: Any) -> list[str]:
    """Normalize a user/config supplied UUID list while preserving order."""
    if not isinstance(values, list):
        return []
    return list(
        dict.fromkeys(
            value for value in values if isinstance(value, str) and value not in config_schema.NONE_SENTINELS
        )
    )


async def _get_pipeline_knowledge_base_uuids(ap: app.Application, query: Any) -> list[str]:
    """Resolve pipeline-scoped KBs from preprocessed variables or runner schema."""
    variables = getattr(query, 'variables', {}) or {}
    if '_knowledge_base_uuids' in variables:
        return _normalize_uuid_list(variables.get('_knowledge_base_uuids'))

    pipeline_config = getattr(query, 'pipeline_config', None)
    if not pipeline_config:
        return []

    runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
    if not runner_id:
        return []

    runner_config = ConfigMigration.resolve_runner_config(pipeline_config, runner_id)
    registry = getattr(ap, 'agent_runner_registry', None)
    if registry is None:
        return []

    bound_plugins = variables.get('_pipeline_bound_plugins')
    try:
        descriptor = await registry.get(runner_id, bound_plugins)
    except Exception as e:
        ap.logger.warning(f'Failed to load AgentRunner descriptor for knowledge-base scope: {e}')
        return []

    return config_schema.extract_knowledge_base_uuids(descriptor, runner_config)


async def _validate_run_authorization(
    run_id: str,
    resource_type: str,
    resource_id: str,
    ap: app.Application,
    caller_plugin_identity: str | None = None,
    operation: str | None = None,
) -> Union[tuple[None, handler.ActionResponse], tuple[Any, None]]:
    """Validate run_id authorization for a resource access.

    Common validation logic for INVOKE_LLM, INVOKE_LLM_STREAM, CALL_TOOL,
    RETRIEVE_KNOWLEDGE_BASE, RETRIEVE_KNOWLEDGE, and storage/file actions.

    Args:
        run_id: The run_id to validate.
        resource_type: Resource type ('model', 'tool', 'knowledge_base', 'storage', 'file').
        resource_id: Resource identifier (model_uuid, tool_name, kb_id, 'plugin'/'workspace', file_key).
        ap: Application instance for logging.
        caller_plugin_identity: Plugin identity (author/name) of the caller.
            Required when the run session is bound to a plugin identity.
        operation: Optional resource operation required by the runtime action.

    Returns:
        Tuple of (session, None) if validation passes.
        Tuple of (None, error_response) if validation fails.
    """
    session_registry = get_session_registry()
    session = await session_registry.get(run_id)
    if not session:
        ap.logger.warning(
            f'{resource_type.upper()}: run_id {run_id} not found in session registry'
        )
        return None, handler.ActionResponse.error(
            message=f'Run session {run_id} not found or expired',
        )

    session_plugin_identity = session.get('plugin_identity')
    if not isinstance(session_plugin_identity, str) or not session_plugin_identity.strip():
        ap.logger.warning(
            f'{resource_type.upper()}: run_id {run_id} has no plugin_identity'
        )
        return None, handler.ActionResponse.error(
            message=f'Run session {run_id} has no plugin_identity',
        )
    if not caller_plugin_identity:
        return None, handler.ActionResponse.error(
            message=f'caller_plugin_identity is required for run_id {run_id}',
        )
    if caller_plugin_identity != session_plugin_identity:
        ap.logger.warning(
            f'{resource_type.upper()}: caller_plugin_identity {caller_plugin_identity} '
            f'does not match session plugin_identity {session_plugin_identity}'
        )
        return None, handler.ActionResponse.error(
            message=f'Plugin identity mismatch: caller {caller_plugin_identity} is not authorized for run_id {run_id}',
        )

    if not session_registry.is_resource_allowed(session, resource_type, resource_id, operation):
        ap.logger.warning(
            f'{resource_type.upper()}: {resource_id} operation {operation or "*"} not allowed for run_id {run_id}'
        )
        operation_suffix = f' for operation {operation}' if operation else ''
        return None, handler.ActionResponse.error(
            message=f'{resource_type} {resource_id} is not authorized{operation_suffix} for this agent run',
        )

    return session, None


def _get_cached_query(ap: app.Application, query_id: int | None) -> Any | None:
    """Return a cached Query for query-based runtime actions when available."""
    if query_id is None:
        return None

    try:
        return ap.query_pool.cached_queries.get(query_id)
    except Exception:
        return None


def _resolve_action_query(data: dict[str, Any], session: Any | None, ap: app.Application) -> Any | None:
    """Resolve the current Query from internal run state or query-based action payload."""
    query_id = None
    if session:
        query_id = session.get('query_id')
    if query_id is None:
        query_id = data.get('query_id')
    query = _get_cached_query(ap, query_id)
    if query is not None and session is not None:
        object.__setattr__(query, '_agent_run_session', session)
    return query


def _resolve_remove_think(data: dict[str, Any], query: Any | None) -> bool:
    """Resolve remove-think using explicit action override, then pipeline config."""
    if 'remove_think' in data:
        return bool(data.get('remove_think'))

    if query and getattr(query, 'pipeline_config', None):
        return bool(query.pipeline_config.get('output', {}).get('misc', {}).get('remove-think', False))

    return False


def _merge_model_extra_args(model: Any, call_extra_args: Any) -> dict[str, Any]:
    """Merge persisted model extra_args with action-level overrides."""
    merged: dict[str, Any] = {}

    model_extra_args = getattr(getattr(model, 'model_entity', None), 'extra_args', None)
    if isinstance(model_extra_args, dict):
        merged.update(model_extra_args)
    if isinstance(call_extra_args, dict):
        merged.update(call_extra_args)

    return merged


class RuntimeConnectionHandler(handler.Handler):
    """Runtime connection handler"""

    ap: app.Application

    def __init__(
        self,
        connection: Connection,
        disconnect_callback: typing.Callable[[], typing.Coroutine[typing.Any, typing.Any, bool]],
        ap: app.Application,
    ):
        super().__init__(connection, disconnect_callback)
        self.ap = ap

        @self.action(RuntimeToLangBotAction.INITIALIZE_PLUGIN_SETTINGS)
        async def initialize_plugin_settings(data: dict[str, Any]) -> handler.ActionResponse:
            """Initialize plugin settings"""
            # check if exists plugin setting
            plugin_author = data['plugin_author']
            plugin_name = data['plugin_name']
            install_source = data['install_source']
            install_info = data['install_info']

            try:
                result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(persistence_plugin.PluginSetting)
                    .where(persistence_plugin.PluginSetting.plugin_author == plugin_author)
                    .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
                )

                setting = result.first()

                if setting is not None:
                    # delete plugin setting
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.delete(persistence_plugin.PluginSetting)
                        .where(persistence_plugin.PluginSetting.plugin_author == plugin_author)
                        .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
                    )

                # create plugin setting
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(persistence_plugin.PluginSetting).values(
                        plugin_author=plugin_author,
                        plugin_name=plugin_name,
                        install_source=install_source,
                        install_info=install_info,
                        # inherit from existing setting
                        enabled=setting.enabled if setting is not None else True,
                        priority=setting.priority if setting is not None else 0,
                        config=setting.config if setting is not None else {},  # noqa: F821
                    )
                )

                return handler.ActionResponse.success(
                    data={},
                )
            except Exception as e:
                traceback.print_exc()
                return handler.ActionResponse.error(
                    message=f'Failed to initialize plugin settings: {e}',
                )

        @self.action(RuntimeToLangBotAction.GET_PLUGIN_SETTINGS)
        async def get_plugin_settings(data: dict[str, Any]) -> handler.ActionResponse:
            """Get plugin settings"""

            plugin_author = data['plugin_author']
            plugin_name = data['plugin_name']

            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_plugin.PluginSetting)
                .where(persistence_plugin.PluginSetting.plugin_author == plugin_author)
                .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
            )

            data = {
                'enabled': True,
                'priority': 0,
                'plugin_config': {},
                'install_source': 'local',
                'install_info': {},
            }

            setting = result.first()

            if setting is not None:
                data['enabled'] = setting.enabled
                data['priority'] = setting.priority
                data['plugin_config'] = setting.config
                data['install_source'] = setting.install_source
                data['install_info'] = setting.install_info

            return handler.ActionResponse.success(
                data=data,
            )

        @self.action(PluginToRuntimeAction.REPLY_MESSAGE)
        async def reply_message(data: dict[str, Any]) -> handler.ActionResponse:
            """Reply message"""
            query_id = data['query_id']
            message_chain = data['message_chain']
            quote_origin = data['quote_origin']

            if query_id not in self.ap.query_pool.cached_queries:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

            query = self.ap.query_pool.cached_queries[query_id]

            message_chain_obj = platform_message.MessageChain.model_validate(message_chain)

            self.ap.logger.debug(f'Reply message: {message_chain_obj.model_dump(serialize_as_any=False)}')

            await query.adapter.reply_message(
                query.message_event,
                message_chain_obj,
                quote_origin,
            )

            return handler.ActionResponse.success(
                data={},
            )

        @self.action(PluginToRuntimeAction.GET_BOT_UUID)
        async def get_bot_uuid(data: dict[str, Any]) -> handler.ActionResponse:
            """Get bot uuid"""
            query_id = data['query_id']
            if query_id not in self.ap.query_pool.cached_queries:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

            query = self.ap.query_pool.cached_queries[query_id]

            return handler.ActionResponse.success(
                data={
                    'bot_uuid': query.bot_uuid,
                },
            )

        @self.action(PluginToRuntimeAction.SET_QUERY_VAR)
        async def set_query_var(data: dict[str, Any]) -> handler.ActionResponse:
            """Set query var"""
            query_id = data['query_id']
            key = data['key']
            value = data['value']

            if query_id not in self.ap.query_pool.cached_queries:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

            query = self.ap.query_pool.cached_queries[query_id]

            query.variables[key] = value

            return handler.ActionResponse.success(
                data={},
            )

        @self.action(PluginToRuntimeAction.GET_QUERY_VAR)
        async def get_query_var(data: dict[str, Any]) -> handler.ActionResponse:
            """Get query var"""
            query_id = data['query_id']
            key = data['key']

            if query_id not in self.ap.query_pool.cached_queries:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

            query = self.ap.query_pool.cached_queries[query_id]

            return handler.ActionResponse.success(
                data={
                    'value': query.variables[key],
                },
            )

        @self.action(PluginToRuntimeAction.GET_QUERY_VARS)
        async def get_query_vars(data: dict[str, Any]) -> handler.ActionResponse:
            """Get query vars"""
            query_id = data['query_id']
            if query_id not in self.ap.query_pool.cached_queries:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

            query = self.ap.query_pool.cached_queries[query_id]

            return handler.ActionResponse.success(
                data={
                    'vars': query.variables,
                },
            )

        @self.action(PluginToRuntimeAction.CREATE_NEW_CONVERSATION)
        async def create_new_conversation(data: dict[str, Any]) -> handler.ActionResponse:
            """Create new conversation"""
            query_id = data['query_id']
            if query_id not in self.ap.query_pool.cached_queries:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

            query = self.ap.query_pool.cached_queries[query_id]

            query.session.using_conversation = None

            return handler.ActionResponse.success(
                data={},
            )

        @self.action(PluginToRuntimeAction.GET_LANGBOT_VERSION)
        async def get_langbot_version(data: dict[str, Any]) -> handler.ActionResponse:
            """Get langbot version"""
            return handler.ActionResponse.success(
                data={
                    'version': constants.semantic_version,
                },
            )

        @self.action(PluginToRuntimeAction.GET_BOTS)
        async def get_bots(data: dict[str, Any]) -> handler.ActionResponse:
            """Get bots"""
            bots = await self.ap.bot_service.get_bots(include_secret=False)
            return handler.ActionResponse.success(
                data={
                    'bots': bots,
                },
            )

        @self.action(PluginToRuntimeAction.GET_BOT_INFO)
        async def get_bot_info(data: dict[str, Any]) -> handler.ActionResponse:
            """Get bot info"""
            bot_uuid = data['bot_uuid']
            bot = await self.ap.bot_service.get_runtime_bot_info(bot_uuid, include_secret=False)
            return handler.ActionResponse.success(
                data={
                    'bot': bot,
                },
            )

        @self.action(PluginToRuntimeAction.SEND_MESSAGE)
        async def send_message(data: dict[str, Any]) -> handler.ActionResponse:
            """Send message"""
            bot_uuid = data['bot_uuid']
            target_type = data['target_type']
            target_id = data['target_id']
            message_chain = data['message_chain']

            # Use custom deserializer that properly handles Forward messages
            message_chain_obj = platform_message.MessageChain.model_validate(message_chain)

            bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
            if bot is None:
                return handler.ActionResponse.error(
                    message=f'Bot with bot_uuid {bot_uuid} not found',
                )

            await bot.adapter.send_message(
                target_type,
                target_id,
                message_chain_obj,
            )

            return handler.ActionResponse.success(
                data={},
            )

        @self.action(PluginToRuntimeAction.GET_LLM_MODELS)
        async def get_llm_models(data: dict[str, Any]) -> handler.ActionResponse:
            """Get llm models, returns list of UUID strings"""
            llm_models = await self.ap.llm_model_service.get_llm_models(include_secret=False)
            return handler.ActionResponse.success(
                data={
                    'llm_models': [m['uuid'] for m in llm_models],
                },
            )

        @self.action(PluginToRuntimeAction.INVOKE_LLM)
        async def invoke_llm(data: dict[str, Any]) -> handler.ActionResponse:
            """Invoke llm

            For AgentRunner calls: requires run_id and validates model_uuid against session.resources.models.
            For regular plugin calls: no run_id, unrestricted access (backward compatibility).
            """
            llm_model_uuid = data['llm_model_uuid']
            messages = data['messages']
            funcs = data.get('funcs', [])
            extra_args = data.get('extra_args', {})
            run_id = data.get('run_id')  # Optional: present for AgentRunner calls
            caller_plugin_identity = data.get('caller_plugin_identity')  # Optional: for cross-plugin validation
            session = None

            # Permission validation for AgentRunner calls
            if run_id:
                session, error = await _validate_run_authorization(
                    run_id, 'model', llm_model_uuid, self.ap, caller_plugin_identity, operation='invoke'
                )
                if error:
                    return error

            llm_model = await self.ap.model_mgr.get_model_by_uuid(llm_model_uuid)
            if llm_model is None:
                return handler.ActionResponse.error(
                    message=f'LLM model with llm_model_uuid {llm_model_uuid} not found',
                )

            messages_obj = [provider_message.Message.model_validate(message) for message in messages]

            # The func field is excluded during model_dump() in plugin side (marked as exclude=True),
            # but it's a required field for LLMTool validation. We need to provide a placeholder
            # function when reconstructing the LLMTool objects from serialized data.
            async def _placeholder_func(**kwargs):
                pass

            funcs_obj = [resource_tool.LLMTool.model_validate({**func, 'func': _placeholder_func}) for func in funcs]
            query = _resolve_action_query(data, session, self.ap)
            effective_extra_args = _merge_model_extra_args(llm_model, extra_args)
            remove_think = _resolve_remove_think(data, query)
            effective_funcs = funcs_obj if 'func_call' in (llm_model.model_entity.abilities or []) else []

            result = await llm_model.provider.invoke_llm(
                query=query,
                model=llm_model,
                messages=messages_obj,
                funcs=effective_funcs,
                extra_args=effective_extra_args,
                remove_think=remove_think,
            )

            usage = None
            if isinstance(result, tuple):
                result, usage = result
            if usage is None:
                usage = _pop_query_llm_usage(query)

            response_data = {
                'message': result.model_dump(),
            }
            if usage is not None:
                response_data['usage'] = usage

            return handler.ActionResponse.success(
                data=response_data,
            )

        @self.action(PluginToRuntimeAction.INVOKE_LLM_STREAM)
        async def invoke_llm_stream(data: dict[str, Any]):
            """Invoke llm with streaming response

            For AgentRunner calls: requires run_id and validates model_uuid against session.resources.models.
            For regular plugin calls: no run_id, unrestricted access (backward compatibility).
            """
            llm_model_uuid = data['llm_model_uuid']
            messages = data['messages']
            funcs = data.get('funcs', [])
            extra_args = data.get('extra_args', {})
            run_id = data.get('run_id')  # Optional: present for AgentRunner calls
            caller_plugin_identity = data.get('caller_plugin_identity')  # Optional: for cross-plugin validation
            session = None

            # Permission validation for AgentRunner calls
            if run_id:
                session, error = await _validate_run_authorization(
                    run_id, 'model', llm_model_uuid, self.ap, caller_plugin_identity, operation='stream'
                )
                if error:
                    yield error
                    return

            llm_model = await self.ap.model_mgr.get_model_by_uuid(llm_model_uuid)
            if llm_model is None:
                yield handler.ActionResponse.error(
                    message=f'LLM model with llm_model_uuid {llm_model_uuid} not found',
                )
                return

            messages_obj = [provider_message.Message.model_validate(message) for message in messages]

            # The func field is excluded during model_dump() in plugin side
            # but required by LLMTool validation on Host.
            async def _placeholder_func(**kwargs):
                pass

            funcs_obj = [resource_tool.LLMTool.model_validate({**func, 'func': _placeholder_func}) for func in funcs]
            query = _resolve_action_query(data, session, self.ap)
            effective_extra_args = _merge_model_extra_args(llm_model, extra_args)
            remove_think = _resolve_remove_think(data, query)
            effective_funcs = funcs_obj if 'func_call' in (llm_model.model_entity.abilities or []) else []

            async for chunk in llm_model.provider.invoke_llm_stream(
                query=query,
                model=llm_model,
                messages=messages_obj,
                funcs=effective_funcs,
                extra_args=effective_extra_args,
                remove_think=remove_think,
            ):
                if chunk is None:
                    continue
                yield handler.ActionResponse.success(
                    data={
                        'chunk': chunk.model_dump(),
                    },
                )
            usage = _pop_query_llm_usage(query)
            if usage is not None:
                yield handler.ActionResponse.success(
                    data={
                        'usage': usage,
                    },
                )

        @self.action(PluginToRuntimeAction.CALL_TOOL)
        async def call_tool(data: dict[str, Any]) -> handler.ActionResponse:
            """Call a tool

            For AgentRunner calls: requires run_id and validates tool_name against session.resources.tools.
            For regular plugin calls: no run_id, unrestricted access (backward compatibility).
            """
            tool_name = data['tool_name']
            run_id = data.get('run_id')  # Optional: present for AgentRunner calls
            caller_plugin_identity = data.get('caller_plugin_identity')  # Optional: for cross-plugin validation
            session = None
            is_agent_runner_call = bool(run_id)

            if is_agent_runner_call:
                if 'parameters' not in data:
                    return handler.ActionResponse.error(
                        message='parameters is required for AgentRunner tool calls',
                    )
                parameters = data.get('parameters') or {}
            else:
                parameters = data.get('tool_parameters') or {}

            # Permission validation for AgentRunner calls
            if run_id:
                session, error = await _validate_run_authorization(
                    run_id, 'tool', tool_name, self.ap, caller_plugin_identity, operation='call'
                )
                if error:
                    return error

            # Convert session_data to Session object (simplified)
            # In real implementation, you would reconstruct the full session
            # For now, we'll call the tool manager's execute method
            try:
                query = _resolve_action_query(data, session, self.ap)
                result = await self.ap.tool_mgr.execute_func_call(
                    name=tool_name,
                    parameters=parameters,
                    query=query,
                )
                if is_agent_runner_call:
                    return handler.ActionResponse.success(data={'result': result})
                return handler.ActionResponse.success(data={'tool_response': result})
            except Exception as e:
                traceback.print_exc()
                return handler.ActionResponse.error(
                    message=f'Failed to execute tool {tool_name}: {e}',
                )

        @self.action(PluginToRuntimeAction.GET_TOOL_DETAIL)
        async def get_tool_detail(data: dict[str, Any]) -> handler.ActionResponse:
            """Get tool detail for LLM function calling.

            For AgentRunner calls: requires run_id and validates tool_name against session.resources.tools.
            For regular plugin calls: no run_id, unrestricted access (backward compatibility).

            Returns tool manifest including name, description, and parameters schema.
            """
            tool_name = data['tool_name']
            run_id = data.get('run_id')  # Optional: present for AgentRunner calls
            caller_plugin_identity = data.get('caller_plugin_identity')  # Optional: for cross-plugin validation

            # Permission validation for AgentRunner calls
            if run_id:
                session, error = await _validate_run_authorization(
                    run_id, 'tool', tool_name, self.ap, caller_plugin_identity, operation='detail'
                )
                if error:
                    return error

            try:
                tool = await self.ap.tool_mgr.get_tool_by_name(tool_name)
                if tool is None:
                    return handler.ActionResponse.error(
                        message=f'Tool {tool_name} not found',
                    )

                tool_detail = _build_tool_detail(tool, requested_tool_name=tool_name)

                return handler.ActionResponse.success(data={'tool': tool_detail})
            except Exception as e:
                traceback.print_exc()
                return handler.ActionResponse.error(
                    message=f'Failed to get tool detail for {tool_name}: {e}',
                )

        # ================= Binary Storage Handlers =================
        # Permission validation:
        # - For AgentRunner calls (with run_id): validates storage permission via session_registry
        # - For regular plugin calls (no run_id): unrestricted access (backward compatibility)
        # - Plugin storage: inherent isolation via owner = plugin identity (set by SDK runtime)
        # - Workspace storage: requires ctx.resources.storage.workspace_storage for AgentRunner

        @self.action(RuntimeToLangBotAction.SET_BINARY_STORAGE)
        async def set_binary_storage(data: dict[str, Any]) -> handler.ActionResponse:
            """Set binary storage

            For AgentRunner calls: validates storage permission via session_registry.
            For regular plugin calls: unrestricted access (backward compatibility).
            """
            key = data['key']
            owner_type = data['owner_type']
            owner = data['owner']
            value = base64.b64decode(data['value_base64'])
            run_id = data.get('run_id')  # Optional: present for AgentRunner calls
            caller_plugin_identity = data.get('caller_plugin_identity')  # Optional: for cross-plugin validation

            # Permission validation for AgentRunner calls
            if run_id:
                # Determine storage type from owner_type
                storage_type = owner_type  # 'plugin' or 'workspace'
                session, error = await _validate_run_authorization(
                    run_id, 'storage', storage_type, self.ap, caller_plugin_identity
                )
                if error:
                    return error

            max_value_bytes = (
                self.ap.instance_config.data.get('plugin', {})
                .get('binary_storage', {})
                .get(
                    'max_value_bytes',
                    10 * 1024 * 1024,
                )
            )
            try:
                max_value_bytes = int(max_value_bytes)
            except (TypeError, ValueError):
                max_value_bytes = 10 * 1024 * 1024
            if max_value_bytes >= 0 and len(value) > max_value_bytes:
                return handler.ActionResponse.error(
                    message=f'Binary storage value exceeds limit ({len(value)} > {max_value_bytes} bytes)',
                )

            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_bstorage.BinaryStorage)
                .where(persistence_bstorage.BinaryStorage.key == key)
                .where(persistence_bstorage.BinaryStorage.owner_type == owner_type)
                .where(persistence_bstorage.BinaryStorage.owner == owner)
            )

            if result.first() is not None:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.update(persistence_bstorage.BinaryStorage)
                    .where(persistence_bstorage.BinaryStorage.key == key)
                    .where(persistence_bstorage.BinaryStorage.owner_type == owner_type)
                    .where(persistence_bstorage.BinaryStorage.owner == owner)
                    .values(value=value)
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(persistence_bstorage.BinaryStorage).values(
                        unique_key=f'{owner_type}:{owner}:{key}',
                        key=key,
                        owner_type=owner_type,
                        owner=owner,
                        value=value,
                    )
                )

            return handler.ActionResponse.success(
                data={},
            )

        @self.action(RuntimeToLangBotAction.GET_BINARY_STORAGE)
        async def get_binary_storage(data: dict[str, Any]) -> handler.ActionResponse:
            """Get binary storage

            For AgentRunner calls: validates storage permission via session_registry.
            For regular plugin calls: unrestricted access (backward compatibility).
            """
            key = data['key']
            owner_type = data['owner_type']
            owner = data['owner']
            run_id = data.get('run_id')  # Optional: present for AgentRunner calls
            caller_plugin_identity = data.get('caller_plugin_identity')  # Optional: for cross-plugin validation

            # Permission validation for AgentRunner calls
            if run_id:
                storage_type = owner_type
                session, error = await _validate_run_authorization(
                    run_id, 'storage', storage_type, self.ap, caller_plugin_identity
                )
                if error:
                    return error

            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_bstorage.BinaryStorage)
                .where(persistence_bstorage.BinaryStorage.key == key)
                .where(persistence_bstorage.BinaryStorage.owner_type == owner_type)
                .where(persistence_bstorage.BinaryStorage.owner == owner)
            )

            storage = result.first()
            if storage is None:
                return handler.ActionResponse.error(
                    message=f'Storage with key {key} not found',
                )

            return handler.ActionResponse.success(
                data={
                    'value_base64': base64.b64encode(storage.value).decode('utf-8'),
                },
            )

        @self.action(RuntimeToLangBotAction.DELETE_BINARY_STORAGE)
        async def delete_binary_storage(data: dict[str, Any]) -> handler.ActionResponse:
            """Delete binary storage

            For AgentRunner calls: validates storage permission via session_registry.
            For regular plugin calls: unrestricted access (backward compatibility).
            """
            key = data['key']
            owner_type = data['owner_type']
            owner = data['owner']
            run_id = data.get('run_id')  # Optional: present for AgentRunner calls
            caller_plugin_identity = data.get('caller_plugin_identity')  # Optional: for cross-plugin validation

            # Permission validation for AgentRunner calls
            if run_id:
                storage_type = owner_type
                session, error = await _validate_run_authorization(
                    run_id, 'storage', storage_type, self.ap, caller_plugin_identity
                )
                if error:
                    return error

            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_bstorage.BinaryStorage)
                .where(persistence_bstorage.BinaryStorage.key == key)
                .where(persistence_bstorage.BinaryStorage.owner_type == owner_type)
                .where(persistence_bstorage.BinaryStorage.owner == owner)
            )

            return handler.ActionResponse.success(
                data={},
            )

        @self.action(RuntimeToLangBotAction.GET_BINARY_STORAGE_KEYS)
        async def get_binary_storage_keys(data: dict[str, Any]) -> handler.ActionResponse:
            """Get binary storage keys

            For AgentRunner calls: validates storage permission via session_registry.
            For regular plugin calls: unrestricted access (backward compatibility).
            """
            owner_type = data['owner_type']
            owner = data['owner']
            run_id = data.get('run_id')  # Optional: present for AgentRunner calls
            caller_plugin_identity = data.get('caller_plugin_identity')  # Optional: for cross-plugin validation

            # Permission validation for AgentRunner calls
            if run_id:
                storage_type = owner_type
                session, error = await _validate_run_authorization(
                    run_id, 'storage', storage_type, self.ap, caller_plugin_identity
                )
                if error:
                    return error

            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_bstorage.BinaryStorage.key)
                .where(persistence_bstorage.BinaryStorage.owner_type == owner_type)
                .where(persistence_bstorage.BinaryStorage.owner == owner)
            )

            return handler.ActionResponse.success(
                data={
                    'keys': result.scalars().all(),
                },
            )

        @self.action(PluginToRuntimeAction.GET_CONFIG_FILE)
        async def get_config_file(data: dict[str, Any]) -> handler.ActionResponse:
            """Get a config file by file key

            For AgentRunner calls: validates file_key against session.resources.files.
            For regular plugin calls: unrestricted access (backward compatibility).
            """
            file_key = data['file_key']
            run_id = data.get('run_id')  # Optional: present for AgentRunner calls
            caller_plugin_identity = data.get('caller_plugin_identity')  # Optional: for cross-plugin validation

            # Permission validation for AgentRunner calls
            if run_id:
                session, error = await _validate_run_authorization(
                    run_id, 'file', file_key, self.ap, caller_plugin_identity, operation='config'
                )
                if error:
                    return error

            try:
                # Load file from storage
                file_bytes = await self.ap.storage_mgr.storage_provider.load(file_key)

                return handler.ActionResponse.success(
                    data={
                        'file_base64': base64.b64encode(file_bytes).decode('utf-8'),
                    },
                )
            except Exception as e:
                return handler.ActionResponse.error(
                    message=f'Failed to load config file {file_key}: {e}',
                )

        # ================= RAG Capability Handlers =================

        @self.action(PluginToRuntimeAction.INVOKE_EMBEDDING)
        async def invoke_embedding(data: dict[str, Any]) -> handler.ActionResponse:
            embedding_model_uuid = data['embedding_model_uuid']
            texts = data['texts']

            embedding_model = await self.ap.model_mgr.get_embedding_model_by_uuid(embedding_model_uuid)
            if embedding_model is None:
                return handler.ActionResponse.error(
                    message=f'Embedding model with embedding_model_uuid {embedding_model_uuid} not found',
                )

            try:
                vectors = await embedding_model.provider.invoke_embedding(embedding_model, texts)
                return handler.ActionResponse.success(data={'vectors': vectors})
            except Exception as e:
                return _make_rag_error_response(e, 'EmbeddingError', embedding_model_uuid=embedding_model_uuid)

        @self.action(PluginToRuntimeAction.INVOKE_RERANK)
        async def invoke_rerank(data: dict[str, Any]) -> handler.ActionResponse:
            """Invoke rerank model for agent runner with run-scoped authorization."""
            run_id = data.get('run_id')
            rerank_model_uuid = data['rerank_model_uuid']
            query = data['query']
            documents = data['documents']
            top_k = data.get('top_k')
            caller_plugin_identity = data.get('caller_plugin_identity')

            # Validate run authorization
            session, error = await _validate_run_authorization(
                run_id, 'model', rerank_model_uuid, self.ap, caller_plugin_identity, operation='rerank'
            )
            if error:
                return error

            # Get rerank model
            rerank_model = await self.ap.model_mgr.get_rerank_model_by_uuid(rerank_model_uuid)
            if rerank_model is None:
                return handler.ActionResponse.error(
                    message=f'Rerank model with uuid {rerank_model_uuid} not found',
                )

            try:
                # Cap documents at 64 for API limit
                documents_capped = documents[:64]

                scores = await rerank_model.provider.invoke_rerank(
                    model=rerank_model,
                    query=query,
                    documents=documents_capped,
                    extra_args=_merge_model_extra_args(rerank_model, data.get('extra_args', {})),
                )

                # Sort by relevance score descending
                scored = sorted(scores, key=lambda x: x.get('relevance_score', 0), reverse=True)

                # Apply top_k if specified
                if top_k is not None:
                    scored = scored[:top_k]

                return handler.ActionResponse.success(data={'results': scored})
            except Exception as e:
                return _make_rag_error_response(e, 'RerankError', rerank_model_uuid=rerank_model_uuid)

        @self.action(PluginToRuntimeAction.VECTOR_UPSERT)
        async def vector_upsert(data: dict[str, Any]) -> handler.ActionResponse:
            collection_id = data['collection_id']
            vectors = data['vectors']
            ids = data['ids']
            metadata = data.get('metadata')
            documents = data.get('documents')
            if len(vectors) != len(ids):
                return handler.ActionResponse.error(message='vectors and ids must have same length')
            if metadata and len(metadata) != len(vectors):
                return handler.ActionResponse.error(message='metadata must match vectors length')
            if documents and len(documents) != len(vectors):
                return handler.ActionResponse.error(message='documents must match vectors length')
            try:
                await self.ap.rag_runtime_service.vector_upsert(
                    collection_id,
                    vectors,
                    ids,
                    metadata,
                    documents,
                )
                return handler.ActionResponse.success(data={})
            except Exception as e:
                return _make_rag_error_response(e, 'VectorStoreError', collection_id=collection_id)

        @self.action(PluginToRuntimeAction.VECTOR_SEARCH)
        async def vector_search(data: dict[str, Any]) -> handler.ActionResponse:
            collection_id = data['collection_id']
            query_vector = data['query_vector']
            top_k = data['top_k']
            filters = data.get('filters')
            search_type = data.get('search_type', 'vector')
            query_text = data.get('query_text', '')
            vector_weight = data.get('vector_weight')
            try:
                results = await self.ap.rag_runtime_service.vector_search(
                    collection_id,
                    query_vector,
                    top_k,
                    filters,
                    search_type,
                    query_text,
                    vector_weight=vector_weight,
                )
                return handler.ActionResponse.success(data={'results': results})
            except Exception as e:
                return _make_rag_error_response(e, 'VectorStoreError', collection_id=collection_id)

        @self.action(PluginToRuntimeAction.VECTOR_DELETE)
        async def vector_delete(data: dict[str, Any]) -> handler.ActionResponse:
            collection_id = data['collection_id']
            file_ids = data.get('file_ids')
            filters = data.get('filters')
            try:
                count = await self.ap.rag_runtime_service.vector_delete(collection_id, file_ids, filters)
                return handler.ActionResponse.success(data={'count': count})
            except Exception as e:
                return _make_rag_error_response(e, 'VectorStoreError', collection_id=collection_id)

        @self.action(PluginToRuntimeAction.VECTOR_LIST)
        async def vector_list(data: dict[str, Any]) -> handler.ActionResponse:
            collection_id = data['collection_id']
            filters = data.get('filters')
            limit = data.get('limit', 20)
            offset = data.get('offset', 0)
            try:
                items, total = await self.ap.rag_runtime_service.vector_list(collection_id, filters, limit, offset)
                return handler.ActionResponse.success(data={'items': items, 'total': total})
            except Exception as e:
                return _make_rag_error_response(e, 'VectorStoreError', collection_id=collection_id)

        @self.action(PluginToRuntimeAction.GET_KNOWLEDEGE_FILE_STREAM)
        async def get_knowledge_file_stream(data: dict[str, Any]) -> handler.ActionResponse:
            storage_path = data['storage_path']
            try:
                content_bytes = await self.ap.rag_runtime_service.get_file_stream(storage_path)
                file_key = await self.send_file(content_bytes, '')
                return handler.ActionResponse.success(data={'file_key': file_key})
            except Exception as e:
                return _make_rag_error_response(e, 'FileServiceError', storage_path=storage_path)

        @self.action(PluginToRuntimeAction.LIST_PARSERS)
        async def list_parsers(data: dict[str, Any]) -> handler.ActionResponse:
            """Plugin requests host to list available parser plugins."""
            mime_type = data.get('mime_type')
            try:
                parsers = await self.ap.knowledge_service.list_parsers(mime_type)
                return handler.ActionResponse.success(data={'parsers': parsers})
            except Exception as e:
                return _make_rag_error_response(e, 'ParserDiscoveryError', mime_type=mime_type)

        @self.action(PluginToRuntimeAction.INVOKE_PARSER)
        async def invoke_parser(data: dict[str, Any]) -> handler.ActionResponse:
            """Plugin requests host to invoke a parser plugin."""
            plugin_author = data['plugin_author']
            plugin_name = data['plugin_name']
            storage_path = data['storage_path']
            mime_type = data.get('mime_type', 'application/octet-stream')
            filename = data.get('filename', '')
            metadata = data.get('metadata', {})
            try:
                # Read file from storage
                file_bytes = await self.ap.rag_runtime_service.get_file_stream(storage_path)
                context_data = {
                    'mime_type': mime_type,
                    'filename': filename,
                    'metadata': metadata,
                }
                result = await self.ap.plugin_connector.call_parser(
                    f'{plugin_author}/{plugin_name}', context_data, file_bytes
                )
                return handler.ActionResponse.success(data=result)
            except Exception as e:
                return _make_rag_error_response(e, 'ParserError')

        # ================= Knowledge Base Query APIs =================

        @self.action(PluginToRuntimeAction.LIST_KNOWLEDGE_BASES)
        async def list_knowledge_bases(data: dict[str, Any]) -> handler.ActionResponse:
            """List all knowledge bases available in the LangBot instance (unrestricted)."""
            knowledge_bases = []
            for kb_uuid, kb in self.ap.rag_mgr.knowledge_bases.items():
                knowledge_bases.append(
                    {
                        'uuid': kb.get_uuid(),
                        'name': kb.get_name(),
                        'description': kb.knowledge_base_entity.description or '',
                    }
                )
            return handler.ActionResponse.success(data={'knowledge_bases': knowledge_bases})

        @self.action(PluginToRuntimeAction.RETRIEVE_KNOWLEDGE)
        async def retrieve_knowledge(data: dict[str, Any]) -> handler.ActionResponse:
            """Retrieve documents from any knowledge base.

            For AgentRunner calls: requires run_id and validates kb_id against session.resources.knowledge_bases.
            For regular plugin calls: no run_id, unrestricted access (backward compatibility).

            Note: SDK AgentRunAPIProxy.retrieve_knowledge calls this action with run_id.
            """
            kb_id = data['kb_id']
            query_text = data['query_text']
            top_k = data.get('top_k', 5)
            filters = data.get('filters') or {}
            run_id = data.get('run_id')  # Optional: present for AgentRunner calls
            caller_plugin_identity = data.get('caller_plugin_identity')  # Optional: for cross-plugin validation

            # Permission validation for AgentRunner calls
            if run_id:
                session, error = await _validate_run_authorization(
                    run_id, 'knowledge_base', kb_id, self.ap, caller_plugin_identity, operation='retrieve'
                )
                if error:
                    return error

            kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_id)
            if not kb:
                return handler.ActionResponse.error(
                    message=f'Knowledge base {kb_id} not found',
                )

            try:
                entries = await kb.retrieve(
                    query_text,
                    settings={
                        'top_k': top_k,
                        'filters': filters,
                    },
                )
                results = [entry.model_dump(mode='json') for entry in entries]
                return handler.ActionResponse.success(data={'results': results})
            except Exception as e:
                return _make_rag_error_response(e, 'RetrievalError', kb_id=kb_id)

        @self.action(PluginToRuntimeAction.LIST_PIPELINE_KNOWLEDGE_BASES)
        async def list_pipeline_knowledge_bases(data: dict[str, Any]) -> handler.ActionResponse:
            """List knowledge bases configured for the current query's pipeline."""
            query_id = data['query_id']

            if query_id not in self.ap.query_pool.cached_queries:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

            query = self.ap.query_pool.cached_queries[query_id]

            kb_uuids = await _get_pipeline_knowledge_base_uuids(self.ap, query)

            knowledge_bases = []
            for kb_uuid in kb_uuids:
                kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
                if kb:
                    knowledge_bases.append(
                        {
                            'uuid': kb.get_uuid(),
                            'name': kb.get_name(),
                            'description': kb.knowledge_base_entity.description or '',
                        }
                    )

            return handler.ActionResponse.success(data={'knowledge_bases': knowledge_bases})

        @self.action(PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE)
        async def retrieve_knowledge_base(data: dict[str, Any]) -> handler.ActionResponse:
            """Retrieve documents from a knowledge base within the current run or query scope.

            For AgentRunner calls: requires run_id and validates kb_id against session.resources.knowledge_bases.
            For regular plugin calls: no run_id, validates against pipeline's configured knowledge bases.

            Note: This action has dual validation paths:
            - AgentRunner: uses session_registry for permission check
            - Regular plugin: uses ConfigMigration.resolve_runner_config for pipeline-level check
            """
            kb_id = data['kb_id']
            query_text = data['query_text']
            top_k = data.get('top_k', 5)
            filters = data.get('filters') or {}
            run_id = data.get('run_id')  # Optional: present for AgentRunner calls
            caller_plugin_identity = data.get('caller_plugin_identity')  # Optional: for cross-plugin validation
            session = None
            query = None

            # Permission validation for AgentRunner calls
            if run_id:
                session, error = await _validate_run_authorization(
                    run_id, 'knowledge_base', kb_id, self.ap, caller_plugin_identity, operation='retrieve'
                )
                if error:
                    return error
                query = _resolve_action_query(data, session, self.ap)
            else:
                query_id = data['query_id']
                if query_id not in self.ap.query_pool.cached_queries:
                    return handler.ActionResponse.error(
                        message=f'Query with query_id {query_id} not found',
                    )

                query = self.ap.query_pool.cached_queries[query_id]

                # Regular plugin call: validate against the runner binding's
                # schema-defined KB selectors or the preprocessed query scope.
                allowed_kb_uuids = await _get_pipeline_knowledge_base_uuids(self.ap, query)

                if kb_id not in allowed_kb_uuids:
                    return handler.ActionResponse.error(
                        message=f'Knowledge base {kb_id} is not configured for this pipeline',
                    )

            kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_id)
            if not kb:
                return handler.ActionResponse.error(
                    message=f'Knowledge base {kb_id} not found',
                )

            try:
                settings: dict[str, Any] = {
                    'top_k': top_k,
                    'filters': filters,
                }
                if query is not None:
                    session_name = f'{query.session.launcher_type.value}_{query.session.launcher_id}'
                    settings.update(
                        {
                            'session_name': session_name,
                            'bot_uuid': query.bot_uuid or '',
                            'sender_id': str(query.sender_id),
                        }
                    )
                entries = await kb.retrieve(
                    query_text,
                    settings=settings,
                )
                results = [entry.model_dump(mode='json') for entry in entries]
                return handler.ActionResponse.success(data={'results': results})
            except Exception as e:
                return _make_rag_error_response(e, 'RetrievalError', kb_id=kb_id)

        # ================= Agent History/Event APIs =================

        @self.action(PluginToRuntimeAction.GET_PROMPT)
        async def get_prompt(data: dict[str, Any]) -> handler.ActionResponse:
            """Return the current run's effective prompt after PromptPreProcessing."""
            run_id = data.get('run_id')
            caller_plugin_identity = data.get('caller_plugin_identity')

            if not run_id:
                return handler.ActionResponse.error(message='run_id is required')

            session, error = await _validate_agent_run_session(
                run_id,
                caller_plugin_identity,
                self.ap,
                'Get prompt',
                api_capability='prompt_get',
            )
            if error:
                return error

            query = _resolve_action_query(data, session, self.ap)
            if query is None:
                return handler.ActionResponse.error(
                    message=f'Query for run_id {run_id} not found or expired',
                )

            prompt = getattr(query, 'prompt', None)
            messages = getattr(prompt, 'messages', []) or []
            return handler.ActionResponse.success(data={
                'prompt': [
                    message.model_dump(mode='json') if hasattr(message, 'model_dump') else message
                    for message in messages
                ],
            })

        @self.action(PluginToRuntimeAction.HISTORY_PAGE)
        async def history_page(data: dict[str, Any]) -> handler.ActionResponse:
            """Page through transcript history for a conversation.

            Requires run_id authorization. Only allows access to current run's conversation.
            """
            run_id = data.get('run_id')
            conversation_id = data.get('conversation_id')
            before_cursor = data.get('before_cursor')
            after_cursor = data.get('after_cursor')
            limit = data.get('limit', 50)
            direction = data.get('direction', 'backward')
            include_artifacts = data.get('include_artifacts', False)
            caller_plugin_identity = data.get('caller_plugin_identity')

            if not run_id:
                return handler.ActionResponse.error(message='run_id is required')

            session, error = await _validate_agent_run_session(
                run_id,
                caller_plugin_identity,
                self.ap,
                'History page',
                api_capability='history_page',
            )
            if error:
                return error

            conversation_id, scope_error = _resolve_run_conversation(
                session,
                conversation_id,
                'History page',
            )
            if scope_error:
                return scope_error

            if not conversation_id:
                return handler.ActionResponse.success(data={
                    'items': [],
                    'next_cursor': None,
                    'prev_cursor': None,
                    'has_more': False,
                })

            # Parse cursors
            before_seq = int(before_cursor) if before_cursor else None
            after_seq = int(after_cursor) if after_cursor else None

            # Query transcript
            from ..agent.runner.transcript_store import TranscriptStore
            store = TranscriptStore(self.ap.persistence_mgr.get_db_engine())

            try:
                items, next_seq, prev_seq, has_more = await store.page_transcript(
                    conversation_id=conversation_id,
                    before_seq=before_seq,
                    after_seq=after_seq,
                    limit=limit,
                    direction=direction,
                    include_artifacts=include_artifacts,
                    **_run_scope_filters(session),
                )

                return handler.ActionResponse.success(data={
                    'items': items,
                    'next_cursor': str(next_seq) if next_seq else None,
                    'prev_cursor': str(prev_seq) if prev_seq else None,
                    'has_more': has_more,
                })
            except Exception as e:
                self.ap.logger.error(f'HISTORY_PAGE error: {e}', exc_info=True)
                return handler.ActionResponse.error(message=f'History page error: {e}')

        @self.action(PluginToRuntimeAction.HISTORY_SEARCH)
        async def history_search(data: dict[str, Any]) -> handler.ActionResponse:
            """Search transcript history.

            Requires run_id authorization. Only searches current run's conversation.
            Basic implementation using LIKE filtering.
            """
            run_id = data.get('run_id')
            query_text = data.get('query', '')
            filters = data.get('filters') or {}
            top_k = data.get('top_k', 10)
            caller_plugin_identity = data.get('caller_plugin_identity')

            if not run_id:
                return handler.ActionResponse.error(message='run_id is required')

            session, error = await _validate_agent_run_session(
                run_id,
                caller_plugin_identity,
                self.ap,
                'History search',
                api_capability='history_search',
            )
            if error:
                return error

            requested_conversation_id = filters.get('conversation_id')
            conversation_id, scope_error = _resolve_run_conversation(
                session,
                requested_conversation_id,
                'History search',
            )
            if scope_error:
                return scope_error

            if not conversation_id:
                return handler.ActionResponse.success(data={
                    'items': [],
                    'total_count': 0,
                    'query': query_text,
                })

            # Search transcript
            from ..agent.runner.transcript_store import TranscriptStore
            store = TranscriptStore(self.ap.persistence_mgr.get_db_engine())

            try:
                safe_filters = {k: v for k, v in filters.items() if k != 'conversation_id'}
                items = await store.search_transcript(
                    conversation_id=conversation_id,
                    query_text=query_text,
                    filters=safe_filters,
                    top_k=top_k,
                    **_run_scope_filters(session),
                )

                return handler.ActionResponse.success(data={
                    'items': items,
                    'total_count': len(items),
                    'query': query_text,
                })
            except Exception as e:
                self.ap.logger.error(f'HISTORY_SEARCH error: {e}', exc_info=True)
                return handler.ActionResponse.error(message=f'History search error: {e}')

        @self.action(PluginToRuntimeAction.EVENT_GET)
        async def event_get(data: dict[str, Any]) -> handler.ActionResponse:
            """Get a single event record by ID.

            Requires run_id authorization. Only allows access to events in current run's conversation.
            """
            run_id = data.get('run_id')
            event_id = data.get('event_id')
            caller_plugin_identity = data.get('caller_plugin_identity')

            if not run_id:
                return handler.ActionResponse.error(message='run_id is required')

            if not event_id:
                return handler.ActionResponse.error(message='event_id is required')

            session, error = await _validate_agent_run_session(
                run_id,
                caller_plugin_identity,
                self.ap,
                'Event get',
                api_capability='event_get',
            )
            if error:
                return error

            # Get event
            from ..agent.runner.event_log_store import EventLogStore
            store = EventLogStore(self.ap.persistence_mgr.get_db_engine())

            try:
                event = await store.get_event(event_id)
                if not event:
                    return handler.ActionResponse.error(
                        message=f'Event {event_id} not found'
                    )

                # Validate event is in the same conversation as the run, or was created by the same run.
                session_conversation_id = _get_run_authorization(session).get('conversation_id')
                event_run_id = event.get('run_id')
                if event_run_id and event_run_id == run_id:
                    return handler.ActionResponse.success(data=_project_event_record_for_api(event))
                if not session_conversation_id or not _event_matches_run_scope(session, event):
                    return handler.ActionResponse.error(
                        message=f'Event {event_id} is not accessible by this run'
                    )

                return handler.ActionResponse.success(data=_project_event_record_for_api(event))
            except Exception as e:
                self.ap.logger.error(f'EVENT_GET error: {e}', exc_info=True)
                return handler.ActionResponse.error(message=f'Event get error: {e}')

        @self.action(PluginToRuntimeAction.EVENT_PAGE)
        async def event_page(data: dict[str, Any]) -> handler.ActionResponse:
            """Page through event records.

            Requires run_id authorization. Only allows access to current run's conversation.
            """
            run_id = data.get('run_id')
            conversation_id = data.get('conversation_id')
            event_types = data.get('event_types')
            before_cursor = data.get('before_cursor')
            limit = data.get('limit', 50)
            caller_plugin_identity = data.get('caller_plugin_identity')

            if not run_id:
                return handler.ActionResponse.error(message='run_id is required')

            session, error = await _validate_agent_run_session(
                run_id,
                caller_plugin_identity,
                self.ap,
                'Event page',
                api_capability='event_page',
            )
            if error:
                return error

            conversation_id, scope_error = _resolve_run_conversation(
                session,
                conversation_id,
                'Event page',
            )
            if scope_error:
                return scope_error

            if not conversation_id:
                return handler.ActionResponse.success(data={
                    'items': [],
                    'next_cursor': None,
                    'prev_cursor': None,
                    'has_more': False,
                })

            # Parse cursor
            before_seq = int(before_cursor) if before_cursor else None

            # Query events
            from ..agent.runner.event_log_store import EventLogStore
            store = EventLogStore(self.ap.persistence_mgr.get_db_engine())

            try:
                items, next_seq, has_more = await store.page_events(
                    conversation_id=conversation_id,
                    event_types=event_types,
                    before_seq=before_seq,
                    limit=limit,
                    **_run_scope_filters(session),
                )

                return handler.ActionResponse.success(data={
                    'items': [_project_event_record_for_api(item) for item in items],
                    'next_cursor': str(next_seq) if next_seq else None,
                    'prev_cursor': None,
                    'has_more': has_more,
                })
            except Exception as e:
                self.ap.logger.error(f'EVENT_PAGE error: {e}', exc_info=True)
                return handler.ActionResponse.error(message=f'Event page error: {e}')

        @self.action(PluginToRuntimeAction.STEERING_PULL)
        async def steering_pull(data: dict[str, Any]) -> handler.ActionResponse:
            """Pull pending steering/follow-up inputs for the current run."""
            run_id = data.get('run_id')
            mode = data.get('mode', 'all')
            limit = data.get('limit')
            caller_plugin_identity = data.get('caller_plugin_identity')

            if not run_id:
                return handler.ActionResponse.error(message='run_id is required')

            if limit is not None:
                try:
                    limit = int(limit)
                except (TypeError, ValueError):
                    return handler.ActionResponse.error(message='limit must be an integer')
                if limit <= 0:
                    return handler.ActionResponse.error(message='limit must be > 0')
                limit = min(limit, 100)

            session, error = await _validate_agent_run_session(
                run_id,
                caller_plugin_identity,
                self.ap,
                'Steering pull',
                api_capability='steering_pull',
            )
            if error:
                return error

            session_registry = get_session_registry()
            items = await session_registry.pull_steering(
                run_id,
                mode=str(mode or 'all'),
                limit=limit,
            )
            if items:
                try:
                    from ..agent.runner.event_log_store import EventLogStore

                    store = EventLogStore(self.ap.persistence_mgr.get_db_engine())
                    for item in items:
                        event = item.get('event') if isinstance(item, dict) else None
                        conversation = item.get('conversation') if isinstance(item, dict) else None
                        actor = item.get('actor') if isinstance(item, dict) else None
                        subject = item.get('subject') if isinstance(item, dict) else None
                        if not isinstance(event, dict):
                            continue
                        await store.append_event(
                            event_id=None,
                            event_type='steering.injected',
                            source='agent_runner',
                            bot_id=conversation.get('bot_id') if isinstance(conversation, dict) else None,
                            workspace_id=conversation.get('workspace_id') if isinstance(conversation, dict) else None,
                            conversation_id=conversation.get('conversation_id') if isinstance(conversation, dict) else None,
                            thread_id=conversation.get('thread_id') if isinstance(conversation, dict) else None,
                            actor_type=actor.get('actor_type') if isinstance(actor, dict) else None,
                            actor_id=actor.get('actor_id') if isinstance(actor, dict) else None,
                            actor_name=actor.get('actor_name') if isinstance(actor, dict) else None,
                            subject_type=subject.get('subject_type') if isinstance(subject, dict) else None,
                            subject_id=subject.get('subject_id') if isinstance(subject, dict) else None,
                            input_summary=f"steering injected from {event.get('event_id')}",
                            run_id=run_id,
                            runner_id=session.get('runner_id') if isinstance(session, dict) else None,
                            metadata={
                                'steering': {
                                    'status': 'injected',
                                    'source_event_id': event.get('event_id'),
                                    'claimed_by_run_id': item.get('claimed_run_id') if isinstance(item, dict) else run_id,
                                    'claimed_runner_id': item.get('runner_id') if isinstance(item, dict) else None,
                                    'claimed_at': item.get('claimed_at') if isinstance(item, dict) else None,
                                    'pull_mode': str(mode or 'all'),
                                },
                            },
                        )
                except Exception as exc:
                    self.ap.logger.warning(
                        f'Failed to write steering injection audit for run {run_id}: {exc}',
                        exc_info=True,
                    )
            return handler.ActionResponse.success(data={'items': items})

        # ================= Artifact APIs =================

        @self.action(PluginToRuntimeAction.ARTIFACT_METADATA)
        async def artifact_metadata(data: dict[str, Any]) -> handler.ActionResponse:
            """Get artifact metadata.

            Requires run_id authorization. Only allows access to artifacts
            in current run's conversation or created by current run.
            """
            run_id = data.get('run_id')
            artifact_id = data.get('artifact_id')
            caller_plugin_identity = data.get('caller_plugin_identity')

            if not run_id:
                return handler.ActionResponse.error(message='run_id is required')

            if not artifact_id:
                return handler.ActionResponse.error(message='artifact_id is required')

            session, error = await _validate_agent_run_session(
                run_id,
                caller_plugin_identity,
                self.ap,
                'Artifact metadata',
                api_capability='artifact_metadata',
            )
            if error:
                return error

            # Get artifact metadata
            from ..agent.runner.artifact_store import ArtifactStore
            store = ArtifactStore(self.ap.persistence_mgr.get_db_engine())

            try:
                metadata = await store.get_authorization_metadata(artifact_id)
                if not metadata:
                    return handler.ActionResponse.error(
                        message=f'Artifact {artifact_id} not found'
                    )

                # Validate artifact access scope
                is_allowed, error_msg = _validate_artifact_access(session, metadata, 'metadata')
                if not is_allowed:
                    return handler.ActionResponse.error(message=error_msg)

                return handler.ActionResponse.success(data=_public_artifact_metadata(metadata))
            except Exception as e:
                self.ap.logger.error(f'ARTIFACT_METADATA error: {e}', exc_info=True)
                return handler.ActionResponse.error(message=f'Artifact metadata error: {e}')

        @self.action(PluginToRuntimeAction.ARTIFACT_READ)
        async def artifact_read(data: dict[str, Any]) -> handler.ActionResponse:
            """Read artifact content.

            Requires run_id authorization. Only allows access to artifacts
            in current run's conversation or created by current run.
            Supports range reads with offset/limit.
            """
            run_id = data.get('run_id')
            artifact_id = data.get('artifact_id')
            caller_plugin_identity = data.get('caller_plugin_identity')

            if not run_id:
                return handler.ActionResponse.error(message='run_id is required')

            if not artifact_id:
                return handler.ActionResponse.error(message='artifact_id is required')

            # Validate and parse offset
            offset = data.get('offset', 0)
            if not isinstance(offset, int):
                try:
                    offset = int(offset)
                except (TypeError, ValueError):
                    return handler.ActionResponse.error(message='offset must be an integer')
            if offset < 0:
                return handler.ActionResponse.error(message='offset must be >= 0')

            # Validate and parse limit if provided
            limit = data.get('limit')
            if limit is not None:
                if not isinstance(limit, int):
                    try:
                        limit = int(limit)
                    except (TypeError, ValueError):
                        return handler.ActionResponse.error(message='limit must be an integer')
                if limit <= 0:
                    return handler.ActionResponse.error(message='limit must be > 0')

            session, error = await _validate_agent_run_session(
                run_id,
                caller_plugin_identity,
                self.ap,
                'Artifact read',
                api_capability='artifact_read',
            )
            if error:
                return error

            # Get artifact metadata first to validate access
            from ..agent.runner.artifact_store import ArtifactStore
            store = ArtifactStore(self.ap.persistence_mgr.get_db_engine())

            try:
                metadata = await store.get_authorization_metadata(artifact_id)
                if not metadata:
                    return handler.ActionResponse.error(
                        message=f'Artifact {artifact_id} not found'
                    )

                # Validate artifact access scope
                is_allowed, error_msg = _validate_artifact_access(session, metadata, 'read')
                if not is_allowed:
                    return handler.ActionResponse.error(message=error_msg)

                # Read artifact content (validates offset/limit internally)
                result = await store.read_artifact(
                    artifact_id=artifact_id,
                    offset=offset,
                    limit=limit,
                )

                if not result:
                    return handler.ActionResponse.error(
                        message=f'Failed to read artifact {artifact_id}'
                    )

                return handler.ActionResponse.success(data=result)
            except ValueError as e:
                # Offset/limit validation error
                return handler.ActionResponse.error(message=str(e))
            except Exception as e:
                self.ap.logger.error(f'ARTIFACT_READ error: {e}', exc_info=True)
                return handler.ActionResponse.error(message=f'Artifact read error: {e}')

        # ================= State APIs (run-scoped, policy-enforced) =================

        @self.action(PluginToRuntimeAction.STATE_GET)
        async def state_get(data: dict[str, Any]) -> handler.ActionResponse:
            """Get a state value from host-owned state store.

            Requires run_id authorization and scope enabled by state_policy.
            """
            run_id = data.get('run_id')
            scope = data.get('scope')
            key = data.get('key')
            caller_plugin_identity = data.get('caller_plugin_identity')

            if not run_id:
                return handler.ActionResponse.error(message='run_id is required')

            if not scope:
                return handler.ActionResponse.error(message='scope is required')

            if not key:
                return handler.ActionResponse.error(message='key is required')

            session, error = await _validate_agent_run_session(
                run_id,
                caller_plugin_identity,
                self.ap,
                'State get',
                api_capability='state',
            )
            if error:
                return error

            _state_context, scope_key, state_error = _resolve_state_scope(session, scope)
            if state_error:
                return state_error

            # Get state from persistent store
            from ..agent.runner.persistent_state_store import get_persistent_state_store
            store = get_persistent_state_store(self.ap.persistence_mgr.get_db_engine())

            try:
                value = await store.state_get(scope_key, key)
                return handler.ActionResponse.success(data={'value': value})
            except Exception as e:
                self.ap.logger.error(f'STATE_GET error: {e}', exc_info=True)
                return handler.ActionResponse.error(message=f'State get error: {e}')

        @self.action(PluginToRuntimeAction.STATE_SET)
        async def state_set(data: dict[str, Any]) -> handler.ActionResponse:
            """Set a state value in host-owned state store.

            Requires run_id authorization and scope enabled by state_policy.
            Value must be JSON-serializable and size-limited.
            """
            run_id = data.get('run_id')
            scope = data.get('scope')
            key = data.get('key')
            value = data.get('value')
            caller_plugin_identity = data.get('caller_plugin_identity')

            if not run_id:
                return handler.ActionResponse.error(message='run_id is required')

            if not scope:
                return handler.ActionResponse.error(message='scope is required')

            if not key:
                return handler.ActionResponse.error(message='key is required')

            session, error = await _validate_agent_run_session(
                run_id,
                caller_plugin_identity,
                self.ap,
                'State set',
                api_capability='state',
            )
            if error:
                return error

            state_context, scope_key, state_error = _resolve_state_scope(session, scope)
            if state_error:
                return state_error

            # Get additional context for DB insert
            runner_id = session.get('runner_id', '')
            binding_identity = state_context.get('binding_identity', 'unknown')

            # Set state in persistent store
            from ..agent.runner.persistent_state_store import get_persistent_state_store
            store = get_persistent_state_store(self.ap.persistence_mgr.get_db_engine())

            try:
                success, error = await store.state_set(
                    scope_key=scope_key,
                    state_key=key,
                    value=value,
                    runner_id=runner_id,
                    binding_identity=binding_identity,
                    scope=scope,
                    context=state_context,
                    logger=self.ap.logger,
                )

                if not success:
                    return handler.ActionResponse.error(message=error or 'Failed to set state')

                return handler.ActionResponse.success(data={'success': True})
            except Exception as e:
                self.ap.logger.error(f'STATE_SET error: {e}', exc_info=True)
                return handler.ActionResponse.error(message=f'State set error: {e}')

        @self.action(PluginToRuntimeAction.STATE_DELETE)
        async def state_delete(data: dict[str, Any]) -> handler.ActionResponse:
            """Delete a state value from host-owned state store.

            Requires run_id authorization and scope enabled by state_policy.
            """
            run_id = data.get('run_id')
            scope = data.get('scope')
            key = data.get('key')
            caller_plugin_identity = data.get('caller_plugin_identity')

            if not run_id:
                return handler.ActionResponse.error(message='run_id is required')

            if not scope:
                return handler.ActionResponse.error(message='scope is required')

            if not key:
                return handler.ActionResponse.error(message='key is required')

            session, error = await _validate_agent_run_session(
                run_id,
                caller_plugin_identity,
                self.ap,
                'State delete',
                api_capability='state',
            )
            if error:
                return error

            _state_context, scope_key, state_error = _resolve_state_scope(session, scope)
            if state_error:
                return state_error

            # Delete state from persistent store
            from ..agent.runner.persistent_state_store import get_persistent_state_store
            store = get_persistent_state_store(self.ap.persistence_mgr.get_db_engine())

            try:
                deleted = await store.state_delete(scope_key, key)
                return handler.ActionResponse.success(data={'success': deleted})
            except Exception as e:
                self.ap.logger.error(f'STATE_DELETE error: {e}', exc_info=True)
                return handler.ActionResponse.error(message=f'State delete error: {e}')

        @self.action(PluginToRuntimeAction.STATE_LIST)
        async def state_list(data: dict[str, Any]) -> handler.ActionResponse:
            """List state keys in a scope.

            Requires run_id authorization and scope enabled by state_policy.
            """
            run_id = data.get('run_id')
            scope = data.get('scope')
            prefix = data.get('prefix')
            limit = data.get('limit', 100)
            caller_plugin_identity = data.get('caller_plugin_identity')

            if not run_id:
                return handler.ActionResponse.error(message='run_id is required')

            if not scope:
                return handler.ActionResponse.error(message='scope is required')

            # Validate limit
            if not isinstance(limit, int) or limit <= 0:
                limit = 100
            limit = min(limit, 100)  # Cap at 100

            session, error = await _validate_agent_run_session(
                run_id,
                caller_plugin_identity,
                self.ap,
                'State list',
                api_capability='state',
            )
            if error:
                return error

            _state_context, scope_key, state_error = _resolve_state_scope(session, scope)
            if state_error:
                return state_error

            # List state keys from persistent store
            from ..agent.runner.persistent_state_store import get_persistent_state_store
            store = get_persistent_state_store(self.ap.persistence_mgr.get_db_engine())

            try:
                keys, has_more = await store.state_list(scope_key, prefix, limit)
                return handler.ActionResponse.success(data={
                    'keys': keys,
                    'has_more': has_more,
                })
            except Exception as e:
                self.ap.logger.error(f'STATE_LIST error: {e}', exc_info=True)
                return handler.ActionResponse.error(message=f'State list error: {e}')

        @self.action(CommonAction.PING)
        async def ping(data: dict[str, Any]) -> handler.ActionResponse:
            """Ping"""
            return handler.ActionResponse.success(
                data={
                    'pong': 'pong',
                },
            )

    async def ping(self) -> dict[str, Any]:
        """Ping the runtime"""
        return await self.call_action(
            CommonAction.PING,
            {},
            timeout=10,
        )

    async def set_runtime_config(self, cloud_service_url: str) -> dict[str, Any]:
        """Push runtime configuration (e.g. marketplace URL) to the runtime."""
        return await self.call_action(
            LangBotToRuntimeAction.SET_RUNTIME_CONFIG,
            {
                'cloud_service_url': cloud_service_url,
            },
            timeout=10,
        )

    async def install_plugin(
        self, install_source: str, install_info: dict[str, Any]
    ) -> typing.AsyncGenerator[dict[str, Any], None]:
        """Install plugin"""
        gen = self.call_action_generator(
            LangBotToRuntimeAction.INSTALL_PLUGIN,
            {
                'install_source': install_source,
                'install_info': install_info,
            },
            timeout=120,
        )

        async for ret in gen:
            yield ret

    async def upgrade_plugin(self, plugin_author: str, plugin_name: str) -> typing.AsyncGenerator[dict[str, Any], None]:
        """Upgrade plugin"""
        gen = self.call_action_generator(
            LangBotToRuntimeAction.UPGRADE_PLUGIN,
            {
                'plugin_author': plugin_author,
                'plugin_name': plugin_name,
            },
            timeout=120,
        )

        async for ret in gen:
            yield ret

    async def delete_plugin(self, plugin_author: str, plugin_name: str) -> typing.AsyncGenerator[dict[str, Any], None]:
        """Delete plugin"""
        gen = self.call_action_generator(
            LangBotToRuntimeAction.DELETE_PLUGIN,
            {
                'plugin_author': plugin_author,
                'plugin_name': plugin_name,
            },
        )

        async for ret in gen:
            yield ret

    async def list_plugins(self) -> list[dict[str, Any]]:
        """List plugins"""
        result = await self.call_action(
            LangBotToRuntimeAction.LIST_PLUGINS,
            {},
            timeout=10,
        )

        return result['plugins']

    async def get_plugin_info(self, author: str, plugin_name: str) -> dict[str, Any]:
        """Get plugin"""
        result = await self.call_action(
            LangBotToRuntimeAction.GET_PLUGIN_INFO,
            {
                'author': author,
                'plugin_name': plugin_name,
            },
            timeout=10,
        )
        return result['plugin']

    async def set_plugin_config(self, plugin_author: str, plugin_name: str, config: dict[str, Any]) -> dict[str, Any]:
        """Set plugin config"""
        # update plugin setting
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_plugin.PluginSetting)
            .where(persistence_plugin.PluginSetting.plugin_author == plugin_author)
            .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
            .values(config=config)
        )

        # restart plugin
        gen = self.call_action_generator(
            LangBotToRuntimeAction.RESTART_PLUGIN,
            {
                'plugin_author': plugin_author,
                'plugin_name': plugin_name,
            },
        )
        async for ret in gen:
            pass

        return {}

    async def emit_event(
        self,
        event_context: dict[str, Any],
        include_plugins: list[str] | None = None,
    ) -> dict[str, Any]:
        """Emit event"""
        result = await self.call_action(
            LangBotToRuntimeAction.EMIT_EVENT,
            {
                'event_context': event_context,
                'include_plugins': include_plugins,
            },
            timeout=180,
        )

        return result

    async def list_tools(self, include_plugins: list[str] | None = None) -> list[dict[str, Any]]:
        """List tools"""
        result = await self.call_action(
            LangBotToRuntimeAction.LIST_TOOLS,
            {
                'include_plugins': include_plugins,
            },
            timeout=20,
        )

        return result['tools']

    async def list_agent_runners(self, include_plugins: list[str] | None = None) -> list[dict[str, Any]]:
        """List agent runners from plugin runtime.

        Returns list of dicts with:
        - plugin_author
        - plugin_name
        - runner_name
        - runner_description
        - manifest
        - config
        """
        result = await self.call_action(
            LangBotToRuntimeAction.LIST_AGENT_RUNNERS,
            {
                'include_plugins': include_plugins,
            },
            timeout=20,
        )

        return result['runners']

    async def run_agent(
        self,
        plugin_author: str,
        plugin_name: str,
        runner_name: str,
        context: dict[str, Any],
    ) -> typing.AsyncGenerator[dict[str, Any], None]:
        """Run an AgentRunner component.

        Yields AgentRunResult dicts.
        """
        timeout = self._get_runner_action_timeout(context)
        gen = self.call_action_generator(
            LangBotToRuntimeAction.RUN_AGENT,
            {
                'plugin_author': plugin_author,
                'plugin_name': plugin_name,
                'runner_name': runner_name,
                'context': context,
            },
            timeout=timeout,
        )

        async for ret in gen:
            yield ret

    def _get_runner_action_timeout(self, context: dict[str, Any]) -> float:
        """Use the run deadline as the transport idle timeout when available."""
        try:
            import time

            deadline_at = (context.get('runtime') or {}).get('deadline_at')
            if deadline_at is None:
                return 300
            remaining = float(deadline_at) - time.time()
            if remaining <= 0:
                return 0.001
            return max(remaining + 1.0, 0.001)
        except (TypeError, ValueError):
            return 300

    async def get_plugin_icon(self, plugin_author: str, plugin_name: str) -> dict[str, Any]:
        """Get plugin icon"""
        result = await self.call_action(
            LangBotToRuntimeAction.GET_PLUGIN_ICON,
            {
                'plugin_author': plugin_author,
                'plugin_name': plugin_name,
            },
        )

        plugin_icon_file_key = result['plugin_icon_file_key']
        mime_type = result['mime_type']

        plugin_icon_bytes = await self.read_local_file(plugin_icon_file_key)

        await self.delete_local_file(plugin_icon_file_key)

        return {
            'plugin_icon_base64': base64.b64encode(plugin_icon_bytes).decode('utf-8'),
            'mime_type': mime_type,
        }

    async def get_plugin_readme(self, plugin_author: str, plugin_name: str, language: str = 'en') -> str:
        """Get plugin readme"""
        try:
            result = await self.call_action(
                LangBotToRuntimeAction.GET_PLUGIN_README,
                {
                    'plugin_author': plugin_author,
                    'plugin_name': plugin_name,
                    'language': language,
                },
                timeout=20,
            )
        except Exception:
            traceback.print_exc()
            return ''

        readme_file_key = result.get('readme_file_key')
        if not readme_file_key:
            return ''

        readme_bytes = await self.read_local_file(readme_file_key)
        await self.delete_local_file(readme_file_key)

        return readme_bytes.decode('utf-8')

    async def get_plugin_logs(
        self,
        plugin_author: str,
        plugin_name: str,
        limit: int = 200,
        level: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent log lines captured from the plugin's stderr."""
        try:
            result = await self.call_action(
                LangBotToRuntimeAction.GET_PLUGIN_LOGS,
                {
                    'plugin_author': plugin_author,
                    'plugin_name': plugin_name,
                    'limit': limit,
                    'level': level,
                },
                timeout=20,
            )
        except Exception:
            traceback.print_exc()
            return []

        return result.get('logs', [])

    async def get_plugin_assets(self, plugin_author: str, plugin_name: str, filepath: str) -> dict[str, Any]:
        """Get plugin assets"""
        result = await self.call_action(
            LangBotToRuntimeAction.GET_PLUGIN_ASSETS_FILE,
            {
                'plugin_author': plugin_author,
                'plugin_name': plugin_name,
                'file_path': filepath,
            },
            timeout=20,
        )
        asset_file_key = result['file_file_key']
        if not asset_file_key:
            return {
                'asset_base64': '',
                'mime_type': '',
            }
        mime_type = result['mime_type']
        asset_bytes = await self.read_local_file(asset_file_key)
        await self.delete_local_file(asset_file_key)
        return {
            'asset_base64': base64.b64encode(asset_bytes).decode('utf-8'),
            'mime_type': mime_type,
        }

    async def handle_page_api(
        self,
        plugin_author: str,
        plugin_name: str,
        page_id: str,
        endpoint: str,
        method: str,
        body: Any = None,
    ) -> dict[str, Any]:
        """Forward a page API call to the plugin via runtime."""
        result = await self.call_action(
            LangBotToRuntimeAction.PAGE_API,
            {
                'plugin_author': plugin_author,
                'plugin_name': plugin_name,
                'page_id': page_id,
                'endpoint': endpoint,
                'method': method,
                'body': body,
            },
            timeout=30,
        )
        return result

    async def cleanup_plugin_data(self, plugin_author: str, plugin_name: str) -> None:
        """Cleanup plugin settings and binary storage"""
        # Delete plugin settings
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_plugin.PluginSetting)
            .where(persistence_plugin.PluginSetting.plugin_author == plugin_author)
            .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
        )

        # Delete all binary storage for this plugin
        owner = f'{plugin_author}/{plugin_name}'
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_bstorage.BinaryStorage)
            .where(persistence_bstorage.BinaryStorage.owner_type == 'plugin')
            .where(persistence_bstorage.BinaryStorage.owner == owner)
        )

    async def call_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        session: dict[str, Any],
        query_id: int,
        include_plugins: list[str] | None = None,
    ) -> dict[str, Any]:
        """Call tool"""
        result = await self.call_action(
            LangBotToRuntimeAction.CALL_TOOL,
            {
                'tool_name': tool_name,
                'tool_parameters': parameters,
                'session': session,
                'query_id': query_id,
                'include_plugins': include_plugins,
            },
            timeout=180,
        )

        return result['tool_response']

    async def list_commands(self, include_plugins: list[str] | None = None) -> list[dict[str, Any]]:
        """List commands"""
        result = await self.call_action(
            LangBotToRuntimeAction.LIST_COMMANDS,
            {
                'include_plugins': include_plugins,
            },
            timeout=10,
        )
        return result['commands']

    async def execute_command(
        self, command_context: dict[str, Any], include_plugins: list[str] | None = None
    ) -> typing.AsyncGenerator[dict[str, Any], None]:
        """Execute command"""
        gen = self.call_action_generator(
            LangBotToRuntimeAction.EXECUTE_COMMAND,
            {
                'command_context': command_context,
                'include_plugins': include_plugins,
            },
            timeout=180,
        )

        async for ret in gen:
            yield ret

    async def retrieve_knowledge(
        self,
        plugin_author: str,
        plugin_name: str,
        retriever_name: str,
        retrieval_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Retrieve knowledge"""
        result = await self.call_action(
            LangBotToRuntimeAction.RETRIEVE_KNOWLEDGE,
            {
                'plugin_author': plugin_author,
                'plugin_name': plugin_name,
                'retriever_name': retriever_name,
                'retrieval_context': retrieval_context,
            },
            timeout=30,
        )
        return result

    async def get_debug_info(self) -> dict[str, Any]:
        """Get debug information including debug key and WS URL"""
        result = await self.call_action(
            LangBotToRuntimeAction.GET_DEBUG_INFO,
            {},
            timeout=10,
        )
        return result

    # ================= RAG Capability Callers (LangBot -> Runtime) =================

    async def rag_ingest_document(
        self, plugin_author: str, plugin_name: str, context_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Send INGEST_DOCUMENT action to runtime."""
        result = await self.call_action(
            LangBotToRuntimeAction.RAG_INGEST_DOCUMENT,
            {'plugin_author': plugin_author, 'plugin_name': plugin_name, 'context': context_data},
            timeout=1200,  # Ingestion can be slow for large documents
        )
        return result

    async def rag_delete_document(self, plugin_author: str, plugin_name: str, document_id: str, kb_id: str) -> bool:
        result = await self.call_action(
            LangBotToRuntimeAction.RAG_DELETE_DOCUMENT,
            {'plugin_author': plugin_author, 'plugin_name': plugin_name, 'document_id': document_id, 'kb_id': kb_id},
            timeout=30,
        )
        return result.get('success', False)

    async def rag_on_kb_create(
        self, plugin_author: str, plugin_name: str, kb_id: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Notify plugin about KB creation."""
        result = await self.call_action(
            LangBotToRuntimeAction.RAG_ON_KB_CREATE,
            {'plugin_author': plugin_author, 'plugin_name': plugin_name, 'kb_id': kb_id, 'config': config},
            timeout=30,
        )
        return result

    async def rag_on_kb_delete(self, plugin_author: str, plugin_name: str, kb_id: str) -> dict[str, Any]:
        """Notify plugin about KB deletion."""
        result = await self.call_action(
            LangBotToRuntimeAction.RAG_ON_KB_DELETE,
            {'plugin_author': plugin_author, 'plugin_name': plugin_name, 'kb_id': kb_id},
            timeout=30,
        )
        return result

    async def get_rag_creation_schema(self, plugin_author: str, plugin_name: str) -> dict[str, Any]:
        return await self.call_action(
            LangBotToRuntimeAction.GET_RAG_CREATION_SETTINGS_SCHEMA,
            {'plugin_author': plugin_author, 'plugin_name': plugin_name},
            timeout=10,
        )

    async def get_rag_retrieval_schema(self, plugin_author: str, plugin_name: str) -> dict[str, Any]:
        return await self.call_action(
            LangBotToRuntimeAction.GET_RAG_RETRIEVAL_SETTINGS_SCHEMA,
            {'plugin_author': plugin_author, 'plugin_name': plugin_name},
            timeout=10,
        )

    async def list_knowledge_engines(self) -> list[dict[str, Any]]:
        """List all available Knowledge Engines from plugins."""
        result = await self.call_action(LangBotToRuntimeAction.LIST_KNOWLEDGE_ENGINES, {}, timeout=60)
        return result.get('engines', [])

    # ================= Parser Capability Callers (LangBot -> Runtime) =================

    async def list_parsers(self) -> list[dict[str, Any]]:
        """List all available parsers from plugins."""
        result = await self.call_action(LangBotToRuntimeAction.LIST_PARSERS, {}, timeout=60)
        return result.get('parsers', [])

    async def parse_document(
        self, plugin_author: str, plugin_name: str, context_data: dict[str, Any], file_bytes: bytes
    ) -> dict[str, Any]:
        """Send PARSE_DOCUMENT action to runtime.

        Sends file content via chunked FILE_CHUNK transfer, then invokes
        the PARSE_DOCUMENT action with a file_key reference.
        """
        # Send file to runtime via chunked transfer
        file_key = await self.send_file(file_bytes, '')

        # Include file_key in context_data for the runtime to read
        context_data['file_key'] = file_key

        result = await self.call_action(
            LangBotToRuntimeAction.PARSE_DOCUMENT,
            {'plugin_author': plugin_author, 'plugin_name': plugin_name, 'context': context_data},
            timeout=300,
        )
        return result
