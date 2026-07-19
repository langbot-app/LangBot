from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from langbot.pkg.api.http.authz import WorkspaceRequiredError
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.service.knowledge import KnowledgeService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.rag import File, KnowledgeBase
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState
from langbot.pkg.rag.knowledge.kbmgr import RAGManager
from langbot.pkg.rag.service.runtime import RAGRuntimeService
from langbot.pkg.vector.mgr import VectorDBManager
from langbot.pkg.vector.vdbs.pgvector_db import PgVectorDatabase
from langbot.pkg.workspace.errors import WorkspaceNotFoundError
from langbot.pkg.workspace.policy import CloudWorkspacePolicy, SingleWorkspacePolicy
from langbot.pkg.workspace.service import WorkspaceService


pytestmark = pytest.mark.asyncio

INSTANCE_UUID = 'instance-rag-isolation'
WORKSPACE_A = '00000000-0000-0000-0000-00000000000a'
WORKSPACE_B = '00000000-0000-0000-0000-00000000000b'


class _PersistenceManager:
    def __init__(self, engine):
        self.engine = engine

    def get_db_engine(self):
        return self.engine

    async def execute_async(self, *args, **kwargs):
        async with self.engine.connect() as connection:
            result = await connection.execute(*args, **kwargs)
            await connection.commit()
            return result

    @asynccontextmanager
    async def tenant_uow(self, _workspace_uuid):
        # This lightweight fixture does not emulate PostgreSQL RLS; production
        # persistence tests cover the transaction-bound unit of work itself.
        async with AsyncSession(self.engine, expire_on_commit=False) as session, session.begin():
            yield SimpleNamespace(session=session)

    @staticmethod
    def serialize_model(model, row, masked_columns=()):
        return {
            column.name: (
                getattr(row, column.name).isoformat()
                if isinstance(getattr(row, column.name), datetime.datetime)
                else getattr(row, column.name)
            )
            for column in model.__table__.columns
            if column.name not in masked_columns
        }


class _RecordingVectorDatabase:
    def __init__(self):
        self.collections: list[str] = []
        self.metadatas: list[list[dict]] = []
        self.calls: list[tuple[str, str]] = []

    async def add_embeddings(self, *, collection, ids, embeddings_list, metadatas, documents):
        self.collections.append(collection)
        self.metadatas.append(metadatas)
        self.calls.append(('upsert', collection))

    async def search(self, *, collection, **_kwargs):
        self.calls.append(('search', collection))
        return {'ids': [[]], 'distances': [[]], 'metadatas': [[]]}

    async def delete_by_file_id(self, collection, _file_id):
        self.calls.append(('delete_by_file_id', collection))

    async def delete_collection(self, collection):
        self.calls.append(('delete_collection', collection))

    async def delete_by_filter(self, collection, _filter):
        self.calls.append(('delete_by_filter', collection))
        return 1

    async def list_by_filter(self, collection, _filter, _limit, _offset):
        self.calls.append(('list_by_filter', collection))
        return [], 0


@pytest.fixture
async def tenant_rag(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "rag-tenant.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            sqlalchemy.insert(Workspace),
            [
                {
                    'uuid': WORKSPACE_A,
                    'instance_uuid': INSTANCE_UUID,
                    'name': 'Workspace A',
                    'slug': 'workspace-a',
                    'source': 'local',
                },
                {
                    'uuid': WORKSPACE_B,
                    'instance_uuid': INSTANCE_UUID,
                    'name': 'Workspace B',
                    'slug': 'workspace-b',
                    'source': 'cloud_projection',
                },
            ],
        )
        await connection.execute(
            sqlalchemy.insert(WorkspaceExecutionState),
            [
                {
                    'workspace_uuid': WORKSPACE_A,
                    'instance_uuid': INSTANCE_UUID,
                    'active_generation': 3,
                    'state': 'active',
                    'source': 'local',
                    'write_fenced': False,
                },
                {
                    'workspace_uuid': WORKSPACE_B,
                    'instance_uuid': INSTANCE_UUID,
                    'active_generation': 3,
                    'state': 'active',
                    'source': 'cloud',
                    'write_fenced': False,
                },
            ],
        )
        await connection.execute(
            sqlalchemy.insert(KnowledgeBase),
            [
                {
                    'uuid': 'kb-a',
                    'workspace_uuid': WORKSPACE_A,
                    'name': 'Same Knowledge Base',
                    'description': 'A',
                    'knowledge_engine_plugin_id': 'author/engine',
                    'collection_id': 'kb-a',
                    'creation_settings': {},
                    'retrieval_settings': {},
                },
                {
                    'uuid': 'kb-b',
                    'workspace_uuid': WORKSPACE_B,
                    'name': 'Same Knowledge Base',
                    'description': 'B',
                    'knowledge_engine_plugin_id': 'author/engine',
                    'collection_id': 'kb-b',
                    'creation_settings': {},
                    'retrieval_settings': {},
                },
            ],
        )
        await connection.execute(
            sqlalchemy.insert(File),
            [
                {
                    'uuid': 'file-a',
                    'workspace_uuid': WORKSPACE_A,
                    'kb_id': 'kb-a',
                    'file_name': 'a.pdf',
                    'extension': 'pdf',
                },
                {
                    'uuid': 'file-b',
                    'workspace_uuid': WORKSPACE_B,
                    'kb_id': 'kb-b',
                    'file_name': 'b.pdf',
                    'extension': 'pdf',
                },
            ],
        )

    app = SimpleNamespace()
    app.persistence_mgr = _PersistenceManager(engine)
    app.logger = Mock()
    app.workspace_policy = SingleWorkspacePolicy()
    app.plugin_connector = SimpleNamespace(
        is_enable_plugin=False,
        rag_on_kb_create=AsyncMock(),
        rag_on_kb_delete=AsyncMock(),
    )
    app.workspace_service = WorkspaceService(app, instance_uuid=INSTANCE_UUID)
    app.rag_mgr = RAGManager(app)
    await app.rag_mgr.initialize()
    app.knowledge_service = KnowledgeService(app)

    yield app, engine
    await engine.dispose()


def _context(workspace_uuid: str) -> ExecutionContext:
    return ExecutionContext(
        instance_uuid=INSTANCE_UUID,
        workspace_uuid=workspace_uuid,
        placement_generation=3,
    )


async def test_context_is_mandatory_and_same_names_are_isolated(tenant_rag):
    app, _engine = tenant_rag

    with pytest.raises(WorkspaceRequiredError):
        await app.knowledge_service.get_knowledge_bases(None)

    bases_a = await app.knowledge_service.get_knowledge_bases(_context(WORKSPACE_A))
    bases_b = await app.knowledge_service.get_knowledge_bases(_context(WORKSPACE_B))
    assert [(item['uuid'], item['name']) for item in bases_a] == [('kb-a', 'Same Knowledge Base')]
    assert [(item['uuid'], item['name']) for item in bases_b] == [('kb-b', 'Same Knowledge Base')]


async def test_cross_workspace_uuid_and_file_guessing_return_not_found(tenant_rag):
    app, engine = tenant_rag
    context_a = _context(WORKSPACE_A)

    assert await app.knowledge_service.get_knowledge_base(context_a, 'kb-b') is None
    with pytest.raises(WorkspaceNotFoundError):
        await app.knowledge_service.update_knowledge_base(context_a, 'kb-b', {'name': 'stolen'})
    with pytest.raises(WorkspaceNotFoundError):
        await app.knowledge_service.delete_knowledge_base(context_a, 'kb-b')
    with pytest.raises(WorkspaceNotFoundError):
        await app.knowledge_service.get_files_by_knowledge_base(context_a, 'kb-b')
    with pytest.raises(WorkspaceNotFoundError):
        await app.knowledge_service.delete_file(context_a, 'kb-b', 'file-b')

    async with engine.connect() as connection:
        assert (
            await connection.scalar(sqlalchemy.select(KnowledgeBase.name).where(KnowledgeBase.uuid == 'kb-b'))
            == 'Same Knowledge Base'
        )
        assert await connection.scalar(sqlalchemy.select(File.uuid).where(File.uuid == 'file-b')) == 'file-b'


async def test_runtime_rejects_cross_workspace_collection_reference(tenant_rag):
    app, _engine = tenant_rag
    app.vector_db_mgr = SimpleNamespace(upsert=AsyncMock())
    service = RAGRuntimeService(app)

    with pytest.raises(WorkspaceNotFoundError):
        await service.vector_upsert(
            _context(WORKSPACE_A),
            'kb-b',
            vectors=[[0.1, 0.2]],
            ids=['chunk-1'],
        )
    app.vector_db_mgr.upsert.assert_not_awaited()


async def test_physical_vector_handles_do_not_collide_across_workspaces(tenant_rag):
    app, _engine = tenant_rag
    database = _RecordingVectorDatabase()
    manager = VectorDBManager(app)
    manager.vector_db = database

    context_a = _context(WORKSPACE_A)
    context_b = _context(WORKSPACE_B)
    assert manager.physical_collection_name(context_a, 'same-kb-id') != manager.physical_collection_name(
        context_b,
        'same-kb-id',
    )

    await manager.upsert(context_a, 'kb-a', [[0.1]], ['a'], metadata=[{'source': 'client'}])
    await manager.upsert(context_b, 'kb-b', [[0.2]], ['b'], metadata=[{'source': 'client'}])
    assert len(set(database.collections)) == 2
    assert database.metadatas[0][0]['_langbot_workspace_uuid'] == WORKSPACE_A
    assert database.metadatas[1][0]['_langbot_workspace_uuid'] == WORKSPACE_B


async def test_migrated_local_kb_keeps_legacy_collection_for_every_vector_operation(tenant_rag):
    app, engine = tenant_rag
    legacy_collection = 'legacy-collection-kb-a'
    async with engine.begin() as connection:
        await connection.execute(
            sqlalchemy.update(KnowledgeBase)
            .where(KnowledgeBase.uuid == 'kb-a')
            .values(
                collection_id=legacy_collection,
                legacy_vector_collection=True,
            )
        )

    database = _RecordingVectorDatabase()
    manager = VectorDBManager(app)
    manager.vector_db = database
    context = _context(WORKSPACE_A)

    await manager.upsert(context, 'kb-a', [[0.1]], ['chunk-a'])
    await manager.search(context, 'kb-a', [0.1], 3)
    await manager.delete_by_file_id(context, 'kb-a', ['file-a'])
    assert await manager.delete_by_filter(context, 'kb-a', {'file_id': 'file-a'}) == 1
    assert await manager.list_by_filter(context, 'kb-a', {'file_id': 'file-a'}) == ([], 0)
    await manager.delete_collection(context, 'kb-a')

    assert database.calls == [
        ('upsert', legacy_collection),
        ('search', legacy_collection),
        ('delete_by_file_id', legacy_collection),
        ('delete_by_filter', legacy_collection),
        ('list_by_filter', legacy_collection),
        ('delete_collection', legacy_collection),
    ]


@pytest.mark.parametrize('deny_by', ['projected_workspace', 'multi_workspace_policy'])
async def test_legacy_marker_is_ignored_outside_single_local_workspace(tenant_rag, deny_by):
    app, engine = tenant_rag
    workspace_uuid = WORKSPACE_B if deny_by == 'projected_workspace' else WORKSPACE_A
    kb_uuid = 'kb-b' if deny_by == 'projected_workspace' else 'kb-a'
    legacy_collection = f'legacy-{deny_by}'
    async with engine.begin() as connection:
        await connection.execute(
            sqlalchemy.update(KnowledgeBase)
            .where(KnowledgeBase.uuid == kb_uuid)
            .values(
                collection_id=legacy_collection,
                legacy_vector_collection=True,
            )
        )
    if deny_by == 'multi_workspace_policy':
        app.workspace_policy = CloudWorkspacePolicy()

    database = _RecordingVectorDatabase()
    manager = VectorDBManager(app)
    manager.vector_db = database
    context = _context(workspace_uuid)
    await manager.search(context, kb_uuid, [0.1], 3)

    assert database.calls == [('search', manager.physical_collection_name(context, kb_uuid))]
    assert database.calls[0][1] != legacy_collection
    app.logger.warning.assert_called_once()


async def test_stale_generation_is_rejected_before_vector_access(tenant_rag):
    app, _engine = tenant_rag
    database = _RecordingVectorDatabase()
    manager = VectorDBManager(app)
    manager.vector_db = database
    stale = ExecutionContext(
        instance_uuid=INSTANCE_UUID,
        workspace_uuid=WORKSPACE_A,
        placement_generation=2,
    )

    with pytest.raises(Exception, match='generation'):
        await manager.upsert(stale, 'kb-a', [[0.1]], ['a'])
    assert database.collections == []


async def test_pgvector_first_write_binds_dimension_and_later_mismatch_fails(tenant_rag):
    app, engine = tenant_rag
    manager = VectorDBManager(app)
    pgvector = object.__new__(PgVectorDatabase)
    pgvector.allowed_dimensions = frozenset({1, 2})
    pgvector.add_embeddings = AsyncMock()
    pgvector.search = AsyncMock(return_value={'ids': [[]], 'distances': [[]], 'metadatas': [[]]})
    manager.vector_db = pgvector
    context = _context(WORKSPACE_A)

    await manager.upsert(context, 'kb-a', [[0.1]], ['chunk-a'])
    scope = pgvector.add_embeddings.await_args.kwargs['scope']
    assert scope.workspace_uuid == WORKSPACE_A
    assert scope.knowledge_base_uuid == 'kb-a'
    assert scope.embedding_dimension == 1

    async with engine.connect() as connection:
        selected_dimension = await connection.scalar(
            sqlalchemy.select(KnowledgeBase.embedding_dimension).where(
                KnowledgeBase.workspace_uuid == WORKSPACE_A,
                KnowledgeBase.uuid == 'kb-a',
            )
        )
    assert selected_dimension == 1

    with pytest.raises(ValueError, match='dimension is 1, not 2'):
        await manager.upsert(context, 'kb-a', [[0.1, 0.2]], ['chunk-b'])
    with pytest.raises(ValueError, match='not enabled'):
        await manager.search(context, 'kb-a', [0.1, 0.2, 0.3], 3)
