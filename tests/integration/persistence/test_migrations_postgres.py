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
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.persistence.mgr import PersistenceManager
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

        await manager._run_alembic_migrations()

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
