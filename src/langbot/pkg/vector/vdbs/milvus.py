from __future__ import annotations
import asyncio
from typing import Any, Dict
from pymilvus import MilvusClient, DataType
from langbot.pkg.vector.vdb import VectorDatabase
from langbot.pkg.core import app


class MilvusVectorDatabase(VectorDatabase):
    """Milvus vector database implementation"""

    def __init__(self, ap: app.Application, uri: str = "milvus.db", token: str = None):
        """Initialize Milvus vector database

        Args:
            ap: Application instance
            uri: Milvus connection URI. For local file: "milvus.db"
                 For remote server: "http://localhost:19530"
            token: Optional authentication token for remote connections
        """
        self.ap = ap
        self.uri = uri
        self.token = token
        self.client = None
        self._collections = {}
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Milvus client connection"""
        try:
            if self.token:
                self.client = MilvusClient(uri=self.uri, token=self.token)
            else:
                self.client = MilvusClient(uri=self.uri)
            self.ap.logger.info(f"Connected to Milvus at {self.uri}")
        except Exception as e:
            self.ap.logger.error(f"Failed to connect to Milvus: {e}")
            raise

    async def get_or_create_collection(self, collection: str):
        """Get or create a Milvus collection

        Args:
            collection: Collection name (corresponds to knowledge base UUID)
        """
        if collection in self._collections:
            return self._collections[collection]

        # Check if collection exists
        has_collection = await asyncio.to_thread(
            self.client.has_collection, collection_name=collection
        )

        if not has_collection:
            # Create collection with custom schema to support string IDs
            from pymilvus import CollectionSchema, FieldSchema, DataType

            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=255),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=1536),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=255),
                FieldSchema(name="chunk_uuid", dtype=DataType.VARCHAR, max_length=255),
            ]

            schema = CollectionSchema(fields=fields, description="LangBot knowledge base vectors")

            await asyncio.to_thread(
                self.client.create_collection,
                collection_name=collection,
                schema=schema,
                metric_type="COSINE",
            )

            # Create index for vector field (required for loading/searching)
            index_params = {
                "metric_type": "COSINE",
                "index_type": "AUTOINDEX",
                "params": {}
            }
            await asyncio.to_thread(
                self.client.create_index,
                collection_name=collection,
                field_name="vector",
                index_params=index_params
            )

            self.ap.logger.info(f"Created Milvus collection '{collection}' with index")
        else:
            self.ap.logger.info(f"Milvus collection '{collection}' already exists")

        self._collections[collection] = collection
        return collection

    async def add_embeddings(
        self,
        collection: str,
        ids: list[str],
        embeddings_list: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str] = None,
    ) -> None:
        """Add vector embeddings to Milvus collection

        Args:
            collection: Collection name
            ids: List of unique IDs for each vector
            embeddings_list: List of embedding vectors
            metadatas: List of metadata dictionaries for each vector
            documents: Optional document texts (ignored by Milvus, kept for interface compatibility)
        """
        await self.get_or_create_collection(collection)

        # Prepare data in Milvus format
        data = []
        for i, vector_id in enumerate(ids):
            entry = {
                "id": vector_id,
                "vector": embeddings_list[i],
            }
            # Add metadata fields
            if metadatas and i < len(metadatas):
                metadata = metadatas[i]
                # Add common metadata fields
                if "text" in metadata:
                    entry["text"] = metadata["text"]
                if "file_id" in metadata:
                    entry["file_id"] = metadata["file_id"]
                if "uuid" in metadata:
                    entry["chunk_uuid"] = metadata["uuid"]
            data.append(entry)

        # Insert data into Milvus
        await asyncio.to_thread(
            self.client.insert,
            collection_name=collection,
            data=data
        )

        # Load collection for searching (Milvus requires this)
        await asyncio.to_thread(
            self.client.load_collection,
            collection_name=collection
        )

        self.ap.logger.info(f"Added {len(ids)} embeddings to Milvus collection '{collection}'")

    async def search(
        self, collection: str, query_embedding: list[float], k: int = 5
    ) -> Dict[str, Any]:
        """Search for similar vectors in Milvus collection

        Args:
            collection: Collection name
            query_embedding: Query vector
            k: Number of top results to return

        Returns:
            Dictionary with search results in Chroma-compatible format
        """
        await self.get_or_create_collection(collection)

        # Perform search
        search_params = {
            "metric_type": "COSINE",
            "params": {}
        }

        results = await asyncio.to_thread(
            self.client.search,
            collection_name=collection,
            data=[query_embedding],
            limit=k,
            search_params=search_params,
            output_fields=["text", "file_id", "chunk_uuid"]
        )

        # Convert results to Chroma-compatible format
        # Milvus returns: [[ {id, distance, entity: {...}} ]]
        ids = []
        distances = []
        metadatas = []

        if results and len(results) > 0:
            for hit in results[0]:
                ids.append(hit.get("id", ""))
                distances.append(hit.get("distance", 0.0))

                # Build metadata from entity fields
                entity = hit.get("entity", {})
                metadata = {}
                if "text" in entity:
                    metadata["text"] = entity["text"]
                if "file_id" in entity:
                    metadata["file_id"] = entity["file_id"]
                if "chunk_uuid" in entity:
                    metadata["uuid"] = entity["chunk_uuid"]
                metadatas.append(metadata)

        # Return in Chroma-compatible format (nested lists)
        result = {
            "ids": [ids],
            "distances": [distances],
            "metadatas": [metadatas]
        }

        self.ap.logger.info(
            f"Milvus search in '{collection}' returned {len(ids)} results"
        )
        return result

    async def delete_by_file_id(self, collection: str, file_id: str) -> None:
        """Delete vectors from collection by file_id

        Args:
            collection: Collection name
            file_id: File ID to filter deletion
        """
        await self.get_or_create_collection(collection)

        # Delete entities matching the file_id
        await asyncio.to_thread(
            self.client.delete,
            collection_name=collection,
            filter=f'file_id == "{file_id}"'
        )
        self.ap.logger.info(
            f"Deleted embeddings from Milvus collection '{collection}' with file_id: {file_id}"
        )

    async def delete_collection(self, collection: str):
        """Delete a Milvus collection

        Args:
            collection: Collection name to delete
        """
        if collection in self._collections:
            del self._collections[collection]

        # Check if collection exists before attempting deletion
        has_collection = await asyncio.to_thread(
            self.client.has_collection, collection_name=collection
        )

        if has_collection:
            await asyncio.to_thread(
                self.client.drop_collection, collection_name=collection
            )
            self.ap.logger.info(f"Deleted Milvus collection '{collection}'")
        else:
            self.ap.logger.warning(f"Milvus collection '{collection}' not found")
