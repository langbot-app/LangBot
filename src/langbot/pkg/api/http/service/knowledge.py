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

    async def get_knowledge_bases(self) -> list[dict]:
        """获取所有知识库"""
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_rag.KnowledgeBase))
        knowledge_bases = result.all()
        return [
            self.ap.persistence_mgr.serialize_model(persistence_rag.KnowledgeBase, knowledge_base)
            for knowledge_base in knowledge_bases
        ]

    async def get_knowledge_base(self, kb_uuid: str) -> dict | None:
        """获取知识库"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.KnowledgeBase).where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )
        knowledge_base = result.first()
        if knowledge_base is None:
            return None
        return self.ap.persistence_mgr.serialize_model(persistence_rag.KnowledgeBase, knowledge_base)

    async def create_knowledge_base(self, kb_data: dict) -> str:
        """创建知识库"""
        kb_data['uuid'] = str(uuid.uuid4())
        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_rag.KnowledgeBase).values(kb_data))

        kb = await self.get_knowledge_base(kb_data['uuid'])

        await self.ap.rag_mgr.load_knowledge_base(kb)

        return kb_data['uuid']

    async def update_knowledge_base(self, kb_uuid: str, kb_data: dict) -> None:
        """更新知识库"""
        if 'uuid' in kb_data:
            del kb_data['uuid']

        if 'embedding_model_uuid' in kb_data:
            del kb_data['embedding_model_uuid']

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_rag.KnowledgeBase)
            .values(kb_data)
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
        return await runtime_kb.store_file(file_id)

    async def retrieve_knowledge_base(self, kb_uuid: str, query: str) -> list[dict]:
        """检索知识库"""
        runtime_kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
        if runtime_kb is None:
            raise Exception('Knowledge base not found')
        return [
            result.model_dump() for result in await runtime_kb.retrieve(query, runtime_kb.knowledge_base_entity.top_k)
        ]

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
        await runtime_kb.delete_file(file_id)

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
