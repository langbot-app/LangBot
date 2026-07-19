from __future__ import annotations

import sqlalchemy

from ....api.http.authz import WorkspaceRequiredError
from ....api.http.context import ExecutionContext, RequestContext
from ....core import app
from ....entity.persistence import rag as persistence_rag
from ....workspace.errors import WorkspaceNotFoundError
from .secrets import redact_secrets, restore_secret_placeholders
from .tenant import TenantContext, require_workspace_uuid


class KnowledgeService:
    """知识库服务"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    @staticmethod
    def _execution_context(context: RequestContext | ExecutionContext) -> ExecutionContext:
        if isinstance(context, RequestContext):
            return ExecutionContext.from_request(context)
        if isinstance(context, ExecutionContext):
            return context
        raise WorkspaceRequiredError('RequestContext or ExecutionContext is required')

    async def get_knowledge_bases(self, context: TenantContext, *, include_secret: bool = False) -> list[dict]:
        """获取所有知识库"""
        require_workspace_uuid(context)
        knowledge_bases = await self.ap.rag_mgr.get_all_knowledge_base_details(context)
        return knowledge_bases if include_secret else [redact_secrets(base) for base in knowledge_bases]

    async def get_knowledge_base(
        self,
        context: TenantContext,
        kb_uuid: str,
        *,
        include_secret: bool = False,
    ) -> dict | None:
        """获取知识库"""
        require_workspace_uuid(context)
        knowledge_base = await self.ap.rag_mgr.get_knowledge_base_details(context, kb_uuid)
        if knowledge_base is None or include_secret:
            return knowledge_base
        return redact_secrets(knowledge_base)

    async def create_knowledge_base(
        self,
        context: RequestContext | ExecutionContext,
        kb_data: dict,
    ) -> str:
        """创建知识库"""
        require_workspace_uuid(context)
        # In new architecture, we delegate entirely to RAGManager which uses plugins.
        # Legacy internal KB creation is removed.

        knowledge_engine_plugin_id = kb_data.get('knowledge_engine_plugin_id')
        if not knowledge_engine_plugin_id:
            raise ValueError('knowledge_engine_plugin_id is required')

        creation_settings = restore_secret_placeholders(kb_data.get('creation_settings', {}))
        retrieval_settings = kb_data.get('retrieval_settings', {})

        # Validate required fields based on plugin's creation_schema and retrieval_schema
        await self._validate_schema_required_fields(
            context,
            knowledge_engine_plugin_id,
            creation_settings,
            retrieval_settings,
        )

        kb = await self.ap.rag_mgr.create_knowledge_base(
            context,
            name=kb_data.get('name', 'Untitled'),
            knowledge_engine_plugin_id=knowledge_engine_plugin_id,
            creation_settings=creation_settings,
            retrieval_settings=retrieval_settings,
            description=kb_data.get('description', ''),
        )
        return kb.uuid

    async def _validate_schema_required_fields(
        self,
        context: RequestContext | ExecutionContext,
        plugin_id: str,
        creation_settings: dict,
        retrieval_settings: dict,
    ) -> None:
        """Validate required fields based on plugin's creation_schema and retrieval_schema.

        This is a business-agnostic validation that checks all fields marked as
        required in the plugin's schema, regardless of field type.

        Args:
            plugin_id: Knowledge Engine plugin ID.
            creation_settings: User-provided creation settings.
            retrieval_settings: User-provided retrieval settings.

        Raises:
            ValueError: If any required field is missing or empty.
        """
        if not self.ap.plugin_connector.is_enable_plugin:
            return

        # Validate creation_schema
        await self.ap.plugin_connector.require_workspace_context(context)
        try:
            creation_schema = await self.ap.plugin_connector.get_rag_creation_schema(plugin_id)
            self._check_required_fields(creation_schema, creation_settings, 'creation_settings')
        except ValueError:
            raise
        except Exception as e:
            self.ap.logger.warning(f'Failed to get creation_schema for validation: {e}')

        # Validate retrieval_schema
        await self.ap.plugin_connector.require_workspace_context(context)
        try:
            retrieval_schema = await self.ap.plugin_connector.get_rag_retrieval_schema(plugin_id)
            self._check_required_fields(retrieval_schema, retrieval_settings, 'retrieval_settings')
        except ValueError:
            raise
        except Exception as e:
            self.ap.logger.warning(f'Failed to get retrieval_schema for validation: {e}')

    def _check_required_fields(
        self,
        schema: dict | list,
        settings: dict,
        context: str,
    ) -> None:
        """Check required fields in schema against provided settings.

        Args:
            schema: Plugin-defined schema (can be list or dict with 'schema' key).
            settings: User-provided settings values.
            context: Context name for error messages (e.g., 'creation_settings').

        Raises:
            ValueError: If a required field is missing or empty.
        """
        if not schema:
            return

        # schema can be a list directly, or a dict with 'schema' key
        items = schema if isinstance(schema, list) else schema.get('schema', [])
        if not items:
            return

        for item in items:
            field_name = item.get('name')
            if not field_name:
                continue

            is_required = item.get('required', False)
            if not is_required:
                continue

            # Check show_if condition - if field is conditionally shown, only validate when condition is met
            show_if = item.get('show_if')
            if show_if:
                depend_field = show_if.get('field')
                operator = show_if.get('operator')
                expected_value = show_if.get('value')

                if depend_field and operator:
                    depend_value = settings.get(depend_field)
                    # If show_if condition is not met, skip validation for this field
                    if operator == 'eq' and depend_value != expected_value:
                        continue
                    if operator == 'neq' and depend_value == expected_value:
                        continue
                    if operator == 'in' and isinstance(expected_value, list) and depend_value not in expected_value:
                        continue

            value = settings.get(field_name)

            # Validate required field has a non-empty value
            if value is None or (isinstance(value, str) and value.strip() == ''):
                # Get field label for friendly error message
                label = item.get('label', {})
                field_label = (
                    label.get('en_US', field_name)
                    or label.get('zh_Hans', field_name)
                    or label.get('zh_Hant', field_name)
                    or field_name
                )
                raise ValueError(f'{field_label} is required ({context}.{field_name})')

    async def update_knowledge_base(
        self,
        context: RequestContext | ExecutionContext,
        kb_uuid: str,
        kb_data: dict,
    ) -> None:
        """更新知识库"""
        workspace_uuid = require_workspace_uuid(context)
        if await self.get_knowledge_base(context, kb_uuid) is None:
            raise WorkspaceNotFoundError('Knowledge base not found')
        # Filter to only mutable fields
        filtered_data = {k: v for k, v in kb_data.items() if k in persistence_rag.KnowledgeBase.MUTABLE_FIELDS}

        if not filtered_data:
            return

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_rag.KnowledgeBase)
            .values(filtered_data)
            .where(persistence_rag.KnowledgeBase.workspace_uuid == workspace_uuid)
            .where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )
        await self.ap.rag_mgr.remove_knowledge_base_from_runtime(context, kb_uuid)

        kb = await self.get_knowledge_base(context, kb_uuid, include_secret=True)
        if kb is None:
            raise WorkspaceNotFoundError('Knowledge base not found')

        await self.ap.rag_mgr.load_knowledge_base(context, kb)

    async def _check_doc_capability(self, context: TenantContext, kb_uuid: str, operation: str) -> None:
        """Check if the KB's Knowledge Engine supports document operations.

        Args:
            kb_uuid: Knowledge base UUID.
            operation: Human-readable operation name for error messages.

        Raises:
            Exception: If the KB does not support doc_ingestion.
        """
        kb_info = await self.ap.rag_mgr.get_knowledge_base_details(context, kb_uuid)
        if not kb_info:
            raise WorkspaceNotFoundError('Knowledge base not found')
        capabilities = kb_info.get('knowledge_engine', {}).get('capabilities', [])
        if 'doc_ingestion' not in capabilities:
            raise Exception(f'This knowledge base does not support {operation}')

    async def store_file(
        self,
        context: RequestContext | ExecutionContext,
        kb_uuid: str,
        file_id: str,
        parser_plugin_id: str | None = None,
    ) -> str:
        """存储文件"""
        execution_context = self._execution_context(context)
        runtime_kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(execution_context, kb_uuid)
        if runtime_kb is None:
            raise WorkspaceNotFoundError('Knowledge base not found')

        await self._check_doc_capability(context, kb_uuid, 'document upload')

        result = await runtime_kb.store_file(execution_context, file_id, parser_plugin_id=parser_plugin_id)

        # Update the KB's updated_at timestamp
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_rag.KnowledgeBase)
            .values(updated_at=sqlalchemy.func.now())
            .where(persistence_rag.KnowledgeBase.workspace_uuid == execution_context.workspace_uuid)
            .where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )

        return result

    async def retrieve_knowledge_base(
        self,
        context: RequestContext | ExecutionContext,
        kb_uuid: str,
        query: str,
        retrieval_settings: dict | None = None,
    ) -> list[dict]:
        """检索知识库"""
        execution_context = self._execution_context(context)
        runtime_kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(execution_context, kb_uuid)
        if runtime_kb is None:
            raise WorkspaceNotFoundError('Knowledge base not found')

        # Pass retrieval_settings
        results = await runtime_kb.retrieve(execution_context, query, settings=retrieval_settings)

        return [result.model_dump() for result in results]

    async def get_files_by_knowledge_base(self, context: TenantContext, kb_uuid: str) -> list[dict]:
        """获取知识库文件"""
        workspace_uuid = require_workspace_uuid(context)
        if await self.get_knowledge_base(context, kb_uuid) is None:
            raise WorkspaceNotFoundError('Knowledge base not found')
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.File)
            .where(persistence_rag.File.workspace_uuid == workspace_uuid)
            .where(persistence_rag.File.kb_id == kb_uuid)
        )
        files = result.all()
        return [self.ap.persistence_mgr.serialize_model(persistence_rag.File, file) for file in files]

    async def delete_file(
        self,
        context: RequestContext | ExecutionContext,
        kb_uuid: str,
        file_id: str,
    ) -> None:
        """删除文件"""
        execution_context = self._execution_context(context)
        runtime_kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(execution_context, kb_uuid)
        if runtime_kb is None:
            raise WorkspaceNotFoundError('Knowledge base not found')

        await self._check_doc_capability(context, kb_uuid, 'document deletion')

        await runtime_kb.delete_file(execution_context, file_id)

        # Update the KB's updated_at timestamp
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_rag.KnowledgeBase)
            .values(updated_at=sqlalchemy.func.now())
            .where(persistence_rag.KnowledgeBase.workspace_uuid == execution_context.workspace_uuid)
            .where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )

    async def delete_knowledge_base(
        self,
        context: RequestContext | ExecutionContext,
        kb_uuid: str,
    ) -> None:
        """删除知识库"""
        workspace_uuid = require_workspace_uuid(context)
        if await self.get_knowledge_base(context, kb_uuid) is None:
            raise WorkspaceNotFoundError('Knowledge base not found')

        # delete files
        # NOTE: Chunk cleanup is for legacy (pre-plugin) KBs that stored chunks locally.
        # For plugin-based Knowledge Engines, the Chunk table is not populated, so this is a no-op.
        files = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.File)
            .where(persistence_rag.File.workspace_uuid == workspace_uuid)
            .where(persistence_rag.File.kb_id == kb_uuid)
        )
        for file in files:
            # delete chunks
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_rag.Chunk)
                .where(persistence_rag.Chunk.workspace_uuid == workspace_uuid)
                .where(persistence_rag.Chunk.file_id == file.uuid)
            )
            # delete file
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_rag.File)
                .where(persistence_rag.File.workspace_uuid == workspace_uuid)
                .where(persistence_rag.File.uuid == file.uuid)
            )

        # Remove from runtime and notify plugin before deleting the owning row.
        await self.ap.rag_mgr.delete_knowledge_base(context, kb_uuid)
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_rag.KnowledgeBase)
            .where(persistence_rag.KnowledgeBase.workspace_uuid == workspace_uuid)
            .where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )

    # ================= Knowledge Engine Discovery =================

    async def list_knowledge_engines(self, context: TenantContext) -> list[dict]:
        """List all available Knowledge Engines from plugins."""
        require_workspace_uuid(context)
        engines = []

        if not self.ap.plugin_connector.is_enable_plugin:
            return engines
        await self.ap.plugin_connector.require_workspace_context(context)

        # Get KnowledgeEngine plugins
        try:
            knowledge_engines = await self.ap.plugin_connector.list_knowledge_engines()
            engines.extend(knowledge_engines)
        except Exception as e:
            self.ap.logger.warning(f'Failed to list Knowledge Engines from plugins: {e}')

        return engines

    async def list_parsers(self, context: TenantContext, mime_type: str | None = None) -> list[dict]:
        """List available parsers, optionally filtered by MIME type."""
        require_workspace_uuid(context)
        if not self.ap.plugin_connector.is_enable_plugin:
            return []
        await self.ap.plugin_connector.require_workspace_context(context)
        try:
            parsers = await self.ap.plugin_connector.list_parsers()
            if mime_type:
                parsers = [p for p in parsers if mime_type in p.get('supported_mime_types', [])]
            return parsers
        except Exception as e:
            self.ap.logger.warning(f'Failed to list parsers: {e}')
            return []

    async def get_engine_creation_schema(self, context: TenantContext, plugin_id: str) -> dict:
        """Get creation settings schema for a specific Knowledge Engine."""
        require_workspace_uuid(context)
        if not self.ap.plugin_connector.is_enable_plugin:
            return {}
        await self.ap.plugin_connector.require_workspace_context(context)
        try:
            return await self.ap.plugin_connector.get_rag_creation_schema(plugin_id)
        except Exception as e:
            self.ap.logger.warning(f'Failed to get creation schema for {plugin_id}: {e}')
            return {}

    async def get_engine_retrieval_schema(self, context: TenantContext, plugin_id: str) -> dict:
        """Get retrieval settings schema for a specific Knowledge Engine."""
        require_workspace_uuid(context)
        if not self.ap.plugin_connector.is_enable_plugin:
            return {}
        await self.ap.plugin_connector.require_workspace_context(context)
        try:
            return await self.ap.plugin_connector.get_rag_retrieval_schema(plugin_id)
        except Exception as e:
            self.ap.logger.warning(f'Failed to get retrieval schema for {plugin_id}: {e}')
            return {}
