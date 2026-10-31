"""
SQLite migration integration tests.

Tests real Alembic migration behavior using temporary SQLite databases.
Validates the migration workflow from .github/workflows/test-migrations.yml.

Run: uv run pytest tests/integration/persistence/test_migrations.py -q
"""

from __future__ import annotations

import json

import pytest
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity import persistence
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.utils import importutil
from langbot.pkg.persistence.alembic_runner import (
    run_alembic_downgrade,
    run_alembic_upgrade,
    run_alembic_stamp,
    get_alembic_current,
    _ALEMBIC_DIR,
)
from alembic.config import Config
from alembic.script import ScriptDirectory


# Match PersistenceManager's model registration before create_all, including
# workspace foreign-key targets, without relying on other tests being collected.
importutil.import_modules_in_pkg(persistence)


def _get_script_head() -> str:
    """Resolve the current Alembic head revision from the script directory.

    Avoids hardcoding a revision number in assertions so adding a new
    migration doesn't require editing the migration tests.
    """
    cfg = Config()
    cfg.set_main_option('script_location', _ALEMBIC_DIR)
    return ScriptDirectory.from_config(cfg).get_current_head()


pytestmark = pytest.mark.integration


@pytest.fixture
def sqlite_db_url(tmp_path):
    """Create SQLite URL with temporary database file."""
    db_file = tmp_path / 'test_migrations.db'
    return f'sqlite+aiosqlite:///{db_file}'


@pytest.fixture
async def sqlite_engine(sqlite_db_url):
    """Create async SQLite engine."""
    engine = create_async_engine(sqlite_db_url)
    yield engine
    await engine.dispose()


def test_migration_graph_has_one_head_containing_both_released_branches():
    cfg = Config()
    cfg.set_main_option('script_location', _ALEMBIC_DIR)
    scripts = ScriptDirectory.from_config(cfg)
    heads = scripts.get_heads()
    assert len(heads) == 1, f'Release migrations must converge, found {heads}'
    ancestors = {revision.revision for revision in scripts.walk_revisions()}
    assert {
        '0024_passkey_credentials',
        '0025_bot_plugin_processors',
        '0025_rag_document_identity',
        '0027_pipeline_migration',
        '0028_merge_knowledge_drafts',
    } <= ancestors
    assert all(len(revision) <= 32 for revision in ancestors)


class TestSQLiteMigrationBaseline:
    """Tests for baseline stamp workflow."""

    @pytest.mark.asyncio
    async def test_baseline_stamp_sets_revision(self, sqlite_engine):
        """
        Stamp baseline on existing tables sets correct revision.

        Workflow:
        1. Create tables via Base.metadata.create_all
        2. Stamp with '0001_baseline'
        3. Verify current revision is '0001_baseline'
        """
        # Create all tables (simulates existing DB created by ORM)
        async with sqlite_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Stamp baseline
        await run_alembic_stamp(sqlite_engine, '0001_baseline')

        # Verify revision
        rev = await get_alembic_current(sqlite_engine)
        assert rev == '0001_baseline', f"Expected '0001_baseline', got {rev}"

    @pytest.mark.asyncio
    async def test_baseline_stamp_on_empty_db(self, sqlite_engine):
        """
        Stamp on empty database (no tables) still sets revision.

        This is an edge case - stamping without tables.
        """
        # Don't create tables - stamp directly
        await run_alembic_stamp(sqlite_engine, '0001_baseline')

        rev = await get_alembic_current(sqlite_engine)
        assert rev == '0001_baseline'


class TestSQLiteMigrationUpgrade:
    """Tests for upgrade to head workflow."""

    @pytest.mark.asyncio
    async def test_execution_filter_index_round_trip_preserves_history(self, sqlite_engine):
        from langbot.pkg.entity.persistence.monitoring import MonitoringMessage

        index_name = 'ix_monitoring_messages_execution_filter'
        index = next(item for item in MonitoringMessage.__table__.indexes if item.name == index_name)

        def indexes(connection):
            return {
                item['name']: item['column_names']
                for item in sqlalchemy.inspect(connection).get_indexes('monitoring_messages')
            }

        async with sqlite_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(
                sqlalchemy.insert(MonitoringMessage).values(
                    id='historical-root',
                    timestamp=sqlalchemy.func.current_timestamp(),
                    workspace_uuid='workspace',
                    bot_id='bot',
                    bot_name='Bot',
                    pipeline_id='pipeline',
                    pipeline_name='Pipeline',
                    session_id='session',
                    message_content='preserve historical payload',
                    status='success',
                    role='user',
                    level='info',
                )
            )
            original = await connection.run_sync(indexes)

        await run_alembic_stamp(sqlite_engine, '0039_execution_lease_indexes')
        # Fresh installations already have the ORM index before Alembic runs.
        await run_alembic_upgrade(sqlite_engine, 'head')
        await run_alembic_downgrade(sqlite_engine, '0039_execution_lease_indexes')
        async with sqlite_engine.connect() as connection:
            remaining = await connection.run_sync(indexes)
        expected = {
            name: columns
            for name, columns in original.items()
            if name not in {index_name, 'ix_monitoring_messages_summary_event'}
        }
        expected['ix_monitoring_messages_workspace_timestamp'] = ['workspace_uuid', 'timestamp']
        assert remaining == expected

        # Existing installations receive the same covering index through migration.
        await run_alembic_upgrade(sqlite_engine, 'head')
        async with sqlite_engine.connect() as connection:
            upgraded = await connection.run_sync(indexes)
            assert upgraded == original
            assert upgraded[index_name] == [column.name for column in index.columns]
            assert await connection.scalar(sqlalchemy.select(MonitoringMessage.message_content)) == (
                'preserve historical payload'
            )

    @pytest.mark.asyncio
    async def test_upgrade_removes_agent_enabled_column(self, sqlite_engine):
        async with sqlite_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.exec_driver_sql('ALTER TABLE agents ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT 1')

        await run_alembic_stamp(sqlite_engine, '0022_merge_agent_reasoning_heads')
        await run_alembic_upgrade(sqlite_engine, 'head')

        async with sqlite_engine.connect() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: {column['name'] for column in sqlalchemy.inspect(sync_conn).get_columns('agents')}
            )

        assert 'enabled' not in columns

    @pytest.mark.asyncio
    async def test_upgrade_from_0012_adds_knowledge_base_embedding_dimension(self, sqlite_engine):
        """The PostgreSQL pgvector revision also evolves the OSS ORM schema."""

        async with sqlite_engine.begin() as conn:
            await conn.exec_driver_sql(
                'CREATE TABLE knowledge_bases ('
                'uuid VARCHAR(255) PRIMARY KEY, workspace_uuid VARCHAR(36) NOT NULL, name VARCHAR(255) NOT NULL)'
            )

        await run_alembic_stamp(sqlite_engine, '0012_plugin_identity')
        await run_alembic_upgrade(sqlite_engine, 'head')

        async with sqlite_engine.connect() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: {
                    item['name'] for item in sqlalchemy.inspect(sync_conn).get_columns('knowledge_bases')
                }
            )
        assert 'embedding_dimension' in columns

    @pytest.mark.asyncio
    async def test_directory_projection_upgrade_downgrade_round_trip(self, sqlite_engine):
        await run_alembic_stamp(sqlite_engine, '0013_tenant_pgvector')

        await run_alembic_upgrade(sqlite_engine, 'head')
        async with sqlite_engine.connect() as conn:
            tables = await conn.run_sync(lambda sync_conn: set(sqlalchemy.inspect(sync_conn).get_table_names()))
        assert {'directory_projection_states', 'directory_projection_inbox'} <= tables

        await run_alembic_downgrade(sqlite_engine, '0013_tenant_pgvector')
        async with sqlite_engine.connect() as conn:
            tables = await conn.run_sync(lambda sync_conn: set(sqlalchemy.inspect(sync_conn).get_table_names()))
        assert 'directory_projection_states' not in tables
        assert 'directory_projection_inbox' not in tables

        await run_alembic_upgrade(sqlite_engine, 'head')
        assert await get_alembic_current(sqlite_engine) == _get_script_head()

    @pytest.mark.asyncio
    async def test_reasoning_config_migrates_existing_models(self, sqlite_engine):
        """Upgrade from 0017 backfills reasoning config and keeps a database default."""
        async with sqlite_engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    CREATE TABLE llm_models (
                        uuid VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        provider_uuid VARCHAR(255) NOT NULL,
                        abilities JSON NOT NULL,
                        context_length INTEGER,
                        extra_args JSON NOT NULL,
                        prefered_ranking INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO llm_models (
                        uuid, name, provider_uuid, abilities, extra_args, prefered_ranking
                    ) VALUES (
                        'existing-model', 'Existing Model', 'provider', '[]', '{}', 0
                    )
                    """
                )
            )

        await run_alembic_stamp(sqlite_engine, '0017_oss_workspace_identity')
        await run_alembic_upgrade(sqlite_engine, 'head')

        async with sqlite_engine.begin() as conn:
            columns = await conn.run_sync(lambda sync_conn: sqlalchemy.inspect(sync_conn).get_columns('llm_models'))
            reasoning_column = next(column for column in columns if column['name'] == 'reasoning_config')
            assert reasoning_column['nullable'] is False

            existing_value = (
                await conn.execute(text("SELECT reasoning_config FROM llm_models WHERE uuid = 'existing-model'"))
            ).scalar_one()
            assert json.loads(existing_value) == {'level': 'provider_default'}

            await conn.execute(
                text(
                    """
                    INSERT INTO llm_models (
                        uuid, name, provider_uuid, abilities, extra_args, prefered_ranking
                    ) VALUES (
                        'new-model', 'New Model', 'provider', '[]', '{}', 0
                    )
                    """
                )
            )
            new_value = (
                await conn.execute(text("SELECT reasoning_config FROM llm_models WHERE uuid = 'new-model'"))
            ).scalar_one()
            assert json.loads(new_value) == {'level': 'provider_default'}


class TestSQLiteMigrationFreshDatabase:
    """Tests for fresh database workflow."""

    @pytest.mark.asyncio
    async def test_bot_scoped_sessions_skips_absent_table(self, sqlite_engine):
        """A partial schema needs no session key migration in either direction."""
        await run_alembic_stamp(sqlite_engine, '0022_codex_credentials')
        await run_alembic_upgrade(sqlite_engine, '0023_bot_scoped_sessions')
        assert await get_alembic_current(sqlite_engine) == '0023_bot_scoped_sessions'
        await run_alembic_downgrade(sqlite_engine, '0022_codex_credentials')
        assert await get_alembic_current(sqlite_engine) == '0022_codex_credentials'

    @pytest.mark.asyncio
    async def test_fresh_db_without_create_all_behavior(self, sqlite_engine):
        """Bare Alembic reaches head but relies on ORM bootstrap for core tables."""
        await run_alembic_upgrade(sqlite_engine, 'head')
        assert await get_alembic_current(sqlite_engine) == _get_script_head()
        async with sqlite_engine.connect() as conn:
            tables = await conn.run_sync(lambda sync: set(sqlalchemy.inspect(sync).get_table_names()))
        assert {'agents', 'runner_state', 'directory_projection_states', 'directory_projection_inbox'} <= tables
        assert not {'users', 'bots', 'workspaces'} & tables


class TestSQLiteMigrationGetCurrent:
    """Tests for get_alembic_current behavior."""

    @pytest.mark.asyncio
    async def test_get_current_on_unstamped_db_returns_none(self, sqlite_engine):
        """
        get_alembic_current returns None for unstamped database.
        """
        # Create tables but don't stamp
        async with sqlite_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # No stamp - should return None
        rev = await get_alembic_current(sqlite_engine)
        assert rev is None, f'Expected None for unstamped DB, got {rev}'
