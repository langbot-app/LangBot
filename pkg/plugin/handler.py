from __future__ import annotations

import typing
from typing import Any
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

from ..core import app
from ..utils import constants


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
            """Get llm models"""
            llm_models = await self.ap.llm_model_service.get_llm_models(include_secret=False)
            return handler.ActionResponse.success(
                data={
                    'llm_models': llm_models,
                },
            )

        @self.action(PluginToRuntimeAction.INVOKE_LLM)
        async def invoke_llm(data: dict[str, Any]) -> handler.ActionResponse:
            """Invoke llm"""
            llm_model_uuid = data['llm_model_uuid']
            messages = data['messages']
            funcs = data.get('funcs', [])
            extra_args = data.get('extra_args', {})

            llm_model = await self.ap.model_mgr.get_model_by_uuid(llm_model_uuid)
            if llm_model is None:
                return handler.ActionResponse.error(
                    message=f'LLM model with llm_model_uuid {llm_model_uuid} not found',
                )

            messages_obj = [provider_message.Message.model_validate(message) for message in messages]
            funcs_obj = [resource_tool.LLMTool.model_validate(func) for func in funcs]

            result = await llm_model.requester.invoke_llm(
                query=None,
                model=llm_model,
                messages=messages_obj,
                funcs=funcs_obj,
                extra_args=extra_args,
            )

            return handler.ActionResponse.success(
                data={
                    'message': result.model_dump(),
                },
            )

        @self.action(RuntimeToLangBotAction.SET_BINARY_STORAGE)
        async def set_binary_storage(data: dict[str, Any]) -> handler.ActionResponse:
            """Set binary storage"""
            key = data['key']
            owner_type = data['owner_type']
            owner = data['owner']
            value = base64.b64decode(data['value_base64'])

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
            """Get binary storage"""
            key = data['key']
            owner_type = data['owner_type']
            owner = data['owner']

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
            """Delete binary storage"""
            key = data['key']
            owner_type = data['owner_type']
            owner = data['owner']

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
            """Get binary storage keys"""
            owner_type = data['owner_type']
            owner = data['owner']

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

        @self.action(RuntimeToLangBotAction.GET_CONFIG_FILE)
        async def get_config_file(data: dict[str, Any]) -> handler.ActionResponse:
            """Get a config file by file key"""
            file_key = data['file_key']

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

    async def ping(self) -> dict[str, Any]:
        """Ping the runtime"""
        return await self.call_action(
            CommonAction.PING,
            {},
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
            timeout=60,
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
        self, tool_name: str, parameters: dict[str, Any], include_plugins: list[str] | None = None
    ) -> dict[str, Any]:
        """Call tool"""
        result = await self.call_action(
            LangBotToRuntimeAction.CALL_TOOL,
            {
                'tool_name': tool_name,
                'tool_parameters': parameters,
                'include_plugins': include_plugins,
            },
            timeout=60,
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
            timeout=60,
        )

        async for ret in gen:
            yield ret
