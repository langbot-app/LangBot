from __future__ import annotations

import json
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
from ..entity.persistence import rag as persistence_rag
from ..storage.providers.localstorage import LocalStorageProvider, LOCAL_STORAGE_PATH
import os

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

            result = await llm_model.provider.invoke_llm(
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

        @self.action(PluginToRuntimeAction.GET_CONFIG_FILE)
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

        # ================= RAG Capability Handlers =================

        async def _get_kb_entity(kb_id: str):
            stmt = sqlalchemy.select(persistence_rag.KnowledgeBase).where(persistence_rag.KnowledgeBase.uuid == kb_id)
            result = await self.ap.persistence_mgr.execute_async(stmt)
            row = result.first()
            if not row:
                 raise ValueError(f"Knowledge Base {kb_id} not found")
            # Convert Row to KnowledgeBase entity
            kb = persistence_rag.KnowledgeBase(**row._mapping)
            return kb

        def _get_embedding_model_uuid(kb: persistence_rag.KnowledgeBase) -> str | None:
            """Get embedding model UUID from creation_settings (preferred) or KB field (fallback)."""
            # First check creation_settings (new approach - plugin defines via creation_schema)
            if kb.creation_settings and isinstance(kb.creation_settings, dict):
                embed_uuid = kb.creation_settings.get('embedding_model_uuid')
                if embed_uuid:
                    return embed_uuid
            # Fallback to KB field (backward compatibility)
            return kb.embedding_model_uuid

        @self.action(PluginToRuntimeAction.RAG_EMBED_DOCUMENTS)
        async def rag_embed_documents(data: dict[str, Any]) -> handler.ActionResponse:
            kb_id = data['kb_id']
            texts = data['texts']
            try:
                # 1. Get KB config to find embedding model
                kb = await _get_kb_entity(kb_id)
                embed_model_uuid = _get_embedding_model_uuid(kb)

                # 2. Get embedder instance
                if not embed_model_uuid:
                     return handler.ActionResponse.error(
                         message=f"Embedding model not configured for this Knowledge Base (kb_id: {kb_id})"
                     )

                embedder_model = await self.ap.model_mgr.get_embedding_model_by_uuid(embed_model_uuid)

                if not embedder_model:
                     return handler.ActionResponse.error(
                         message=f"Embedding model {embed_model_uuid} not found"
                     )

                # 3. Generate embeddings
                vectors = await embedder_model.embed_documents(texts)
                return handler.ActionResponse.success(data={'vectors': vectors})
            except Exception as e:
                return handler.ActionResponse.error(
                    message=f"{str(e)} (Original Error: {type(e).__name__}, Data: {json.dumps({'error_type': 'EmbeddingError', 'original_error': type(e).__name__})})"
                )

        @self.action(PluginToRuntimeAction.RAG_EMBED_QUERY)
        async def rag_embed_query(data: dict[str, Any]) -> handler.ActionResponse:
            kb_id = data['kb_id']
            text = data['text']
            try:
                kb = await _get_kb_entity(kb_id)
                embed_model_uuid = _get_embedding_model_uuid(kb)

                if not embed_model_uuid:
                     return handler.ActionResponse.error(
                         message=f"Embedding model not configured (kb_id: {kb_id})"
                     )

                embedder_model = await self.ap.model_mgr.get_embedding_model_by_uuid(embed_model_uuid)
                if not embedder_model:
                     return handler.ActionResponse.error(
                         message=f"Embedding model {embed_model_uuid} not found"
                     )

                vector = await embedder_model.embed_query(text)
                return handler.ActionResponse.success(data={'vector': vector})
            except Exception as e:
                return handler.ActionResponse.error(
                    message=f"{str(e)} (Original Error: {type(e).__name__}, Data: {json.dumps({'error_type': 'EmbeddingError', 'original_error': type(e).__name__})})"
                )

        @self.action(PluginToRuntimeAction.RAG_VECTOR_UPSERT)
        async def rag_vector_upsert(data: dict[str, Any]) -> handler.ActionResponse:
            collection_id = data['collection_id']
            vectors = data['vectors']
            ids = data['ids']
            metadata = data.get('metadata')
            try:
                metadatas = metadata if metadata else [{} for _ in vectors]
                await self.ap.vector_db_mgr.upsert(
                    collection_name=collection_id,
                    vectors=vectors,
                    ids=ids,
                    metadata=metadatas
                )
                return handler.ActionResponse.success(data={})
            except Exception as e:
                return handler.ActionResponse.error(
                    message=f"{str(e)} (Original Error: {type(e).__name__}, Data: {json.dumps({'error_type': 'VectorStoreError', 'collection_id': collection_id, 'original_error': type(e).__name__})})"
                )

        @self.action(PluginToRuntimeAction.RAG_VECTOR_SEARCH)
        async def rag_vector_search(data: dict[str, Any]) -> handler.ActionResponse:
            collection_id = data['collection_id']
            query_vector = data['query_vector']
            top_k = data['top_k']
            filters = data.get('filters')
            try:
                results = await self.ap.vector_db_mgr.search(
                    collection_name=collection_id,
                    query_vector=query_vector,
                    limit=top_k,
                    filter=filters
                )
                return handler.ActionResponse.success(data={'results': results})
            except Exception as e:
                return handler.ActionResponse.error(
                    message=f"{str(e)} (Original Error: {type(e).__name__}, Data: {json.dumps({'error_type': 'VectorStoreError', 'collection_id': collection_id, 'original_error': type(e).__name__})})"
                )

        @self.action(PluginToRuntimeAction.RAG_VECTOR_DELETE)
        async def rag_vector_delete(data: dict[str, Any]) -> handler.ActionResponse:
            collection_id = data['collection_id']
            ids = data.get('ids')
            filters = data.get('filters')
            try:
                count = 0
                if ids:
                    await self.ap.vector_db_mgr.delete(collection_name=collection_id, ids=ids)
                    count = len(ids)
                elif filters:
                     await self.ap.vector_db_mgr.delete_by_filter(collection_name=collection_id, filter=filters)

                return handler.ActionResponse.success(data={'count': count})
            except Exception as e:
                return handler.ActionResponse.error(
                    message=f"{str(e)} (Original Error: {type(e).__name__}, Data: {json.dumps({'error_type': 'VectorStoreError', 'collection_id': collection_id, 'original_error': type(e).__name__})})"
                )

        @self.action(PluginToRuntimeAction.RAG_GET_FILE_STREAM)
        async def rag_get_file_stream(data: dict[str, Any]) -> handler.ActionResponse:
            storage_path = data['storage_path']
            try:
                provider = self.ap.storage_mgr.storage_provider
                content_bytes = b""

                if isinstance(provider, LocalStorageProvider):
                    real_path = os.path.join(LOCAL_STORAGE_PATH, storage_path)
                    if os.path.exists(real_path):
                         with open(real_path, "rb") as f:
                             content_bytes = f.read()
                    else:
                        content_bytes = await self.ap.storage_mgr.load(storage_path)
                else:
                    content_bytes = await self.ap.storage_mgr.load(storage_path)

                content_base64 = base64.b64encode(content_bytes).decode('utf-8')
                return handler.ActionResponse.success(data={'content_base64': content_base64})
            except Exception as e:
                return handler.ActionResponse.error(
                    message=f"{str(e)} (Original Error: {type(e).__name__}, Data: {json.dumps({'error_type': 'FileServiceError', 'storage_path': storage_path, 'original_error': type(e).__name__})})"
                )

        @self.action(CommonAction.PING)
        async def ping(data: dict[str, Any]) -> handler.ActionResponse:
            """Ping"""
            return handler.ActionResponse.success(
                data={
                     "pong": "pong",
                },
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
        mime_type = result['mime_type']
        asset_bytes = await self.read_local_file(asset_file_key)
        await self.delete_local_file(asset_file_key)
        return {
            'asset_base64': base64.b64encode(asset_bytes).decode('utf-8'),
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
        instance_id: str,
        retrieval_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Retrieve knowledge"""
        result = await self.call_action(
            LangBotToRuntimeAction.RETRIEVE_KNOWLEDGE,
            {
                'plugin_author': plugin_author,
                'plugin_name': plugin_name,
                'retriever_name': retriever_name,
                'instance_id': instance_id,
                'retrieval_context': retrieval_context,
            },
            timeout=30,
        )
        return result

    async def sync_polymorphic_component_instances(self, required_instances: list[dict[str, Any]]) -> dict[str, Any]:
        """Sync polymorphic component instances with runtime"""
        result = await self.call_action(
            LangBotToRuntimeAction.SYNC_POLYMORPHIC_COMPONENT_INSTANCES,
            {
                'required_instances': required_instances,
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

    async def rag_ingest_document(self, plugin_author: str, plugin_name: str, context_data: dict[str, Any]) -> dict[str, Any]:
        """Send INGEST_DOCUMENT action to runtime."""
        result = await self.call_action(
            LangBotToRuntimeAction.RAG_INGEST_DOCUMENT,
            {
                "plugin_author": plugin_author,
                "plugin_name": plugin_name,
                "context": context_data
            },
            timeout=300  # Ingestion can be slow
        )
        return result

    async def rag_delete_document(self, plugin_author: str, plugin_name: str, document_id: str, kb_id: str) -> bool:
        result = await self.call_action(
            LangBotToRuntimeAction.RAG_DELETE_DOCUMENT,
            {
                "plugin_author": plugin_author,
                "plugin_name": plugin_name,
                "document_id": document_id,
                "kb_id": kb_id
            },
            timeout=30
        )
        return result.get("success", False)

    async def rag_on_kb_create(self, plugin_author: str, plugin_name: str, kb_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Notify plugin about KB creation."""
        result = await self.call_action(
            LangBotToRuntimeAction.RAG_ON_KB_CREATE,
            {
                "plugin_author": plugin_author,
                "plugin_name": plugin_name,
                "kb_id": kb_id,
                "config": config
            },
            timeout=30
        )
        return result

    async def rag_on_kb_delete(self, plugin_author: str, plugin_name: str, kb_id: str) -> dict[str, Any]:
        """Notify plugin about KB deletion."""
        result = await self.call_action(
            LangBotToRuntimeAction.RAG_ON_KB_DELETE,
            {
                "plugin_author": plugin_author,
                "plugin_name": plugin_name,
                "kb_id": kb_id
            },
            timeout=30
        )
        return result

    async def get_rag_creation_schema(self, plugin_author: str, plugin_name: str) -> dict[str, Any]:
        return await self.call_action(
            LangBotToRuntimeAction.GET_RAG_CREATION_SETTINGS_SCHEMA,
            {
                "plugin_author": plugin_author,
                "plugin_name": plugin_name
            },
            timeout=10
        )

    async def get_rag_retrieval_schema(self, plugin_author: str, plugin_name: str) -> dict[str, Any]:
        return await self.call_action(
            LangBotToRuntimeAction.GET_RAG_RETRIEVAL_SETTINGS_SCHEMA,
            {
                "plugin_author": plugin_author,
                "plugin_name": plugin_name
            },
            timeout=10
        )

    async def list_rag_engines(self) -> list[dict[str, Any]]:
        """List all available RAG engines from plugins."""
        result = await self.call_action(
            LangBotToRuntimeAction.LIST_RAG_ENGINES,
            {},
            timeout=60
        )
        return result.get("engines", [])
