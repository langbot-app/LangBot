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


class SeekDBVectorDatabase(VectorDatabase):
    """SeekDB vector database adapter for LangBot.

    SeekDB is an AI-native search database by OceanBase that unifies
    relational, vector, text, JSON and GIS in a single engine.

    Supports both embedded mode and remote server mode.
    """

    def __init__(self, ap: app.Application, config_override: dict = None):
        """SeekDB Vector Database Adapter.

        Args:
            ap: Application instance
            config_override: Optional configuration dictionary
        """
        if not SEEKDB_AVAILABLE:
            raise ImportError('pyseekdb is not installed. Install it with: pip install pyseekdb')

        self.ap = ap
        # Use config_override if provided (from multi-instance manager), else fallback to default config path
        if config_override:
            config = config_override
        else:
            config = self.ap.instance_config.data['vdb']['seekdb']

        
        # Determine connection mode based on config
        mode = config.get('mode', 'embedded')  # 'embedded' or 'server'

        if mode == 'embedded':
            # Embedded mode: local database
            path = config.get('path', './data/seekdb')
            database = config.get('database', 'langbot')

            self.ap.logger.info(f"Initializing SeekDB embedded mode at '{path}', database '{database}'...")

            # Use AdminClient for database management operations
            try:
                self.ap.logger.debug(f"Creating AdminClient for path: {path}")
                admin_client = pyseekdb.AdminClient(path=path)

                # Check if database exists using public API
                existing_dbs = [db.name for db in admin_client.list_databases()]

                if database not in existing_dbs:
                    self.ap.logger.info(f"Database '{database}' not found, creating...")
                    # Use public API to create database
                    admin_client.create_database(database)
                    self.ap.logger.info(f"Created SeekDB database '{database}'")
            except Exception as e:
                self.ap.logger.error(f"Failed to initialize SeekDB AdminClient or list databases: {e}")
                self.ap.logger.warning(
                    f"If SeekDB data is corrupted, try deleting the directory: {path}"
                )
                raise

            try:
                self.client = pyseekdb.Client(path=path, database=database)
                self.ap.logger.info(f"Successfully initialized SeekDB in embedded mode at '{path}', database '{database}'")
            except Exception as e:
                self.ap.logger.error(f"Failed to connect to SeekDB database '{database}': {e}")
                self.ap.logger.warning(
                    f"If SeekDB data is corrupted, try deleting the directory: {path}"
                )
                raise
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
        # Mapping from original collection names to safe SQL identifiers
        self._collection_name_map: Dict[str, str] = {}

        # Escape table for metadata (stored as JSON in SeekDB)
        # We need to be careful not to break JSON format
        # Based on error 3104, SeekDB has issues with backslash and some special chars in metadata
        self._metadata_escape_table = str.maketrans({
            '\x00': '',       # Remove null bytes (invalid in JSON)
            '\\': '',         # Remove backslash (causes error 3104 in SeekDB)
            '\b': '',         # Remove backspace
            '\f': '',         # Remove form feed
        })

        # For documents, we keep the text as-is since pyseekdb should handle fulltext indexing
        # If there are SQL injection issues, the SDK should handle them

    def _get_safe_collection_name(self, collection: str) -> str:
        """Get a safe SQL identifier for the collection name.

        SeekDB generates SQL queries that may not handle collection names with
        hyphens (like in UUIDs) properly. This method simply replaces hyphens
        with underscores to create safe SQL identifiers.

        Args:
            collection: Original collection name

        Returns:
            Safe SQL identifier for the collection
        """
        if collection in self._collection_name_map:
            return self._collection_name_map[collection]

        # Simply replace hyphens with underscores
        safe_name = collection.replace('-', '_')

        self._collection_name_map[collection] = safe_name
        self.ap.logger.debug(f"Mapped collection name '{collection}' to safe SQL identifier '{safe_name}'")
        return safe_name

    async def _get_collection_if_exists(self, collection: str) -> Any:
        """Get collection object if it exists, None otherwise.

        This method handles caching and retrieval logic for existing collections.

        Args:
            collection: Collection name

        Returns:
            Collection object if exists, None otherwise
        """
        # Check cache first
        if collection in self._collections:
            return self._collections[collection]

        # Check if collection exists in database using safe name
        safe_collection_name = self._get_safe_collection_name(collection)
        try:
            exists = await asyncio.to_thread(self.client.has_collection, safe_collection_name)
            if not exists:
                return None

            # Collection exists, get it
            coll = await asyncio.to_thread(self.client.get_collection, safe_collection_name, embedding_function=None)
            self._collections[collection] = coll
            return coll
        except Exception as e:
            self.ap.logger.error(f"Failed to get collection '{collection}' (safe name: '{safe_collection_name}'): {e}")
            return None

    def get_capabilities(self) -> set[str]:
        """
        Return capabilities supported by this SeekDB instance.

        SeekDB natively supports:
        - vector: Vector similarity search
        - fulltext: Full-text keyword search (automatically indexed when documents are provided)
        - hybrid: Native hybrid search combining vector + fulltext with RRF fusion

        Returns:
            Set of capability names
        """
        # SeekDB natively supports all three capabilities
        # Vector search is always available
        # Fulltext and hybrid are available as long as documents are provided during add_embeddings
        return {'vector', 'fulltext', 'hybrid'}

    async def _get_or_create_collection_internal(self, collection: str, vector_size: int = None) -> Any:
        """Internal method to get or create a collection with proper configuration."""
        if collection in self._collections:
            self.ap.logger.debug(f"SeekDB collection '{collection}' found in cache")
            return self._collections[collection]

        # Use default dimension if not specified
        if vector_size is None:
            vector_size = 384

        # Get the safe collection name for SQL operations
        safe_collection_name = self._get_safe_collection_name(collection)

        self.ap.logger.info(f"Getting or creating SeekDB collection '{collection}' (safe name: '{safe_collection_name}') with dimension={vector_size}...")

        # Create HNSW configuration
        config = HNSWConfiguration(dimension=vector_size, distance='cosine')
        self._collection_configs[collection] = config

        # Prepare kwargs for get_or_create_collection
        create_kwargs = {
            'configuration': config,
            'embedding_function': None,  # Disable automatic embedding
        }

        try:
            import time
            start_time = time.time()
            self.ap.logger.info(f"Starting collection get/create for '{collection}'...")

            # Use safe collection name for SeekDB operations
            coll = await asyncio.to_thread(self.client.get_or_create_collection, safe_collection_name, **create_kwargs)

            elapsed = time.time() - start_time
            self.ap.logger.info(f"Collection '{collection}' ready in {elapsed:.2f}s")
        except Exception as e:
            self.ap.logger.error(f"Failed to get/create collection '{collection}' (safe name: '{safe_collection_name}', dimension={vector_size}): {e}")
            raise

        self._collections[collection] = coll
        self.ap.logger.info(f"SeekDB collection '{collection}' ready with dimension={vector_size}, distance='cosine'")
        return coll

    def _clean_metadata(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Clean metadata to avoid SeekDB error 3104 and Invalid JSON errors.

        SeekDB stores metadata as JSON. We need to ensure all values are JSON-compatible.

        IMPORTANT: We exclude the 'text' field from metadata because:
        1. Text content is passed via the 'documents' parameter
        2. Text can be very long and contain special characters that break JSON
        3. Storing text in both metadata and documents is redundant
        """
        cleaned = {}
        for k, v in meta.items():
            # Skip 'text' field - it should only be in documents parameter
            if k == 'text':
                continue

            if v is None:
                continue
            elif isinstance(v, (int, float, bool)):
                # These types are always JSON-safe
                cleaned[k] = v
            elif isinstance(v, str):
                # Remove only characters that are truly problematic
                # Keep the string mostly as-is, just remove null bytes
                cleaned_str = v.replace('\x00', '')  # Remove null bytes
                # Also remove other control characters that might break JSON
                cleaned_str = ''.join(char for char in cleaned_str if ord(char) >= 32 or char in '\t\n\r')
                cleaned[k] = cleaned_str
            else:
                # Convert other types to string
                cleaned[k] = str(v)
        return cleaned

    def _clean_document(self, doc: str) -> str:
        """Clean document text for fulltext indexing.

        For now, we keep documents as-is and let pyseekdb SDK handle the encoding.
        The SDK should properly escape documents when inserting into the database.
        """
        if not isinstance(doc, str):
            return str(doc) if doc is not None else ""

        # Remove only null bytes which are invalid in most contexts
        if '\x00' in doc:
            return doc.replace('\x00', '')

        return doc

    async def get_or_create_collection(self, collection: str):
        """Get or create collection (without vector size - will use default)."""
        return await self._get_or_create_collection_internal(collection)

    async def add_embeddings(
        self,
        collection: str,
        ids: List[str],
        embeddings_list: List[List[float]],
        metadatas: List[Dict[str, Any]],
        documents: List[str] = None
    ) -> None:
        """Add vector embeddings to the specified collection.

        Args:
            collection: Collection name
            ids: List of document IDs
            embeddings_list: List of embedding vectors
            metadatas: List of metadata dictionaries
            documents: List of document texts (optional, for fulltext search)
        """
        if not embeddings_list:
            self.ap.logger.warning(f"add_embeddings called with empty embeddings_list for collection '{collection}'")
            return

        # Ensure collection exists with correct dimension
        vector_size = len(embeddings_list[0])
        total_items = len(ids)

        self.ap.logger.info(
            f"Adding {total_items} embeddings to SeekDB collection '{collection}' "
            f"(dimension={vector_size}, with_documents={documents is not None})"
        )

        coll = await self._get_or_create_collection_internal(collection, vector_size)

        # Prepare data: clean metadata and documents if provided
        cleaned_metadatas = [self._clean_metadata(meta) for meta in metadatas]

        # Debug: Log sample data
        if cleaned_metadatas:
            self.ap.logger.debug(f"Sample cleaned metadata (first item): {cleaned_metadatas[0]}")

        # Build add parameters - SeekDB supports optional documents parameter
        add_kwargs = {
            'ids': ids,
            'embeddings': embeddings_list,
            'metadatas': cleaned_metadatas
        }

        if documents:
            cleaned_documents = [self._clean_document(doc) for doc in documents]
            add_kwargs['documents'] = cleaned_documents
            self.ap.logger.debug(f"Cleaned {len(documents)} document texts for SQL compatibility")

           

        # Insert embeddings - SeekDB handles batching internally
        # If documents are provided, they're automatically indexed for fulltext search
        try:
            import time
            start_time = time.time()
            self.ap.logger.info(f"Inserting {total_items} embeddings...")

            await asyncio.to_thread(coll.add, **add_kwargs)
            elapsed = time.time() - start_time

            self.ap.logger.info(
                f"Successfully added {total_items} embeddings to SeekDB collection '{collection}' in {elapsed:.2f}s"
            )
        except Exception as e:
            # If large batch fails, try smaller batches as fallback
            if total_items > 20:
                self.ap.logger.warning(f"Large batch insertion failed, falling back to smaller batches: {e}")
                await self._batch_add_embeddings_fallback(coll, collection, add_kwargs, total_items)
            else:
                self.ap.logger.error(f"Failed to insert embeddings to collection '{collection}': {e}")
                raise

    async def _batch_add_embeddings_fallback(self, coll, collection_name: str, add_kwargs: dict, total_items: int) -> None:
        """Fallback batch insertion when large batch fails."""
        batch_size = 20
        ids = add_kwargs['ids']
        embeddings = add_kwargs['embeddings']
        metadatas = add_kwargs['metadatas']
        documents = add_kwargs.get('documents')

        successful_inserts = 0
        num_batches = (total_items + batch_size - 1) // batch_size

        self.ap.logger.info(f"Fallback: Inserting {total_items} embeddings in {num_batches} smaller batches...")

        for i in range(0, total_items, batch_size):
            end_idx = min(i + batch_size, total_items)
            batch_num = i // batch_size + 1

            # Prepare batch data
            batch_kwargs = {
                'ids': ids[i:end_idx],
                'embeddings': embeddings[i:end_idx],
                'metadatas': metadatas[i:end_idx]
            }
            if documents:
                batch_kwargs['documents'] = documents[i:end_idx]

            batch_count = len(batch_kwargs['ids'])

            try:
                await asyncio.to_thread(coll.add, **batch_kwargs)
                successful_inserts += batch_count
                self.ap.logger.debug(f"Batch {batch_num}/{num_batches}: {batch_count} embeddings inserted")
            except Exception as e:
                self.ap.logger.error(f"Batch {batch_num} failed: {e}")
                # Continue with other batches - partial success is acceptable
                break

        if successful_inserts > 0:
            self.ap.logger.info(f"Fallback insertion completed: {successful_inserts}/{total_items} embeddings added")
        else:
            raise Exception("All fallback batches failed")

    async def search(self, collection: str, query_embedding: List[float], k: int = 5) -> Dict[str, Any]:
        """Search for the most similar vectors in the specified collection.

        Args:
            collection: Collection name
            query_embedding: Query vector
            k: Number of results to return

        Returns:
            Dictionary with 'ids', 'metadatas', 'distances' keys
        """
        # Get collection if it exists
        coll = await self._get_collection_if_exists(collection)
        if coll is None:
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}

        # Perform query
        # SeekDB's query() returns: {'ids': [[...]], 'metadatas': [[...]], 'distances': [[...]]}
        results = await asyncio.to_thread(coll.query, query_embeddings=query_embedding, n_results=k)

        self.ap.logger.info(f"SeekDB search in '{collection}' returned {len(results.get('ids', [[]])[0])} results")

        return results

    async def search_fulltext(self, collection: str, query: str, k: int = 5) -> Dict[str, Any]:
        """
        Search for documents matching the keyword query using SeekDB's fulltext capabilities.

        Uses collection.get() with where_document filter to perform pure fulltext search.
        This leverages SeekDB's native fulltext indexing for keyword matching.
        """
        # Get collection if it exists
        coll = await self._get_collection_if_exists(collection)
        if coll is None:
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}

        # Use collection.get() with where_document filter for fulltext search
        try:
            results = await asyncio.to_thread(
                coll.get,
                where_document={"$contains": query},
                limit=k,
                include=["documents", "metadatas"]
            )

            # .get() returns flat lists, wrap them for consistency with other search methods
            ids = [results.get('ids', [])]
            metas = [results.get('metadatas', [])]
            docs = [results.get('documents', [])]
            # Provide dummy distances (0.0 for fulltext results)
            dists = [[0.0] * len(ids[0])]

            self.ap.logger.info(f"SeekDB fulltext search in '{collection}' returned {len(ids[0])} results")

            return {
                'ids': ids,
                'metadatas': metas,
                'distances': dists,
                'documents': docs
            }
        except Exception as e:
            self.ap.logger.error(f"SeekDB fulltext search failed: {e}")
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}

    async def search_hybrid(
        self, collection: str, query_embedding: List[float], query: str, k: int = 5, **kwargs
    ) -> Dict[str, Any]:
        """Search using native hybrid search via SDK."""
        # Get collection if it exists
        coll = await self._get_collection_if_exists(collection)
        if coll is None:
             return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}
            
        # Ref: hybrid_search(query={}, knn={}, rank={}, n_results=...)
        # query: {where_document: {$contains: ...}}
        # knn: {query_embeddings: ...}
        
        hybrid_args = {
            "query": {
                "where_document": {"$contains": query},
                "n_results": k
            },
            "knn": {
                "query_embeddings": query_embedding, # Expects List[List[float]] or List[float]. Our input is usually List[float] (single vector) or List[List] (batch)
                # But search interface contract is: query_embedding is List[float] (single vector)
                # We need to wrap it as list of list for batch API? 
                # Wait, generic interface search signature: query_embedding is List[float] (single).
                # SeekDB SDK expects list of vectors usually? 
                # Let's wrap it in a list if it's a flat list.
                "n_results": k
            },
            "rank": {"rrf": {}},  # Default to RRF
            "n_results": k,
            "include": ["documents", "metadatas", "distances"] # 'distances' might not be standard in hybrid return?
        }

        # Handle batch vs single vector format
        # query_embedding is typically [0.1, 0.2, ...] (one vector) from the interface
        # But SDK expects [[0.1, 0.2, ...]] (batch format) for query_embeddings
        # Check if the first element is a scalar (not a list/array) to detect single vector
        if query_embedding and not isinstance(query_embedding[0], (list, type(query_embedding))):
            # Single vector format: wrap it in a list
            hybrid_args['knn']['query_embeddings'] = [query_embedding]
        else:
            # Already in batch format or empty
            hybrid_args['knn']['query_embeddings'] = query_embedding

        results = await asyncio.to_thread(coll.hybrid_search, **hybrid_args)

        self.ap.logger.info(f"SeekDB hybrid search in '{collection}' returned {len(results.get('ids', [[]])[0])} results")
        return results

    async def delete_by_file_id(self, collection: str, file_id: str) -> None:
        """Delete vectors from the collection by file_id metadata.

        Args:
            collection: Collection name
            file_id: File ID to delete
        """
        # Get collection if it exists
        coll = await self._get_collection_if_exists(collection)
        if coll is None:
            self.ap.logger.warning(f"SeekDB collection '{collection}' not found for deletion")
            return

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

        # Check if collection exists and delete it
        safe_collection_name = self._get_safe_collection_name(collection)
        try:
            exists = await asyncio.to_thread(self.client.has_collection, safe_collection_name)
            if not exists:
                self.ap.logger.warning(f"SeekDB collection '{collection}' (safe name: '{safe_collection_name}') not found for deletion")
                return

            # Delete collection
            await asyncio.to_thread(self.client.delete_collection, safe_collection_name)
            self.ap.logger.info(f"SeekDB collection '{collection}' deleted")
        except Exception as e:
            self.ap.logger.error(f"Failed to delete SeekDB collection '{collection}' (safe name: '{safe_collection_name}'): {e}")
            raise
