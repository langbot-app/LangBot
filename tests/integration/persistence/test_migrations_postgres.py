"""
PostgreSQL migration integration tests.

Tests real Alembic migration behavior using PostgreSQL database.
Marked as slow - requires external PostgreSQL service.

Run locally (requires PostgreSQL):
    TEST_POSTGRES_URL=postgresql+asyncpg://user:pass@localhost:5432/test_db \
        uv run pytest tests/integration/persistence/test_migrations_postgres.py -q

CI runs automatically with PostgreSQL service container.
"""

from __future__ import annotations

import logging
import os
import uuid
import asyncio
import contextlib
import datetime
import hashlib
import typing
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from quart import Quart
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy import text

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.persistence.tenant_uow import (
    TENANT_POLICY_NAME,
    TENANT_TABLE_COLUMNS,
    ScopedSessionTransactionError,
    TenantUnitOfWork,
    TransactionRollbackOnlyError,
)
from langbot.pkg.persistence.alembic_runner import (
    run_alembic_upgrade,
    run_alembic_stamp,
    get_alembic_current,
    _ALEMBIC_DIR,
)
from alembic.config import Config
from alembic.script import ScriptDirectory
from langbot.pkg.utils import constants
from langbot.pkg.workspace.collaboration import normalize_email
from langbot.pkg.workspace.collaboration import WorkspaceCollaborationService
from langbot.pkg.workspace.policy import CloudWorkspacePolicy
from langbot.pkg.workspace.service import WorkspaceService
from langbot.pkg.api.http.authz import Permission
from langbot.pkg.api.http.controller import group as http_group
from langbot.pkg.api.http.controller.groups.knowledge.migration import _CURRENT_KNOWLEDGE_BASE
from langbot.pkg.api.http.controller.groups.system import SystemRouterGroup
from langbot.pkg.api.http.controller.groups.webhooks import WebhookRouterGroup
from langbot.pkg.api.http.context import ExecutionContext, RequestContext
from langbot.pkg.api.http.service.apikey import ApiKeyService
from langbot.pkg.api.http.service.monitoring import MonitoringService
from langbot.pkg.api.http.service.user import UserService
from langbot.pkg.api.mcp.context import get_request_context as get_mcp_request_context
from langbot.pkg.api.mcp.mount import MCPMount
from langbot.pkg.entity.persistence.apikey import ApiKey
from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
from langbot.pkg.entity.persistence.monitoring import MonitoringFeedback
from langbot.pkg.entity.persistence.workspace import (
    Workspace,
    WorkspaceExecutionState,
    WorkspaceMembership,
)
from langbot.pkg.platform.botmgr import PlatformManager
from langbot.pkg.pipeline.pipelinemgr import PipelineManager
from langbot.pkg.provider.modelmgr.modelmgr import ModelManager
from langbot.pkg.provider.tools.loaders.mcp import MCPLoader
from langbot.pkg.rag.knowledge.kbmgr import RAGManager

from .resource_migration_support import TENANT_TABLES, create_legacy_resource_schema


def _get_script_head() -> str:
    """Resolve the current Alembic head revision from the script directory.

    Avoids hardcoding a revision number in assertions so adding a new
    migration doesn't require editing the migration tests.
    """
    cfg = Config()
    cfg.set_main_option('script_location', _ALEMBIC_DIR)
    return ScriptDirectory.from_config(cfg).get_current_head()


async def _grant_runtime_role_business_objects(
    conn: AsyncConnection,
    role_name: str,
    quote: typing.Callable[[str], str],
) -> None:
    """Mirror the release job's object ACLs without overgranting Alembic."""

    business_tables = tuple(sorted({table.name for table in Base.metadata.tables.values()} | {'langbot_vectors'}))
    quoted_tables = ', '.join(f'public.{quote(table_name)}' for table_name in business_tables)
    await conn.execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {quoted_tables} TO {quote(role_name)}'))
    await conn.execute(text(f'GRANT SELECT ON TABLE public.alembic_version TO {quote(role_name)}'))
    sequence_query = text(
        """
        SELECT DISTINCT sequence.relname
        FROM pg_class sequence
        JOIN pg_namespace sequence_namespace ON sequence_namespace.oid = sequence.relnamespace
        JOIN pg_depend dependency
          ON dependency.classid = 'pg_class'::regclass
         AND dependency.objid = sequence.oid
         AND dependency.refclassid = 'pg_class'::regclass
         AND dependency.deptype IN ('a', 'i')
        JOIN pg_class business_table ON business_table.oid = dependency.refobjid
        JOIN pg_namespace table_namespace ON table_namespace.oid = business_table.relnamespace
        WHERE sequence.relkind = 'S'
          AND sequence_namespace.nspname = 'public'
          AND table_namespace.nspname = 'public'
          AND business_table.relname IN :table_names
        ORDER BY sequence.relname
        """
    ).bindparams(sa.bindparam('table_names', expanding=True))
    sequence_names = tuple((await conn.execute(sequence_query, {'table_names': business_tables})).scalars().all())
    if sequence_names:
        quoted_sequences = ', '.join(f'public.{quote(sequence_name)}' for sequence_name in sequence_names)
        await conn.execute(text(f'GRANT USAGE, SELECT ON SEQUENCE {quoted_sequences} TO {quote(role_name)}'))


def _application_for_postgres_url(postgres_url: str, logger_name: str) -> SimpleNamespace:
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


async def _dispose_manager(manager: PersistenceManager | None) -> None:
    if manager is not None and getattr(manager, 'db', None) is not None:
        await manager.get_db_engine().dispose()


def _restore_postgres_manager_registry(monkeypatch) -> None:
    """Undo the registry isolation used by test_database_decorator.py."""
    from langbot.pkg.persistence import mgr as persistence_mgr_module
    from langbot.pkg.persistence.databases.postgresql import PostgreSQLDatabaseManager

    monkeypatch.setattr(
        persistence_mgr_module.database,
        'preregistered_managers',
        [PostgreSQLDatabaseManager],
    )


pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.fixture
def postgres_url():
    """Get PostgreSQL URL from environment."""
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL not set')
    return url


@pytest.fixture
async def postgres_engine(postgres_url):
    """Create async PostgreSQL engine."""
    engine = create_async_engine(postgres_url, isolation_level='AUTOCOMMIT')
    yield engine
    await engine.dispose()


@pytest.fixture
async def clean_tables(postgres_engine):
    """Drop all tables before and after each test for isolation."""

    async def drop_all_tables() -> None:
        # Alembic can create tables (notably langbot_vectors) outside the ORM
        # metadata, and legacy migration tests intentionally alter constraints.
        # Reflect the dedicated test schema instead of relying on stale ORM DDL.
        async with postgres_engine.begin() as conn:
            table_names = await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).get_table_names())
            quote = postgres_engine.dialect.identifier_preparer.quote
            for table_name in table_names:
                await conn.execute(text(f'DROP TABLE {quote(table_name)} CASCADE'))

    await drop_all_tables()
    yield
    await drop_all_tables()


@pytest.fixture
async def clean_alembic_version(postgres_engine):
    """Drop alembic_version table before and after each test."""
    async with postgres_engine.begin() as conn:
        # Drop alembic_version table if exists
        try:
            await conn.execute(text('DROP TABLE IF EXISTS alembic_version'))
        except Exception:
            pass

    yield

    async with postgres_engine.begin() as conn:
        try:
            await conn.execute(text('DROP TABLE IF EXISTS alembic_version'))
        except Exception:
            pass


class TestPostgreSQLMigrationBaseline:
    """Tests for baseline stamp workflow on PostgreSQL."""

    @pytest.mark.asyncio
    async def test_postgres_baseline_stamp_sets_revision(self, postgres_engine, clean_tables, clean_alembic_version):
        """
        Stamp baseline on existing tables sets correct revision.

        Workflow:
        1. Create tables via Base.metadata.create_all
        2. Stamp with '0001_baseline'
        3. Verify current revision is '0001_baseline'
        """
        # Create all tables (simulates existing DB created by ORM)
        async with postgres_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Stamp baseline
        await run_alembic_stamp(postgres_engine, '0001_baseline')

        # Verify revision
        rev = await get_alembic_current(postgres_engine)
        assert rev == '0001_baseline', f"Expected '0001_baseline', got {rev}"

    @pytest.mark.asyncio
    async def test_postgres_baseline_stamp_on_empty_db(self, postgres_engine, clean_tables, clean_alembic_version):
        """
        Stamp on empty database (no tables) still sets revision.

        This is an edge case - stamping without tables.
        """
        # Don't create tables - stamp directly
        await run_alembic_stamp(postgres_engine, '0001_baseline')

        rev = await get_alembic_current(postgres_engine)
        assert rev == '0001_baseline'

    @pytest.mark.asyncio
    async def test_fresh_postgres_schema_accepts_application_casefold_identity(
        self,
        postgres_engine,
        clean_tables,
        clean_alembic_version,
    ):
        canonical_email = normalize_email('Ꭰ@Example.COM')
        async with postgres_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                sa.insert(User).values(
                    uuid='00000000-0000-0000-0000-000000000099',
                    user=canonical_email,
                    normalized_email=canonical_email,
                    password='hash',
                )
            )
        async with postgres_engine.connect() as conn:
            assert await conn.scalar(sa.select(User.normalized_email)) == 'Ꭰ@example.com'


class TestPostgreSQLMigrationUpgrade:
    """Tests for upgrade to head workflow on PostgreSQL."""

    @pytest.mark.asyncio
    async def test_postgres_upgrade_from_baseline_to_head(self, postgres_engine, clean_tables, clean_alembic_version):
        """
        Upgrade from baseline to head applies all migrations.

        Workflow:
        1. Create tables
        2. Stamp baseline
        3. Upgrade to head
        4. Verify current revision is head
        """
        # Create tables
        async with postgres_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Stamp baseline
        await run_alembic_stamp(postgres_engine, '0001_baseline')

        # Upgrade to head
        await run_alembic_upgrade(postgres_engine, 'head')

        # Verify revision
        rev = await get_alembic_current(postgres_engine)
        assert rev is not None, 'Expected a revision after upgrade'
        # Head should be the latest migration. Resolve the actual head from the
        # Alembic script directory instead of hardcoding a revision number, so
        # adding a new migration doesn't require editing this assertion.
        assert rev == _get_script_head(), f'Expected head {_get_script_head()}, got {rev}'

    @pytest.mark.asyncio
    async def test_postgres_upgrade_idempotent(self, postgres_engine, clean_tables, clean_alembic_version):
        """
        Running upgrade to head multiple times is idempotent.

        Workflow:
        1. Upgrade to head
        2. Get revision
        3. Upgrade to head again
        4. Verify same revision
        """
        # Create tables
        async with postgres_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Stamp and upgrade
        await run_alembic_stamp(postgres_engine, '0001_baseline')
        await run_alembic_upgrade(postgres_engine, 'head')

        rev1 = await get_alembic_current(postgres_engine)

        # Upgrade again - should be idempotent
        await run_alembic_upgrade(postgres_engine, 'head')

        rev2 = await get_alembic_current(postgres_engine)
        assert rev2 == rev1, f'Expected {rev1}, got {rev2}'

    @pytest.mark.asyncio
    @pytest.mark.parametrize('settings_type', ['TEXT', 'JSON'])
    async def test_legacy_knowledge_restore_statement_accepts_historical_and_fresh_settings_types(
        self,
        postgres_engine,
        clean_tables,
        clean_alembic_version,
        settings_type,
    ):
        timestamp = datetime.datetime(2026, 7, 20, 3, 0, 0, 123456)
        async with postgres_engine.begin() as conn:
            await conn.execute(
                text(f"""
                    CREATE TABLE knowledge_bases (
                        uuid TEXT PRIMARY KEY,
                        workspace_uuid TEXT NOT NULL,
                        name TEXT,
                        description TEXT,
                        emoji TEXT,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP,
                        knowledge_engine_plugin_id TEXT,
                        collection_id TEXT,
                        creation_settings {settings_type},
                        retrieval_settings {settings_type}
                    )
                """)
            )
            await conn.execute(
                _CURRENT_KNOWLEDGE_BASE.insert().values(
                    uuid=f'kb-{settings_type.lower()}',
                    workspace_uuid='workspace-a',
                    name='Legacy KB',
                    description='Compatibility probe',
                    emoji='📚',
                    created_at=timestamp,
                    updated_at=timestamp,
                    knowledge_engine_plugin_id='langbot-team/LangRAG',
                    collection_id=f'kb-{settings_type.lower()}',
                    creation_settings='{"embedding_model_uuid": "embedding-model"}',
                    retrieval_settings='{"top_k": 5}',
                )
            )
            row = (
                await conn.execute(
                    text('SELECT created_at, creation_settings::text AS creation_settings FROM knowledge_bases')
                )
            ).one()
            assert row.created_at == timestamp
            assert 'embedding_model_uuid' in row.creation_settings


class TestPostgreSQLMigrationGetCurrent:
    """Tests for get_alembic_current behavior on PostgreSQL."""

    @pytest.mark.asyncio
    async def test_postgres_get_current_on_unstamped_db_returns_none(
        self, postgres_engine, clean_tables, clean_alembic_version
    ):
        """
        get_alembic_current returns None for unstamped database.
        """
        # Create tables but don't stamp
        async with postgres_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # No stamp - should return None
        rev = await get_alembic_current(postgres_engine)
        assert rev is None, f'Expected None for unstamped DB, got {rev}'

    @pytest.mark.asyncio
    async def test_postgres_get_current_after_stamp_returns_revision(
        self, postgres_engine, clean_tables, clean_alembic_version
    ):
        """
        get_alembic_current returns correct revision after stamp.
        """
        async with postgres_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await run_alembic_stamp(postgres_engine, '0001_baseline')

        rev = await get_alembic_current(postgres_engine)
        assert rev == '0001_baseline'


class TestPostgreSQLWorkspaceMigration:
    """Focused coverage for upgrading a pre-tenancy PostgreSQL instance."""

    @pytest.mark.asyncio
    async def test_postgres_legacy_instance_gets_default_workspace(
        self,
        postgres_engine,
        clean_tables,
        clean_alembic_version,
        monkeypatch,
    ):
        legacy_metadata = sa.MetaData()
        metadata_table = sa.Table(
            'metadata',
            legacy_metadata,
            sa.Column('key', sa.String(255), primary_key=True),
            sa.Column('value', sa.String(255)),
        )
        users = sa.Table(
            'users',
            legacy_metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('user', sa.String(255), nullable=False),
            sa.Column('password', sa.String(255), nullable=False),
            sa.Column(
                'account_type',
                sa.String(32),
                nullable=False,
                server_default='local',
            ),
            sa.Column('created_at', sa.DateTime, server_default=text('now()')),
            sa.Column('updated_at', sa.DateTime, server_default=text('now()')),
        )
        async with postgres_engine.begin() as conn:
            await conn.run_sync(legacy_metadata.create_all)
            await conn.execute(metadata_table.insert().values(key='database_version', value='25'))
            await conn.execute(metadata_table.insert().values(key='instance_uuid', value='instance_postgres_test'))
            await conn.execute(users.insert().values(user='owner@example.com', password='owner-hash'))

        await run_alembic_stamp(postgres_engine, '0008_mcp_resource_prefs')
        monkeypatch.setattr(constants, 'instance_id', 'instance_postgres_test')
        database = type('Database', (), {'get_engine': lambda self: postgres_engine})()
        application = type('Application', (), {})()
        application.logger = logging.getLogger('postgres-workspace-startup-test')
        manager = PersistenceManager(application)
        manager.db = database

        await manager.create_tables()
        async with postgres_engine.connect() as conn:
            tables_before_migration = set(
                await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).get_table_names())
            )
        assert 'workspaces' not in tables_before_migration

        await manager._initialize_managed_schema()

        async with postgres_engine.connect() as conn:
            account = (await conn.execute(text('SELECT uuid, status, source FROM users'))).mappings().one()
            workspace = (
                (await conn.execute(text('SELECT * FROM workspaces WHERE source = :source'), {'source': 'local'}))
                .mappings()
                .one()
            )
            membership = (await conn.execute(text('SELECT * FROM workspace_memberships'))).mappings().one()
            execution_state = (await conn.execute(text('SELECT * FROM workspace_execution_states'))).mappings().one()

        assert account['status'] == 'active'
        assert account['source'] == 'local'
        assert workspace['instance_uuid'] == 'instance_postgres_test'
        assert workspace['created_by_account_uuid'] == account['uuid']
        assert membership['account_uuid'] == account['uuid']
        assert membership['role'] == 'owner'
        assert execution_state['active_generation'] == 1
        assert execution_state['write_fenced'] is False


class TestPostgreSQLResourceTenancyMigration:
    """Legacy backfill and scoped-key enforcement on real PostgreSQL."""

    @pytest.mark.asyncio
    async def test_postgres_resources_are_backfilled_and_scoped(
        self,
        postgres_engine,
        clean_tables,
        clean_alembic_version,
    ):
        await create_legacy_resource_schema(
            postgres_engine,
            instance_uuid='postgres-resource-migration-test',
        )
        async with postgres_engine.begin() as conn:
            await conn.execute(text('UPDATE users SET "user" = \'Straße@Example.COM\''))
            await conn.execute(
                text('INSERT INTO users ("user", password) VALUES (:email, :password)'),
                {'email': 'Ꭰ@Example.COM', 'password': 'cherokee-hash'},
            )
        await run_alembic_stamp(postgres_engine, '0008_mcp_resource_prefs')
        await run_alembic_upgrade(postgres_engine, 'head')

        async with postgres_engine.connect() as conn:
            workspace_uuid = await conn.scalar(text("SELECT uuid FROM workspaces WHERE source = 'local'"))
            for table_name in TENANT_TABLES:
                count, distinct_workspaces = (
                    await conn.execute(text(f'SELECT COUNT(*), COUNT(DISTINCT workspace_uuid) FROM {table_name}'))
                ).one()
                assert (count, distinct_workspaces) == (1, 1), table_name
                columns = await conn.run_sync(
                    lambda sync_conn, name=table_name: {
                        column['name']: column for column in sa.inspect(sync_conn).get_columns(name)
                    }
                )
                assert columns['workspace_uuid']['nullable'] is False, table_name

            api_columns = await conn.run_sync(
                lambda sync_conn: {column['name'] for column in sa.inspect(sync_conn).get_columns('api_keys')}
            )
            assert 'key' not in api_columns
            assert await conn.scalar(text('SELECT scopes FROM api_keys')) == ['*']
            assert (await conn.execute(text('SELECT normalized_email FROM users ORDER BY id'))).scalars().all() == [
                'strasse@example.com',
                'Ꭰ@example.com',
            ]

        second_workspace_uuid = '00000000-0000-0000-0000-000000000002'
        async with postgres_engine.begin() as conn:
            await conn.execute(
                text(
                    'INSERT INTO workspaces '
                    '(uuid, instance_uuid, name, slug, type, status, source, projection_revision) '
                    "VALUES (:uuid, 'postgres-resource-migration-test', 'Second', 'second', "
                    "'team', 'active', 'cloud_projection', 0)"
                ),
                {'uuid': second_workspace_uuid},
            )
            await conn.execute(
                text(
                    'INSERT INTO mcp_servers (uuid, workspace_uuid, name, enable, updated_at) '
                    "VALUES ('mcp-2', :workspace_uuid, 'shared-name', true, now())"
                ),
                {'workspace_uuid': second_workspace_uuid},
            )
            await conn.execute(
                text(
                    'INSERT INTO plugin_settings '
                    '(workspace_uuid, plugin_author, plugin_name, enabled, '
                    'installation_uuid, artifact_digest, runtime_revision) '
                    "VALUES (:workspace_uuid, 'author', 'plugin', true, "
                    ':installation_uuid, :artifact_digest, 1)'
                ),
                {
                    'workspace_uuid': second_workspace_uuid,
                    'installation_uuid': str(uuid.uuid4()),
                    'artifact_digest': hashlib.sha256(b'test-plugin-artifact').hexdigest(),
                },
            )

        with pytest.raises(IntegrityError):
            async with postgres_engine.begin() as conn:
                await conn.execute(
                    text(
                        'INSERT INTO mcp_servers '
                        '(uuid, workspace_uuid, name, enable, updated_at) '
                        "VALUES ('mcp-duplicate', :workspace_uuid, 'shared-name', true, now())"
                    ),
                    {'workspace_uuid': workspace_uuid},
                )

        with pytest.raises(IntegrityError):
            async with postgres_engine.begin() as conn:
                await conn.execute(
                    text(
                        'INSERT INTO llm_models (uuid, workspace_uuid, name, provider_uuid) '
                        "VALUES ('cross-workspace-model', :workspace_uuid, 'model', 'provider-1')"
                    ),
                    {'workspace_uuid': second_workspace_uuid},
                )


class TestPostgreSQLTenantRuntime:
    """Release bootstrap, RLS enforcement, and runtime-role safety."""

    @pytest.mark.asyncio
    async def test_oss_postgres_defaults_to_the_singleton_workspace(
        self,
        postgres_url,
        clean_tables,
        clean_alembic_version,
        monkeypatch,
    ):
        instance_uuid = 'oss-postgres-rls-compatibility-test'
        _restore_postgres_manager_registry(monkeypatch)
        monkeypatch.setattr(constants, 'instance_id', instance_uuid)
        manager = PersistenceManager(
            _application_for_postgres_url(postgres_url, 'postgres-oss-rls-compatibility-test'),
            mode=PersistenceMode.OSS_COMPAT,
        )
        try:
            await manager.initialize()
            async with manager.get_db_engine().connect() as conn:
                workspace_uuid = await conn.scalar(text("SELECT uuid FROM workspaces WHERE source = 'local'"))
                tenant_setting = await conn.scalar(text("SELECT current_setting('langbot.workspace_uuid', true)"))
                visible_workspaces = await conn.scalar(text('SELECT COUNT(*) FROM workspaces'))
            assert workspace_uuid == tenant_setting
            assert visible_workspaces == 1
        finally:
            await _dispose_manager(manager)

    @pytest.mark.asyncio
    async def test_release_bootstrap_and_runtime_isolation(
        self,
        postgres_url,
        postgres_engine,
        clean_tables,
        clean_alembic_version,
        monkeypatch,
    ):
        instance_uuid = 'cloud-runtime-persistence-test'
        workspace_a = '10000000-0000-0000-0000-000000000001'
        workspace_b = '20000000-0000-0000-0000-000000000002'
        role_suffix = uuid.uuid4().hex[:12]
        runtime_role = f'lb_runtime_{role_suffix}'
        bypass_role = f'lb_bypass_{role_suffix}'
        owner_role = f'lb_owner_{role_suffix}'
        role_password = f'Lb{uuid.uuid4().hex}'
        created_roles: list[str] = []
        managers: list[PersistenceManager] = []
        runtime_engine: AsyncEngine | None = None
        owner_changed = False

        _restore_postgres_manager_registry(monkeypatch)
        monkeypatch.setattr(constants, 'instance_id', instance_uuid)
        release_manager = PersistenceManager(
            _application_for_postgres_url(postgres_url, 'postgres-release-bootstrap-test'),
            mode=PersistenceMode.RELEASE_MIGRATION,
        )
        managers.append(release_manager)

        async with postgres_engine.connect() as conn:
            admin_user = await conn.scalar(text('SELECT current_user'))
        quote = postgres_engine.dialect.identifier_preparer.quote

        def role_url(role_name: str) -> str:
            return (
                sa.engine.make_url(postgres_url)
                .set(
                    username=role_name,
                    password=role_password,
                )
                .render_as_string(hide_password=False)
            )

        async def create_role(role_name: str, *, bypass_rls: bool = False) -> None:
            bypass_clause = ' BYPASSRLS' if bypass_rls else ''
            async with postgres_engine.connect() as conn:
                await conn.execute(
                    text(f"CREATE ROLE {quote(role_name)} LOGIN{bypass_clause} PASSWORD '{role_password}'")
                )
                await conn.execute(
                    text(
                        f'GRANT CONNECT ON DATABASE {quote(sa.engine.make_url(postgres_url).database)} '
                        f'TO {quote(role_name)}'
                    )
                )
                await conn.execute(text(f'GRANT USAGE ON SCHEMA public TO {quote(role_name)}'))
                await _grant_runtime_role_business_objects(conn, role_name, quote)
            created_roles.append(role_name)

        try:
            await release_manager.initialize()
            release_engine = release_manager.get_db_engine()

            assert await get_alembic_current(release_engine) == _get_script_head()
            async with release_engine.connect() as conn:
                assert await conn.scalar(text('SELECT COUNT(*) FROM workspaces')) == 0
                rls_rows = (
                    (
                        await conn.execute(
                            text(
                                """
                            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                                   EXISTS (
                                       SELECT 1 FROM pg_policy p
                                       WHERE p.polrelid = c.oid AND p.polname = :policy_name
                                   ) AS has_policy
                            FROM pg_class c
                            JOIN pg_namespace n ON n.oid = c.relnamespace
                            WHERE n.nspname = current_schema() AND c.relname IN :table_names
                            """
                            ).bindparams(sa.bindparam('table_names', expanding=True)),
                            {
                                'policy_name': TENANT_POLICY_NAME,
                                'table_names': tuple(TENANT_TABLE_COLUMNS),
                            },
                        )
                    )
                    .mappings()
                    .all()
                )
            assert {row['relname'] for row in rls_rows} == set(TENANT_TABLE_COLUMNS)
            assert all(row['relrowsecurity'] and row['relforcerowsecurity'] and row['has_policy'] for row in rls_rows)

            for workspace_uuid, slug in ((workspace_a, 'workspace-a'), (workspace_b, 'workspace-b')):
                async with TenantUnitOfWork(release_engine, workspace_uuid) as uow:
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
                        sa.insert(WorkspaceMetadata).values(
                            workspace_uuid=workspace_uuid,
                            key='seed',
                            value=slug,
                        )
                    )

            await create_role(runtime_role)
            runtime_engine = create_async_engine(role_url(runtime_role), pool_size=1, max_overflow=0)

            async with runtime_engine.connect() as conn:
                assert (await conn.execute(text('SELECT uuid FROM workspaces'))).all() == []
                assert (await conn.execute(text('SELECT * FROM workspace_metadata'))).all() == []

            with pytest.raises(sa.exc.DBAPIError):
                async with runtime_engine.begin() as conn:
                    await conn.execute(
                        text(
                            'INSERT INTO workspace_metadata (workspace_uuid, key, value) '
                            "VALUES (:workspace_uuid, 'no-scope', 'rejected')"
                        ),
                        {'workspace_uuid': workspace_a},
                    )

            async with TenantUnitOfWork(runtime_engine, workspace_a) as uow:
                assert (await uow.execute(sa.select(Workspace.uuid))).scalars().all() == [workspace_a]
                assert (await uow.execute(sa.select(Workspace.uuid).where(Workspace.uuid == workspace_b))).all() == []

            with pytest.raises(sa.exc.DBAPIError):
                async with TenantUnitOfWork(runtime_engine, workspace_a) as uow:
                    await uow.execute(
                        sa.insert(WorkspaceMetadata).values(
                            workspace_uuid=workspace_b,
                            key='cross-scope',
                            value='rejected',
                        )
                    )

            async with TenantUnitOfWork(runtime_engine, workspace_a) as uow:
                assert (await uow.execute(sa.select(WorkspaceMetadata.value))).scalars().all() == ['workspace-a']
            async with TenantUnitOfWork(runtime_engine, workspace_b) as uow:
                assert (await uow.execute(sa.select(WorkspaceMetadata.value))).scalars().all() == ['workspace-b']

            with pytest.raises(TransactionRollbackOnlyError, match='transaction was rolled back'):
                async with TenantUnitOfWork(runtime_engine, workspace_a) as uow:
                    with pytest.raises(ScopedSessionTransactionError, match='SQL function'):
                        await uow.execute(
                            sa.select(
                                sa.func.query_to_xml(
                                    sa.literal("SELECT set_config('langbot.workspace_uuid', 'workspace-b', true)"),
                                    sa.literal(True),
                                    sa.literal(False),
                                    sa.literal(''),
                                )
                            )
                        )
                    assert (await uow.execute(sa.select(Workspace.uuid))).scalars().all() == [workspace_a]

            async with runtime_engine.connect() as conn:
                setting = await conn.scalar(text("SELECT current_setting('langbot.workspace_uuid', true)"))
                assert setting in (None, '')
                assert await conn.scalar(text('SELECT COUNT(*) FROM workspace_metadata')) == 0

            with pytest.raises(RuntimeError, match='force rollback'):
                async with TenantUnitOfWork(runtime_engine, workspace_a) as uow:
                    await uow.execute(
                        sa.insert(WorkspaceMetadata).values(
                            workspace_uuid=workspace_a,
                            key='rolled-back',
                            value='no',
                        )
                    )
                    raise RuntimeError('force rollback')
            async with TenantUnitOfWork(runtime_engine, workspace_a) as uow:
                assert (
                    await uow.session.scalar(
                        sa.select(sa.func.count())
                        .select_from(WorkspaceMetadata)
                        .where(WorkspaceMetadata.key == 'rolled-back')
                    )
                    == 0
                )
            async with runtime_engine.connect() as conn:
                setting = await conn.scalar(text("SELECT current_setting('langbot.workspace_uuid', true)"))
                assert setting in (None, '')

            cloud_manager = PersistenceManager(
                _application_for_postgres_url(role_url(runtime_role), 'postgres-cloud-runtime-test'),
                mode=PersistenceMode.CLOUD_RUNTIME,
            )
            cloud_manager.create_tables = AsyncMock(side_effect=AssertionError('Cloud runtime attempted create_all'))
            cloud_manager._run_alembic_migrations = AsyncMock(
                side_effect=AssertionError('Cloud runtime attempted an Alembic upgrade')
            )
            managers.append(cloud_manager)
            await cloud_manager.initialize()
            cloud_manager.create_tables.assert_not_awaited()
            cloud_manager._run_alembic_migrations.assert_not_awaited()

            with pytest.raises(TransactionRollbackOnlyError, match='after-commit work was cancelled'):
                async with cloud_manager.tenant_uow(workspace_a):
                    duplicate_statement = sa.insert(WorkspaceMetadata).values(
                        workspace_uuid=workspace_a,
                        key='rollback-only-unique',
                        value='must-not-commit',
                    )
                    await cloud_manager.execute_async(duplicate_statement)
                    after_commit_gate = cloud_manager.create_after_commit_gate()
                    assert after_commit_gate is not None
                    try:
                        await cloud_manager.execute_async(duplicate_statement)
                    except IntegrityError:
                        pass

            assert after_commit_gate.cancelled()
            async with cloud_manager.tenant_uow(workspace_a):
                assert (
                    await cloud_manager.execute_async(
                        sa.select(sa.func.count())
                        .select_from(WorkspaceMetadata)
                        .where(WorkspaceMetadata.key == 'rollback-only-unique')
                    )
                ).scalar_one() == 0

            superuser_manager = PersistenceManager(
                _application_for_postgres_url(postgres_url, 'postgres-superuser-runtime-test'),
                mode=PersistenceMode.CLOUD_RUNTIME,
            )
            managers.append(superuser_manager)
            with pytest.raises(RuntimeError, match='must not be a superuser'):
                await superuser_manager.initialize()

            await create_role(bypass_role, bypass_rls=True)
            bypass_manager = PersistenceManager(
                _application_for_postgres_url(role_url(bypass_role), 'postgres-bypass-runtime-test'),
                mode=PersistenceMode.CLOUD_RUNTIME,
            )
            managers.append(bypass_manager)
            with pytest.raises(RuntimeError, match='must not have BYPASSRLS'):
                await bypass_manager.initialize()

            await create_role(owner_role)
            async with postgres_engine.connect() as conn:
                await conn.execute(text(f'ALTER TABLE workspace_metadata OWNER TO {quote(owner_role)}'))
            owner_changed = True
            owner_manager = PersistenceManager(
                _application_for_postgres_url(role_url(owner_role), 'postgres-owner-runtime-test'),
                mode=PersistenceMode.CLOUD_RUNTIME,
            )
            managers.append(owner_manager)
            with pytest.raises(RuntimeError, match='must not own tenant tables'):
                await owner_manager.initialize()
        finally:
            if runtime_engine is not None:
                await runtime_engine.dispose()
            for manager in reversed(managers):
                await _dispose_manager(manager)

            async with postgres_engine.connect() as conn:
                if owner_changed:
                    await conn.execute(text(f'ALTER TABLE workspace_metadata OWNER TO {quote(admin_user)}'))
                for role_name in reversed(created_roles):
                    await conn.execute(text(f'DROP OWNED BY {quote(role_name)}'))
                    await conn.execute(text(f'DROP ROLE {quote(role_name)}'))

    @pytest.mark.asyncio
    async def test_cloud_discovery_http_and_transaction_contract(
        self,
        postgres_url,
        postgres_engine,
        clean_tables,
        clean_alembic_version,
        monkeypatch,
    ):
        """Exercise the complete request/discovery path as a non-owner role."""

        instance_uuid = 'cloud-request-rls-test'
        other_instance_uuid = 'other-cloud-instance'
        workspace_a = '31000000-0000-0000-0000-000000000001'
        workspace_b = '32000000-0000-0000-0000-000000000002'
        workspace_other = '33000000-0000-0000-0000-000000000003'
        workspace_fenced = '34000000-0000-0000-0000-000000000004'
        account_a_uuid = '41000000-0000-0000-0000-000000000001'
        shared_account_uuid = '42000000-0000-0000-0000-000000000002'
        active_secret = 'lbk_active-request-key'
        revoked_secret = 'lbk_revoked-request-key'
        expired_secret = 'lbk_expired-request-key'
        role_name = f'lb_request_{uuid.uuid4().hex[:12]}'
        role_password = f'Lb{uuid.uuid4().hex}'
        quote = postgres_engine.dialect.identifier_preparer.quote
        managers: list[PersistenceManager] = []
        role_created = False

        _restore_postgres_manager_registry(monkeypatch)
        monkeypatch.setattr(constants, 'instance_id', instance_uuid)
        release_manager = PersistenceManager(
            _application_for_postgres_url(postgres_url, 'postgres-request-release-test'),
            mode=PersistenceMode.RELEASE_MIGRATION,
        )
        managers.append(release_manager)

        def role_url() -> str:
            return (
                sa.engine.make_url(postgres_url)
                .set(username=role_name, password=role_password)
                .render_as_string(hide_password=False)
            )

        async def seed_workspace(
            workspace_uuid: str,
            *,
            target_instance: str,
            state: str = 'active',
            write_fenced: bool = False,
        ) -> None:
            async with release_manager.tenant_uow(workspace_uuid) as uow:
                uow.session.add(
                    Workspace(
                        uuid=workspace_uuid,
                        instance_uuid=target_instance,
                        name=workspace_uuid[-4:],
                        slug=f'workspace-{workspace_uuid[-4:]}',
                        type='team',
                        status='active',
                        source='cloud_projection',
                        projection_revision=1,
                    )
                )
                await uow.session.flush()
                uow.session.add(
                    WorkspaceExecutionState(
                        workspace_uuid=workspace_uuid,
                        instance_uuid=target_instance,
                        active_generation=1,
                        state=state,
                        write_fenced=write_fenced,
                        source='cloud',
                        desired_state_revision=1,
                    )
                )
                uow.session.add(
                    WorkspaceMetadata(
                        workspace_uuid=workspace_uuid,
                        key='tenant-marker',
                        value=workspace_uuid,
                    )
                )

        try:
            await release_manager.initialize()
            async with release_manager.get_db_engine().begin() as conn:
                await conn.execute(
                    sa.insert(User),
                    [
                        {
                            'uuid': account_a_uuid,
                            'user': 'account-a@example.com',
                            'normalized_email': 'account-a@example.com',
                            'password': 'closed-directory',
                            'account_type': 'local',
                            'status': 'active',
                            'source': 'cloud_projection',
                            'projection_revision': 1,
                        },
                        {
                            'uuid': shared_account_uuid,
                            'user': 'shared@example.com',
                            'normalized_email': 'shared@example.com',
                            'password': 'closed-directory',
                            'account_type': 'local',
                            'status': 'active',
                            'source': 'cloud_projection',
                            'projection_revision': 1,
                        },
                    ],
                )

            await seed_workspace(workspace_a, target_instance=instance_uuid)
            await seed_workspace(workspace_b, target_instance=instance_uuid)
            await seed_workspace(workspace_other, target_instance=other_instance_uuid)
            await seed_workspace(
                workspace_fenced,
                target_instance=instance_uuid,
                write_fenced=True,
            )

            async with release_manager.tenant_uow(workspace_a) as uow:
                uow.session.add_all(
                    [
                        WorkspaceMembership(
                            uuid=str(uuid.uuid4()),
                            workspace_uuid=workspace_a,
                            account_uuid=account_a_uuid,
                            role='owner',
                            status='active',
                            projection_revision=1,
                        ),
                        WorkspaceMembership(
                            uuid=str(uuid.uuid4()),
                            workspace_uuid=workspace_a,
                            account_uuid=shared_account_uuid,
                            role='viewer',
                            status='active',
                            projection_revision=1,
                        ),
                        ApiKey(
                            uuid=str(uuid.uuid4()),
                            workspace_uuid=workspace_a,
                            name='active-key',
                            key_hash=hashlib.sha256(active_secret.encode()).hexdigest(),
                            scopes=[Permission.WORKSPACE_VIEW.value],
                            status='active',
                        ),
                    ]
                )
            async with release_manager.tenant_uow(workspace_b) as uow:
                uow.session.add_all(
                    [
                        WorkspaceMembership(
                            uuid=str(uuid.uuid4()),
                            workspace_uuid=workspace_b,
                            account_uuid=shared_account_uuid,
                            role='viewer',
                            status='active',
                            projection_revision=1,
                        ),
                        ApiKey(
                            uuid=str(uuid.uuid4()),
                            workspace_uuid=workspace_b,
                            name='revoked-key',
                            key_hash=hashlib.sha256(revoked_secret.encode()).hexdigest(),
                            scopes=[Permission.WORKSPACE_VIEW.value],
                            status='revoked',
                        ),
                        ApiKey(
                            uuid=str(uuid.uuid4()),
                            workspace_uuid=workspace_b,
                            name='expired-key',
                            key_hash=hashlib.sha256(expired_secret.encode()).hexdigest(),
                            scopes=[Permission.WORKSPACE_VIEW.value],
                            status='active',
                            expires_at=datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
                            - datetime.timedelta(minutes=1),
                        ),
                    ]
                )

            async with postgres_engine.connect() as conn:
                await conn.execute(text(f"CREATE ROLE {quote(role_name)} LOGIN PASSWORD '{role_password}'"))
                role_created = True
                await conn.execute(
                    text(
                        f'GRANT CONNECT ON DATABASE {quote(sa.engine.make_url(postgres_url).database)} '
                        f'TO {quote(role_name)}'
                    )
                )
                await conn.execute(text(f'GRANT USAGE ON SCHEMA public TO {quote(role_name)}'))
                await _grant_runtime_role_business_objects(conn, role_name, quote)

            runtime_application = _application_for_postgres_url(role_url(), 'postgres-request-runtime-test')
            runtime_application.instance_config.data.update(
                {
                    'system': {
                        'jwt': {'secret': 'postgres-request-jwt', 'expire': 3600},
                    },
                    'api': {'global_api_key': ''},
                }
            )
            runtime_application.logger = logging.getLogger('postgres-request-runtime-test')
            cloud_manager = PersistenceManager(runtime_application, mode=PersistenceMode.CLOUD_RUNTIME)
            managers.append(cloud_manager)
            await cloud_manager.initialize()

            runtime_application.persistence_mgr = cloud_manager
            cloud_manager.ap = runtime_application
            runtime_application.workspace_service = WorkspaceService(
                runtime_application,
                policy=CloudWorkspacePolicy(),
                instance_uuid=instance_uuid,
            )
            runtime_application.workspace_collaboration_service = WorkspaceCollaborationService(
                runtime_application,
                runtime_application.workspace_service,
                policy=CloudWorkspacePolicy(),
            )
            runtime_application.user_service = UserService(runtime_application)
            runtime_application.apikey_service = ApiKeyService(runtime_application)
            runtime_application.monitoring_service = MonitoringService(runtime_application)

            bindings = await runtime_application.workspace_service.list_active_execution_bindings()
            assert {binding.workspace_uuid for binding in bindings} == {workspace_a, workspace_b}

            # No scope is an application error before SQL reaches PostgreSQL.
            with pytest.raises(RuntimeError, match='explicit Workspace or discovery'):
                await cloud_manager.execute_async(sa.select(WorkspaceMetadata))

            # Discovery exposes only its index rows and cannot write.
            with pytest.raises(TransactionRollbackOnlyError, match='transaction was rolled back'):
                async with cloud_manager.account_discovery_uow(shared_account_uuid) as discovery:
                    assert set(
                        (
                            await discovery.session.scalars(
                                sa.select(WorkspaceMembership.workspace_uuid).order_by(
                                    WorkspaceMembership.workspace_uuid
                                )
                            )
                        ).all()
                    ) == {workspace_a, workspace_b}
                    with pytest.raises(sa.exc.DBAPIError):
                        await discovery.session.execute(
                            sa.insert(WorkspaceMembership).values(
                                uuid=str(uuid.uuid4()),
                                workspace_uuid=workspace_a,
                                account_uuid=shared_account_uuid,
                                role='viewer',
                                status='active',
                                projection_revision=1,
                            )
                        )

            async with cloud_manager.api_key_discovery_uow(
                hashlib.sha256(active_secret.encode()).hexdigest()
            ) as discovery:
                assert await discovery.session.scalar(sa.select(ApiKey.workspace_uuid)) == workspace_a
                update_result = await discovery.session.execute(
                    sa.update(ApiKey)
                    .where(ApiKey.key_hash == hashlib.sha256(active_secret.encode()).hexdigest())
                    .values(name='discovery-must-not-write')
                )
                assert update_result.rowcount == 0
            async with cloud_manager.api_key_discovery_uow(
                hashlib.sha256(revoked_secret.encode()).hexdigest()
            ) as discovery:
                assert await discovery.session.scalar(sa.select(ApiKey.workspace_uuid)) is None
            async with cloud_manager.api_key_discovery_uow(
                hashlib.sha256(expired_secret.encode()).hexdigest()
            ) as discovery:
                assert await discovery.session.scalar(sa.select(ApiKey.workspace_uuid)) is None

            async with cloud_manager.instance_discovery_uow(instance_uuid) as discovery:
                assert set(
                    (await discovery.session.scalars(sa.select(WorkspaceExecutionState.workspace_uuid))).all()
                ) == {workspace_a, workspace_b}
                update_result = await discovery.session.execute(
                    sa.update(WorkspaceExecutionState)
                    .where(WorkspaceExecutionState.workspace_uuid == workspace_a)
                    .values(write_fenced=True)
                )
                assert update_result.rowcount == 0
                # Instance discovery deliberately cannot see business rows.
                assert (await discovery.session.execute(sa.select(WorkspaceMetadata))).all() == []

            platform_manager = PlatformManager(runtime_application)
            platform_manager._load_workspace_bots = AsyncMock()
            await platform_manager.load_bots_from_db()
            assert {call.args[0] for call in platform_manager._load_workspace_bots.await_args_list} == {
                workspace_a,
                workspace_b,
            }

            # Every startup cache loader traverses the instance index first,
            # then reads business resources in one tenant transaction at a time.
            await ModelManager(runtime_application).load_models_from_db()
            await PipelineManager(runtime_application).load_pipelines_from_db()
            await MCPLoader(runtime_application).load_mcp_servers_from_db()
            await RAGManager(runtime_application).load_knowledge_bases_from_db()

            # An omitted Workspace predicate remains isolated by RLS.
            async with cloud_manager.tenant_uow(workspace_a):
                values = (await cloud_manager.execute_async(sa.select(WorkspaceMetadata.value))).scalars().all()
                assert values == [workspace_a]

            async def read_tenant_repeatedly(workspace_uuid: str) -> list[str]:
                observed: list[str] = []
                for _ in range(5):
                    async with cloud_manager.tenant_uow(workspace_uuid):
                        observed.extend(
                            (await cloud_manager.execute_async(sa.select(WorkspaceMetadata.value))).scalars().all()
                        )
                    await asyncio.sleep(0)
                return observed

            observed_a, observed_b = await asyncio.gather(
                read_tenant_repeatedly(workspace_a),
                read_tenant_repeatedly(workspace_b),
            )
            assert observed_a == [workspace_a] * 5
            assert observed_b == [workspace_b] * 5

            accesses = await runtime_application.workspace_collaboration_service.list_account_workspaces(
                shared_account_uuid
            )
            assert {access.workspace.uuid for access in accesses} == {workspace_a, workspace_b}
            assert await runtime_application.apikey_service.authenticate_api_key(revoked_secret) is None
            assert await runtime_application.apikey_service.authenticate_api_key(expired_secret) is None
            active_identity = await runtime_application.apikey_service.authenticate_api_key(active_secret)
            assert active_identity is not None
            assert active_identity.workspace_uuid == workspace_a

            async def record_feedback(feedback_type: int) -> str | None:
                async with cloud_manager.tenant_scope(workspace_a):
                    return await runtime_application.monitoring_service.record_feedback(
                        ExecutionContext(
                            instance_uuid=instance_uuid,
                            workspace_uuid=workspace_a,
                            placement_generation=1,
                        ),
                        feedback_id='concurrent-feedback',
                        feedback_type=feedback_type,
                    )

            feedback_ids = await asyncio.gather(record_feedback(1), record_feedback(2))
            assert feedback_ids[0] == feedback_ids[1]
            async with cloud_manager.tenant_uow(workspace_a) as uow:
                feedback_rows = (
                    (
                        await uow.execute(
                            sa.select(MonitoringFeedback).where(MonitoringFeedback.feedback_id == 'concurrent-feedback')
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(feedback_rows) == 1
                assert feedback_rows[0].feedback_type in {1, 2}
                await uow.execute(
                    sa.delete(MonitoringFeedback).where(MonitoringFeedback.feedback_id == 'concurrent-feedback')
                )

            class TenantRuntimeRouter(http_group.RouterGroup):
                name = 'postgres-tenant-runtime'
                path = '/tenant-runtime'

                async def initialize(self) -> None:
                    @self.route('/account', permission=Permission.WORKSPACE_VIEW)
                    async def account_route(request_context: RequestContext):
                        assert self.ap.persistence_mgr.current_session() is None
                        if self.quart_app.config.get('FORCE_HANDLER_FAILURE'):
                            async with self.ap.persistence_mgr.tenant_uow(request_context.workspace_uuid):
                                await self.ap.persistence_mgr.execute_async(
                                    sa.insert(WorkspaceMetadata).values(
                                        workspace_uuid=request_context.workspace_uuid,
                                        key='rolled-back-handler',
                                        value='must-not-commit',
                                    )
                                )
                                raise RuntimeError('forced handler failure')
                        values = (
                            (await self.ap.persistence_mgr.execute_async(sa.select(WorkspaceMetadata.value)))
                            .scalars()
                            .all()
                        )
                        assert self.ap.persistence_mgr.current_session() is None
                        return self.success(data={'workspace_uuid': request_context.workspace_uuid, 'values': values})

                    @self.route('/key', auth_type=http_group.AuthType.API_KEY)
                    async def key_route(request_context: RequestContext):
                        values = (
                            (await self.ap.persistence_mgr.execute_async(sa.select(WorkspaceMetadata.value)))
                            .scalars()
                            .all()
                        )
                        return self.success(data={'workspace_uuid': request_context.workspace_uuid, 'values': values})

                    @self.route('/bootstrap', auth_type=http_group.AuthType.ACCOUNT_TOKEN)
                    async def bootstrap_route(user_email: str):
                        account = await self.ap.user_service.get_user_by_email(user_email)
                        accesses = await self.ap.workspace_collaboration_service.list_account_workspaces(account.uuid)
                        return self.success(data=sorted(access.workspace.uuid for access in accesses))

            quart_app = Quart(__name__)
            await TenantRuntimeRouter(runtime_application, quart_app).initialize()

            webhook_bot_uuid = str(uuid.uuid4())

            class TenantAwareWebhookAdapter:
                async def handle_unified_webhook(self, **_kwargs):
                    assert cloud_manager.current_session() is None
                    await asyncio.sleep(0)
                    assert cloud_manager.current_session() is None
                    values = (
                        (
                            await cloud_manager.execute_async(
                                sa.select(WorkspaceMetadata.value).where(WorkspaceMetadata.key == 'tenant-marker')
                            )
                        )
                        .scalars()
                        .all()
                    )
                    assert cloud_manager.current_session() is None
                    return {'values': values}

            runtime_application.platform_mgr = SimpleNamespace(
                resolve_public_bot=AsyncMock(
                    return_value=SimpleNamespace(
                        workspace_uuid=workspace_a,
                        placement_generation=1,
                        enable=True,
                        adapter=TenantAwareWebhookAdapter(),
                    )
                )
            )
            await WebhookRouterGroup(runtime_application, quart_app).initialize()
            await SystemRouterGroup(runtime_application, quart_app).initialize()
            client = quart_app.test_client()
            account_a = await runtime_application.user_service.get_user_by_uuid(account_a_uuid)
            shared_account = await runtime_application.user_service.get_user_by_uuid(shared_account_uuid)
            assert account_a is not None and shared_account is not None
            account_token = await runtime_application.user_service.generate_jwt_token(account_a)
            shared_token = await runtime_application.user_service.generate_jwt_token(shared_account)

            async with cloud_manager.tenant_uow(workspace_a):
                await cloud_manager.execute_async(
                    sa.insert(WorkspaceMetadata).values(
                        workspace_uuid=workspace_a,
                        key='wizard_status',
                        value='completed',
                    )
                )
            response = await client.get(
                '/api/v1/system/info',
                headers={
                    'Authorization': f'Bearer {account_token}',
                    'X-Workspace-Id': workspace_a,
                },
            )
            assert response.status_code == 200
            assert (await response.get_json())['data']['wizard_status'] == 'completed'
            async with cloud_manager.tenant_uow(workspace_a):
                await cloud_manager.execute_async(
                    sa.delete(WorkspaceMetadata).where(
                        WorkspaceMetadata.workspace_uuid == workspace_a,
                        WorkspaceMetadata.key == 'wizard_status',
                    )
                )

            response = await client.post(f'/bots/{webhook_bot_uuid}')
            assert response.status_code == 200
            assert await response.get_json() == {'values': [workspace_a]}

            response = await client.get(
                '/tenant-runtime/account',
                headers={
                    'Authorization': f'Bearer {account_token}',
                    'X-Workspace-Id': workspace_a,
                },
            )
            assert response.status_code == 200
            assert (await response.get_json())['data'] == {
                'workspace_uuid': workspace_a,
                'values': [workspace_a],
            }

            response = await client.get(
                '/tenant-runtime/account',
                headers={
                    'Authorization': f'Bearer {account_token}',
                    'X-Workspace-Id': workspace_b,
                },
            )
            assert response.status_code == 404
            response = await client.get(
                '/tenant-runtime/account',
                headers={'Authorization': f'Bearer {shared_token}'},
            )
            assert response.status_code == 404

            response = await client.get(
                '/tenant-runtime/bootstrap',
                headers={'Authorization': f'Bearer {shared_token}'},
            )
            assert response.status_code == 200
            assert (await response.get_json())['data'] == [workspace_a, workspace_b]

            response = await client.get(
                '/tenant-runtime/key',
                headers={'X-API-Key': active_secret, 'X-Workspace-Id': workspace_b},
            )
            assert response.status_code == 200
            assert (await response.get_json())['data'] == {
                'workspace_uuid': workspace_a,
                'values': [workspace_a],
            }

            # The parallel MCP ASGI entrypoint authenticates the same key and
            # retains only a trusted Workspace scope for the full tool request.
            # Each DB call gets its own short RLS transaction.
            mcp_observation: dict[str, typing.Any] = {}

            async def fake_mcp_asgi(scope, receive, send):
                del scope, receive
                context = get_mcp_request_context()
                assert cloud_manager.current_session() is None
                values = (await cloud_manager.execute_async(sa.select(WorkspaceMetadata.value))).scalars().all()
                assert cloud_manager.current_session() is None
                await asyncio.sleep(0)
                assert cloud_manager.current_session() is None
                repeated_values = (
                    (await cloud_manager.execute_async(sa.select(WorkspaceMetadata.value))).scalars().all()
                )
                assert repeated_values == values
                assert cloud_manager.current_session() is None
                mcp_observation.update(
                    workspace_uuid=context.workspace_uuid,
                    values=values,
                )
                await send({'type': 'http.response.start', 'status': 200, 'headers': []})
                await send({'type': 'http.response.body', 'body': b'{}'})

            async def unused_quart_asgi(scope, receive, send):  # pragma: no cover - routing assertion
                del scope, receive, send
                raise AssertionError('MCP request was routed to Quart')

            mount = MCPMount.__new__(MCPMount)
            mount.ap = runtime_application
            mount._mcp_asgi = fake_mcp_asgi
            sent_messages: list[dict[str, typing.Any]] = []

            async def receive():
                return {'type': 'http.request', 'body': b'', 'more_body': False}

            async def send(message):
                sent_messages.append(message)

            await mount.wrap(unused_quart_asgi)(
                {
                    'type': 'http',
                    'path': '/mcp',
                    'headers': [
                        (b'x-api-key', active_secret.encode()),
                        (b'x-workspace-id', workspace_b.encode()),
                    ],
                },
                receive,
                send,
            )
            assert sent_messages[0]['status'] == 200
            assert mcp_observation == {'workspace_uuid': workspace_a, 'values': [workspace_a]}

            original_api_key_discovery = cloud_manager.api_key_discovery_uow

            @contextlib.asynccontextmanager
            async def revoke_after_discovery(key_hash: str):
                async with original_api_key_discovery(key_hash) as discovery:
                    yield discovery
                async with cloud_manager.tenant_uow(workspace_a):
                    await cloud_manager.execute_async(
                        sa.update(ApiKey).where(ApiKey.key_hash == key_hash).values(status='revoked')
                    )

            monkeypatch.setattr(cloud_manager, 'api_key_discovery_uow', revoke_after_discovery)
            assert await runtime_application.apikey_service.authenticate_api_key(active_secret) is None
            monkeypatch.setattr(cloud_manager, 'api_key_discovery_uow', original_api_key_discovery)

            quart_app.config['FORCE_HANDLER_FAILURE'] = True
            response = await client.get(
                '/tenant-runtime/account',
                headers={
                    'Authorization': f'Bearer {account_token}',
                    'X-Workspace-Id': workspace_a,
                },
            )
            assert response.status_code == 500
            quart_app.config['FORCE_HANDLER_FAILURE'] = False
            async with cloud_manager.tenant_uow(workspace_a):
                assert (
                    await cloud_manager.execute_async(
                        sa.select(sa.func.count())
                        .select_from(WorkspaceMetadata)
                        .where(WorkspaceMetadata.key == 'rolled-back-handler')
                    )
                ).scalar_one() == 0

            # Transaction-local settings are gone when pooled connections are reused.
            async with cloud_manager.get_db_engine().connect() as conn:
                assert await conn.scalar(text("SELECT current_setting('langbot.workspace_uuid', true)")) in (
                    None,
                    '',
                )
                assert await conn.scalar(text('SELECT COUNT(*) FROM workspace_metadata')) == 0

            # Runtime validation rejects both extra permissive policies and a
            # modified expression even if the expected policy name remains.
            async with postgres_engine.connect() as conn:
                await conn.execute(text('CREATE POLICY injected_policy ON bots FOR SELECT USING (true)'))
            with pytest.raises(RuntimeError, match='policy set does not match'):
                await cloud_manager._validate_postgres_tenant_schema(validate_runtime_role=True)
            async with postgres_engine.connect() as conn:
                await conn.execute(text('DROP POLICY injected_policy ON bots'))
                await conn.execute(text('DROP POLICY langbot_workspace_isolation ON workspace_metadata'))
                await conn.execute(
                    text(
                        'CREATE POLICY langbot_workspace_isolation ON workspace_metadata '
                        'FOR ALL TO PUBLIC USING (true) WITH CHECK (true)'
                    )
                )
            with pytest.raises(RuntimeError, match='policy definitions are invalid'):
                await cloud_manager._validate_postgres_tenant_schema(validate_runtime_role=True)
        finally:
            for manager in reversed(managers):
                await _dispose_manager(manager)
            if role_created:
                async with postgres_engine.connect() as conn:
                    await conn.execute(text(f'DROP OWNED BY {quote(role_name)}'))
                    await conn.execute(text(f'DROP ROLE IF EXISTS {quote(role_name)}'))
