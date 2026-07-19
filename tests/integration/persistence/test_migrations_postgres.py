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
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy import text

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.persistence.tenant_uow import TENANT_POLICY_NAME, TENANT_TABLE_COLUMNS, TenantUnitOfWork
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

from .resource_migration_support import TENANT_TABLES, create_legacy_resource_schema


def _get_script_head() -> str:
    """Resolve the current Alembic head revision from the script directory.

    Avoids hardcoding a revision number in assertions so adding a new
    migration doesn't require editing the migration tests.
    """
    cfg = Config()
    cfg.set_main_option('script_location', _ALEMBIC_DIR)
    return ScriptDirectory.from_config(cfg).get_current_head()


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
    # Drop all tables before test
    async with postgres_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    yield

    # Drop all tables after test
    async with postgres_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


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
                    '(workspace_uuid, plugin_author, plugin_name, enabled) '
                    "VALUES (:workspace_uuid, 'author', 'plugin', true)"
                ),
                {'workspace_uuid': second_workspace_uuid},
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
                await conn.execute(
                    text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {quote(role_name)}')
                )
                await conn.execute(text(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quote(role_name)}'))
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
                        text(
                            """
                            INSERT INTO workspaces
                                (uuid, instance_uuid, name, slug, type, status, source, projection_revision)
                            VALUES
                                (:uuid, :instance_uuid, :name, :slug, 'team', 'active', 'cloud_projection', 0)
                            """
                        ),
                        {
                            'uuid': workspace_uuid,
                            'instance_uuid': instance_uuid,
                            'name': slug,
                            'slug': slug,
                        },
                    )
                    await uow.execute(
                        text(
                            'INSERT INTO workspace_metadata (workspace_uuid, key, value) '
                            "VALUES (:workspace_uuid, 'seed', :value)"
                        ),
                        {'workspace_uuid': workspace_uuid, 'value': slug},
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
                assert (await uow.execute(text('SELECT uuid FROM workspaces'))).scalars().all() == [workspace_a]
                assert (
                    await uow.execute(
                        text('SELECT uuid FROM workspaces WHERE uuid = :workspace_uuid'),
                        {'workspace_uuid': workspace_b},
                    )
                ).all() == []

            with pytest.raises(sa.exc.DBAPIError):
                async with TenantUnitOfWork(runtime_engine, workspace_a) as uow:
                    await uow.execute(
                        text(
                            'INSERT INTO workspace_metadata (workspace_uuid, key, value) '
                            "VALUES (:workspace_uuid, 'cross-scope', 'rejected')"
                        ),
                        {'workspace_uuid': workspace_b},
                    )

            async with TenantUnitOfWork(runtime_engine, workspace_a) as uow:
                assert (await uow.execute(text('SELECT value FROM workspace_metadata'))).scalars().all() == [
                    'workspace-a'
                ]
            async with TenantUnitOfWork(runtime_engine, workspace_b) as uow:
                assert (await uow.execute(text('SELECT value FROM workspace_metadata'))).scalars().all() == [
                    'workspace-b'
                ]
            async with runtime_engine.connect() as conn:
                setting = await conn.scalar(text("SELECT current_setting('langbot.workspace_uuid', true)"))
                assert setting in (None, '')
                assert await conn.scalar(text('SELECT COUNT(*) FROM workspace_metadata')) == 0

            with pytest.raises(RuntimeError, match='force rollback'):
                async with TenantUnitOfWork(runtime_engine, workspace_a) as uow:
                    await uow.execute(
                        text(
                            'INSERT INTO workspace_metadata (workspace_uuid, key, value) '
                            "VALUES (:workspace_uuid, 'rolled-back', 'no')"
                        ),
                        {'workspace_uuid': workspace_a},
                    )
                    raise RuntimeError('force rollback')
            async with TenantUnitOfWork(runtime_engine, workspace_a) as uow:
                assert (
                    await uow.session.scalar(text("SELECT COUNT(*) FROM workspace_metadata WHERE key = 'rolled-back'"))
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
