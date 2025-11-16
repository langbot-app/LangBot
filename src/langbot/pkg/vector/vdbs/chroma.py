from __future__ import annotations
import asyncio
from typing import Any
from chromadb import PersistentClient
from langbot.pkg.vector.vdb import VectorDatabase
from langbot.pkg.core import app
import chromadb
import chromadb.errors


class ChromaVectorDatabase(VectorDatabase):
    def __init__(self, ap: app.Application, base_path: str = './data/chroma'):
        self.ap = ap
        self.client = PersistentClient(path=base_path)
        self._collections = {}

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
    ) -> None:
        col = await self.get_or_create_collection(collection)
        await asyncio.to_thread(col.add, embeddings=embeddings_list, ids=ids, metadatas=metadatas)
        self.ap.logger.info(f"Added {len(ids)} embeddings to Chroma collection '{collection}'.")

    async def search(self, collection: str, query_embedding: list[float], k: int = 5) -> dict[str, Any]:
        col = await self.get_or_create_collection(collection)
        results = await asyncio.to_thread(
            col.query,
            query_embeddings=query_embedding,
            n_results=k,
            include=['metadatas', 'distances', 'documents'],
        )
        self.ap.logger.info(f"Chroma search in '{collection}' returned {len(results.get('ids', [[]])[0])} results.")
        return results

    async def delete_by_file_id(self, collection: str, file_id: str) -> None:
        col = await self.get_or_create_collection(collection)
        await asyncio.to_thread(col.delete, where={'file_id': file_id})
        self.ap.logger.info(f"Deleted embeddings from Chroma collection '{collection}' with file_id: {file_id}")

    async def delete_collection(self, collection: str):
        if collection in self._collections:
            del self._collections[collection]

        try:
            await asyncio.to_thread(self.client.delete_collection, name=collection)
        except chromadb.errors.NotFoundError:
            self.ap.logger.warning(f"Chroma collection '{collection}' not found.")
            return
        self.ap.logger.info(f"Chroma collection '{collection}' deleted.")
