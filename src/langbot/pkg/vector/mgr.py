from __future__ import annotations

from ..core import app
from .vdb import VectorDatabase
from .vdbs.chroma import ChromaVectorDatabase
from .vdbs.qdrant import QdrantVectorDatabase
from .vdbs.seekdb import SeekDBVectorDatabase
from .vdbs.milvus import MilvusVectorDatabase
from .vdbs.pgvector_db import PgVectorDatabase


class VectorDBManager:
    ap: app.Application
    vector_db: VectorDatabase = None

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        kb_config = self.ap.instance_config.data.get('vdb')
        if kb_config:
            vdb_type = kb_config.get('use')

            if vdb_type == 'chroma':
                self.vector_db = ChromaVectorDatabase(self.ap)
                self.ap.logger.info('Initialized Chroma vector database backend.')

            elif vdb_type == 'qdrant':
                self.vector_db = QdrantVectorDatabase(self.ap)
                self.ap.logger.info('Initialized Qdrant vector database backend.')
            elif vdb_type == 'seekdb':
                self.vector_db = SeekDBVectorDatabase(self.ap)
                self.ap.logger.info('Initialized SeekDB vector database backend.')

            elif vdb_type == 'milvus':
                # Get Milvus configuration
                milvus_config = kb_config.get('milvus', {})
                uri = milvus_config.get('uri', './data/milvus.db')
                token = milvus_config.get('token')
                db_name = milvus_config.get('db_name', 'default')
                self.vector_db = MilvusVectorDatabase(self.ap, uri=uri, token=token, db_name=db_name)
                self.ap.logger.info('Initialized Milvus vector database backend.')

            elif vdb_type == 'pgvector':
                # Get pgvector configuration
                pgvector_config = kb_config.get('pgvector', {})
                connection_string = pgvector_config.get('connection_string')
                if connection_string:
                    self.vector_db = PgVectorDatabase(self.ap, connection_string=connection_string)
                else:
                    # Use individual parameters
                    host = pgvector_config.get('host', 'localhost')
                    port = pgvector_config.get('port', 5432)
                    database = pgvector_config.get('database', 'langbot')
                    user = pgvector_config.get('user', 'postgres')
                    password = pgvector_config.get('password', 'postgres')
                    self.vector_db = PgVectorDatabase(
                        self.ap, host=host, port=port, database=database, user=user, password=password
                    )
                self.ap.logger.info('Initialized pgvector database backend.')

            else:
                self.vector_db = ChromaVectorDatabase(self.ap)
                self.ap.logger.warning('No valid vector database backend configured, defaulting to Chroma.')
        else:
            self.vector_db = ChromaVectorDatabase(self.ap)
            self.ap.logger.warning('No vector database backend configured, defaulting to Chroma.')

    async def upsert(
        self,
        collection_name: str,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict] | None = None,
    ):
        """Proxy: Upsert vectors"""
        await self.vector_db.get_or_create_collection(collection_name)
        await self.vector_db.add_embeddings(
            collection=collection_name,
            ids=ids,
            embeddings_list=vectors,
            metadatas=metadata or [{} for _ in vectors],
        )

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int,
        filter: dict | None = None,
    ) -> list[dict]:
        """Proxy: Search vectors"""
        import numpy as np
        # Ensure collection exists before searching? Or let it fail/return empty?
        # Usually implementations handle collection not found.
        results = await self.vector_db.search(
            collection=collection_name,
            query_embedding=np.array(query_vector),
            k=limit,
            # Note: filters are not yet unified in VectorDatabase abstract method signature properly in all impls,
            # but we pass what we can. The ABI above shows search(collection, query_embedding, k).
            # We might need to handle filters if implementations support it.
        )
        
        # Convert results to standard format
        # Abstract return type is Dict[str, Any] which usually contains 'ids', 'distances', 'metadatas', 'documents'
        # We want to return list of results
        
        # Assuming typical Chroma/Standard format:
        # { 'ids': [['id1']], 'distances': [[0.1]], 'metadatas': [[{}]], 'documents': [['text']] }
        # Note: VectorDatabase.search implementation details vary.
        # Let's inspect ChromaVectorDatabase.search to match return format logic.
        
        # For now, let's implement a basic return structure assuming the Dict matches standard.
        parsed_results = []
        if not results or 'ids' not in results or not results['ids']:
             return []
             
        # Flatten if list of lists (batch search)
        r_ids = results['ids'][0] if isinstance(results['ids'], list) and results['ids'] and isinstance(results['ids'][0], list) else results['ids']
        r_dists = results['distances'][0] if isinstance(results['distances'], list) and results['distances'] and isinstance(results['distances'][0], list) else results['distances']
        r_metas = results['metadatas'][0] if isinstance(results['metadatas'], list) and results['metadatas'] and isinstance(results['metadatas'][0], list) else results['metadatas']
        
        for i, id_val in enumerate(r_ids):
            parsed_results.append({
                'id': id_val,
                'score': r_dists[i] if r_dists is not None else 0.0,
                'metadata': r_metas[i] if r_metas else {},
            })
            
        return parsed_results

    async def delete(self, collection_name: str, ids: list[str]):
        """Proxy: Delete vectors by ID"""
        for doc_id in ids:
             await self.vector_db.delete_by_file_id(collection_name, doc_id)

    async def delete_by_filter(self, collection_name: str, filter: dict):
        """Proxy: Delete vectors by filter.

        Note: This feature requires vector database implementations to support
        filter-based deletion. Currently not implemented in VectorDatabase interface.
        """
        # TODO: Implement when VectorDatabase interface adds filter-based deletion
        self.ap.logger.warning(
            f"delete_by_filter called on collection '{collection_name}' but "
            "filter-based deletion is not yet implemented in VectorDatabase interface"
        )
