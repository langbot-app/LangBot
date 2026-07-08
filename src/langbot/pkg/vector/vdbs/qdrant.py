from __future__ import annotations

from typing import Any, Dict, List

from qdrant_client import AsyncQdrantClient, models
from langbot.pkg.core import app
from langbot.pkg.vector.vdb import VectorDatabase
from langbot.pkg.vector.filter_utils import normalize_filter


def _build_qdrant_filter(filter_dict: dict[str, Any]) -> models.Filter:
    """Translate canonical filter dict into a Qdrant ``models.Filter``."""
    triples = normalize_filter(filter_dict)
    must: list[models.Condition] = []
    must_not: list[models.Condition] = []

    for field, op, value in triples:
        if op == '$eq':
            must.append(models.FieldCondition(key=field, match=models.MatchValue(value=value)))
        elif op == '$ne':
            must_not.append(models.FieldCondition(key=field, match=models.MatchValue(value=value)))
        elif op == '$in':
            must.append(models.FieldCondition(key=field, match=models.MatchAny(any=value)))
        elif op == '$nin':
            must_not.append(models.FieldCondition(key=field, match=models.MatchAny(any=value)))
        elif op in ('$gt', '$gte', '$lt', '$lte'):
            range_kwargs: dict[str, Any] = {}
            if op == '$gt':
                range_kwargs['gt'] = value
            elif op == '$gte':
                range_kwargs['gte'] = value
            elif op == '$lt':
                range_kwargs['lt'] = value
            elif op == '$lte':
                range_kwargs['lte'] = value
            must.append(models.FieldCondition(key=field, range=models.Range(**range_kwargs)))

    return models.Filter(must=must or None, must_not=must_not or None)


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
        documents: List[str] | None = None,
    ) -> None:
        if not embeddings_list:
            return

        await self._ensure_collection(collection, len(embeddings_list[0]))

        points = [
            models.PointStruct(id=ids[i], vector=embeddings_list[i], payload=metadatas[i]) for i in range(len(ids))
        ]
        await self.client.upsert(collection_name=collection, points=points)
        self.ap.logger.info(f"Added {len(ids)} embeddings to Qdrant collection '{collection}'.")

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        k: int = 5,
        search_type: str = 'vector',
        query_text: str = '',
        filter: dict[str, Any] | None = None,
        vector_weight: float | None = None,
    ) -> dict[str, Any]:
        exists = await self.client.collection_exists(collection)
        if not exists:
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}

        query_kwargs: dict[str, Any] = dict(
            collection_name=collection,
            query=query_embedding,
            limit=k,
            with_payload=True,
        )
        if filter:
            query_kwargs['query_filter'] = _build_qdrant_filter(filter)

        hits = (await self.client.query_points(**query_kwargs)).points
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

    async def delete_by_filter(self, collection: str, filter: dict[str, Any]) -> int:
        exists = await self.client.collection_exists(collection)
        if not exists:
            return 0

        qdrant_filter = _build_qdrant_filter(filter)
        await self.client.delete(
            collection_name=collection,
            points_selector=qdrant_filter,
        )
        self.ap.logger.info(f"Deleted embeddings from Qdrant collection '{collection}' by filter")
        return 0  # Qdrant delete does not return a count

    async def list_by_filter(
        self,
        collection: str,
        filter: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        exists = await self.client.collection_exists(collection)
        if not exists:
            return [], 0

        qdrant_filter = _build_qdrant_filter(filter) if filter else None

        # Qdrant scroll uses cursor-based pagination (offset = point ID),
        # not numeric skip.  To support numeric offset we scroll through
        # `offset + limit` items and discard the first `offset`.
        remaining_to_skip = offset
        remaining_to_collect = limit
        cursor: int | str | None = None
        collected: list[dict[str, Any]] = []

        while remaining_to_skip > 0 or remaining_to_collect > 0:
            batch_size = remaining_to_skip + remaining_to_collect if remaining_to_skip > 0 else remaining_to_collect
            scroll_kwargs: dict[str, Any] = dict(
                collection_name=collection,
                limit=min(batch_size, 256),
                with_payload=True if remaining_to_skip == 0 else False,
                with_vectors=False,
            )
            if qdrant_filter:
                scroll_kwargs['scroll_filter'] = qdrant_filter
            if cursor is not None:
                scroll_kwargs['offset'] = cursor

            points, next_cursor = await self.client.scroll(**scroll_kwargs)
            if not points:
                break

            for point in points:
                if remaining_to_skip > 0:
                    remaining_to_skip -= 1
                    continue
                if remaining_to_collect <= 0:
                    break
                # Re-fetch payload if we skipped it during the skip phase
                payload = point.payload or {}
                collected.append(
                    {
                        'id': str(point.id),
                        'document': payload.get('text') or payload.get('document'),
                        'metadata': payload,
                    }
                )
                remaining_to_collect -= 1

            if next_cursor is None:
                break
            cursor = next_cursor

        # If we skipped without payload, re-fetch the collected items' payloads
        # (only needed when offset > 0 and items were collected in a skip batch)
        if offset > 0 and collected:
            refetch_ids = [item['id'] for item in collected if not item.get('metadata')]
            if refetch_ids:
                fetched_points = await self.client.retrieve(
                    collection_name=collection,
                    ids=refetch_ids,
                    with_payload=True,
                    with_vectors=False,
                )
                payload_map = {str(p.id): p.payload or {} for p in fetched_points}
                for item in collected:
                    if item['id'] in payload_map:
                        payload = payload_map[item['id']]
                        item['metadata'] = payload
                        item['document'] = payload.get('text') or payload.get('document')

        # Use count() for accurate total (supports filter)
        total = -1
        try:
            count_result = await self.client.count(
                collection_name=collection,
                count_filter=qdrant_filter,
                exact=True,
            )
            total = count_result.count
        except Exception:
            pass

        return collected, total

    async def delete_collection(self, collection: str):
        try:
            await self.client.delete_collection(collection)
            self._collections.discard(collection)
            self.ap.logger.info(f"Qdrant collection '{collection}' deleted.")
        except Exception:
            self.ap.logger.warning(f"Qdrant collection '{collection}' not found.")
