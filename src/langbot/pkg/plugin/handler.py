from __future__ import annotations

import inspect
import typing
from typing import Any
import base64
import contextlib
import contextvars
import traceback
from dataclasses import dataclass

import sqlalchemy

from langbot_plugin.runtime.io import handler
from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.entities.io.context import (
    ActionContext,
    ApplyPluginInstallationRequest,
    InstallationBinding,
    PluginInstallationDesiredState,
    PluginWorkerPolicy,
    ReconcilePluginInstallationsRequest,
    RemovePluginInstallationRequest,
    RuntimeConfig,
    RuntimeIdentity,
)
from langbot_plugin.entities.io.actions.enums import (
    CommonAction,
    RuntimeToLangBotAction,
    LangBotToRuntimeAction,
    PluginToRuntimeAction,
)
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool

from ..api.http.context import ExecutionContext
from ..entity.persistence import plugin as persistence_plugin
from ..entity.persistence import bstorage as persistence_bstorage
from ..entity.persistence import bot as persistence_bot
from ..entity.persistence import model as persistence_model

from ..core import app
from ..utils import constants


class _RawAction:
    def __init__(self, value: str):
        self.value = value


def _langbot_to_runtime_action(enum_name: str, fallback_value: str) -> Any:
    return getattr(LangBotToRuntimeAction, enum_name, _RawAction(fallback_value))


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


@dataclass(frozen=True, slots=True)
class _PluginInstallationIdentity:
    workspace_uuid: str
    plugin_author: str
    plugin_name: str
    installation_uuid: str
    runtime_revision: int
    artifact_digest: str


_UNTRUSTED_SCOPE_FIELDS = frozenset(
    {
        'context',
        'action_context',
        'instance_uuid',
        'workspace_uuid',
        'placement_generation',
        'installation_uuid',
        'runtime_revision',
        'artifact_digest',
    }
)

_RUNTIME_SCOPED_ACTIONS = frozenset(
    {
        CommonAction.FILE_CHUNK.value,
        RuntimeToLangBotAction.INITIALIZE_PLUGIN_SETTINGS.value,
        RuntimeToLangBotAction.GET_PLUGIN_SETTINGS.value,
    }
)


class RuntimeConnectionHandler(handler.Handler):
    """Runtime connection handler"""

    ap: app.Application

    def validate_inbound_action_context(
        self,
        action: str,
        action_context: ActionContext | None,
    ) -> ActionContext | None:
        """Require a complete installation tuple on every tenant action."""

        if action == CommonAction.PING.value:
            if action_context is not None:
                raise ValueError('PING does not accept an installation binding')
            return None
        if isinstance(action_context, InstallationBinding):
            return action_context
        if self._allow_legacy_oss_context(action, action_context):
            return action_context
        raise ValueError(f'{action} requires a complete InstallationBinding context')

    def _allow_legacy_oss_context(self, action: str, action_context: ActionContext | None) -> bool:
        """Keep pre-v4 local plugins usable without weakening shared Runtime."""

        if not (
            getattr(getattr(self.ap, 'deployment', None), 'mode', 'oss') == 'oss'
            and isinstance(action_context, ActionContext)
            and not isinstance(action_context, InstallationBinding)
        ):
            return False
        if action in {
            RuntimeToLangBotAction.INITIALIZE_PLUGIN_SETTINGS.value,
            RuntimeToLangBotAction.GET_PLUGIN_SETTINGS.value,
            CommonAction.FILE_CHUNK.value,
        }:
            return True
        # Pre-v4 OSS workers receive this capability from Core's settings
        # response, but their pinned SDK cannot carry revision/digest fields.
        # Shared Runtime never enters this compatibility branch.
        return bool(action_context.installation_uuid)

    def _require_runtime_action_context(self) -> ActionContext:
        action_context = self.current_action_context
        if action_context is None:
            raise ValueError('Plugin Runtime action is missing a trusted Workspace context')
        return action_context

    async def _resolve_installation_identity(
        self,
        action_context: InstallationBinding,
    ) -> _PluginInstallationIdentity:
        cached = self._installation_bindings.get(action_context.installation_uuid)
        if cached is not None:
            cached_binding, identity = cached
            if cached_binding != action_context:
                raise ValueError('Plugin installation revision or artifact is stale')
            return identity

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(
                persistence_plugin.PluginSetting.plugin_author,
                persistence_plugin.PluginSetting.plugin_name,
                persistence_plugin.PluginSetting.installation_uuid,
                persistence_plugin.PluginSetting.runtime_revision,
                persistence_plugin.PluginSetting.artifact_digest,
            )
            .where(persistence_plugin.PluginSetting.workspace_uuid == action_context.workspace_uuid)
            .where(persistence_plugin.PluginSetting.installation_uuid == action_context.installation_uuid)
        )
        setting = result.first()
        if setting is None:
            raise ValueError('Plugin installation is not registered in this Workspace')
        if (
            setting.runtime_revision != action_context.runtime_revision
            or setting.artifact_digest != action_context.artifact_digest
        ):
            raise ValueError('Plugin installation revision or artifact is stale')
        identity = _PluginInstallationIdentity(
            workspace_uuid=action_context.workspace_uuid,
            plugin_author=setting.plugin_author,
            plugin_name=setting.plugin_name,
            installation_uuid=setting.installation_uuid,
            runtime_revision=setting.runtime_revision,
            artifact_digest=setting.artifact_digest,
        )
        self._installation_bindings[action_context.installation_uuid] = (action_context, identity)
        return identity

    async def _resolve_legacy_oss_installation_identity(
        self,
        action_context: ActionContext,
    ) -> _PluginInstallationIdentity:
        if not action_context.installation_uuid:
            raise ValueError('Legacy OSS plugin action is missing its installation capability')
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(
                persistence_plugin.PluginSetting.plugin_author,
                persistence_plugin.PluginSetting.plugin_name,
                persistence_plugin.PluginSetting.installation_uuid,
                persistence_plugin.PluginSetting.runtime_revision,
                persistence_plugin.PluginSetting.artifact_digest,
            )
            .where(persistence_plugin.PluginSetting.workspace_uuid == action_context.workspace_uuid)
            .where(persistence_plugin.PluginSetting.installation_uuid == action_context.installation_uuid)
        )
        setting = result.first()
        if setting is None:
            raise ValueError('Plugin installation is not registered in this Workspace')
        return _PluginInstallationIdentity(
            workspace_uuid=action_context.workspace_uuid,
            plugin_author=setting.plugin_author,
            plugin_name=setting.plugin_name,
            installation_uuid=setting.installation_uuid,
            runtime_revision=setting.runtime_revision,
            artifact_digest=setting.artifact_digest,
        )

    async def _require_plugin_action_context(
        self,
    ) -> tuple[ActionContext, _PluginInstallationIdentity]:
        action_context = self._require_runtime_action_context()
        if isinstance(action_context, InstallationBinding):
            identity = await self._resolve_installation_identity(action_context)
        elif self._allow_legacy_oss_context('plugin_action', action_context):
            identity = await self._resolve_legacy_oss_installation_identity(action_context)
        else:
            raise ValueError('Plugin action requires a complete InstallationBinding context')
        return action_context, identity

    async def _require_active_action_context(self, action_context: ActionContext) -> None:
        """Fence stale Runtime generations against Core's active projection."""

        workspace_service = getattr(self.ap, 'workspace_service', None)
        if workspace_service is None:
            raise ValueError('Workspace execution service is unavailable')
        binding = await workspace_service.get_execution_binding(
            action_context.workspace_uuid,
            expected_generation=action_context.placement_generation,
        )
        if (
            binding.instance_uuid != action_context.instance_uuid
            or binding.workspace_uuid != action_context.workspace_uuid
            or binding.placement_generation != action_context.placement_generation
        ):
            raise ValueError('Plugin Runtime action uses a stale Workspace execution binding')

    @contextlib.asynccontextmanager
    async def _tenant_action_scope(self, action_context: ActionContext):
        """Bind Runtime-origin work to the trusted Workspace database scope.

        Cloud persistence deliberately rejects unscoped access and PostgreSQL
        RLS reads the Workspace id from each short database transaction. The
        wire envelope is validated before this helper is entered, so plugin
        payload fields can never select the scope. A transaction-free boundary
        avoids reserving one pooled connection across provider and network waits.
        """

        persistence_mgr = getattr(self.ap, 'persistence_mgr', None)
        if persistence_mgr is None:
            yield
            return
        tenant_scope_descriptor = getattr(type(persistence_mgr), 'tenant_scope', None)
        if not callable(tenant_scope_descriptor):
            # Lightweight test doubles and older OSS persistence managers do
            # not expose the transaction-free scope API.
            yield
            return
        async with persistence_mgr.tenant_scope(action_context.workspace_uuid):
            yield

    def _secure_plugin_actions(self) -> None:
        """Wrap plugin-origin actions with installation validation and payload scrubbing."""

        for action_name, action_handler in list(self.actions.items()):
            if action_name == CommonAction.PING.value:
                continue

            async def secured_action(
                data: dict[str, Any],
                *,
                _action_handler=action_handler,
                _runtime_scoped=action_name in _RUNTIME_SCOPED_ACTIONS,
            ) -> handler.ActionResponse:
                action_context = self._require_runtime_action_context()
                async with self._tenant_action_scope(action_context):
                    if not _runtime_scoped:
                        action_context, _ = await self._require_plugin_action_context()
                    await self._require_active_action_context(action_context)
                    safe_data = {key: value for key, value in data.items() if key not in _UNTRUSTED_SCOPE_FIELDS}
                    response = _action_handler(safe_data)
                    if inspect.isawaitable(response):
                        response = await response
                    return response

            self.actions[action_name] = secured_action

    async def _get_plugin_setting(
        self,
        action_context: ActionContext,
        identity: _PluginInstallationIdentity,
    ):
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_plugin.PluginSetting)
            .where(persistence_plugin.PluginSetting.workspace_uuid == action_context.workspace_uuid)
            .where(persistence_plugin.PluginSetting.plugin_author == identity.plugin_author)
            .where(persistence_plugin.PluginSetting.plugin_name == identity.plugin_name)
        )
        setting = result.first()
        if setting is None:
            raise ValueError('Plugin installation setting was not found')
        return setting

    async def _get_plugin_setting_by_name(
        self,
        action_context: ActionContext,
        plugin_author: str,
        plugin_name: str,
    ):
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_plugin.PluginSetting)
            .where(persistence_plugin.PluginSetting.workspace_uuid == action_context.workspace_uuid)
            .where(persistence_plugin.PluginSetting.plugin_author == plugin_author)
            .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
        )
        return result.first()

    @staticmethod
    def _require_setting_binding(setting, action_context: InstallationBinding) -> None:
        if setting is None:
            raise ValueError('Plugin installation setting was not found')
        if (
            setting.installation_uuid != action_context.installation_uuid
            or setting.runtime_revision != action_context.runtime_revision
            or setting.artifact_digest != action_context.artifact_digest
        ):
            raise ValueError('Plugin installation binding does not match the active setting')

    async def _resolve_query(
        self,
        data: dict[str, Any],
        action_context: ActionContext,
    ):
        query_uuid = data.get('query_uuid')
        if query_uuid is not None:
            query = await self.ap.query_pool.get_query(
                action_context.workspace_uuid,
                query_uuid,
            )
        else:
            query = await self.ap.query_pool.get_query_by_legacy_id(
                action_context.workspace_uuid,
                data['query_id'],
            )

        if query is None:
            return None
        if (
            getattr(query, 'instance_uuid', None) != action_context.instance_uuid
            or getattr(query, 'workspace_uuid', None) != action_context.workspace_uuid
            or getattr(query, 'placement_generation', None) != action_context.placement_generation
        ):
            return None
        return query

    async def _resource_exists(
        self,
        model,
        uuid_column,
        resource_uuid: str,
        workspace_uuid: str,
    ) -> bool:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(uuid_column)
            .select_from(model)
            .where(model.workspace_uuid == workspace_uuid)
            .where(uuid_column == resource_uuid)
            .limit(1)
        )
        return result.first() is not None

    @staticmethod
    def _config_contains_file_key(value: Any, file_key: str) -> bool:
        if isinstance(value, dict):
            return any(RuntimeConnectionHandler._config_contains_file_key(item, file_key) for item in value.values())
        if isinstance(value, list):
            return any(RuntimeConnectionHandler._config_contains_file_key(item, file_key) for item in value)
        return isinstance(value, str) and value == file_key

    @staticmethod
    def _execution_context(action_context: ActionContext) -> ExecutionContext:
        """Project the trusted wire binding into Core's runtime context."""

        return ExecutionContext(
            instance_uuid=action_context.instance_uuid,
            workspace_uuid=action_context.workspace_uuid,
            placement_generation=action_context.placement_generation,
        )

    @staticmethod
    def _binary_storage_owner(
        action_context: ActionContext,
        identity: _PluginInstallationIdentity,
        owner_type: str,
    ) -> str:
        """Resolve storage ownership exclusively from the trusted binding."""

        if owner_type == 'workspace':
            return action_context.workspace_uuid
        if owner_type == 'plugin':
            return f'{identity.plugin_author}/{identity.plugin_name}'
        raise ValueError(f'Unsupported binary storage owner_type {owner_type!r}')

    @classmethod
    def _binary_storage_key(
        cls,
        action_context: ActionContext,
        *,
        owner_type: str,
        owner: str,
        key: str,
    ) -> str:
        """Use Core's canonical key across every persistent owner dimension."""

        # Import lazily: StorageMgr references the Application type, whose
        # module wires the plugin connector during startup.
        from ..storage.mgr import StorageMgr

        return StorageMgr.canonical_binary_storage_key(
            cls._execution_context(action_context),
            owner_type=owner_type,
            owner=owner,
            key=key,
        )

    def __init__(
        self,
        connection: Connection,
        disconnect_callback: typing.Callable[[], typing.Coroutine[typing.Any, typing.Any, bool]],
        ap: app.Application,
    ):
        super().__init__(connection, disconnect_callback)
        self.ap = ap
        self._outbound_installation_context: contextvars.ContextVar[InstallationBinding | None] = (
            contextvars.ContextVar(
                f'{self.__class__.__name__}_{id(self)}_outbound_installation',
                default=None,
            )
        )
        self._installation_bindings: dict[
            str,
            tuple[InstallationBinding, _PluginInstallationIdentity],
        ] = {}

        @self.action(RuntimeToLangBotAction.INITIALIZE_PLUGIN_SETTINGS)
        async def initialize_plugin_settings(data: dict[str, Any]) -> handler.ActionResponse:
            """Initialize plugin settings"""
            action_context = self._require_runtime_action_context()
            # check if exists plugin setting
            plugin_author = data['plugin_author']
            plugin_name = data['plugin_name']
            install_source = data['install_source']
            install_info = data['install_info']

            try:
                setting = await self._get_plugin_setting_by_name(
                    action_context,
                    plugin_author,
                    plugin_name,
                )
                if isinstance(action_context, InstallationBinding):
                    self._require_setting_binding(setting, action_context)
                elif setting is None:
                    # OSS debug and pre-v4 data/plugins are the only callers
                    # allowed to create settings without a desired-state row.
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.insert(persistence_plugin.PluginSetting).values(
                            workspace_uuid=action_context.workspace_uuid,
                            plugin_author=plugin_author,
                            plugin_name=plugin_name,
                            install_source=install_source,
                            install_info=install_info,
                            enabled=True,
                            priority=0,
                            config={},
                        )
                    )
                else:
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.update(persistence_plugin.PluginSetting)
                        .where(persistence_plugin.PluginSetting.workspace_uuid == action_context.workspace_uuid)
                        .where(persistence_plugin.PluginSetting.plugin_author == plugin_author)
                        .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
                        .values(install_source=install_source, install_info=install_info)
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

            action_context = self._require_runtime_action_context()
            plugin_author = data['plugin_author']
            plugin_name = data['plugin_name']

            setting = await self._get_plugin_setting_by_name(
                action_context,
                plugin_author,
                plugin_name,
            )
            if isinstance(action_context, InstallationBinding):
                self._require_setting_binding(setting, action_context)

            data = {
                'enabled': True,
                'priority': 0,
                'plugin_config': {},
                'install_source': 'local',
                'install_info': {},
                'installation_uuid': None,
                'runtime_revision': None,
                'artifact_digest': None,
            }

            if setting is not None:
                data['enabled'] = setting.enabled
                data['priority'] = setting.priority
                data['plugin_config'] = setting.config
                data['install_source'] = setting.install_source
                data['install_info'] = setting.install_info
                data['installation_uuid'] = setting.installation_uuid
                data['runtime_revision'] = setting.runtime_revision
                data['artifact_digest'] = setting.artifact_digest

            return handler.ActionResponse.success(
                data=data,
            )

        @self.action(PluginToRuntimeAction.REPLY_MESSAGE)
        async def reply_message(data: dict[str, Any]) -> handler.ActionResponse:
            """Reply message"""
            action_context, _ = await self._require_plugin_action_context()
            query_id = data['query_id']
            message_chain = data['message_chain']
            quote_origin = data['quote_origin']

            query = await self._resolve_query(data, action_context)
            if query is None:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

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
            action_context, _ = await self._require_plugin_action_context()
            query_id = data['query_id']
            query = await self._resolve_query(data, action_context)
            if query is None:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

            return handler.ActionResponse.success(
                data={
                    'bot_uuid': query.bot_uuid,
                },
            )

        @self.action(PluginToRuntimeAction.SET_QUERY_VAR)
        async def set_query_var(data: dict[str, Any]) -> handler.ActionResponse:
            """Set query var"""
            action_context, _ = await self._require_plugin_action_context()
            query_id = data['query_id']
            key = data['key']
            value = data['value']

            query = await self._resolve_query(data, action_context)
            if query is None:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

            query.variables[key] = value

            return handler.ActionResponse.success(
                data={},
            )

        @self.action(PluginToRuntimeAction.GET_QUERY_VAR)
        async def get_query_var(data: dict[str, Any]) -> handler.ActionResponse:
            """Get query var"""
            action_context, _ = await self._require_plugin_action_context()
            query_id = data['query_id']
            key = data['key']

            query = await self._resolve_query(data, action_context)
            if query is None:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

            return handler.ActionResponse.success(
                data={
                    'value': query.variables[key],
                },
            )

        @self.action(PluginToRuntimeAction.GET_QUERY_VARS)
        async def get_query_vars(data: dict[str, Any]) -> handler.ActionResponse:
            """Get query vars"""
            action_context, _ = await self._require_plugin_action_context()
            query_id = data['query_id']
            query = await self._resolve_query(data, action_context)
            if query is None:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

            return handler.ActionResponse.success(
                data={
                    'vars': query.variables,
                },
            )

        @self.action(PluginToRuntimeAction.CREATE_NEW_CONVERSATION)
        async def create_new_conversation(data: dict[str, Any]) -> handler.ActionResponse:
            """Create new conversation"""
            action_context, _ = await self._require_plugin_action_context()
            query_id = data['query_id']
            query = await self._resolve_query(data, action_context)
            if query is None:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

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
            action_context, _ = await self._require_plugin_action_context()
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_bot.Bot).where(
                    persistence_bot.Bot.workspace_uuid == action_context.workspace_uuid
                )
            )
            bots = [
                self.ap.persistence_mgr.serialize_model(
                    persistence_bot.Bot,
                    bot,
                    ['adapter_config'],
                )
                for bot in result.all()
            ]
            return handler.ActionResponse.success(
                data={
                    'bots': bots,
                },
            )

        @self.action(PluginToRuntimeAction.GET_BOT_INFO)
        async def get_bot_info(data: dict[str, Any]) -> handler.ActionResponse:
            """Get bot info"""
            action_context, _ = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
            bot_uuid = data['bot_uuid']
            if not await self._resource_exists(
                persistence_bot.Bot,
                persistence_bot.Bot.uuid,
                bot_uuid,
                action_context.workspace_uuid,
            ):
                return handler.ActionResponse.error(
                    message=f'Bot with bot_uuid {bot_uuid} not found',
                )
            bot = await self.ap.bot_service.get_runtime_bot_info(
                execution_context,
                bot_uuid,
                include_secret=False,
            )
            return handler.ActionResponse.success(
                data={
                    'bot': bot,
                },
            )

        @self.action(PluginToRuntimeAction.SEND_MESSAGE)
        async def send_message(data: dict[str, Any]) -> handler.ActionResponse:
            """Send message"""
            action_context, _ = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
            bot_uuid = data['bot_uuid']
            target_type = data['target_type']
            target_id = data['target_id']
            message_chain = data['message_chain']

            if not await self._resource_exists(
                persistence_bot.Bot,
                persistence_bot.Bot.uuid,
                bot_uuid,
                action_context.workspace_uuid,
            ):
                return handler.ActionResponse.error(
                    message=f'Bot with bot_uuid {bot_uuid} not found',
                )

            # Use custom deserializer that properly handles Forward messages
            message_chain_obj = platform_message.MessageChain.model_validate(message_chain)

            bot = await self.ap.platform_mgr.get_bot_by_uuid(
                execution_context,
                bot_uuid,
            )
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
            action_context, _ = await self._require_plugin_action_context()
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_model.LLMModel.uuid).where(
                    persistence_model.LLMModel.workspace_uuid == action_context.workspace_uuid
                )
            )
            return handler.ActionResponse.success(
                data={
                    'llm_models': list(result.scalars().all()),
                },
            )

        @self.action(PluginToRuntimeAction.INVOKE_LLM)
        async def invoke_llm(data: dict[str, Any]) -> handler.ActionResponse:
            """Invoke llm"""
            action_context, _ = await self._require_plugin_action_context()
            llm_model_uuid = data['llm_model_uuid']
            messages = data['messages']
            funcs = data.get('funcs', [])
            extra_args = data.get('extra_args', {})

            if not await self._resource_exists(
                persistence_model.LLMModel,
                persistence_model.LLMModel.uuid,
                llm_model_uuid,
                action_context.workspace_uuid,
            ):
                return handler.ActionResponse.error(
                    message=f'LLM model with llm_model_uuid {llm_model_uuid} not found',
                )
            try:
                execution_context = self._execution_context(action_context)
                llm_model = await self.ap.model_mgr.get_model_by_uuid(
                    execution_context,
                    llm_model_uuid,
                )
            except ValueError:
                return handler.ActionResponse.error(
                    message=f'LLM model with llm_model_uuid {llm_model_uuid} not found',
                )
            runtime_workspace_uuid = getattr(
                getattr(llm_model, 'model_entity', None),
                'workspace_uuid',
                None,
            )
            if runtime_workspace_uuid not in (None, action_context.workspace_uuid):
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

            result = await llm_model.provider.invoke_llm(
                query=None,
                model=llm_model,
                messages=messages_obj,
                funcs=funcs_obj,
                extra_args=extra_args,
                execution_context=execution_context,
            )

            return handler.ActionResponse.success(
                data={
                    'message': result.model_dump(),
                },
            )

        @self.action(RuntimeToLangBotAction.SET_BINARY_STORAGE)
        async def set_binary_storage(data: dict[str, Any]) -> handler.ActionResponse:
            """Set binary storage"""
            action_context, identity = await self._require_plugin_action_context()
            key = data['key']
            owner_type = data['owner_type']
            try:
                owner = self._binary_storage_owner(action_context, identity, owner_type)
                unique_key = self._binary_storage_key(
                    action_context,
                    owner_type=owner_type,
                    owner=owner,
                    key=key,
                )
            except ValueError as e:
                return handler.ActionResponse.error(
                    message=str(e),
                )
            value = base64.b64decode(data['value_base64'])
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
                .where(persistence_bstorage.BinaryStorage.workspace_uuid == action_context.workspace_uuid)
                .where(persistence_bstorage.BinaryStorage.unique_key == unique_key)
            )

            if result.first() is not None:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.update(persistence_bstorage.BinaryStorage)
                    .where(persistence_bstorage.BinaryStorage.workspace_uuid == action_context.workspace_uuid)
                    .where(persistence_bstorage.BinaryStorage.unique_key == unique_key)
                    .values(value=value)
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(persistence_bstorage.BinaryStorage).values(
                        workspace_uuid=action_context.workspace_uuid,
                        unique_key=unique_key,
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
            """Get binary storage"""
            action_context, identity = await self._require_plugin_action_context()
            key = data['key']
            owner_type = data['owner_type']
            try:
                owner = self._binary_storage_owner(action_context, identity, owner_type)
                unique_key = self._binary_storage_key(
                    action_context,
                    owner_type=owner_type,
                    owner=owner,
                    key=key,
                )
            except ValueError as e:
                return handler.ActionResponse.error(
                    message=str(e),
                )

            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_bstorage.BinaryStorage)
                .where(persistence_bstorage.BinaryStorage.workspace_uuid == action_context.workspace_uuid)
                .where(persistence_bstorage.BinaryStorage.unique_key == unique_key)
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
            """Delete binary storage"""
            action_context, identity = await self._require_plugin_action_context()
            key = data['key']
            owner_type = data['owner_type']
            try:
                owner = self._binary_storage_owner(action_context, identity, owner_type)
                unique_key = self._binary_storage_key(
                    action_context,
                    owner_type=owner_type,
                    owner=owner,
                    key=key,
                )
            except ValueError as e:
                return handler.ActionResponse.error(
                    message=str(e),
                )

            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_bstorage.BinaryStorage)
                .where(persistence_bstorage.BinaryStorage.workspace_uuid == action_context.workspace_uuid)
                .where(persistence_bstorage.BinaryStorage.unique_key == unique_key)
            )

            return handler.ActionResponse.success(
                data={},
            )

        @self.action(RuntimeToLangBotAction.GET_BINARY_STORAGE_KEYS)
        async def get_binary_storage_keys(data: dict[str, Any]) -> handler.ActionResponse:
            """Get binary storage keys"""
            action_context, identity = await self._require_plugin_action_context()
            owner_type = data['owner_type']
            try:
                owner = self._binary_storage_owner(action_context, identity, owner_type)
            except ValueError as e:
                return handler.ActionResponse.error(
                    message=str(e),
                )

            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_bstorage.BinaryStorage.key)
                .where(persistence_bstorage.BinaryStorage.workspace_uuid == action_context.workspace_uuid)
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
            """Get a config file by file key"""
            action_context, identity = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
            file_key = data['file_key']

            try:
                setting = await self._get_plugin_setting(action_context, identity)
                if not self._config_contains_file_key(setting.config, file_key):
                    raise ValueError('Config file does not belong to this plugin installation')
                # The persisted config is user-controlled and therefore cannot
                # turn an arbitrary opaque object key into authority. Validate
                # every trusted scope dimension before touching the provider.
                file_bytes = await self.ap.storage_mgr.load_scoped_object_key(
                    execution_context,
                    file_key,
                    expected_owner_type='plugin_config',
                )

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
            action_context, _ = await self._require_plugin_action_context()
            embedding_model_uuid = data['embedding_model_uuid']
            texts = data['texts']

            if not await self._resource_exists(
                persistence_model.EmbeddingModel,
                persistence_model.EmbeddingModel.uuid,
                embedding_model_uuid,
                action_context.workspace_uuid,
            ):
                return handler.ActionResponse.error(
                    message=f'Embedding model with embedding_model_uuid {embedding_model_uuid} not found',
                )
            try:
                execution_context = self._execution_context(action_context)
                embedding_model = await self.ap.model_mgr.get_embedding_model_by_uuid(
                    execution_context,
                    embedding_model_uuid,
                )
            except ValueError:
                return handler.ActionResponse.error(
                    message=f'Embedding model with embedding_model_uuid {embedding_model_uuid} not found',
                )
            runtime_workspace_uuid = getattr(
                getattr(embedding_model, 'model_entity', None),
                'workspace_uuid',
                None,
            )
            if runtime_workspace_uuid not in (None, action_context.workspace_uuid):
                return handler.ActionResponse.error(
                    message=f'Embedding model with embedding_model_uuid {embedding_model_uuid} not found',
                )

            try:
                vectors = await embedding_model.provider.invoke_embedding(
                    embedding_model,
                    texts,
                    execution_context=execution_context,
                )
                return handler.ActionResponse.success(data={'vectors': vectors})
            except Exception as e:
                return _make_rag_error_response(e, 'EmbeddingError', embedding_model_uuid=embedding_model_uuid)

        @self.action(PluginToRuntimeAction.INVOKE_RERANK)
        async def invoke_rerank(data: dict[str, Any]) -> handler.ActionResponse:
            action_context, _ = await self._require_plugin_action_context()
            rerank_model_uuid = data['rerank_model_uuid']
            query = data['query']
            documents = data['documents']
            top_k = data.get('top_k')
            extra_args = data.get('extra_args', {})

            if not await self._resource_exists(
                persistence_model.RerankModel,
                persistence_model.RerankModel.uuid,
                rerank_model_uuid,
                action_context.workspace_uuid,
            ):
                return handler.ActionResponse.error(
                    message=f'Rerank model with rerank_model_uuid {rerank_model_uuid} not found',
                )
            try:
                execution_context = self._execution_context(action_context)
                rerank_model = await self.ap.model_mgr.get_rerank_model_by_uuid(
                    execution_context,
                    rerank_model_uuid,
                )
            except ValueError:
                return handler.ActionResponse.error(
                    message=f'Rerank model with rerank_model_uuid {rerank_model_uuid} not found',
                )
            runtime_workspace_uuid = getattr(
                getattr(rerank_model, 'model_entity', None),
                'workspace_uuid',
                None,
            )
            if runtime_workspace_uuid not in (None, action_context.workspace_uuid):
                return handler.ActionResponse.error(
                    message=f'Rerank model with rerank_model_uuid {rerank_model_uuid} not found',
                )

            try:
                scores = await rerank_model.provider.invoke_rerank(
                    model=rerank_model,
                    query=query,
                    documents=documents[:64],
                    extra_args=extra_args,
                    execution_context=execution_context,
                )
                scored = sorted(scores, key=lambda x: x.get('relevance_score', 0), reverse=True)
                if top_k is not None:
                    scored = scored[: int(top_k)]
                return handler.ActionResponse.success(data={'results': scored})
            except Exception as e:
                return _make_rag_error_response(e, 'RerankError', rerank_model_uuid=rerank_model_uuid)

        @self.action(PluginToRuntimeAction.VECTOR_UPSERT)
        async def vector_upsert(data: dict[str, Any]) -> handler.ActionResponse:
            action_context, _ = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
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
                    execution_context,
                    collection_id,
                    vectors,
                    ids,
                    metadata,
                    documents,
                )
                return handler.ActionResponse.success(data={})
            except Exception as e:
                return _make_rag_error_response(
                    e,
                    'VectorStoreError',
                    collection_id=collection_id,
                )

        @self.action(PluginToRuntimeAction.VECTOR_SEARCH)
        async def vector_search(data: dict[str, Any]) -> handler.ActionResponse:
            action_context, _ = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
            collection_id = data['collection_id']
            query_vector = data['query_vector']
            top_k = data['top_k']
            filters = data.get('filters')
            search_type = data.get('search_type', 'vector')
            query_text = data.get('query_text', '')
            vector_weight = data.get('vector_weight')
            try:
                results = await self.ap.rag_runtime_service.vector_search(
                    execution_context,
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
                return _make_rag_error_response(
                    e,
                    'VectorStoreError',
                    collection_id=collection_id,
                )

        @self.action(PluginToRuntimeAction.VECTOR_DELETE)
        async def vector_delete(data: dict[str, Any]) -> handler.ActionResponse:
            action_context, _ = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
            collection_id = data['collection_id']
            file_ids = data.get('file_ids')
            filters = data.get('filters')
            try:
                count = await self.ap.rag_runtime_service.vector_delete(
                    execution_context,
                    collection_id,
                    file_ids,
                    filters,
                )
                return handler.ActionResponse.success(data={'count': count})
            except Exception as e:
                return _make_rag_error_response(
                    e,
                    'VectorStoreError',
                    collection_id=collection_id,
                )

        @self.action(PluginToRuntimeAction.VECTOR_LIST)
        async def vector_list(data: dict[str, Any]) -> handler.ActionResponse:
            action_context, _ = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
            collection_id = data['collection_id']
            filters = data.get('filters')
            limit = data.get('limit', 20)
            offset = data.get('offset', 0)
            try:
                items, total = await self.ap.rag_runtime_service.vector_list(
                    execution_context,
                    collection_id,
                    filters,
                    limit,
                    offset,
                )
                return handler.ActionResponse.success(data={'items': items, 'total': total})
            except Exception as e:
                return _make_rag_error_response(
                    e,
                    'VectorStoreError',
                    collection_id=collection_id,
                )

        @self.action(PluginToRuntimeAction.GET_KNOWLEDEGE_FILE_STREAM)
        async def get_knowledge_file_stream(data: dict[str, Any]) -> handler.ActionResponse:
            action_context, _ = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
            storage_path = data['storage_path']
            try:
                content_bytes = await self.ap.rag_runtime_service.get_file_stream(
                    execution_context,
                    storage_path,
                )
                file_key = await self.send_file(content_bytes, '')
                return handler.ActionResponse.success(data={'file_key': file_key})
            except Exception as e:
                return _make_rag_error_response(e, 'FileServiceError', storage_path=storage_path)

        @self.action(PluginToRuntimeAction.LIST_PARSERS)
        async def list_parsers(data: dict[str, Any]) -> handler.ActionResponse:
            """Plugin requests host to list available parser plugins."""
            action_context, _ = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
            mime_type = data.get('mime_type')
            try:
                parsers = await self.ap.knowledge_service.list_parsers(
                    execution_context,
                    mime_type,
                )
                return handler.ActionResponse.success(data={'parsers': parsers})
            except Exception as e:
                return _make_rag_error_response(e, 'ParserDiscoveryError', mime_type=mime_type)

        @self.action(PluginToRuntimeAction.INVOKE_PARSER)
        async def invoke_parser(data: dict[str, Any]) -> handler.ActionResponse:
            """Plugin requests host to invoke a parser plugin."""
            action_context, _ = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
            plugin_author = data['plugin_author']
            plugin_name = data['plugin_name']
            storage_path = data['storage_path']
            mime_type = data.get('mime_type', 'application/octet-stream')
            filename = data.get('filename', '')
            metadata = data.get('metadata', {})
            try:
                # Read file from storage
                file_bytes = await self.ap.rag_runtime_service.get_file_stream(
                    execution_context,
                    storage_path,
                )
                context_data = {
                    'mime_type': mime_type,
                    'filename': filename,
                    'metadata': metadata,
                }
                await self.ap.plugin_connector.require_workspace_context(execution_context)
                result = await self.ap.plugin_connector.call_parser(
                    f'{plugin_author}/{plugin_name}', context_data, file_bytes
                )
                return handler.ActionResponse.success(data=result)
            except Exception as e:
                return _make_rag_error_response(e, 'ParserError')

        # ================= Knowledge Base Query APIs =================

        @self.action(PluginToRuntimeAction.LIST_KNOWLEDGE_BASES)
        async def list_knowledge_bases(data: dict[str, Any]) -> handler.ActionResponse:
            """List knowledge bases visible to the bound Workspace."""
            action_context, _ = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
            details = await self.ap.rag_mgr.get_all_knowledge_base_details(execution_context)
            knowledge_bases = [
                {
                    'uuid': kb['uuid'],
                    'name': kb['name'],
                    'description': kb.get('description') or '',
                }
                for kb in details
            ]
            return handler.ActionResponse.success(data={'knowledge_bases': knowledge_bases})

        @self.action(PluginToRuntimeAction.RETRIEVE_KNOWLEDGE)
        async def retrieve_knowledge(data: dict[str, Any]) -> handler.ActionResponse:
            """Retrieve documents from a knowledge base in the bound Workspace."""
            action_context, _ = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
            kb_id = data['kb_id']
            query_text = data['query_text']
            top_k = data.get('top_k', 5)
            filters = data.get('filters', {})

            kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(
                execution_context,
                kb_id,
            )
            if not kb:
                return handler.ActionResponse.error(
                    message=f'Knowledge base {kb_id} not found',
                )

            try:
                entries = await kb.retrieve(
                    execution_context,
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
            action_context, _ = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
            query_id = data['query_id']

            query = await self._resolve_query(data, action_context)
            if query is None:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

            kb_uuids = []
            if query.pipeline_config:
                local_agent_config = query.pipeline_config.get('ai', {}).get('local-agent', {})
                kb_uuids = local_agent_config.get('knowledge-bases', [])
                # Backward compatibility
                if not kb_uuids:
                    old_kb_uuid = local_agent_config.get('knowledge-base', '')
                    if old_kb_uuid and old_kb_uuid != '__none__':
                        kb_uuids = [old_kb_uuid]

            knowledge_bases = []
            for kb_uuid in kb_uuids:
                kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(
                    execution_context,
                    kb_uuid,
                )
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
            """Retrieve documents from a knowledge base within the pipeline's scope."""
            action_context, _ = await self._require_plugin_action_context()
            execution_context = self._execution_context(action_context)
            query_id = data['query_id']
            kb_id = data['kb_id']
            query_text = data['query_text']
            top_k = data.get('top_k', 5)
            filters = data.get('filters', {})

            query = await self._resolve_query(data, action_context)
            if query is None:
                return handler.ActionResponse.error(
                    message=f'Query with query_id {query_id} not found',
                )

            # Validate kb_id is in pipeline's allowed list
            allowed_kb_uuids = []
            if query.pipeline_config:
                local_agent_config = query.pipeline_config.get('ai', {}).get('local-agent', {})
                allowed_kb_uuids = local_agent_config.get('knowledge-bases', [])
                if not allowed_kb_uuids:
                    old_kb_uuid = local_agent_config.get('knowledge-base', '')
                    if old_kb_uuid and old_kb_uuid != '__none__':
                        allowed_kb_uuids = [old_kb_uuid]

            if kb_id not in allowed_kb_uuids:
                return handler.ActionResponse.error(
                    message=f'Knowledge base {kb_id} is not configured for this pipeline',
                )

            kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(
                execution_context,
                kb_id,
            )
            if not kb:
                return handler.ActionResponse.error(
                    message=f'Knowledge base {kb_id} not found',
                )

            try:
                session_name = f'{query.session.launcher_type.value}_{query.session.launcher_id}'
                entries = await kb.retrieve(
                    execution_context,
                    query_text,
                    settings={
                        'top_k': top_k,
                        'filters': filters,
                        'session_name': session_name,
                        'bot_uuid': query.bot_uuid or '',
                        'sender_id': str(query.sender_id),
                    },
                )
                results = [entry.model_dump(mode='json') for entry in entries]
                return handler.ActionResponse.success(data={'results': results})
            except Exception as e:
                return _make_rag_error_response(e, 'RetrievalError', kb_id=kb_id)

        @self.action(CommonAction.PING)
        async def ping(data: dict[str, Any]) -> handler.ActionResponse:
            """Ping"""
            return handler.ActionResponse.success(
                data={
                    'pong': 'pong',
                },
            )

        self._secure_plugin_actions()

    @contextlib.contextmanager
    def installation_scope(self, binding: InstallationBinding | None):
        """Attach one immutable installation tuple to nested wire actions."""

        token = self._outbound_installation_context.set(binding)
        try:
            yield
        finally:
            self._outbound_installation_context.reset(token)

    def register_installation_binding(
        self,
        binding: InstallationBinding,
        *,
        plugin_author: str,
        plugin_name: str,
    ) -> None:
        """Install Core's current desired-state fence for inbound actions."""

        existing = self._installation_bindings.get(binding.installation_uuid)
        if existing is not None:
            existing_binding = existing[0]
            if existing_binding.workspace_uuid != binding.workspace_uuid:
                raise ValueError('Plugin installation cannot move between Workspaces')
            if binding.placement_generation < existing_binding.placement_generation or (
                binding.placement_generation == existing_binding.placement_generation
                and binding.runtime_revision < existing_binding.runtime_revision
            ):
                raise ValueError('Cannot register a stale plugin installation binding')
        self._installation_bindings[binding.installation_uuid] = (
            binding,
            _PluginInstallationIdentity(
                workspace_uuid=binding.workspace_uuid,
                plugin_author=plugin_author,
                plugin_name=plugin_name,
                installation_uuid=binding.installation_uuid,
                runtime_revision=binding.runtime_revision,
                artifact_digest=binding.artifact_digest,
            ),
        )

    def unregister_installation_binding(self, binding: InstallationBinding) -> None:
        existing = self._installation_bindings.get(binding.installation_uuid)
        if existing is not None and existing[0] == binding:
            self._installation_bindings.pop(binding.installation_uuid, None)

    def resolve_outbound_action_context(
        self,
        action_context: InstallationBinding | ActionContext | dict[str, Any] | None,
    ) -> InstallationBinding | ActionContext | None:
        if action_context is not None:
            return super().resolve_outbound_action_context(action_context)
        inbound_context = self.current_action_context
        if inbound_context is not None:
            return inbound_context
        return self._outbound_installation_context.get()

    def require_outbound_installation_context(self) -> InstallationBinding:
        binding = self._outbound_installation_context.get()
        if not isinstance(binding, InstallationBinding):
            raise ValueError('Host plugin action requires an InstallationBinding scope')
        return binding

    async def ping(self) -> dict[str, Any]:
        """Ping the runtime"""
        with self.installation_scope(None):
            return await self.call_action(
                CommonAction.PING,
                {},
                timeout=10,
            )

    async def set_runtime_config(
        self,
        *,
        runtime_identity: RuntimeIdentity,
        worker_policy: PluginWorkerPolicy,
        runtime_profile: typing.Literal['oss_dev', 'shared'],
        cloud_service_url: str | None,
    ) -> dict[str, Any]:
        """Push the instance-scoped, immutable Runtime handshake."""

        runtime_config = RuntimeConfig(
            runtime_identity=runtime_identity,
            worker_policy=worker_policy,
            runtime_profile=runtime_profile,
            cloud_service_url=cloud_service_url,
        )
        with self.installation_scope(None):
            return await self.call_action(
                LangBotToRuntimeAction.SET_RUNTIME_CONFIG,
                runtime_config.model_dump(exclude_none=True),
                timeout=10,
            )

    async def reconcile_plugin_installations(
        self,
        installations: tuple[PluginInstallationDesiredState, ...],
    ) -> dict[str, Any]:
        request = ReconcilePluginInstallationsRequest(installations=installations)
        with self.installation_scope(None):
            return await self.call_action(
                LangBotToRuntimeAction.RECONCILE_PLUGIN_INSTALLATIONS,
                request.model_dump(),
                timeout=120,
            )

    async def apply_plugin_installation(
        self,
        binding: InstallationBinding,
        *,
        artifact_package: bytes | None,
        enabled: bool,
    ) -> dict[str, Any]:
        with self.installation_scope(binding):
            artifact_file_key = None
            if artifact_package is not None:
                artifact_file_key = await self.send_file(artifact_package, 'lbpkg')
            request = ApplyPluginInstallationRequest(
                artifact_file_key=artifact_file_key,
                enabled=enabled,
            )
            return await self.call_action(
                LangBotToRuntimeAction.APPLY_PLUGIN_INSTALLATION,
                request.model_dump(exclude_none=True),
                timeout=120,
            )

    async def remove_plugin_installation(
        self,
        binding: InstallationBinding,
    ) -> dict[str, Any]:
        with self.installation_scope(binding):
            return await self.call_action(
                LangBotToRuntimeAction.REMOVE_PLUGIN_INSTALLATION,
                RemovePluginInstallationRequest().model_dump(),
                timeout=120,
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
        action_context = self.require_outbound_installation_context()
        # update plugin setting
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_plugin.PluginSetting)
            .where(persistence_plugin.PluginSetting.workspace_uuid == action_context.workspace_uuid)
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

    async def notify_plugin_diagnostic(self, diagnostic: dict[str, Any]) -> dict[str, Any]:
        """Notify the plugin runtime about a best-effort plugin diagnostic.

        This intentionally uses the raw protocol string instead of a SDK enum so
        LangBot can keep running with older langbot-plugin versions.
        """
        return await self.call_action(
            _langbot_to_runtime_action('PLUGIN_DIAGNOSTIC', 'plugin_diagnostic'),
            diagnostic,
            timeout=5,
        )

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
        action_context = self.require_outbound_installation_context()
        # Delete plugin settings
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_plugin.PluginSetting)
            .where(persistence_plugin.PluginSetting.workspace_uuid == action_context.workspace_uuid)
            .where(persistence_plugin.PluginSetting.plugin_author == plugin_author)
            .where(persistence_plugin.PluginSetting.plugin_name == plugin_name)
        )

        # Delete all binary storage for this plugin
        owner = f'{plugin_author}/{plugin_name}'
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_bstorage.BinaryStorage)
            .where(persistence_bstorage.BinaryStorage.workspace_uuid == action_context.workspace_uuid)
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
        query_uuid: str | None = None,
    ) -> dict[str, Any]:
        """Call tool"""
        query_ref: dict[str, Any] = {'query_id': query_id}
        if query_uuid is not None:
            query_ref['query_uuid'] = query_uuid
        result = await self.call_action(
            LangBotToRuntimeAction.CALL_TOOL,
            {
                'tool_name': tool_name,
                'tool_parameters': parameters,
                'session': session,
                **query_ref,
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
        with self.installation_scope(None):
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
