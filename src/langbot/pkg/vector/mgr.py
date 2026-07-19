from __future__ import annotations

import uuid

import sqlalchemy

from ..api.http.authz import WorkspaceRequiredError
from ..api.http.context import ExecutionContext
from ..core import app
from ..entity.persistence import rag as persistence_rag
from ..entity.persistence import workspace as persistence_workspace
from ..workspace.errors import WorkspaceNotFoundError
from .vdb import VectorDatabase, SearchType


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
                from .vdbs.chroma import ChromaVectorDatabase

                self.vector_db = ChromaVectorDatabase(self.ap)
                self.ap.logger.info('Initialized Chroma vector database backend.')

            elif vdb_type == 'qdrant':
                from .vdbs.qdrant import QdrantVectorDatabase

                self.vector_db = QdrantVectorDatabase(self.ap)
                self.ap.logger.info('Initialized Qdrant vector database backend.')
            elif vdb_type == 'seekdb':
                from .vdbs.seekdb import SeekDBVectorDatabase

                self.vector_db = SeekDBVectorDatabase(self.ap)
                self.ap.logger.info('Initialized SeekDB vector database backend.')

            elif vdb_type == 'valkey_search':
                from .vdbs.valkey_search import ValkeySearchVectorDatabase

                self.vector_db = ValkeySearchVectorDatabase(self.ap)
                self.ap.logger.info('Initialized Valkey Search vector database backend.')

            elif vdb_type == 'milvus':
                from .vdbs.milvus import MilvusVectorDatabase

                # Get Milvus configuration
                milvus_config = kb_config.get('milvus', {})
                uri = milvus_config.get('uri', './data/milvus.db')
                token = milvus_config.get('token')
                db_name = milvus_config.get('db_name', 'default')
                self.vector_db = MilvusVectorDatabase(self.ap, uri=uri, token=token, db_name=db_name)
                self.ap.logger.info('Initialized Milvus vector database backend.')

            elif vdb_type == 'pgvector':
                from .vdbs.pgvector_db import PgVectorDatabase

                # Get pgvector configuration
                pgvector_config = kb_config.get('pgvector', {})
                use_business_database = pgvector_config.get('use_business_database', False)
                allowed_dimensions = pgvector_config.get(
                    'allowed_dimensions',
                    [384, 512, 768, 1024, 1536],
                )
                common_options = {
                    'use_business_database': use_business_database,
                    'allowed_dimensions': allowed_dimensions,
                }
                if use_business_database:
                    self.vector_db = PgVectorDatabase(self.ap, **common_options)
                    self.ap.logger.info('Initialized pgvector on the shared business PostgreSQL database.')
                    return
                connection_string = pgvector_config.get('connection_string')
                if connection_string:
                    self.vector_db = PgVectorDatabase(
                        self.ap,
                        connection_string=connection_string,
                        **common_options,
                    )
                else:
                    # Use individual parameters
                    host = pgvector_config.get('host', 'localhost')
                    port = pgvector_config.get('port', 5432)
                    database = pgvector_config.get('database', 'langbot')
                    user = pgvector_config.get('user', 'postgres')
                    password = pgvector_config.get('password', 'postgres')
                    self.vector_db = PgVectorDatabase(
                        self.ap,
                        host=host,
                        port=port,
                        database=database,
                        user=user,
                        password=password,
                        **common_options,
                    )
                self.ap.logger.info('Initialized pgvector database backend.')

            else:
                from .vdbs.chroma import ChromaVectorDatabase

                self.vector_db = ChromaVectorDatabase(self.ap)
                self.ap.logger.warning('No valid vector database backend configured, defaulting to Chroma.')
        else:
            from .vdbs.chroma import ChromaVectorDatabase

            self.vector_db = ChromaVectorDatabase(self.ap)
            self.ap.logger.warning('No vector database backend configured, defaulting to Chroma.')

    def get_supported_search_types(self) -> list[str]:
        """Return the search types supported by the current VDB backend."""
        if self.vector_db is None:
            return [SearchType.VECTOR.value]
        return [st.value for st in self.vector_db.supported_search_types()]

    @staticmethod
    def physical_collection_name(
        execution_context: ExecutionContext,
        knowledge_base_uuid: str,
    ) -> str:
        """Derive an opaque physical collection from trusted tenant identity.

        Vector backends have different collection-name constraints, so the
        instance, Workspace and knowledge-base identifiers are encoded through
        UUIDv5 instead of being concatenated into a client-visible handle.
        Placement generation is deliberately not part of the name: generation
        fencing rejects stale work while preserving data across placements.
        """

        if not isinstance(execution_context, ExecutionContext):
            raise WorkspaceRequiredError('ExecutionContext is required for vector access')
        instance_uuid = execution_context.instance_uuid.strip()
        workspace_uuid = execution_context.workspace_uuid.strip()
        kb_uuid = knowledge_base_uuid.strip() if isinstance(knowledge_base_uuid, str) else ''
        if not instance_uuid or not workspace_uuid or not kb_uuid:
            raise WorkspaceRequiredError('Instance, Workspace and knowledge-base context are required')
        if execution_context.placement_generation <= 0:
            raise WorkspaceRequiredError('A positive placement generation is required')

        collection_uuid = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f'langbot:knowledge-vector:{instance_uuid}:{workspace_uuid}:{kb_uuid}',
        )
        return f'lb_{collection_uuid.hex}'

    async def _validate_execution_context(self, execution_context: ExecutionContext) -> None:
        """Validate the active placement before touching a vector backend."""

        # Also performs structural validation before accessing app services.
        self.physical_collection_name(execution_context, 'context-validation')
        workspace_service = getattr(self.ap, 'workspace_service', None)
        if workspace_service is None:
            raise WorkspaceRequiredError('Workspace execution service is unavailable')
        binding = await workspace_service.get_execution_binding(
            execution_context.workspace_uuid,
            expected_generation=execution_context.placement_generation,
        )
        if binding.instance_uuid != execution_context.instance_uuid:
            raise WorkspaceRequiredError('ExecutionContext belongs to another LangBot instance')

    async def _resolve_physical_collection_name(
        self,
        execution_context: ExecutionContext,
        knowledge_base_uuid: str,
    ) -> str:
        """Resolve a scoped collection or an explicitly migrated OSS handle.

        Legacy handles are server-owned migration state, not caller input.
        They are honored only for the one local Workspace under the OSS
        single-Workspace policy.  A projected/cloud Workspace always gets the
        opaque tenant-derived collection, even if its database row was
        incorrectly marked as legacy.
        """

        await self._validate_execution_context(execution_context)
        async with self.ap.persistence_mgr.tenant_uow(execution_context.workspace_uuid):
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(
                    persistence_rag.KnowledgeBase.collection_id,
                    persistence_rag.KnowledgeBase.legacy_vector_collection,
                    persistence_workspace.Workspace.source,
                )
                .join(
                    persistence_workspace.Workspace,
                    persistence_workspace.Workspace.uuid == persistence_rag.KnowledgeBase.workspace_uuid,
                )
                .where(
                    persistence_rag.KnowledgeBase.workspace_uuid == execution_context.workspace_uuid,
                    persistence_rag.KnowledgeBase.uuid == knowledge_base_uuid,
                    persistence_workspace.Workspace.instance_uuid == execution_context.instance_uuid,
                )
                .limit(1)
            )
        row = result.first()
        if row is None:
            raise WorkspaceNotFoundError('Knowledge base not found')

        collection_id, legacy_vector_collection, workspace_source = row
        if legacy_vector_collection:
            policy = getattr(self.ap, 'workspace_policy', None)
            is_single_workspace = policy is not None and not getattr(
                policy,
                'multi_workspace_enabled',
                True,
            )
            is_local_workspace = workspace_source == persistence_workspace.WorkspaceSource.LOCAL.value
            if is_single_workspace and is_local_workspace and isinstance(collection_id, str) and collection_id.strip():
                return collection_id
            self.ap.logger.warning(
                'Ignored a legacy vector collection marker outside the local single-Workspace compatibility boundary.'
            )

        return self.physical_collection_name(execution_context, knowledge_base_uuid)

    def _pgvector_database(self):
        from .vdbs.pgvector_db import PgVectorDatabase

        return self.vector_db if isinstance(self.vector_db, PgVectorDatabase) else None

    async def _resolve_pgvector_scope(
        self,
        execution_context: ExecutionContext,
        knowledge_base_uuid: str,
        *,
        expected_dimension: int | None,
        initialize_dimension: bool,
    ):
        """Bind and verify the server-owned knowledge-base vector dimension."""

        from .vdbs.pgvector_db import PgVectorScope

        pgvector = self._pgvector_database()
        if pgvector is None:  # pragma: no cover - private call invariant
            raise RuntimeError('pgvector scope requested for another vector backend')
        if expected_dimension is not None and expected_dimension not in pgvector.allowed_dimensions:
            raise ValueError(f'Embedding dimension {expected_dimension} is not enabled for this deployment')

        async with self.ap.persistence_mgr.tenant_uow(execution_context.workspace_uuid):
            query = sqlalchemy.select(persistence_rag.KnowledgeBase.embedding_dimension).where(
                persistence_rag.KnowledgeBase.workspace_uuid == execution_context.workspace_uuid,
                persistence_rag.KnowledgeBase.uuid == knowledge_base_uuid,
            )
            current_dimension = (await self.ap.persistence_mgr.execute_async(query)).scalar_one_or_none()
            if current_dimension is None and expected_dimension is not None and initialize_dimension:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.update(persistence_rag.KnowledgeBase)
                    .where(
                        persistence_rag.KnowledgeBase.workspace_uuid == execution_context.workspace_uuid,
                        persistence_rag.KnowledgeBase.uuid == knowledge_base_uuid,
                        persistence_rag.KnowledgeBase.embedding_dimension.is_(None),
                    )
                    .values(embedding_dimension=expected_dimension)
                )
                current_dimension = (await self.ap.persistence_mgr.execute_async(query)).scalar_one_or_none()

            if expected_dimension is not None and current_dimension != expected_dimension:
                if current_dimension is None:
                    raise ValueError('Knowledge base has no selected pgvector embedding dimension')
                raise ValueError(f'Knowledge base embedding dimension is {current_dimension}, not {expected_dimension}')

        return PgVectorScope(
            workspace_uuid=execution_context.workspace_uuid,
            knowledge_base_uuid=knowledge_base_uuid,
            embedding_dimension=current_dimension,
        )

    async def upsert(
        self,
        execution_context: ExecutionContext,
        knowledge_base_uuid: str,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict] | None = None,
        documents: list[str] | None = None,
    ):
        """Upsert vectors into a server-derived tenant collection."""

        collection_name = await self._resolve_physical_collection_name(
            execution_context,
            knowledge_base_uuid,
        )
        source_metadata = metadata or [{} for _ in vectors]
        scoped_metadata = [
            {
                **item,
                '_langbot_instance_uuid': execution_context.instance_uuid,
                '_langbot_workspace_uuid': execution_context.workspace_uuid,
                '_langbot_knowledge_base_uuid': knowledge_base_uuid,
            }
            for item in source_metadata
        ]
        pgvector = self._pgvector_database()
        if pgvector is not None:
            if not vectors:
                return
            scope = await self._resolve_pgvector_scope(
                execution_context,
                knowledge_base_uuid,
                expected_dimension=len(vectors[0]),
                initialize_dimension=True,
            )
            await pgvector.add_embeddings(
                collection=collection_name,
                ids=ids,
                embeddings_list=vectors,
                metadatas=scoped_metadata,
                documents=documents,
                scope=scope,
            )
            return
        await self.vector_db.add_embeddings(
            collection=collection_name,
            ids=ids,
            embeddings_list=vectors,
            metadatas=scoped_metadata,
            documents=documents,
        )

    async def search(
        self,
        execution_context: ExecutionContext,
        knowledge_base_uuid: str,
        query_vector: list[float],
        limit: int,
        filter: dict | None = None,
        search_type: str = 'vector',
        query_text: str = '',
        vector_weight: float | None = None,
    ) -> list[dict]:
        """Proxy: Search vectors.

        Returns a list of dicts with keys: 'id', 'distance', 'metadata'.
        The underlying VectorDatabase.search returns Chroma-style format:
        { 'ids': [['id1']], 'distances': [[0.1]], 'metadatas': [[{}]] }
        """
        collection_name = await self._resolve_physical_collection_name(
            execution_context,
            knowledge_base_uuid,
        )
        pgvector = self._pgvector_database()
        if pgvector is not None:
            scope = await self._resolve_pgvector_scope(
                execution_context,
                knowledge_base_uuid,
                expected_dimension=len(query_vector),
                initialize_dimension=False,
            )
            results = await pgvector.search(
                collection=collection_name,
                query_embedding=query_vector,
                k=limit,
                search_type=search_type,
                query_text=query_text,
                filter=filter,
                vector_weight=vector_weight,
                scope=scope,
            )
        else:
            results = await self.vector_db.search(
                collection=collection_name,
                query_embedding=query_vector,
                k=limit,
                search_type=search_type,
                query_text=query_text,
                filter=filter,
                vector_weight=vector_weight,
            )

        if not results or 'ids' not in results or not results['ids']:
            return []

        # Flatten nested lists (Chroma returns batch-style: list of lists)
        raw_ids = results['ids']
        raw_dists = results.get('distances', [])
        raw_metas = results.get('metadatas', [])

        r_ids = raw_ids[0] if raw_ids and isinstance(raw_ids[0], list) else raw_ids
        r_dists = raw_dists[0] if raw_dists and isinstance(raw_dists[0], list) else raw_dists
        r_metas = raw_metas[0] if raw_metas and isinstance(raw_metas[0], list) else raw_metas

        parsed_results = []
        for i, id_val in enumerate(r_ids):
            parsed_results.append(
                {
                    'id': id_val,
                    'distance': r_dists[i] if r_dists and i < len(r_dists) else 0.0,
                    'metadata': r_metas[i] if r_metas and i < len(r_metas) else {},
                }
            )

        return parsed_results

    async def delete_by_file_id(
        self,
        execution_context: ExecutionContext,
        knowledge_base_uuid: str,
        file_ids: list[str],
    ):
        """Proxy: Delete vectors by file_id (metadata-level identifier).

        This delegates to VectorDatabase.delete_by_file_id which removes
        all vectors associated with the given file IDs.
        """
        collection_name = await self._resolve_physical_collection_name(
            execution_context,
            knowledge_base_uuid,
        )
        pgvector = self._pgvector_database()
        scope = None
        if pgvector is not None:
            scope = await self._resolve_pgvector_scope(
                execution_context,
                knowledge_base_uuid,
                expected_dimension=None,
                initialize_dimension=False,
            )
        for file_id in file_ids:
            if pgvector is not None:
                await pgvector.delete_by_file_id(collection_name, file_id, scope=scope)
            else:
                await self.vector_db.delete_by_file_id(collection_name, file_id)

    async def delete_collection(
        self,
        execution_context: ExecutionContext,
        knowledge_base_uuid: str,
    ):
        """Delete one server-derived tenant collection."""

        collection_name = await self._resolve_physical_collection_name(
            execution_context,
            knowledge_base_uuid,
        )
        pgvector = self._pgvector_database()
        if pgvector is not None:
            scope = await self._resolve_pgvector_scope(
                execution_context,
                knowledge_base_uuid,
                expected_dimension=None,
                initialize_dimension=False,
            )
            await pgvector.delete_collection(collection_name, scope=scope)
        else:
            await self.vector_db.delete_collection(collection_name)

    async def delete_by_filter(
        self,
        execution_context: ExecutionContext,
        knowledge_base_uuid: str,
        filter: dict,
    ) -> int:
        """Proxy: Delete vectors by metadata filter.

        Returns:
            Number of deleted vectors (best-effort; some backends return 0).
        """
        collection_name = await self._resolve_physical_collection_name(
            execution_context,
            knowledge_base_uuid,
        )
        pgvector = self._pgvector_database()
        if pgvector is not None:
            scope = await self._resolve_pgvector_scope(
                execution_context,
                knowledge_base_uuid,
                expected_dimension=None,
                initialize_dimension=False,
            )
            return await pgvector.delete_by_filter(collection_name, filter, scope=scope)
        return await self.vector_db.delete_by_filter(collection_name, filter)

    async def list_by_filter(
        self,
        execution_context: ExecutionContext,
        knowledge_base_uuid: str,
        filter: dict | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Proxy: List vectors by metadata filter with pagination.

        Returns:
            Tuple of (items, total).
        """
        collection_name = await self._resolve_physical_collection_name(
            execution_context,
            knowledge_base_uuid,
        )
        pgvector = self._pgvector_database()
        if pgvector is not None:
            scope = await self._resolve_pgvector_scope(
                execution_context,
                knowledge_base_uuid,
                expected_dimension=None,
                initialize_dimension=False,
            )
            return await pgvector.list_by_filter(collection_name, filter, limit, offset, scope=scope)
        return await self.vector_db.list_by_filter(collection_name, filter, limit, offset)
