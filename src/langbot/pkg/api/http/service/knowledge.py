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

        rag_engine_plugin_id = kb_data.get('rag_engine_plugin_id')
        if not rag_engine_plugin_id:
            raise ValueError('rag_engine_plugin_id is required')

        kb = await self.ap.rag_mgr.create_knowledge_base(
            name=kb_data.get('name', 'Untitled'),
            rag_engine_plugin_id=rag_engine_plugin_id,
            creation_settings=kb_data.get('creation_settings', {}),
            description=kb_data.get('description', ''),
            embedding_model_uuid=kb_data.get('embedding_model_uuid', ''),
        )
        return kb.uuid

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

        await self.ap.rag_mgr.load_knowledge_base(kb)

    async def _check_doc_capability(self, kb_uuid: str, operation: str) -> None:
        """Check if the KB's RAG engine supports document operations.

        Args:
            kb_uuid: Knowledge base UUID.
            operation: Human-readable operation name for error messages.

        Raises:
            Exception: If the KB does not support doc_ingestion.
        """
        kb_info = await self.ap.rag_mgr.get_knowledge_base_details(kb_uuid)
        if not kb_info:
            raise Exception('Knowledge base not found')
        capabilities = kb_info.get('rag_engine', {}).get('capabilities', [])
        if 'doc_ingestion' not in capabilities:
            raise Exception(f'This knowledge base does not support {operation}')

    async def store_file(self, kb_uuid: str, file_id: str) -> int:
        """存储文件"""
        runtime_kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
        if runtime_kb is None:
            raise Exception('Knowledge base not found')

        await self._check_doc_capability(kb_uuid, 'document upload')

        result = await runtime_kb.store_file(file_id)

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
        results = await runtime_kb.retrieve(query, runtime_kb.knowledge_base_entity.top_k, settings=retrieval_settings)

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
        await self.ap.rag_mgr.delete_knowledge_base(kb_uuid)

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_rag.KnowledgeBase).where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )

        # delete files
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

    # ================= RAG Engine Discovery =================

    async def list_rag_engines(self) -> list[dict]:
        """List all available RAG engines from plugins."""
        engines = []

        if not self.ap.plugin_connector.is_enable_plugin:
            return engines

        # Get RAGEngine plugins
        try:
            rag_engines = await self.ap.plugin_connector.list_rag_engines()
            engines.extend(rag_engines)
        except Exception as e:
            self.ap.logger.warning(f'Failed to list RAG engines from plugins: {e}')

        return engines

    async def get_engine_creation_schema(self, plugin_id: str) -> dict:
        """Get creation settings schema for a specific RAG engine."""
        try:
            return await self.ap.plugin_connector.get_rag_creation_schema(plugin_id)
        except Exception as e:
            self.ap.logger.warning(f'Failed to get creation schema for {plugin_id}: {e}')
            return {}

    async def get_engine_retrieval_schema(self, plugin_id: str) -> dict:
        """Get retrieval settings schema for a specific RAG engine."""
        try:
            return await self.ap.plugin_connector.get_rag_retrieval_schema(plugin_id)
        except Exception as e:
            self.ap.logger.warning(f'Failed to get retrieval schema for {plugin_id}: {e}')
            return {}
