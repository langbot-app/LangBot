from __future__ import annotations

import asyncio
from typing import Any, Dict, List


from langbot.pkg.core import app
from langbot.pkg.vector.vdb import VectorDatabase

try:
    import pyseekdb
    from pyseekdb import HNSWConfiguration

    SEEKDB_AVAILABLE = True
except ImportError:
    SEEKDB_AVAILABLE = False

SEEKDB_EMBEDDING_MODEL_UUID = 'seekdb-builtin-embedding'
SEEKDB_EMBEDDING_REQUESTER = 'seekdb-embedding'


class SeekDBVectorDatabase(VectorDatabase):
    """SeekDB vector database adapter for LangBot.

    SeekDB is an AI-native search database by OceanBase that unifies
    relational, vector, text, JSON and GIS in a single engine.

    Supports both embedded mode and remote server mode.
    """

    def __init__(self, ap: app.Application):
        if not SEEKDB_AVAILABLE:
            raise ImportError('pyseekdb is not installed. Install it with: pip install pyseekdb')

        self.ap = ap
        config = self.ap.instance_config.data['vdb']['seekdb']

        # Determine connection mode based on config
        mode = config.get('mode', 'embedded')  # 'embedded' or 'server'

        if mode == 'embedded':
            # Embedded mode: local database
            path = config.get('path', './data/seekdb')
            database = config.get('database', 'langbot')

            # Use AdminClient for database management operations
            admin_client = pyseekdb.AdminClient(path=path)
            # Check if database exists using public API
            existing_dbs = [db.name for db in admin_client.list_databases()]
            if database not in existing_dbs:
                # Use public API to create database
                admin_client.create_database(database)
                self.ap.logger.info(f"Created SeekDB database '{database}'")

            self.client = pyseekdb.Client(path=path, database=database)
            self.ap.logger.info(f"Initialized SeekDB in embedded mode at '{path}', database '{database}'")
        elif mode == 'server':
            # Server mode: remote SeekDB or OceanBase server
            host = config.get('host', 'localhost')
            port = config.get('port', 2881)
            database = config.get('database', 'langbot')
            user = config.get('user', 'root')
            password = config.get('password', '')
            tenant = config.get('tenant', None)  # Optional, for OceanBase

            connection_params = {
                'host': host,
                'port': int(port),
                'database': database,
                'user': user,
                'password': password,
            }

            if tenant:
                connection_params['tenant'] = tenant

            self.client = pyseekdb.Client(**connection_params)
            self.ap.logger.info(
                f"Initialized SeekDB in server mode: {host}:{port}, database '{database}'"
                + (f", tenant '{tenant}'" if tenant else '')
            )
        else:
            raise ValueError(f"Invalid SeekDB mode: {mode}. Must be 'embedded' or 'server'")

        self._collections: Dict[str, Any] = {}
        self._collection_configs: Dict[str, HNSWConfiguration] = {}

        self._escape_table = str.maketrans(
            {
                '\x00': '',
                '\\': '\\\\',
                '"': '\\"',
                '\n': '\\n',
                '\r': '\\r',
                '\t': '\\t',
            }
        )

    async def _get_or_create_collection_internal(self, collection: str, vector_size: int = None) -> Any:
        """Internal method to get or create a collection with proper configuration."""
        if collection in self._collections:
            return self._collections[collection]

        # Check if collection exists
        if await asyncio.to_thread(self.client.has_collection, collection):
            # Collection exists, get it
            coll = await asyncio.to_thread(self.client.get_collection, collection, embedding_function=None)
            self._collections[collection] = coll
            self.ap.logger.info(f"SeekDB collection '{collection}' retrieved.")
            return coll

        # Collection doesn't exist, create it
        if vector_size is None:
            # Default dimension if not specified
            vector_size = 384

        # Create HNSW configuration
        config = HNSWConfiguration(dimension=vector_size, distance='cosine')
        self._collection_configs[collection] = config

        # Create collection without embedding function (we manage embeddings externally)
        coll = await asyncio.to_thread(
            self.client.create_collection,
            name=collection,
            configuration=config,
            embedding_function=None,  # Disable automatic embedding
        )

        self._collections[collection] = coll
        self.ap.logger.info(f"SeekDB collection '{collection}' created with dimension={vector_size}, distance='cosine'")
        return coll

    def _clean_metadata(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """SeekDB metadata doesn't support \\ and ", insert will error 3104"""
        return {
            k: v.translate(self._escape_table)
            if isinstance(v, str)
            else v
            if v is None or isinstance(v, (int, float, bool))
            else str(v)
            for k, v in meta.items()
            if v is not None
        }

    async def get_or_create_collection(self, collection: str):
        """Get or create collection (without vector size - will use default)."""
        return await self._get_or_create_collection_internal(collection)

    async def add_embeddings(
        self, collection: str, ids: List[str], embeddings_list: List[List[float]], metadatas: List[Dict[str, Any]]
    ) -> None:
        """Add vector embeddings to the specified collection.

        Args:
            collection: Collection name
            ids: List of document IDs
            embeddings_list: List of embedding vectors
            metadatas: List of metadata dictionaries
        """
        if not embeddings_list:
            return

        # Ensure collection exists with correct dimension
        vector_size = len(embeddings_list[0])
        coll = await self._get_or_create_collection_internal(collection, vector_size)

        cleaned_metadatas = [self._clean_metadata(meta) for meta in metadatas]

        await asyncio.to_thread(coll.add, ids=ids, embeddings=embeddings_list, metadatas=cleaned_metadatas)

        self.ap.logger.info(f"Added {len(ids)} embeddings to SeekDB collection '{collection}'")

    async def search(self, collection: str, query_embedding: List[float], k: int = 5) -> Dict[str, Any]:
        """Search for the most similar vectors in the specified collection.

        Args:
            collection: Collection name
            query_embedding: Query vector
            k: Number of results to return

        Returns:
            Dictionary with 'ids', 'metadatas', 'distances' keys
        """
        # Check if collection exists
        exists = await asyncio.to_thread(self.client.has_collection, collection)
        if not exists:
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}

        # Get collection
        if collection not in self._collections:
            coll = await asyncio.to_thread(self.client.get_collection, collection, embedding_function=None)
            self._collections[collection] = coll
        else:
            coll = self._collections[collection]

        # Perform query
        # SeekDB's query() returns: {'ids': [[...]], 'metadatas': [[...]], 'distances': [[...]]}
        results = await asyncio.to_thread(coll.query, query_embeddings=query_embedding, n_results=k)

        self.ap.logger.info(f"SeekDB search in '{collection}' returned {len(results.get('ids', [[]])[0])} results")

        return results

    async def delete_by_file_id(self, collection: str, file_id: str) -> None:
        """Delete vectors from the collection by file_id metadata.

        Args:
            collection: Collection name
            file_id: File ID to delete
        """
        # Check if collection exists
        exists = await asyncio.to_thread(self.client.has_collection, collection)
        if not exists:
            self.ap.logger.warning(f"SeekDB collection '{collection}' not found for deletion")
            return

        # Get collection
        if collection not in self._collections:
            coll = await asyncio.to_thread(self.client.get_collection, collection, embedding_function=None)
            self._collections[collection] = coll
        else:
            coll = self._collections[collection]

        # SeekDB's delete() expects a where clause for filtering
        # Delete all records where metadata['file_id'] == file_id
        await asyncio.to_thread(coll.delete, where={'file_id': file_id})

        self.ap.logger.info(f"Deleted embeddings from SeekDB collection '{collection}' with file_id: {file_id}")

    async def delete_collection(self, collection: str):
        """Delete the entire collection.

        Args:
            collection: Collection name
        """
        # Remove from cache
        if collection in self._collections:
            del self._collections[collection]
        if collection in self._collection_configs:
            del self._collection_configs[collection]

        # Check if collection exists
        exists = await asyncio.to_thread(self.client.has_collection, collection)
        if not exists:
            self.ap.logger.warning(f"SeekDB collection '{collection}' not found for deletion")
            return

        # Delete collection
        await asyncio.to_thread(self.client.delete_collection, collection)
        self.ap.logger.info(f"SeekDB collection '{collection}' deleted")
