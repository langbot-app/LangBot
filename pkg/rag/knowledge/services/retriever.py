from __future__ import annotations

from . import base_service
from ....core import app
from ....provider.modelmgr.requester import RuntimeEmbeddingModel
from ....entity.rag import retriever as retriever_entities


class Retriever(base_service.BaseService):
    def __init__(self, ap: app.Application):
        super().__init__()
        self.ap = ap

    async def retrieve(
        self, kb_id: str, query: str, embedding_model: RuntimeEmbeddingModel, k: int = 5
    ) -> list[retriever_entities.RetrieveResultEntry]:
        self.ap.logger.info(
            f"Retrieving for query: '{query[:10]}' with k={k} using {embedding_model.model_entity.uuid}"
        )

        query_embedding: list[float] = await embedding_model.requester.invoke_embedding(
            model=embedding_model,
            input_text=[query],
            extra_args={},  # TODO: add extra args
        )

        chroma_results = await self.ap.vector_db_mgr.vector_db.search(kb_id, query_embedding[0], k)

        # 'ids' is always returned by ChromaDB, even if not explicitly in 'include'
        matched_chroma_ids = chroma_results.get('ids', [[]])[0]
        distances = chroma_results.get('distances', [[]])[0]
        chroma_metadatas = chroma_results.get('metadatas', [[]])[0]

        if not matched_chroma_ids:
            self.ap.logger.info('No relevant chunks found in Chroma.')
            return []

        result: list[retriever_entities.RetrieveResultEntry] = []

        for i, id in enumerate(matched_chroma_ids):
            entry = retriever_entities.RetrieveResultEntry(
                id=id,
                metadata=chroma_metadatas[i],
                distance=distances[i],
            )
            result.append(entry)

        return result
