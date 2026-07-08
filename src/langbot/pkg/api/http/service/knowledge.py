from __future__ import annotations

import sqlalchemy

from ....core import app
from ....entity.persistence import rag as persistence_rag


class KnowledgeService:
    """知识库服务"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_knowledge_bases(self) -> list[dict]:
        """获取所有知识库"""
        return await self.ap.rag_mgr.get_all_knowledge_base_details()

    async def get_knowledge_base(self, kb_uuid: str) -> dict | None:
        """获取知识库"""
        return await self.ap.rag_mgr.get_knowledge_base_details(kb_uuid)

    async def create_knowledge_base(self, kb_data: dict) -> str:
        """创建知识库"""
        # In new architecture, we delegate entirely to RAGManager which uses plugins.
        # Legacy internal KB creation is removed.

        knowledge_engine_plugin_id = kb_data.get('knowledge_engine_plugin_id')
        if not knowledge_engine_plugin_id:
            raise ValueError('knowledge_engine_plugin_id is required')

        creation_settings = kb_data.get('creation_settings', {})
        retrieval_settings = kb_data.get('retrieval_settings', {})

        # Validate required fields based on plugin's creation_schema and retrieval_schema
        await self._validate_schema_required_fields(
            knowledge_engine_plugin_id,
            creation_settings,
            retrieval_settings,
        )

        kb = await self.ap.rag_mgr.create_knowledge_base(
            name=kb_data.get('name', 'Untitled'),
            knowledge_engine_plugin_id=knowledge_engine_plugin_id,
            creation_settings=creation_settings,
            retrieval_settings=retrieval_settings,
            description=kb_data.get('description', ''),
        )
        return kb.uuid

    async def _validate_schema_required_fields(
        self,
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
        # Validate creation_schema
        try:
            creation_schema = await self.ap.plugin_connector.get_rag_creation_schema(plugin_id)
            self._check_required_fields(creation_schema, creation_settings, 'creation_settings')
        except ValueError:
            raise
        except Exception as e:
            self.ap.logger.warning(f'Failed to get creation_schema for validation: {e}')

        # Validate retrieval_schema
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

    async def update_knowledge_base(self, kb_uuid: str, kb_data: dict) -> None:
        """更新知识库"""
        # Filter to only mutable fields
        filtered_data = {k: v for k, v in kb_data.items() if k in persistence_rag.KnowledgeBase.MUTABLE_FIELDS}

        if not filtered_data:
            return

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_rag.KnowledgeBase)
            .values(filtered_data)
            .where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )
        await self.ap.rag_mgr.remove_knowledge_base_from_runtime(kb_uuid)

        kb = await self.get_knowledge_base(kb_uuid)
        if kb is None:
            raise Exception('Knowledge base not found after update')

        await self.ap.rag_mgr.load_knowledge_base(kb)

    async def _check_doc_capability(self, kb_uuid: str, operation: str) -> None:
        """Check if the KB's Knowledge Engine supports document operations.

        Args:
            kb_uuid: Knowledge base UUID.
            operation: Human-readable operation name for error messages.

        Raises:
            Exception: If the KB does not support doc_ingestion.
        """
        kb_info = await self.ap.rag_mgr.get_knowledge_base_details(kb_uuid)
        if not kb_info:
            raise Exception('Knowledge base not found')
        capabilities = kb_info.get('knowledge_engine', {}).get('capabilities', [])
        if 'doc_ingestion' not in capabilities:
            raise Exception(f'This knowledge base does not support {operation}')

    async def store_file(self, kb_uuid: str, file_id: str, parser_plugin_id: str | None = None) -> str:
        """存储文件"""
        runtime_kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
        if runtime_kb is None:
            raise Exception('Knowledge base not found')

        await self._check_doc_capability(kb_uuid, 'document upload')

        result = await runtime_kb.store_file(file_id, parser_plugin_id=parser_plugin_id)

        # Update the KB's updated_at timestamp
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_rag.KnowledgeBase)
            .values(updated_at=sqlalchemy.func.now())
            .where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )

        return result

    async def retrieve_knowledge_base(
        self, kb_uuid: str, query: str, retrieval_settings: dict | None = None
    ) -> list[dict]:
        """检索知识库"""
        runtime_kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
        if runtime_kb is None:
            raise Exception('Knowledge base not found')

        # Pass retrieval_settings
        results = await runtime_kb.retrieve(query, settings=retrieval_settings)

        return [result.model_dump() for result in results]

    async def get_files_by_knowledge_base(self, kb_uuid: str) -> list[dict]:
        """获取知识库文件"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.File).where(persistence_rag.File.kb_id == kb_uuid)
        )
        files = result.all()
        return [self.ap.persistence_mgr.serialize_model(persistence_rag.File, file) for file in files]

    async def delete_file(self, kb_uuid: str, file_id: str) -> None:
        """删除文件"""
        runtime_kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
        if runtime_kb is None:
            raise Exception('Knowledge base not found')

        await self._check_doc_capability(kb_uuid, 'document deletion')

        await runtime_kb.delete_file(file_id)

        # Update the KB's updated_at timestamp
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_rag.KnowledgeBase)
            .values(updated_at=sqlalchemy.func.now())
            .where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )

    async def delete_knowledge_base(self, kb_uuid: str) -> None:
        """删除知识库"""
        # Delete from DB first to commit the deletion, then clean up runtime/plugin (best-effort)
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_rag.KnowledgeBase).where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )

        # delete files
        # NOTE: Chunk cleanup is for legacy (pre-plugin) KBs that stored chunks locally.
        # For plugin-based Knowledge Engines, the Chunk table is not populated, so this is a no-op.
        files = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.File).where(persistence_rag.File.kb_id == kb_uuid)
        )
        for file in files:
            # delete chunks
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_rag.Chunk).where(persistence_rag.Chunk.file_id == file.uuid)
            )
            # delete file
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_rag.File).where(persistence_rag.File.uuid == file.uuid)
            )

        # Remove from runtime and notify plugin (best-effort, DB is already cleaned up)
        await self.ap.rag_mgr.delete_knowledge_base(kb_uuid)

    # ================= Knowledge Engine Discovery =================

    async def list_knowledge_engines(self) -> list[dict]:
        """List all available Knowledge Engines from plugins."""
        engines = []

        if not self.ap.plugin_connector.is_enable_plugin:
            return engines

        # Get KnowledgeEngine plugins
        try:
            knowledge_engines = await self.ap.plugin_connector.list_knowledge_engines()
            engines.extend(knowledge_engines)
        except Exception as e:
            self.ap.logger.warning(f'Failed to list Knowledge Engines from plugins: {e}')

        return engines

    async def list_parsers(self, mime_type: str | None = None) -> list[dict]:
        """List available parsers, optionally filtered by MIME type."""
        if not self.ap.plugin_connector.is_enable_plugin:
            return []
        try:
            parsers = await self.ap.plugin_connector.list_parsers()
            if mime_type:
                parsers = [p for p in parsers if mime_type in p.get('supported_mime_types', [])]
            return parsers
        except Exception as e:
            self.ap.logger.warning(f'Failed to list parsers: {e}')
            return []

    async def get_engine_creation_schema(self, plugin_id: str) -> dict:
        """Get creation settings schema for a specific Knowledge Engine."""
        try:
            return await self.ap.plugin_connector.get_rag_creation_schema(plugin_id)
        except Exception as e:
            self.ap.logger.warning(f'Failed to get creation schema for {plugin_id}: {e}')
            return {}

    async def get_engine_retrieval_schema(self, plugin_id: str) -> dict:
        """Get retrieval settings schema for a specific Knowledge Engine."""
        try:
            return await self.ap.plugin_connector.get_rag_retrieval_schema(plugin_id)
        except Exception as e:
            self.ap.logger.warning(f'Failed to get retrieval schema for {plugin_id}: {e}')
            return {}
