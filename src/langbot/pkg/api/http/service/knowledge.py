from __future__ import annotations

import uuid
import sqlalchemy

from ....core import app
from ....entity.persistence import rag as persistence_rag


class KnowledgeService:
    """知识库服务"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def _enrich_kb_with_engine_info(self, kb_dict: dict) -> dict:
        """Enrich knowledge base dict with RAG engine information."""
        plugin_id = kb_dict.get("rag_engine_plugin_id")

        if plugin_id:
            # Try to get engine info from plugin
            try:
                engines = await self.list_rag_engines()
                engine_info = next(
                    (e for e in engines if e["plugin_id"] == plugin_id),
                    None
                )
                if engine_info:
                    kb_dict["rag_engine"] = {
                        "plugin_id": plugin_id,
                        "name": engine_info.get("name", plugin_id),
                        "capabilities": engine_info.get("capabilities", []),
                    }
                else:
                    # Plugin not loaded, use basic info
                    kb_dict["rag_engine"] = {
                        "plugin_id": plugin_id,
                        "name": plugin_id,
                        "capabilities": ["doc_ingestion"],
                    }
            except Exception:
                kb_dict["rag_engine"] = {
                    "plugin_id": plugin_id,
                    "name": plugin_id,
                    "capabilities": ["doc_ingestion"],
                }
        else:
            # Legacy internal KB without plugin
            kb_dict["rag_engine"] = {
                "plugin_id": None,
                "name": "Internal (Legacy)",
                "capabilities": ["doc_ingestion"],
            }

        return kb_dict

    async def get_knowledge_bases(self) -> list[dict]:
        """获取所有知识库"""
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_rag.KnowledgeBase))
        knowledge_bases = result.all()

        kb_list = []
        for knowledge_base in knowledge_bases:
            kb_dict = self.ap.persistence_mgr.serialize_model(persistence_rag.KnowledgeBase, knowledge_base)
            kb_dict = await self._enrich_kb_with_engine_info(kb_dict)
            kb_list.append(kb_dict)

        return kb_list

    async def get_knowledge_base(self, kb_uuid: str) -> dict | None:
        """获取知识库"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.KnowledgeBase).where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )
        knowledge_base = result.first()
        if knowledge_base is None:
            return None

        kb_dict = self.ap.persistence_mgr.serialize_model(persistence_rag.KnowledgeBase, knowledge_base)
        kb_dict = await self._enrich_kb_with_engine_info(kb_dict)
        return kb_dict

    async def create_knowledge_base(self, kb_data: dict) -> str:
        """创建知识库"""
        # Check if plugin-based creation
        if 'rag_engine_plugin_id' in kb_data and kb_data['rag_engine_plugin_id']:
            # Use new manager method
            kb = await self.ap.rag_mgr.create_knowledge_base(
                name=kb_data.get('name', 'Untitled'),
                rag_engine_plugin_id=kb_data['rag_engine_plugin_id'],
                creation_settings=kb_data.get('creation_settings', {}),
                description=kb_data.get('description', ''),
                embedding_model_uuid=kb_data.get('embedding_model_uuid', '')
            )
            return kb.uuid

        # Filter to only valid database fields for internal KB
        valid_fields = {'uuid', 'name', 'description', 'embedding_model_uuid', 'top_k', 'rag_engine_plugin_id', 'creation_settings'}
        filtered_data = {k: v for k, v in kb_data.items() if k in valid_fields}

        filtered_data['uuid'] = str(uuid.uuid4())
        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_rag.KnowledgeBase).values(filtered_data))

        kb = await self.get_knowledge_base(filtered_data['uuid'])

        await self.ap.rag_mgr.load_knowledge_base(kb)

        return filtered_data['uuid']

    async def update_knowledge_base(self, kb_uuid: str, kb_data: dict) -> None:
        """更新知识库"""
        # Filter to only valid database fields
        valid_fields = {'name', 'description', 'top_k', 'rag_engine_plugin_id', 'creation_settings'}
        filtered_data = {k: v for k, v in kb_data.items() if k in valid_fields}

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

    async def store_file(self, kb_uuid: str, file_id: str) -> int:
        """存储文件"""
        # await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_rag.File).values(kb_id=kb_uuid, file_id=file_id))
        # await self.ap.rag_mgr.store_file(file_id)
        runtime_kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
        if runtime_kb is None:
            raise Exception('Knowledge base not found')
        # Only internal KBs support file storage
        if runtime_kb.get_type() != 'internal':
            raise Exception('Only internal knowledge bases support file storage')
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
        results = await runtime_kb.retrieve(
            query, 
            runtime_kb.knowledge_base_entity.top_k, 
            settings=retrieval_settings
        )
        
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
        # Only internal KBs support file deletion
        if runtime_kb.get_type() != 'internal':
            raise Exception('Only internal knowledge bases support file deletion')
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
        """List all available knowledge base engines from plugins.

        Returns both KnowledgeRetriever (external) and RAGEngine types.
        """
        engines = []

        if not self.ap.plugin_connector.is_enable_plugin:
            return engines

        # 1. Get KnowledgeRetriever plugins (external knowledge bases like dify)
        try:
            retrievers = await self.ap.plugin_connector.list_knowledge_retrievers()
            for retriever in retrievers:
                # Get config from manifest.manifest.spec.config
                manifest_data = retriever.get('manifest', {})
                raw_manifest = manifest_data.get('manifest', {})
                spec = raw_manifest.get('spec', {})
                config_items = spec.get('config', [])

                engines.append({
                    'plugin_id': f"{retriever['plugin_author']}/{retriever['plugin_name']}",
                    'name': retriever.get('retriever_name', 'Unknown'),
                    'description': retriever.get('retriever_description'),
                    'type': 'retriever',  # External retriever type
                    'capabilities': [],  # No doc_ingestion
                    'creation_schema': config_items,  # Use config items as creation schema
                    'retrieval_schema': None,
                    # Keep original info for creating external KB
                    'component_name': retriever.get('retriever_name', ''),
                })
        except Exception as e:
            self.ap.logger.warning(f"Failed to list knowledge retrievers: {e}")

        # 2. Get RAGEngine plugins (new type with doc_ingestion support)
        try:
            rag_engines = await self.ap.plugin_connector.list_rag_engines()
            for engine in rag_engines:
                engine['type'] = 'rag_engine'  # Mark as RAG engine type
                engines.append(engine)
        except Exception as e:
            self.ap.logger.warning(f"Failed to list RAG engines from plugins: {e}")

        return engines

    async def get_engine_creation_schema(self, plugin_id: str) -> dict:
        """Get creation settings schema for a specific RAG engine."""
        try:
            return await self.ap.plugin_connector.get_rag_creation_schema(plugin_id)
        except Exception as e:
            self.ap.logger.warning(f"Failed to get creation schema for {plugin_id}: {e}")
            return {}

    async def get_engine_retrieval_schema(self, plugin_id: str) -> dict:
        """Get retrieval settings schema for a specific RAG engine."""
        try:
            return await self.ap.plugin_connector.get_rag_retrieval_schema(plugin_id)
        except Exception as e:
            self.ap.logger.warning(f"Failed to get retrieval schema for {plugin_id}: {e}")
            return {}
