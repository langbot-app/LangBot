from __future__ import annotations
import uuid
from typing import List
from langbot.pkg.rag.knowledge.services.base_service import BaseService
from langbot.pkg.entity.persistence import rag as persistence_rag
from langbot.pkg.core import app
from langbot.pkg.provider.modelmgr.requester import RuntimeEmbeddingModel
import sqlalchemy


class Embedder(BaseService):
    def __init__(self, ap: app.Application) -> None:
        super().__init__()
        self.ap = ap

    async def embed_and_store(
        self, kb_id: str, file_id: str, chunks: List[str], embedding_model: RuntimeEmbeddingModel
    ) -> list[persistence_rag.Chunk]:
        # save chunk to db
        chunk_entities: list[persistence_rag.Chunk] = []
        chunk_ids: list[str] = []

        for chunk_text in chunks:
            chunk_uuid = str(uuid.uuid4())
            chunk_ids.append(chunk_uuid)
            chunk_entity = persistence_rag.Chunk(uuid=chunk_uuid, file_id=file_id, text=chunk_text)
            chunk_entities.append(chunk_entity)

        chunk_dicts = [
            self.ap.persistence_mgr.serialize_model(persistence_rag.Chunk, chunk) for chunk in chunk_entities
        ]

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_rag.Chunk).values(chunk_dicts))

        # get embeddings
        embeddings_list: list[list[float]] = await embedding_model.requester.invoke_embedding(
            model=embedding_model,
            input_text=chunks,
            extra_args={},  # TODO: add extra args
        )

        # Write to all instantiated VDBs in parallel
        # Since VDB manager already knows which VDBs are configured and instantiated,
        # we simply write to all available VDBs
        tasks = []
        for vdb_name, vdb_instance in self.ap.vector_db_mgr.databases.items():
            self.ap.logger.debug(f'Storing embeddings and documents to VDB: {vdb_name}')
            tasks.append(
                vdb_instance.add_embeddings(kb_id, chunk_ids, embeddings_list, chunk_dicts, chunks)
            )

        if tasks:
            import asyncio
            await asyncio.gather(*tasks)
            self.ap.logger.info(
                f'Successfully saved {len(chunk_entities)} chunks to {len(tasks)}'
            )
        else:
            self.ap.logger.warning(f'No VDBs available to store embeddings for KB {kb_id}')

        return chunk_entities

