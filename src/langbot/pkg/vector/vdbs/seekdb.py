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
    
    If 'fulltext' config is provided, it can specify 'create_options' (passed to create_collection)
    or other tokenizer settings (e.g. 'tokenizer': 'ik_max_word') which might be
    handled if the SDK exposes tokenization control on the client side or during index creation.
    """

    def __init__(self, ap: app.Application, config_override: dict = None, fulltext_config: dict = None):
        """SeekDB Vector Database Adapter.
        
        Args:
            ap: Application instance
            config_override: Optional configuration dictionary
            fulltext_config: Optional configuration for fulltext indexing (parser, language)
        """
        if not SEEKDB_AVAILABLE:
            raise ImportError('pyseekdb is not installed. Install it with: pip install pyseekdb')

        self.ap = ap
        # Use config_override if provided (from multi-instance manager), else fallback to default config path
        if config_override:
            config = config_override
        else:
            config = self.ap.instance_config.data['vdb']['seekdb']

        self.fulltext_config = fulltext_config or {}
        
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

                self.ap.logger.debug("Listing existing databases...")
                # Check if database exists using public API
                existing_dbs = [db.name for db in admin_client.list_databases()]
                self.ap.logger.debug(f"Found databases: {existing_dbs}")

                if database not in existing_dbs:
                    self.ap.logger.info(f"Database '{database}' not found, creating...")
                    # Use public API to create database
                    admin_client.create_database(database)
                    self.ap.logger.info(f"Created SeekDB database '{database}'")
                else:
                    self.ap.logger.debug(f"Database '{database}' already exists")
            except Exception as e:
                self.ap.logger.error(f"Failed to initialize SeekDB AdminClient or list databases: {e}")
                self.ap.logger.warning(
                    f"If SeekDB data is corrupted, try deleting the directory: {path}"
                )
                raise

            try:
                self.ap.logger.debug(f"Connecting to database '{database}'...")
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

    def _sanitize_collection_name(self, collection: str) -> str:
        """Sanitize collection name to avoid SQL syntax errors.

        pyseekdb SDK has issues with hyphens in collection names when generating SQL.
        We convert hyphens to underscores to work around this limitation.

        Args:
            collection: Original collection name (e.g., UUID with hyphens)

        Returns:
            Sanitized collection name safe for SQL (e.g., UUID with underscores)
        """
        # Replace hyphens with underscores to avoid SQL syntax errors
        # e.g., "6b648b14-b34a-4393-8fed-230af9d1fe52" -> "6b648b14_b34a_4393_8fed_230af9d1fe52"
        return collection.replace('-', '_')

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
        # Sanitize collection name to avoid SQL syntax errors
        safe_collection = self._sanitize_collection_name(collection)

        if safe_collection in self._collections:
            self.ap.logger.debug(f"SeekDB collection '{safe_collection}' found in cache")
            return self._collections[safe_collection]

        # Check if collection exists
        self.ap.logger.info(f"Checking if SeekDB collection '{safe_collection}' exists...")
        try:
            exists = await asyncio.to_thread(self.client.has_collection, safe_collection)
            if exists:
                # Collection exists, get it
                self.ap.logger.info(f"SeekDB collection '{safe_collection}' exists, retrieving...")
                coll = await asyncio.to_thread(self.client.get_collection, safe_collection, embedding_function=None)
                self._collections[safe_collection] = coll
                self.ap.logger.info(f"SeekDB collection '{safe_collection}' retrieved successfully.")
                return coll
        except Exception as e:
            self.ap.logger.error(f"Failed to check/retrieve collection '{safe_collection}': {e}")
            raise

        # Collection doesn't exist, create it
        if vector_size is None:
            # Default dimension if not specified
            vector_size = 384

        self.ap.logger.info(f"SeekDB collection '{safe_collection}' does not exist, creating with dimension={vector_size}...")

        # Create HNSW configuration
        config = HNSWConfiguration(dimension=vector_size, distance='cosine')
        self._collection_configs[safe_collection] = config

        # Prepare kwargs for create_collection
        create_kwargs = {
            'name': safe_collection,
            'configuration': config,
            'embedding_function': None,  # Disable automatic embedding
        }

        # Inject fulltext-related creation params if configured
        # E.g. user wants to specify tokenizer/parser for fulltext index at creation time
        # pyseekdb likely supports `create_collection_params` or similar in next versions or via specific kwargs
        # Assuming we can pass extra params or check `self.fulltext_config` for relevant keys
        # For now, we assume simple creation. If `fulltext_config` has `create_options`, we spread them.
        if self.fulltext_config and 'create_options' in self.fulltext_config:
             create_kwargs.update(self.fulltext_config['create_options'])

        # Create collection without embedding function (we manage embeddings externally)
        try:
            import time
            start_time = time.time()
            self.ap.logger.info(f"Starting collection creation for '{safe_collection}'...")
            coll = await asyncio.to_thread(self.client.create_collection, **create_kwargs)
            elapsed = time.time() - start_time
            self.ap.logger.info(f"Collection '{safe_collection}' created successfully in {elapsed:.2f}s")
        except Exception as e:
            self.ap.logger.error(f"Failed to create collection '{safe_collection}' (dimension={vector_size}): {e}")
            raise

        self._collections[safe_collection] = coll
        self.ap.logger.info(f"SeekDB collection '{safe_collection}' created with dimension={vector_size}, distance='cosine'")
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
            documents: List of document texts (required for fulltext search)
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

        # Clean metadata and documents to avoid SQL syntax errors
        cleaned_metadatas = [self._clean_metadata(meta) for meta in metadatas]

        # Debug: Log first metadata to see what we're working with
        if cleaned_metadatas:
            self.ap.logger.debug(f"Sample cleaned metadata (first item): {cleaned_metadatas[0]}")

        cleaned_documents = None
        if documents:
            cleaned_documents = [self._clean_document(doc) for doc in documents]
            self.ap.logger.debug(f"Cleaned {len(documents)} document texts for SQL compatibility")
            # Debug: Log first document snippet
            if cleaned_documents:
                sample_doc = cleaned_documents[0][:100] if len(cleaned_documents[0]) > 100 else cleaned_documents[0]
                self.ap.logger.debug(f"Sample cleaned document (first 100 chars): {repr(sample_doc)}")

        # Batch insert to avoid timeout on large datasets
        # SeekDB embedded mode can timeout with large batches
        batch_size = 20
        successful_inserts = 0

        if total_items <= batch_size:
            # Small batch, insert directly
            add_kwargs = {
                'ids': ids,
                'embeddings': embeddings_list,
                'metadatas': cleaned_metadatas
            }
            if cleaned_documents:
                add_kwargs['documents'] = cleaned_documents

            try:
                import time
                start_time = time.time()
                self.ap.logger.info(f"Inserting {total_items} embeddings in single batch...")
                await asyncio.to_thread(coll.add, **add_kwargs)
                elapsed = time.time() - start_time
                successful_inserts = len(ids)
                self.ap.logger.info(
                    f"Successfully added {successful_inserts} embeddings to SeekDB collection '{collection}' in {elapsed:.2f}s"
                )
            except Exception as e:
                self.ap.logger.error(
                    f"Failed to insert batch of {total_items} embeddings to collection '{collection}': {e}"
                )
                raise
        else:
            # Large batch, split into chunks
            num_batches = (total_items + batch_size - 1) // batch_size
            self.ap.logger.info(f"Inserting {total_items} embeddings in {num_batches} batches of {batch_size}...")

            for i in range(0, total_items, batch_size):
                end_idx = min(i + batch_size, total_items)
                batch_num = i // batch_size + 1
                batch_ids = ids[i:end_idx]
                batch_embeddings = embeddings_list[i:end_idx]
                batch_metadatas = cleaned_metadatas[i:end_idx]
                batch_count = len(batch_ids)

                add_kwargs = {
                    'ids': batch_ids,
                    'embeddings': batch_embeddings,
                    'metadatas': batch_metadatas
                }
                if cleaned_documents:
                    batch_documents = cleaned_documents[i:end_idx]
                    add_kwargs['documents'] = batch_documents

                try:
                    import time
                    start_time = time.time()
                    self.ap.logger.info(
                        f"Batch {batch_num}/{num_batches}: Inserting {batch_count} embeddings (items {i+1}-{end_idx}/{total_items})..."
                    )
                    await asyncio.to_thread(coll.add, **add_kwargs)
                    elapsed = time.time() - start_time
                    successful_inserts += batch_count
                    self.ap.logger.info(
                        f"Batch {batch_num}/{num_batches}: Successfully inserted {batch_count} embeddings in {elapsed:.2f}s "
                        f"(total: {successful_inserts}/{total_items})"
                    )
                except Exception as e:
                    self.ap.logger.error(
                        f"Batch {batch_num}/{num_batches} FAILED: Could not insert {batch_count} embeddings "
                        f"(items {i+1}-{end_idx}). Successfully inserted {successful_inserts}/{total_items} before failure. Error: {e}"
                    )
                    # Rollback: delete all successfully inserted items from this batch operation
                    if successful_inserts > 0:
                        self.ap.logger.warning(
                            f"Attempting to rollback {successful_inserts} successfully inserted embeddings to maintain consistency..."
                        )
                        try:
                            # Delete by IDs that were successfully inserted
                            rollback_ids = ids[:successful_inserts]
                            await asyncio.to_thread(coll.delete, ids=rollback_ids)
                            self.ap.logger.info(f"Rollback successful: removed {successful_inserts} embeddings")
                        except Exception as rollback_error:
                            self.ap.logger.error(
                                f"Rollback FAILED: Could not remove {successful_inserts} embeddings. "
                                f"Database may be in inconsistent state. Error: {rollback_error}"
                            )
                            self.ap.logger.warning(
                                f"Consider deleting the SeekDB data directory to fix: {self.ap.instance_config.data.get('vdb', {}).get('seekdb', {}).get('path', './data/seekdb')}"
                            )
                    raise

            self.ap.logger.info(
                f"Completed batch insertion: {successful_inserts}/{total_items} embeddings successfully added "
                f"to SeekDB collection '{collection}' in {num_batches} batches"
            )

    async def search(self, collection: str, query_embedding: List[float], k: int = 5) -> Dict[str, Any]:
        """Search for the most similar vectors in the specified collection.

        Args:
            collection: Collection name
            query_embedding: Query vector
            k: Number of results to return

        Returns:
            Dictionary with 'ids', 'metadatas', 'distances' keys
        """
        # Sanitize collection name
        safe_collection = self._sanitize_collection_name(collection)

        # Check if collection exists
        exists = await asyncio.to_thread(self.client.has_collection, safe_collection)
        if not exists:
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}

        # Get collection
        if safe_collection not in self._collections:
            coll = await asyncio.to_thread(self.client.get_collection, safe_collection, embedding_function=None)
            self._collections[safe_collection] = coll
        else:
            coll = self._collections[safe_collection]

        # Perform query
        # SeekDB's query() returns: {'ids': [[...]], 'metadatas': [[...]], 'distances': [[...]]}
        results = await asyncio.to_thread(coll.query, query_embeddings=query_embedding, n_results=k)

        self.ap.logger.info(f"SeekDB search in '{safe_collection}' returned {len(results.get('ids', [[]])[0])} results")

        return results

    async def search_fulltext(self, collection: str, query: str, k: int = 5) -> Dict[str, Any]:
        """
        Search for documents matching the keyword query using SeekDB's fulltext capabilities.

        Uses hybrid_search with only the 'query' parameter (no 'knn') to perform pure fulltext search.
        This leverages SeekDB's native fulltext indexing for better relevance ranking.
        """
        # Sanitize collection name
        safe_collection = self._sanitize_collection_name(collection)

        # Check if collection exists
        exists = await asyncio.to_thread(self.client.has_collection, safe_collection)
        if not exists:
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}

        # Get collection
        if safe_collection not in self._collections:
            coll = await asyncio.to_thread(self.client.get_collection, safe_collection, embedding_function=None)
            self._collections[safe_collection] = coll
        else:
            coll = self._collections[safe_collection]

        # Use hybrid_search with only query parameter (no knn) for pure fulltext search
        # This provides relevance-ranked results based on fulltext matching
        try:
            results = await asyncio.to_thread(
                coll.hybrid_search,
                query={
                    "where_document": {"$contains": query},
                    "n_results": k
                },
                # No 'knn' parameter - pure fulltext search
                n_results=k,
                include=["documents", "metadatas"]
            )

            # hybrid_search returns format: {'ids': [[id1, id2]], 'metadatas': [[meta1, meta2]], ...}
            # Add dummy distances for compatibility
            ids = results.get('ids', [[]])
            metas = results.get('metadatas', [[]])

            # Provide dummy distances (0.0 for fulltext results)
            dists = [[0.0] * len(ids[0])] if ids and ids[0] else [[]]

            self.ap.logger.info(f"SeekDB fulltext search in '{safe_collection}' returned {len(ids[0]) if ids else 0} results")

            return {
                'ids': ids,
                'metadatas': metas,
                'distances': dists,
                'documents': results.get('documents', [[]])
            }
        except Exception as e:
            # Fallback to .get() if hybrid_search is not available or fails
            self.ap.logger.warning(f"SeekDB hybrid_search failed, falling back to .get(): {e}")
            results = await asyncio.to_thread(
                coll.get,
                where_document={"$contains": query},
                limit=k,
                include=["documents", "metadatas"]
            )

            # .get returns flat lists, wrap them for consistency
            ids = [results.get('ids', [])]
            metas = [results.get('metadatas', [])]
            docs = [results.get('documents', [])]
            dists = [[0.0] * len(ids[0])]

            return {
                'ids': ids,
                'metadatas': metas,
                'distances': dists,
                'documents': docs
            }

    async def search_hybrid(
        self, collection: str, query_embedding: List[float], query: str, k: int = 5, **kwargs
    ) -> Dict[str, Any]:
        """Search using native hybrid search via SDK."""
        # Sanitize collection name
        safe_collection = self._sanitize_collection_name(collection)

        exists = await asyncio.to_thread(self.client.has_collection, safe_collection)
        if not exists:
             return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}

        # Get collection
        if safe_collection not in self._collections:
            coll = await asyncio.to_thread(self.client.get_collection, safe_collection, embedding_function=None)
            self._collections[safe_collection] = coll
        else:
            coll = self._collections[safe_collection]
            
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
        
        # Handle batch vs single vector ambiguity
        # query_embedding is typically [0.1, 0.2, ...] (one vector)
        # sdk usually wants [[0.1, 0.2, ...]] for query_embeddings
        if query_embedding and isinstance(query_embedding[0], float):
             hybrid_args['knn']['query_embeddings'] = [query_embedding]
        else:
             hybrid_args['knn']['query_embeddings'] = query_embedding

        results = await asyncio.to_thread(coll.hybrid_search, **hybrid_args)

        self.ap.logger.info(f"SeekDB hybrid search in '{safe_collection}' returned {len(results.get('ids', [[]])[0])} results")
        return results

    async def delete_by_file_id(self, collection: str, file_id: str) -> None:
        """Delete vectors from the collection by file_id metadata.

        Args:
            collection: Collection name
            file_id: File ID to delete
        """
        # Sanitize collection name
        safe_collection = self._sanitize_collection_name(collection)

        # Check if collection exists
        exists = await asyncio.to_thread(self.client.has_collection, safe_collection)
        if not exists:
            self.ap.logger.warning(f"SeekDB collection '{safe_collection}' not found for deletion")
            return

        # Get collection
        if safe_collection not in self._collections:
            coll = await asyncio.to_thread(self.client.get_collection, safe_collection, embedding_function=None)
            self._collections[safe_collection] = coll
        else:
            coll = self._collections[safe_collection]

        # SeekDB's delete() expects a where clause for filtering
        # Delete all records where metadata['file_id'] == file_id
        await asyncio.to_thread(coll.delete, where={'file_id': file_id})

        self.ap.logger.info(f"Deleted embeddings from SeekDB collection '{safe_collection}' with file_id: {file_id}")

    async def delete_collection(self, collection: str):
        """Delete the entire collection.

        Args:
            collection: Collection name
        """
        # Sanitize collection name
        safe_collection = self._sanitize_collection_name(collection)

        # Remove from cache
        if safe_collection in self._collections:
            del self._collections[safe_collection]
        if safe_collection in self._collection_configs:
            del self._collection_configs[safe_collection]

        # Check if collection exists
        exists = await asyncio.to_thread(self.client.has_collection, safe_collection)
        if not exists:
            self.ap.logger.warning(f"SeekDB collection '{safe_collection}' not found for deletion")
            return

        # Delete collection
        await asyncio.to_thread(self.client.delete_collection, safe_collection)
        self.ap.logger.info(f"SeekDB collection '{safe_collection}' deleted")
