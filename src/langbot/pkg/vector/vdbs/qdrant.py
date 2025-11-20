from __future__ import annotations

from typing import Any, Dict, List

from qdrant_client import AsyncQdrantClient, models
from langbot.pkg.core import app
from langbot.pkg.vector.vdb import VectorDatabase


class QdrantVectorDatabase(VectorDatabase):
    def __init__(self, ap: app.Application):
        self.ap = ap
        url = self.ap.instance_config.data['vdb']['qdrant']['url']
        host = self.ap.instance_config.data['vdb']['qdrant']['host']
        port = self.ap.instance_config.data['vdb']['qdrant']['port']
        api_key = self.ap.instance_config.data['vdb']['qdrant']['api_key']

        if url:
            self.client = AsyncQdrantClient(url=url, api_key=api_key)
        else:
            self.client = AsyncQdrantClient(host=host, port=int(port), api_key=api_key)

        self._collections: set[str] = set()

    async def _ensure_collection(self, collection: str, vector_size: int) -> None:
        if collection in self._collections:
            return

        exists = await self.client.collection_exists(collection)
        if exists:
            self._collections.add(collection)
            return

        await self.client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )
        self._collections.add(collection)
        self.ap.logger.info(f"Qdrant collection '{collection}' created with dim={vector_size}.")

    async def get_or_create_collection(self, collection: str):
        # Qdrant requires vector size to create a collection; no-op here.
        pass

    async def add_embeddings(
        self,
        collection: str,
        ids: List[str],
        embeddings_list: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        if not embeddings_list:
            return

        await self._ensure_collection(collection, len(embeddings_list[0]))

        points = [
            models.PointStruct(id=ids[i], vector=embeddings_list[i], payload=metadatas[i]) for i in range(len(ids))
        ]
        await self.client.upsert(collection_name=collection, points=points)
        self.ap.logger.info(f"Added {len(ids)} embeddings to Qdrant collection '{collection}'.")

    async def search(self, collection: str, query_embedding: list[float], k: int = 5) -> dict[str, Any]:
        exists = await self.client.collection_exists(collection)
        if not exists:
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}

        hits = (
            await self.client.query_points(
                collection_name=collection,
                query=query_embedding,
                limit=k,
                with_payload=True,
            )
        ).points
        ids = [str(hit.id) for hit in hits]
        metadatas = [hit.payload or {} for hit in hits]
        # Qdrant's score is similarity; convert to a pseudo-distance for consistency
        distances = [1 - float(hit.score) if hit.score is not None else 1.0 for hit in hits]
        results = {'ids': [ids], 'metadatas': [metadatas], 'distances': [distances]}

        self.ap.logger.info(f"Qdrant search in '{collection}' returned {len(results.get('ids', [[]])[0])} results.")
        return results

    async def delete_by_file_id(self, collection: str, file_id: str) -> None:
        exists = await self.client.collection_exists(collection)
        if not exists:
            return

        await self.client.delete(
            collection_name=collection,
            points_selector=models.Filter(
                must=[models.FieldCondition(key='file_id', match=models.MatchValue(value=file_id))]
            ),
        )
        self.ap.logger.info(f"Deleted embeddings from Qdrant collection '{collection}' with file_id: {file_id}")

    async def delete_collection(self, collection: str):
        try:
            await self.client.delete_collection(collection)
            self._collections.discard(collection)
            self.ap.logger.info(f"Qdrant collection '{collection}' deleted.")
        except Exception:
            self.ap.logger.warning(f"Qdrant collection '{collection}' not found.")
