from __future__ import annotations

import contextlib
import dataclasses
from collections.abc import AsyncIterator
from typing import Any

import sqlalchemy
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from langbot.pkg.core import app
from langbot.pkg.vector.filter_utils import normalize_filter, strip_unsupported_fields
from langbot.pkg.vector.vdb import VectorDatabase


Base = declarative_base()

DEFAULT_ALLOWED_DIMENSIONS = (384, 512, 768, 1024, 1536)

# pgvector schema only stores these metadata fields.
_PG_SUPPORTED_FIELDS = {'text', 'file_id', 'chunk_uuid'}

# Callers use canonical metadata key 'uuid' but pgvector stores it as 'chunk_uuid'.
_PG_FIELD_ALIASES = {'uuid': 'chunk_uuid'}

_PG_COLUMN_MAP = {
    'text': 'text',
    'file_id': 'file_id',
    'chunk_uuid': 'chunk_uuid',
}


@dataclasses.dataclass(frozen=True, slots=True)
class PgVectorScope:
    """Trusted relational tenant key for one knowledge-base operation."""

    workspace_uuid: str
    knowledge_base_uuid: str
    embedding_dimension: int | None = None

    def __post_init__(self) -> None:
        for field_name in ('workspace_uuid', 'knowledge_base_uuid'):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{field_name} must not be empty')
            object.__setattr__(self, field_name, value.strip())
        dimension = self.embedding_dimension
        if dimension is not None and (isinstance(dimension, bool) or not isinstance(dimension, int) or dimension <= 0):
            raise ValueError('embedding_dimension must be a positive integer')


class PgVectorEntry(Base):
    """Tenant-scoped pgvector row created only by release/OSS migrations."""

    __tablename__ = 'langbot_vectors'

    workspace_uuid = sqlalchemy.Column(sqlalchemy.String(36), primary_key=True)
    knowledge_base_uuid = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    vector_id = sqlalchemy.Column(sqlalchemy.String(255), primary_key=True)
    embedding_dimension = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    embedding = sqlalchemy.Column(Vector(), nullable=False)
    text = sqlalchemy.Column(sqlalchemy.Text)
    file_id = sqlalchemy.Column(sqlalchemy.String(255), index=True)
    chunk_uuid = sqlalchemy.Column(sqlalchemy.String(255))

    __table_args__ = (
        sqlalchemy.CheckConstraint(
            'vector_dims(embedding) = embedding_dimension',
            name='ck_langbot_vectors_embedding_dimension',
        ),
    )


def _build_pg_conditions(filter_dict: dict[str, Any]) -> list:
    """Translate canonical filter dict into SQLAlchemy conditions."""

    triples = normalize_filter(filter_dict)
    triples = strip_unsupported_fields(triples, _PG_SUPPORTED_FIELDS, _PG_FIELD_ALIASES)

    conditions = []
    for field, op, value in triples:
        col = getattr(PgVectorEntry, _PG_COLUMN_MAP[field])
        if op == '$eq':
            conditions.append(col == value)
        elif op == '$ne':
            conditions.append(col != value)
        elif op == '$gt':
            conditions.append(col > value)
        elif op == '$gte':
            conditions.append(col >= value)
        elif op == '$lt':
            conditions.append(col < value)
        elif op == '$lte':
            conditions.append(col <= value)
        elif op == '$in':
            conditions.append(col.in_(value))
        elif op == '$nin':
            conditions.append(col.notin_(value))
    return conditions


class PgVectorDatabase(VectorDatabase):
    """PostgreSQL vector adapter with explicit Workspace/RLS scope.

    Cloud reuses the business database engine and never performs DDL. OSS can
    still opt into a standalone pgvector database; that compatibility mode may
    create a fresh schema, but it uses the same explicit tenant keys.
    """

    def __init__(
        self,
        ap: app.Application,
        connection_string: str | None = None,
        host: str = 'localhost',
        port: int = 5432,
        database: str = 'langbot',
        user: str = 'postgres',
        password: str = 'postgres',
        *,
        use_business_database: bool = False,
        allowed_dimensions: list[int] | tuple[int, ...] = DEFAULT_ALLOWED_DIMENSIONS,
    ) -> None:
        self.ap = ap
        self.use_business_database = use_business_database
        self.allowed_dimensions = self._normalize_allowed_dimensions(allowed_dimensions)
        self.engine = None
        self.async_engine = None
        self.AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None

        if use_business_database:
            persistence_mgr = getattr(ap, 'persistence_mgr', None)
            if persistence_mgr is None:
                raise RuntimeError('Shared pgvector requires the initialized business persistence manager')
            business_engine = persistence_mgr.get_db_engine()
            if business_engine.dialect.name != 'postgresql':
                raise RuntimeError('Shared pgvector requires the PostgreSQL business database')
            self.async_engine = business_engine
            self.ap.logger.info('Connected pgvector adapter to the shared PostgreSQL business database')
            return

        if connection_string:
            self.connection_string = connection_string
        else:
            self.connection_string = f'postgresql+psycopg://{user}:{password}@{host}:{port}/{database}'
        self.async_connection_string = self.connection_string.replace('postgresql://', 'postgresql+asyncpg://').replace(
            'postgresql+psycopg://', 'postgresql+asyncpg://'
        )
        self._initialize_standalone_db()

    @staticmethod
    def _normalize_allowed_dimensions(dimensions: list[int] | tuple[int, ...]) -> frozenset[int]:
        if not isinstance(dimensions, (list, tuple)) or not dimensions:
            raise ValueError('pgvector allowed_dimensions must be a non-empty list')
        if any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in dimensions):
            raise ValueError('pgvector allowed_dimensions must contain positive integers')
        unsupported = set(dimensions) - set(DEFAULT_ALLOWED_DIMENSIONS)
        if unsupported:
            raise ValueError(f'pgvector dimensions do not have release-created ANN indexes: {sorted(unsupported)}')
        return frozenset(dimensions)

    def _initialize_standalone_db(self) -> None:
        """Initialize the explicit OSS external database compatibility path."""

        from sqlalchemy import create_engine

        self.async_engine = create_async_engine(self.async_connection_string, echo=False, pool_pre_ping=True)
        self.AsyncSessionLocal = async_sessionmaker(self.async_engine, class_=AsyncSession, expire_on_commit=False)
        sync_connection_string = self.connection_string.replace('postgresql+asyncpg://', 'postgresql+psycopg://')
        self.engine = create_engine(sync_connection_string, echo=False)

        with self.engine.begin() as conn:
            conn.execute(sqlalchemy.text('CREATE EXTENSION IF NOT EXISTS vector'))
            existing_tables = set(sqlalchemy.inspect(conn).get_table_names())
            if PgVectorEntry.__tablename__ in existing_tables:
                columns = {
                    column['name'] for column in sqlalchemy.inspect(conn).get_columns(PgVectorEntry.__tablename__)
                }
                required = {
                    'workspace_uuid',
                    'knowledge_base_uuid',
                    'vector_id',
                    'embedding_dimension',
                    'embedding',
                }
                if not required.issubset(columns):
                    raise RuntimeError(
                        'The external pgvector database uses the legacy unscoped schema; '
                        'migrate it before enabling multi-tenant vector access'
                    )
            Base.metadata.create_all(conn)

        self.ap.logger.info('Connected to standalone PostgreSQL pgvector database')

    def _require_scope(self, scope: PgVectorScope | None, *, require_dimension: bool) -> PgVectorScope:
        if not isinstance(scope, PgVectorScope):
            raise ValueError('pgvector operations require a trusted PgVectorScope')
        dimension = scope.embedding_dimension
        if require_dimension and dimension is None:
            raise ValueError('pgvector operation requires an embedding dimension')
        if dimension is not None and dimension not in self.allowed_dimensions:
            raise ValueError(f'Embedding dimension {dimension} is not enabled for this pgvector deployment')
        return scope

    @staticmethod
    def _scope_conditions(scope: PgVectorScope) -> tuple[Any, Any]:
        return (
            PgVectorEntry.workspace_uuid == scope.workspace_uuid,
            PgVectorEntry.knowledge_base_uuid == scope.knowledge_base_uuid,
        )

    @contextlib.asynccontextmanager
    async def _session(self, scope: PgVectorScope) -> AsyncIterator[AsyncSession]:
        admission = getattr(self.ap, 'deployment_admission', None)
        if admission is not None:
            admission.require_active()

        if self.use_business_database:
            async with self.ap.persistence_mgr.tenant_uow(scope.workspace_uuid) as uow:
                yield uow.session
                if admission is not None:
                    admission.require_active()
            return

        if self.AsyncSessionLocal is None:  # pragma: no cover - constructor invariant
            raise RuntimeError('Standalone pgvector session factory is unavailable')
        async with self.AsyncSessionLocal() as session, session.begin():
            yield session
            if admission is not None:
                admission.require_active()

    async def get_or_create_collection(self, collection: str):
        """Retain the common adapter API; relational rows need no collection DDL."""

        if not isinstance(collection, str) or not collection.strip():
            raise ValueError('collection must not be empty')
        return collection

    async def add_embeddings(
        self,
        collection: str,
        ids: list[str],
        embeddings_list: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str] | None = None,
        *,
        scope: PgVectorScope | None = None,
    ) -> None:
        scope = self._require_scope(scope, require_dimension=True)
        await self.get_or_create_collection(collection)
        if not ids:
            return
        if len(ids) != len(embeddings_list) or len(metadatas) != len(ids):
            raise ValueError('pgvector ids, embeddings and metadata lengths must match')
        if documents is not None and len(documents) != len(ids):
            raise ValueError('pgvector documents length must match ids')
        if len(set(ids)) != len(ids) or any(not isinstance(item, str) or not item.strip() for item in ids):
            raise ValueError('pgvector vector IDs must be unique non-empty strings per upsert')
        expected_dimension = scope.embedding_dimension
        if any(len(embedding) != expected_dimension for embedding in embeddings_list):
            raise ValueError(f'All embeddings must have the selected dimension {expected_dimension}')

        values = []
        for index, vector_id in enumerate(ids):
            metadata = metadatas[index]
            document = documents[index] if documents is not None else None
            values.append(
                {
                    'workspace_uuid': scope.workspace_uuid,
                    'knowledge_base_uuid': scope.knowledge_base_uuid,
                    'vector_id': vector_id.strip(),
                    'embedding_dimension': expected_dimension,
                    'embedding': embeddings_list[index],
                    'text': metadata.get('text', document or ''),
                    'file_id': metadata.get('file_id', ''),
                    'chunk_uuid': metadata.get('uuid', metadata.get('chunk_uuid', '')),
                }
            )

        statement = postgresql_insert(PgVectorEntry).values(values)
        excluded = statement.excluded
        statement = statement.on_conflict_do_update(
            index_elements=[
                PgVectorEntry.workspace_uuid,
                PgVectorEntry.knowledge_base_uuid,
                PgVectorEntry.vector_id,
            ],
            set_={
                'embedding_dimension': excluded.embedding_dimension,
                'embedding': excluded.embedding,
                'text': excluded.text,
                'file_id': excluded.file_id,
                'chunk_uuid': excluded.chunk_uuid,
            },
        )
        async with self._session(scope) as session:
            await session.execute(statement)
        self.ap.logger.info(f'Upserted {len(ids)} pgvector embeddings for knowledge base {scope.knowledge_base_uuid}')

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        k: int = 5,
        search_type: str = 'vector',
        query_text: str = '',
        filter: dict[str, Any] | None = None,
        vector_weight: float | None = None,
        *,
        scope: PgVectorScope | None = None,
    ) -> dict[str, Any]:
        del query_text, vector_weight
        scope = self._require_scope(scope, require_dimension=True)
        await self.get_or_create_collection(collection)
        if search_type != 'vector':
            raise ValueError('pgvector currently supports vector search only')
        if k <= 0:
            raise ValueError('pgvector search limit must be positive')
        if len(query_embedding) != scope.embedding_dimension:
            raise ValueError(f'Query embedding must have the selected dimension {scope.embedding_dimension}')

        typed_embedding = sqlalchemy.cast(PgVectorEntry.embedding, Vector(scope.embedding_dimension))
        distance = typed_embedding.cosine_distance(query_embedding)
        statement = (
            sqlalchemy.select(
                PgVectorEntry.vector_id,
                PgVectorEntry.text,
                PgVectorEntry.file_id,
                PgVectorEntry.chunk_uuid,
                distance.label('distance'),
            )
            .where(*self._scope_conditions(scope), PgVectorEntry.embedding_dimension == scope.embedding_dimension)
            .order_by(distance)
            .limit(k)
        )
        for condition in _build_pg_conditions(filter or {}):
            statement = statement.where(condition)

        async with self._session(scope) as session:
            rows = (await session.execute(statement)).all()

        ids = [row.vector_id for row in rows]
        distances = [float(row.distance) for row in rows]
        metadatas = [
            {'text': row.text or '', 'file_id': row.file_id or '', 'uuid': row.chunk_uuid or ''} for row in rows
        ]
        return {'ids': [ids], 'distances': [distances], 'metadatas': [metadatas]}

    async def delete_by_file_id(
        self,
        collection: str,
        file_id: str,
        *,
        scope: PgVectorScope | None = None,
    ) -> None:
        scope = self._require_scope(scope, require_dimension=False)
        await self.get_or_create_collection(collection)
        statement = sqlalchemy.delete(PgVectorEntry).where(
            *self._scope_conditions(scope),
            PgVectorEntry.file_id == file_id,
        )
        async with self._session(scope) as session:
            await session.execute(statement)

    async def delete_by_filter(
        self,
        collection: str,
        filter: dict[str, Any],
        *,
        scope: PgVectorScope | None = None,
    ) -> int:
        scope = self._require_scope(scope, require_dimension=False)
        await self.get_or_create_collection(collection)
        conditions = _build_pg_conditions(filter)
        if not conditions:
            self.ap.logger.warning('pgvector delete_by_filter produced no supported conditions; skipping')
            return 0
        statement = sqlalchemy.delete(PgVectorEntry).where(*self._scope_conditions(scope), *conditions)
        async with self._session(scope) as session:
            result = await session.execute(statement)
        return int(result.rowcount or 0)

    async def list_by_filter(
        self,
        collection: str,
        filter: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
        *,
        scope: PgVectorScope | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        scope = self._require_scope(scope, require_dimension=False)
        await self.get_or_create_collection(collection)
        if limit <= 0 or offset < 0:
            raise ValueError('pgvector pagination requires limit > 0 and offset >= 0')

        conditions = [*self._scope_conditions(scope), *_build_pg_conditions(filter or {})]
        statement = (
            sqlalchemy.select(
                PgVectorEntry.vector_id,
                PgVectorEntry.text,
                PgVectorEntry.file_id,
                PgVectorEntry.chunk_uuid,
            )
            .where(*conditions)
            .order_by(PgVectorEntry.vector_id)
            .offset(offset)
            .limit(limit)
        )
        count_statement = sqlalchemy.select(sqlalchemy.func.count()).select_from(PgVectorEntry).where(*conditions)
        async with self._session(scope) as session:
            rows = (await session.execute(statement)).all()
            total = int((await session.execute(count_statement)).scalar_one())

        return (
            [
                {
                    'id': row.vector_id,
                    'document': row.text or '',
                    'metadata': {
                        'text': row.text or '',
                        'file_id': row.file_id or '',
                        'uuid': row.chunk_uuid or '',
                    },
                }
                for row in rows
            ],
            total,
        )

    async def delete_collection(
        self,
        collection: str,
        *,
        scope: PgVectorScope | None = None,
    ) -> None:
        scope = self._require_scope(scope, require_dimension=False)
        await self.get_or_create_collection(collection)
        statement = sqlalchemy.delete(PgVectorEntry).where(*self._scope_conditions(scope))
        async with self._session(scope) as session:
            await session.execute(statement)

    async def close(self) -> None:
        if not self.use_business_database and self.async_engine is not None:
            await self.async_engine.dispose()
        if self.engine is not None:
            self.engine.dispose()
