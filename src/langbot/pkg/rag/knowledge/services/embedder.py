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

        # Determine which VDBs to write to based on global retrieval configuration
        # Only write to VDBs that are actually used by configured providers
        vdb_names_to_write = self._get_required_vdbs_from_config()

        if not vdb_names_to_write:
            # Fallback: if no config, write to default VDB only
            self.ap.logger.warning(
                'No provider config found in global config, using default VDB'
            )
            vdb_names_to_write = {'default'}

        # Write to required VDBs in parallel
        tasks = []
        for vdb_name in vdb_names_to_write:
            vdb_instance = self.ap.vector_db_mgr.get_db(vdb_name)
            if not vdb_instance:
                # Try fallback to default
                if vdb_name == 'default':
                    vdb_instance = self.ap.vector_db_mgr.vector_db

                if not vdb_instance:
                    self.ap.logger.error(f'VDB "{vdb_name}" not found, skipping')
                    continue

            self.ap.logger.debug(f'Storing embeddings to VDB: {vdb_name}')
            tasks.append(
                vdb_instance.add_embeddings(kb_id, chunk_ids, embeddings_list, chunk_dicts, chunks)
            )

        if tasks:
            import asyncio
            await asyncio.gather(*tasks)
            self.ap.logger.info(
                f'Successfully saved {len(chunk_entities)} chunks to {len(tasks)} VDB(s): {vdb_names_to_write}'
            )
        else:
            self.ap.logger.warning(f'No VDBs available to store embeddings for KB {kb_id}')

        return chunk_entities

    def _get_required_vdbs_from_config(self) -> set[str]:
        """
        Determine which VDBs need to be written to based on global retrieval config.

        Returns:
            Set of VDB names that need to receive embeddings
        """
        # Try to get retrieval config from global config
        # This assumes config structure like: config.retrieval.providers
        try:
            retrieval_config = self.ap.instance_config.data.get('retrieval', {})
            providers = retrieval_config.get('providers', [])

            if not providers:
                # No providers configured, use default VDB
                return {'default'}

            # Parse providers config to extract VDB names
            vdb_names = set()
            for provider_config in providers:
                vdb_name = provider_config.get('vdb', 'default')
                vdb_names.add(vdb_name)

            return vdb_names if vdb_names else {'default'}

        except Exception as e:
            self.ap.logger.warning(f'Failed to parse retrieval config: {e}')
            return {'default'}
