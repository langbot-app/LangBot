from __future__ import annotations
import asyncio
from typing import Any
from chromadb import PersistentClient
from langbot.pkg.vector.vdb import VectorDatabase, SearchType
from langbot.pkg.core import app
import chromadb
import chromadb.errors

# RRF smoothing constant (standard value from the literature)
_RRF_K = 60


class ChromaVectorDatabase(VectorDatabase):
    def __init__(self, ap: app.Application, base_path: str = './data/chroma'):
        self.ap = ap
        self.client = PersistentClient(path=base_path)
        self._collections = {}

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.VECTOR, SearchType.FULL_TEXT, SearchType.HYBRID]

    async def get_or_create_collection(self, collection: str) -> chromadb.Collection:
        if collection not in self._collections:
            self._collections[collection] = await asyncio.to_thread(
                self.client.get_or_create_collection, name=collection
            )
            self.ap.logger.info(f"Chroma collection '{collection}' accessed/created.")
        return self._collections[collection]

    async def add_embeddings(
        self,
        collection: str,
        ids: list[str],
        embeddings_list: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str] | None = None,
    ) -> None:
        col = await self.get_or_create_collection(collection)
        kwargs: dict[str, Any] = dict(embeddings=embeddings_list, ids=ids, metadatas=metadatas)
        if documents is not None:
            kwargs['documents'] = documents
        await asyncio.to_thread(col.upsert, **kwargs)
        self.ap.logger.info(f"Upserted {len(ids)} embeddings to Chroma collection '{collection}'.")

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
        col = await self.get_or_create_collection(collection)

        if search_type == SearchType.FULL_TEXT:
            return await self._full_text_search(col, collection, k, query_text, filter)
        elif search_type == SearchType.HYBRID:
            return await self._hybrid_search(
                col, collection, query_embedding, k, query_text, filter, vector_weight=vector_weight
            )

        # Default: vector search
        return await self._vector_search(col, collection, query_embedding, k, filter)

    async def _vector_search(
        self,
        col: chromadb.Collection,
        collection: str,
        query_embedding: list[float],
        k: int,
        filter: dict[str, Any] | None,
    ) -> dict[str, Any]:
        query_kwargs: dict[str, Any] = dict(
            query_embeddings=query_embedding,
            n_results=k,
            include=['metadatas', 'distances', 'documents'],
        )
        if filter:
            query_kwargs['where'] = filter
        results = await asyncio.to_thread(col.query, **query_kwargs)
        self.ap.logger.info(
            f"Chroma vector search in '{collection}' returned {len(results.get('ids', [[]])[0])} results."
        )
        return results

    async def _full_text_search(
        self,
        col: chromadb.Collection,
        collection: str,
        k: int,
        query_text: str,
        filter: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not query_text:
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]], 'documents': [[]]}

        get_kwargs: dict[str, Any] = dict(
            where_document={'$contains': query_text},
            include=['metadatas', 'documents'],
            limit=k,
        )
        if filter:
            get_kwargs['where'] = filter
        results = await asyncio.to_thread(col.get, **get_kwargs)

        # col.get returns flat lists; wrap into column-major format.
        # Distances are all 0.0 because Chroma's local $contains is a boolean
        # filter with no relevance scoring.  Chroma's BM25 sparse embedding
        # function (ChromaBm25EmbeddingFunction) can generate scored sparse
        # vectors, but sparse vector *indexing* is only available on Chroma
        # Cloud, not locally.  For ranked results, use hybrid mode or apply a
        # reranker in a downstream stage.
        ids = results.get('ids', [])
        metadatas = results.get('metadatas', []) or [None] * len(ids)
        documents = results.get('documents', []) or [None] * len(ids)
        distances = [0.0] * len(ids)

        self.ap.logger.info(f"Chroma full-text search in '{collection}' returned {len(ids)} results.")
        return {'ids': [ids], 'metadatas': [metadatas], 'distances': [distances], 'documents': [documents]}

    async def _hybrid_search(
        self,
        col: chromadb.Collection,
        collection: str,
        query_embedding: list[float],
        k: int,
        query_text: str,
        filter: dict[str, Any] | None,
        vector_weight: float | None = None,
    ) -> dict[str, Any]:
        # Fall back to pure vector search when no text is provided
        if not query_text:
            return await self._vector_search(col, collection, query_embedding, k, filter)

        # Run vector search and full-text search in parallel
        vector_task = self._vector_search(col, collection, query_embedding, k, filter)
        text_task = self._full_text_search(col, collection, k, query_text, filter)
        vector_results, text_results = await asyncio.gather(vector_task, text_task)

        vector_ids = vector_results.get('ids', [[]])[0]
        text_ids = text_results.get('ids', [[]])[0]

        if not vector_ids and not text_ids:
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]], 'documents': [[]]}

        # RRF fusion
        weights = None
        if vector_weight is not None:
            weights = [vector_weight, 1.0 - vector_weight]
        self.ap.logger.info(
            f"Chroma hybrid fusion config in '{collection}': "
            f'vector_weight={vector_weight}, weights={weights or [1.0, 1.0]}, '
            f'vector_hits={len(vector_ids)}, text_hits={len(text_ids)}'
        )
        fused = self._rrf_fuse([vector_ids, text_ids], k, weights=weights)
        if not fused:
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]], 'documents': [[]]}

        fused_ids = [doc_id for doc_id, _ in fused]

        # Fetch full metadata and documents for fused results
        fetched = await asyncio.to_thread(col.get, ids=fused_ids, include=['metadatas', 'documents'])

        # col.get returns results in arbitrary order; re-order to match fused ranking
        fetched_map: dict[str, tuple] = {}
        for i, fid in enumerate(fetched.get('ids', [])):
            meta = (fetched.get('metadatas') or [None] * len(fetched['ids']))[i]
            doc = (fetched.get('documents') or [None] * len(fetched['ids']))[i]
            fetched_map[fid] = (meta, doc)

        ordered_ids = []
        ordered_metas = []
        ordered_docs = []
        ordered_dists = []

        # Normalize RRF scores to 0~1 distances via min-max scaling.
        # Raw RRF scores are tiny (e.g. 0.016~0.033 with k=60) so a naive
        # ``1 - score`` would compress all distances into a narrow 0.96~0.98
        # band with almost no discriminative power.  Min-max normalization
        # spreads them across the full 0~1 range (0.0 = best match).
        max_score = fused[0][1]
        min_score = fused[-1][1]
        score_range = max_score - min_score

        for doc_id, score in fused:
            if doc_id in fetched_map:
                meta, doc = fetched_map[doc_id]
                ordered_ids.append(doc_id)
                ordered_metas.append(meta)
                ordered_docs.append(doc)
                if score_range > 0:
                    ordered_dists.append(1.0 - (score - min_score) / score_range)
                else:
                    ordered_dists.append(0.0)

        self.ap.logger.info(
            f"Chroma hybrid search in '{collection}' returned {len(ordered_ids)} results "
            f'(vector={len(vector_ids)}, text={len(text_ids)}).'
        )
        return {
            'ids': [ordered_ids],
            'metadatas': [ordered_metas],
            'distances': [ordered_dists],
            'documents': [ordered_docs],
        }

    @staticmethod
    def _rrf_fuse(result_lists: list[list[str]], k: int, weights: list[float] | None = None) -> list[tuple[str, float]]:
        """Reciprocal Rank Fusion over multiple ranked ID lists.

        Returns a list of (doc_id, rrf_score) sorted by descending score,
        truncated to *k* entries.

        Args:
            result_lists: Ranked ID lists from different search methods.
            k: Number of results to return.
            weights: Per-list weights.  ``None`` means equal weight (1.0 each).
        """
        if weights is None:
            weights = [1.0] * len(result_lists)
        scores: dict[str, float] = {}
        for list_idx, ranked_ids in enumerate(result_lists):
            w = weights[list_idx]
            for rank, doc_id in enumerate(ranked_ids):
                scores[doc_id] = scores.get(doc_id, 0.0) + w / (_RRF_K + rank + 1)
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results[:k]

    async def delete_by_file_id(self, collection: str, file_id: str) -> None:
        col = await self.get_or_create_collection(collection)
        await asyncio.to_thread(col.delete, where={'file_id': file_id})
        self.ap.logger.info(f"Deleted embeddings from Chroma collection '{collection}' with file_id: {file_id}")

    async def delete_by_filter(self, collection: str, filter: dict[str, Any]) -> int:
        col = await self.get_or_create_collection(collection)
        await asyncio.to_thread(col.delete, where=filter)
        self.ap.logger.info(f"Deleted embeddings from Chroma collection '{collection}' by filter")
        return 0  # Chroma delete does not return a count

    async def list_by_filter(
        self,
        collection: str,
        filter: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        col = await self.get_or_create_collection(collection)
        get_kwargs: dict[str, Any] = dict(
            include=['metadatas', 'documents'],
            limit=limit,
            offset=offset,
        )
        if filter:
            get_kwargs['where'] = filter
        results = await asyncio.to_thread(col.get, **get_kwargs)

        ids = results.get('ids', [])
        metadatas = results.get('metadatas', []) or [None] * len(ids)
        documents = results.get('documents', []) or [None] * len(ids)

        items = []
        for i, vid in enumerate(ids):
            items.append(
                {
                    'id': vid,
                    'document': documents[i] if i < len(documents) else None,
                    'metadata': metadatas[i] if i < len(metadatas) else {},
                }
            )

        # Chroma col.count() gives total in collection; filtered count not available
        total = await asyncio.to_thread(col.count) if not filter else -1
        return items, total

    async def delete_collection(self, collection: str):
        if collection in self._collections:
            del self._collections[collection]

        try:
            await asyncio.to_thread(self.client.delete_collection, name=collection)
        except chromadb.errors.NotFoundError:
            self.ap.logger.warning(f"Chroma collection '{collection}' not found.")
            return
        self.ap.logger.info(f"Chroma collection '{collection}' deleted.")
