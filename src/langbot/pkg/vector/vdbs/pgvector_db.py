from __future__ import annotations
from typing import Any, Dict
from sqlalchemy import create_engine, text, Column, String, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from pgvector.sqlalchemy import Vector
from langbot.pkg.vector.vdb import VectorDatabase
from langbot.pkg.core import app

Base = declarative_base()


class PgVectorEntry(Base):
    """SQLAlchemy model for pgvector entries"""

    __tablename__ = 'langbot_vectors'

    id = Column(String, primary_key=True)
    collection = Column(String, index=True, nullable=False)
    embedding = Column(Vector(1536))  # Default dimension, will be created dynamically
    text = Column(Text)
    file_id = Column(String, index=True)
    chunk_uuid = Column(String)


class PgVectorDatabase(VectorDatabase):
    """PostgreSQL with pgvector extension database implementation"""

    def __init__(
        self,
        ap: app.Application,
        connection_string: str = None,
        host: str = 'localhost',
        port: int = 5432,
        database: str = 'langbot',
        user: str = 'postgres',
        password: str = 'postgres',
    ):
        """Initialize pgvector database

        Args:
            ap: Application instance
            connection_string: Full PostgreSQL connection string (overrides other params)
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            user: Database user
            password: Database password
        """
        self.ap = ap

        # Build connection string if not provided
        if connection_string:
            self.connection_string = connection_string
        else:
            self.connection_string = f'postgresql+psycopg://{user}:{password}@{host}:{port}/{database}'

        self.async_connection_string = self.connection_string.replace('postgresql://', 'postgresql+asyncpg://').replace(
            'postgresql+psycopg://', 'postgresql+asyncpg://'
        )

        self.engine = None
        self.async_engine = None
        self.SessionLocal = None
        self.AsyncSessionLocal = None
        self._collections = set()
        self._initialize_db()

    def _initialize_db(self):
        """Initialize database connection and create tables"""
        try:
            # Create async engine for async operations
            self.async_engine = create_async_engine(self.async_connection_string, echo=False, pool_pre_ping=True)
            self.AsyncSessionLocal = async_sessionmaker(self.async_engine, class_=AsyncSession, expire_on_commit=False)

            # Create sync engine for table creation
            sync_connection_string = self.connection_string.replace('postgresql+asyncpg://', 'postgresql+psycopg://')
            self.engine = create_engine(sync_connection_string, echo=False)

            # Create pgvector extension and tables
            with self.engine.connect() as conn:
                # Enable pgvector extension
                conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
                conn.commit()

            # Create tables
            Base.metadata.create_all(self.engine)

            self.ap.logger.info('Connected to PostgreSQL with pgvector')
        except Exception as e:
            self.ap.logger.error(f'Failed to connect to PostgreSQL: {e}')
            raise

    async def get_or_create_collection(self, collection: str):
        """Get or create a collection (logical grouping in pgvector)

        Args:
            collection: Collection name (knowledge base UUID)
        """
        # In pgvector, collections are logical - we just track them
        if collection not in self._collections:
            self._collections.add(collection)
            self.ap.logger.info(f"Registered pgvector collection '{collection}'")
        return collection

    async def add_embeddings(
        self,
        collection: str,
        ids: list[str],
        embeddings_list: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Add vector embeddings to pgvector

        Args:
            collection: Collection name
            ids: List of unique IDs for each vector
            embeddings_list: List of embedding vectors
            metadatas: List of metadata dictionaries
        """
        await self.get_or_create_collection(collection)

        async with self.AsyncSessionLocal() as session:
            try:
                for i, vector_id in enumerate(ids):
                    metadata = metadatas[i] if i < len(metadatas) else {}

                    entry = PgVectorEntry(
                        id=vector_id,
                        collection=collection,
                        embedding=embeddings_list[i],
                        text=metadata.get('text', ''),
                        file_id=metadata.get('file_id', ''),
                        chunk_uuid=metadata.get('uuid', ''),
                    )
                    session.add(entry)

                await session.commit()
                self.ap.logger.info(f"Added {len(ids)} embeddings to pgvector collection '{collection}'")
            except Exception as e:
                await session.rollback()
                self.ap.logger.error(f'Error adding embeddings to pgvector: {e}')
                raise

    async def search(self, collection: str, query_embedding: list[float], k: int = 5) -> Dict[str, Any]:
        """Search for similar vectors using cosine distance

        Args:
            collection: Collection name
            query_embedding: Query vector
            k: Number of top results to return

        Returns:
            Dictionary with search results in Chroma-compatible format
        """
        await self.get_or_create_collection(collection)

        async with self.AsyncSessionLocal() as session:
            try:
                # Use cosine distance for similarity search
                from sqlalchemy import select

                # Query for similar vectors
                stmt = (
                    select(
                        PgVectorEntry.id,
                        PgVectorEntry.text,
                        PgVectorEntry.file_id,
                        PgVectorEntry.chunk_uuid,
                        PgVectorEntry.embedding.cosine_distance(query_embedding).label('distance'),
                    )
                    .filter(PgVectorEntry.collection == collection)
                    .order_by(PgVectorEntry.embedding.cosine_distance(query_embedding))
                    .limit(k)
                )

                result = await session.execute(stmt)
                rows = result.fetchall()

                # Convert to Chroma-compatible format
                ids = []
                distances = []
                metadatas = []

                for row in rows:
                    ids.append(row.id)
                    distances.append(float(row.distance))
                    metadatas.append(
                        {'text': row.text or '', 'file_id': row.file_id or '', 'uuid': row.chunk_uuid or ''}
                    )

                result_dict = {'ids': [ids], 'distances': [distances], 'metadatas': [metadatas]}

                self.ap.logger.info(f"pgvector search in '{collection}' returned {len(ids)} results")
                return result_dict

            except Exception as e:
                self.ap.logger.error(f'Error searching pgvector: {e}')
                raise

    async def delete_by_file_id(self, collection: str, file_id: str) -> None:
        """Delete vectors by file_id

        Args:
            collection: Collection name
            file_id: File ID to filter deletion
        """
        await self.get_or_create_collection(collection)

        async with self.AsyncSessionLocal() as session:
            try:
                from sqlalchemy import delete

                stmt = delete(PgVectorEntry).where(
                    PgVectorEntry.collection == collection, PgVectorEntry.file_id == file_id
                )
                await session.execute(stmt)
                await session.commit()

                self.ap.logger.info(
                    f"Deleted embeddings from pgvector collection '{collection}' with file_id: {file_id}"
                )
            except Exception as e:
                await session.rollback()
                self.ap.logger.error(f'Error deleting from pgvector: {e}')
                raise

    async def delete_collection(self, collection: str):
        """Delete all vectors in a collection

        Args:
            collection: Collection name to delete
        """
        if collection in self._collections:
            self._collections.remove(collection)

        async with self.AsyncSessionLocal() as session:
            try:
                from sqlalchemy import delete

                stmt = delete(PgVectorEntry).where(PgVectorEntry.collection == collection)
                await session.execute(stmt)
                await session.commit()

                self.ap.logger.info(f"Deleted pgvector collection '{collection}'")
            except Exception as e:
                await session.rollback()
                self.ap.logger.error(f'Error deleting pgvector collection: {e}')
                raise

    async def close(self):
        """Close database connections"""
        if self.async_engine:
            await self.async_engine.dispose()
        if self.engine:
            self.engine.dispose()
