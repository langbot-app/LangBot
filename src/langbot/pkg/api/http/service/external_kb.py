from __future__ import annotations

from ....core import app
import sqlalchemy
from langbot.pkg.entity.persistence import rag as persistence_rag
import uuid


class ExternalKBService:
    """External KB service"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    # External Knowledge Base methods
    async def get_external_knowledge_bases(self) -> list[dict]:
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_rag.ExternalKnowledgeBase))
        external_kbs = result.all()
        return [
            self.ap.persistence_mgr.serialize_model(persistence_rag.ExternalKnowledgeBase, external_kb)
            for external_kb in external_kbs
        ]

    async def get_external_knowledge_base(self, kb_uuid: str) -> dict | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.ExternalKnowledgeBase).where(
                persistence_rag.ExternalKnowledgeBase.uuid == kb_uuid
            )
        )
        external_kb = result.first()
        if external_kb is None:
            return None
        return self.ap.persistence_mgr.serialize_model(persistence_rag.ExternalKnowledgeBase, external_kb)

    async def create_external_knowledge_base(self, kb_data: dict) -> str:
        kb_data['uuid'] = str(uuid.uuid4())
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_rag.ExternalKnowledgeBase).values(kb_data)
        )

        kb = await self.get_external_knowledge_base(kb_data['uuid'])

        await self.ap.rag_mgr.load_external_knowledge_base(kb)

        return kb_data['uuid']

    async def retrieve_external_knowledge_base(self, kb_uuid: str, query: str) -> list[dict]:
        """Retrieve external knowledge base"""
        runtime_kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
        if runtime_kb is None:
            raise Exception('Knowledge base not found')
        return [
            result.model_dump() for result in await runtime_kb.retrieve(query, 5)
        ]  # top_k is just a placeholder for external knowledge base

    async def update_external_knowledge_base(self, kb_uuid: str, kb_data: dict) -> None:
        if 'uuid' in kb_data:
            del kb_data['uuid']

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_rag.ExternalKnowledgeBase)
            .values(kb_data)
            .where(persistence_rag.ExternalKnowledgeBase.uuid == kb_uuid)
        )
        await self.ap.rag_mgr.remove_knowledge_base_from_runtime(kb_uuid)

        kb = await self.get_external_knowledge_base(kb_uuid)

        await self.ap.rag_mgr.load_external_knowledge_base(kb)

    async def delete_external_knowledge_base(self, kb_uuid: str) -> None:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_rag.ExternalKnowledgeBase).where(
                persistence_rag.ExternalKnowledgeBase.uuid == kb_uuid
            )
        )

        await self.ap.rag_mgr.delete_knowledge_base(kb_uuid)
