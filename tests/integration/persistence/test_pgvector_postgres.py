"""Real PostgreSQL/pgvector tenant isolation and CRUD verification."""

from __future__ import annotations

import logging
import os
import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.rag import KnowledgeBase
from langbot.pkg.entity.persistence.workspace import Workspace
from langbot.pkg.persistence.alembic_runner import get_alembic_current, run_alembic_stamp, run_alembic_upgrade
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.utils import constants
from langbot.pkg.vector.vdbs.pgvector_db import PgVectorDatabase, PgVectorEntry, PgVectorScope


pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.asyncio]


def _application(postgres_url: str, logger_name: str) -> SimpleNamespace:
    url = sa.engine.make_url(postgres_url)
    return SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'database': {
                    'use': 'postgresql',
                    'postgresql': {
                        'host': url.host,
                        'port': url.port,
                        'user': url.username,
                        'password': url.password,
                        'database': url.database,
                    },
                }
            }
        ),
        logger=logging.getLogger(logger_name),
    )


def _restore_postgres_registry(monkeypatch) -> None:
    from langbot.pkg.persistence import mgr as persistence_mgr_module
    from langbot.pkg.persistence.databases.postgresql import PostgreSQLDatabaseManager

    monkeypatch.setattr(
        persistence_mgr_module.database,
        'preregistered_managers',
        [PostgreSQLDatabaseManager],
    )


@pytest.fixture
def postgres_url() -> str:
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL not set')
    return url


@pytest.fixture
async def postgres_engine(postgres_url: str):
    engine = create_async_engine(postgres_url, isolation_level='AUTOCOMMIT')
    yield engine
    await engine.dispose()


@pytest.fixture
async def clean_database(postgres_engine: AsyncEngine):
    async def clean() -> None:
        async with postgres_engine.begin() as conn:
            await conn.execute(text('DROP TABLE IF EXISTS langbot_vectors_legacy_0013 CASCADE'))
            await conn.execute(text('DROP TABLE IF EXISTS langbot_vectors CASCADE'))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.execute(text('DROP TABLE IF EXISTS alembic_version'))

    await clean()
    yield
    await clean()


async def test_legacy_upgrade_temporarily_suspends_and_restores_source_rls_for_unprivileged_owner(
    postgres_url: str,
    postgres_engine: AsyncEngine,
    clean_database,
) -> None:
    workspace_uuid = '30000000-0000-0000-0000-000000000303'
    knowledge_base_uuid = 'legacy-knowledge-base'
    migrator_role = f'lb_vector_migrator_{uuid.uuid4().hex[:12]}'
    migrator_password = f'Lb{uuid.uuid4().hex}'
    quote = postgres_engine.dialect.identifier_preparer.quote
    database_name = sa.engine.make_url(postgres_url).database
    migrator_url = (
        sa.engine.make_url(postgres_url)
        .set(username=migrator_role, password=migrator_password)
        .render_as_string(hide_password=False)
    )
    migrator_engine: AsyncEngine | None = None
    role_created = False
    admin_role: str | None = None
    source_tables = ('knowledge_bases', 'knowledge_base_files', 'knowledge_base_chunks')

    async def read_rls_states(conn, table_names: tuple[str, ...]) -> dict[str, tuple[bool, bool]]:
        rows = (
            (
                await conn.execute(
                    text(
                        """
                        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                        FROM pg_class AS c
                        JOIN pg_namespace AS n ON n.oid = c.relnamespace
                        WHERE n.nspname = current_schema()
                          AND c.relname IN :table_names
                        """
                    ).bindparams(sa.bindparam('table_names', expanding=True)),
                    {'table_names': table_names},
                )
            )
            .mappings()
            .all()
        )
        return {str(row['relname']): (bool(row['relrowsecurity']), bool(row['relforcerowsecurity'])) for row in rows}

    try:
        async with postgres_engine.begin() as conn:
            admin_role = await conn.scalar(text('SELECT current_user'))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text(
                    'ALTER TABLE knowledge_bases DROP CONSTRAINT IF EXISTS '
                    'ck_knowledge_bases_embedding_dimension_positive'
                )
            )
            await conn.execute(text('ALTER TABLE knowledge_bases DROP COLUMN IF EXISTS embedding_dimension'))

        await run_alembic_stamp(postgres_engine, '0010_scope_resources')
        await run_alembic_upgrade(postgres_engine, '0012_plugin_identity')
        assert await get_alembic_current(postgres_engine) == '0012_plugin_identity'

        embedding_a = '[' + ','.join(['0.125'] * 384) + ']'
        embedding_b = '[' + ','.join(['0.25'] * 384) + ']'
        async with postgres_engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO workspaces
                        (uuid, instance_uuid, name, slug, type, status, source, projection_revision)
                    VALUES
                        (:uuid, 'legacy-vector-instance', 'legacy', 'legacy-vector',
                         'team', 'active', 'cloud_projection', 0)
                    """
                ),
                {'uuid': workspace_uuid},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO knowledge_bases
                        (uuid, workspace_uuid, name, collection_id, legacy_vector_collection)
                    VALUES
                        (:uuid, :workspace_uuid, 'legacy', 'legacy-collection', true)
                    """
                ),
                {'uuid': knowledge_base_uuid, 'workspace_uuid': workspace_uuid},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO knowledge_base_files
                        (uuid, workspace_uuid, kb_id, file_name, extension, status)
                    VALUES
                        ('legacy-file', :workspace_uuid, :kb_uuid, 'legacy.txt', 'txt', 'completed')
                    """
                ),
                {'workspace_uuid': workspace_uuid, 'kb_uuid': knowledge_base_uuid},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO knowledge_base_chunks (uuid, workspace_uuid, file_id, text)
                    VALUES ('legacy-chunk', :workspace_uuid, 'legacy-file', 'chunk text')
                    """
                ),
                {'workspace_uuid': workspace_uuid},
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE langbot_vectors (
                        id VARCHAR(255) PRIMARY KEY,
                        collection VARCHAR(255),
                        embedding vector NOT NULL,
                        text TEXT,
                        file_id VARCHAR(255),
                        chunk_uuid VARCHAR(255)
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO langbot_vectors
                        (id, collection, embedding, text, file_id, chunk_uuid)
                    VALUES
                        ('legacy-by-collection', 'legacy-collection', CAST(:embedding_a AS vector),
                         'collection row', NULL, NULL),
                        ('legacy-by-chunk', 'unmatched-collection', CAST(:embedding_b AS vector),
                         'chunk row', NULL, 'legacy-chunk')
                    """
                ),
                {'embedding_a': embedding_a, 'embedding_b': embedding_b},
            )

            # Exercise exact restoration rather than assuming all source tables
            # arrived with identical flags.
            await conn.execute(text('ALTER TABLE knowledge_base_files NO FORCE ROW LEVEL SECURITY'))
            await conn.execute(text('ALTER TABLE knowledge_base_chunks NO FORCE ROW LEVEL SECURITY'))
            await conn.execute(text('ALTER TABLE knowledge_base_chunks DISABLE ROW LEVEL SECURITY'))
            expected_source_rls = await read_rls_states(conn, source_tables)
            assert expected_source_rls == {
                'knowledge_bases': (True, True),
                'knowledge_base_files': (True, False),
                'knowledge_base_chunks': (False, False),
            }

            await conn.execute(
                text(f"CREATE ROLE {quote(migrator_role)} LOGIN PASSWORD '{migrator_password}' NOSUPERUSER NOBYPASSRLS")
            )
            role_created = True
            await conn.execute(text(f'GRANT CONNECT ON DATABASE {quote(database_name)} TO {quote(migrator_role)}'))
            await conn.execute(text(f'GRANT USAGE, CREATE ON SCHEMA public TO {quote(migrator_role)}'))
            await conn.execute(text(f'GRANT SELECT, UPDATE ON alembic_version TO {quote(migrator_role)}'))
            for table_name in (*source_tables, 'langbot_vectors'):
                await conn.execute(text(f'ALTER TABLE {quote(table_name)} OWNER TO {quote(migrator_role)}'))

            role = (
                await conn.execute(
                    text('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :role'),
                    {'role': migrator_role},
                )
            ).one()
            assert role == (False, False)
            owned_tables = set(
                (
                    await conn.execute(
                        text(
                            """
                            SELECT c.relname
                            FROM pg_class AS c
                            JOIN pg_namespace AS n ON n.oid = c.relnamespace
                            WHERE n.nspname = current_schema()
                              AND c.relname IN :table_names
                              AND pg_get_userbyid(c.relowner) = :role
                            """
                        ).bindparams(sa.bindparam('table_names', expanding=True)),
                        {'table_names': (*source_tables, 'langbot_vectors'), 'role': migrator_role},
                    )
                ).scalars()
            )
            assert owned_tables == {*source_tables, 'langbot_vectors'}

        migrator_engine = create_async_engine(migrator_url)
        await run_alembic_upgrade(migrator_engine, '0013_tenant_pgvector')
        assert await get_alembic_current(migrator_engine) == '0013_tenant_pgvector'

        async with postgres_engine.connect() as conn:
            migrated_rows = (
                (
                    await conn.execute(
                        text(
                            """
                            SELECT workspace_uuid, knowledge_base_uuid, vector_id,
                                   embedding_dimension, text, file_id, chunk_uuid
                            FROM langbot_vectors
                            ORDER BY vector_id
                            """
                        )
                    )
                )
                .mappings()
                .all()
            )
            assert [dict(row) for row in migrated_rows] == [
                {
                    'workspace_uuid': workspace_uuid,
                    'knowledge_base_uuid': knowledge_base_uuid,
                    'vector_id': 'legacy-by-chunk',
                    'embedding_dimension': 384,
                    'text': 'chunk row',
                    'file_id': None,
                    'chunk_uuid': 'legacy-chunk',
                },
                {
                    'workspace_uuid': workspace_uuid,
                    'knowledge_base_uuid': knowledge_base_uuid,
                    'vector_id': 'legacy-by-collection',
                    'embedding_dimension': 384,
                    'text': 'collection row',
                    'file_id': None,
                    'chunk_uuid': None,
                },
            ]
            assert (
                await conn.scalar(
                    text('SELECT embedding_dimension FROM knowledge_bases WHERE uuid = :uuid'),
                    {'uuid': knowledge_base_uuid},
                )
                == 384
            )
            assert await conn.scalar(text("SELECT to_regclass('langbot_vectors_legacy_0013') IS NULL")) is True
            assert await read_rls_states(conn, source_tables) == expected_source_rls
            assert await read_rls_states(conn, ('langbot_vectors',)) == {'langbot_vectors': (True, True)}
            assert (
                await conn.scalar(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM pg_policy AS p
                        JOIN pg_class AS c ON c.oid = p.polrelid
                        JOIN pg_namespace AS n ON n.oid = c.relnamespace
                        WHERE n.nspname = current_schema()
                          AND c.relname = 'langbot_vectors'
                          AND p.polname = 'langbot_workspace_isolation'
                        """
                    )
                )
                == 1
            )

        async with migrator_engine.connect() as conn:
            assert await conn.scalar(text('SELECT COUNT(*) FROM langbot_vectors')) == 0
        async with migrator_engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('langbot.workspace_uuid', :workspace_uuid, true)"),
                {'workspace_uuid': workspace_uuid},
            )
            assert await conn.scalar(text('SELECT COUNT(*) FROM langbot_vectors')) == 2
    finally:
        if migrator_engine is not None:
            await migrator_engine.dispose()
        if role_created:
            async with postgres_engine.connect() as conn:
                if admin_role is None:  # pragma: no cover - setup cannot create the role without an admin
                    admin_role = await conn.scalar(text('SELECT current_user'))
                await conn.execute(text(f'REASSIGN OWNED BY {quote(migrator_role)} TO {quote(admin_role)}'))
                await conn.execute(text(f'DROP OWNED BY {quote(migrator_role)}'))
                await conn.execute(text(f'DROP ROLE IF EXISTS {quote(migrator_role)}'))


async def test_pgvector_shared_database_is_scoped_indexed_and_ddl_free_at_runtime(
    postgres_url: str,
    postgres_engine: AsyncEngine,
    clean_database,
    monkeypatch,
) -> None:
    instance_uuid = 'pgvector-tenant-integration'
    workspace_a = '10000000-0000-0000-0000-000000000101'
    workspace_b = '20000000-0000-0000-0000-000000000202'
    kb_a = 'knowledge-base-a'
    kb_b = 'knowledge-base-b'
    role_suffix = uuid.uuid4().hex[:12]
    runtime_role = f'lb_vector_runtime_{role_suffix}'
    role_password = f'Lb{uuid.uuid4().hex}'
    release_manager: PersistenceManager | None = None
    runtime_manager: PersistenceManager | None = None
    role_created = False

    _restore_postgres_registry(monkeypatch)
    monkeypatch.setattr(constants, 'instance_id', instance_uuid)
    quote = postgres_engine.dialect.identifier_preparer.quote
    database_name = sa.engine.make_url(postgres_url).database
    runtime_url = (
        sa.engine.make_url(postgres_url)
        .set(username=runtime_role, password=role_password)
        .render_as_string(hide_password=False)
    )

    try:
        release_app = _application(postgres_url, 'pgvector-release-migration-test')
        release_manager = PersistenceManager(release_app, mode=PersistenceMode.RELEASE_MIGRATION)
        release_app.persistence_mgr = release_manager
        await release_manager.initialize()

        for workspace_uuid, kb_uuid, slug in (
            (workspace_a, kb_a, 'vector-a'),
            (workspace_b, kb_b, 'vector-b'),
        ):
            async with release_manager.tenant_uow(workspace_uuid) as uow:
                await uow.execute(
                    sa.insert(Workspace).values(
                        uuid=workspace_uuid,
                        instance_uuid=instance_uuid,
                        name=slug,
                        slug=slug,
                        type='team',
                        status='active',
                        source='cloud_projection',
                        projection_revision=0,
                    )
                )
                await uow.execute(
                    sa.insert(KnowledgeBase).values(
                        uuid=kb_uuid,
                        workspace_uuid=workspace_uuid,
                        name=slug,
                        embedding_dimension=384,
                    )
                )

        async with postgres_engine.connect() as conn:
            await conn.execute(text(f"CREATE ROLE {quote(runtime_role)} LOGIN PASSWORD '{role_password}'"))
            await conn.execute(text(f'GRANT CONNECT ON DATABASE {quote(database_name)} TO {quote(runtime_role)}'))
            await conn.execute(text(f'GRANT USAGE ON SCHEMA public TO {quote(runtime_role)}'))
            business_tables = release_manager._runtime_business_table_names()
            quoted_tables = ', '.join(f'public.{quote(table_name)}' for table_name in business_tables)
            await conn.execute(
                text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {quoted_tables} TO {quote(runtime_role)}')
            )
            await conn.execute(text(f'GRANT SELECT ON TABLE public.alembic_version TO {quote(runtime_role)}'))
            sequence_names = await release_manager._runtime_business_sequence_names(conn, business_tables)
            if sequence_names:
                quoted_sequences = ', '.join(f'public.{quote(sequence_name)}' for sequence_name in sequence_names)
                await conn.execute(text(f'GRANT USAGE, SELECT ON SEQUENCE {quoted_sequences} TO {quote(runtime_role)}'))
        role_created = True

        runtime_app = _application(runtime_url, 'pgvector-runtime-test')
        runtime_manager = PersistenceManager(runtime_app, mode=PersistenceMode.CLOUD_RUNTIME)
        runtime_app.persistence_mgr = runtime_manager
        await runtime_manager.initialize()

        adapter = PgVectorDatabase(
            runtime_app,
            use_business_database=True,
            allowed_dimensions=[384],
        )
        scope_a = PgVectorScope(workspace_a, kb_a, 384)
        scope_b = PgVectorScope(workspace_b, kb_b, 384)

        # The same vector ID is valid in two Workspaces because the relational
        # primary key includes Workspace and knowledge base.
        await adapter.add_embeddings(
            'opaque-a',
            ['same-vector'],
            [[0.1] * 384],
            [{'text': 'workspace-a', 'file_id': 'file-a', 'uuid': 'chunk-a'}],
            scope=scope_a,
        )
        await adapter.add_embeddings(
            'opaque-b',
            ['same-vector'],
            [[0.2] * 384],
            [{'text': 'workspace-b', 'file_id': 'file-b', 'uuid': 'chunk-b'}],
            scope=scope_b,
        )

        result_a = await adapter.search('opaque-a', [0.1] * 384, scope=scope_a)
        result_b = await adapter.search('opaque-b', [0.2] * 384, scope=scope_b)
        assert result_a['metadatas'][0][0]['text'] == 'workspace-a'
        assert result_b['metadatas'][0][0]['text'] == 'workspace-b'

        # Guessing another knowledge-base UUID while retaining A's Workspace
        # cannot escape either the explicit conditions or PostgreSQL RLS.
        guessed = await adapter.search(
            'attacker-controlled-name',
            [0.2] * 384,
            scope=PgVectorScope(workspace_a, kb_b, 384),
        )
        assert guessed['ids'] == [[]]

        with pytest.raises(ValueError, match='trusted PgVectorScope'):
            await adapter.search('opaque-a', [0.1] * 384)
        with pytest.raises(ValueError, match='selected dimension'):
            await adapter.add_embeddings(
                'opaque-a',
                ['bad-dimension'],
                [[0.1] * 383],
                [{}],
                scope=scope_a,
            )

        # Deliberately omit the application Workspace predicate. FORCE RLS is
        # still the second isolation boundary and returns only A.
        async with runtime_manager.tenant_uow(workspace_a) as uow:
            rows = (
                await uow.execute(
                    sa.select(PgVectorEntry.workspace_uuid, PgVectorEntry.vector_id).where(
                        PgVectorEntry.vector_id == 'same-vector'
                    )
                )
            ).all()
            assert rows == [(workspace_a, 'same-vector')]

        # Index-plan inspection is deployment diagnostics, not a public tenant
        # Session capability. Establish the same transaction-local RLS scope on
        # a test-only connection and keep raw EXPLAIN outside TenantUnitOfWork.
        runtime_engine = runtime_manager.get_db_engine()
        async with runtime_engine.begin() as conn:
            await conn.execute(
                text('SELECT set_config(:setting_name, :setting_value, true)'),
                {'setting_name': 'langbot.workspace_uuid', 'setting_value': workspace_a},
            )
            await conn.execute(text('SET LOCAL enable_seqscan = off'))
            plan = '\n'.join(
                (
                    await conn.execute(
                        text(
                            """
                            EXPLAIN SELECT vector_id
                            FROM langbot_vectors
                            WHERE workspace_uuid = :workspace_uuid
                              AND knowledge_base_uuid = :knowledge_base_uuid
                              AND embedding_dimension = 384
                            ORDER BY (embedding::vector(384)) <=> CAST(:query AS vector(384))
                            LIMIT 5
                            """
                        ),
                        {
                            'workspace_uuid': workspace_a,
                            'knowledge_base_uuid': kb_a,
                            'query': '[' + ','.join(['0.1'] * 384) + ']',
                        },
                    )
                ).scalars()
            )
            assert 'ix_langbot_vectors_hnsw_cosine_384' in plan

        async with runtime_engine.connect() as conn:
            assert await conn.scalar(text('SELECT COUNT(*) FROM langbot_vectors')) == 0
            assert await conn.scalar(text("SELECT current_setting('langbot.workspace_uuid', true)")) in (None, '')

        items_a, total_a = await adapter.list_by_filter('opaque-a', scope=scope_a)
        assert total_a == 1
        assert items_a[0]['metadata']['file_id'] == 'file-a'
        await adapter.delete_by_file_id('opaque-a', 'file-a', scope=scope_a)
        assert (await adapter.list_by_filter('opaque-a', scope=scope_a))[1] == 0
        assert (await adapter.list_by_filter('opaque-b', scope=scope_b))[1] == 1
    finally:
        if runtime_manager is not None and getattr(runtime_manager, 'db', None) is not None:
            await runtime_manager.get_db_engine().dispose()
        if release_manager is not None and getattr(release_manager, 'db', None) is not None:
            await release_manager.get_db_engine().dispose()
        if role_created:
            async with postgres_engine.connect() as conn:
                await conn.execute(text(f'DROP OWNED BY {quote(runtime_role)}'))
                await conn.execute(text(f'DROP ROLE IF EXISTS {quote(runtime_role)}'))
