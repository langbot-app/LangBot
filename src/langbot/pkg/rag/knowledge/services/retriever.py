from __future__ import annotations

from . import base_service
from ....core import app
from ....provider.modelmgr.requester import RuntimeEmbeddingModel
from langbot_plugin.api.entities.builtin.rag import context as rag_context
from langbot_plugin.api.entities.builtin.provider.message import ContentElement


class Retriever(base_service.BaseService):
    def __init__(self, ap: app.Application):
        super().__init__()
        self.ap = ap

    async def retrieve(
        self, kb_id: str, query: str, embedding_model: RuntimeEmbeddingModel, k: int = 5
    ) -> list[rag_context.RetrievalResultEntry]:
        self.ap.logger.info(
            f"Retrieving for query: '{query[:10]}' with k={k} using {embedding_model.model_entity.uuid}"
        )

        query_embedding: list[float] = await embedding_model.provider.invoke_embedding(
            model=embedding_model,
            input_text=[query],
            extra_args={},  # TODO: add extra args
            knowledge_base_id=kb_id,
            query_text=query,
            call_type='retrieve',
        )

        vector_results = await self.ap.vector_db_mgr.vector_db.search(kb_id, query_embedding[0], k)

        # 'ids' shape mirrors the Chroma-style response contract for compatibility
        matched_vector_ids = vector_results.get('ids', [[]])[0]
        distances = vector_results.get('distances', [[]])[0]
        vector_metadatas = vector_results.get('metadatas', [[]])[0]

        if not matched_vector_ids:
            self.ap.logger.info('No relevant chunks found in vector database.')
            return []

        result: list[rag_context.RetrievalResultEntry] = []

        for i, id in enumerate(matched_vector_ids):
            entry = rag_context.RetrievalResultEntry(
                id=id,
                content=[ContentElement.from_text(vector_metadatas[i].get('text', ''))],
                metadata=vector_metadatas[i],
                distance=distances[i],
            )
            result.append(entry)

        return result
