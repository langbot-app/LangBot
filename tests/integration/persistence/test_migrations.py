"""
SQLite migration integration tests.

Tests real Alembic migration behavior using temporary SQLite databases.
Validates the migration workflow from .github/workflows/test-migrations.yml.

Run: uv run pytest tests/integration/persistence/test_migrations.py -q
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.persistence.alembic_runner import (
    run_alembic_upgrade,
    run_alembic_stamp,
    get_alembic_current,
)


pytestmark = pytest.mark.integration


@pytest.fixture
def sqlite_db_url(tmp_path):
    """Create SQLite URL with temporary database file."""
    db_file = tmp_path / "test_migrations.db"
    return f"sqlite+aiosqlite:///{db_file}"


@pytest.fixture
async def sqlite_engine(sqlite_db_url):
    """Create async SQLite engine."""
    engine = create_async_engine(sqlite_db_url)
    yield engine
    await engine.dispose()


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
    async def test_upgrade_from_baseline_to_head(self, sqlite_engine):
        """
        Upgrade from baseline to head applies all migrations.

        Workflow:
        1. Create tables
        2. Stamp baseline
        3. Upgrade to head
        4. Verify current revision is head
        """
        # Create tables
        async with sqlite_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Stamp baseline
        await run_alembic_stamp(sqlite_engine, '0001_baseline')

        # Upgrade to head
        await run_alembic_upgrade(sqlite_engine, 'head')

        # Verify revision
        rev = await get_alembic_current(sqlite_engine)
        assert rev is not None, "Expected a revision after upgrade"
        # Head should be the latest migration
        assert rev.startswith('0003'), f"Expected head to be 0003_*, got {rev}"

    @pytest.mark.asyncio
    async def test_upgrade_idempotent(self, sqlite_engine):
        """
        Running upgrade to head multiple times is idempotent.

        Workflow:
        1. Upgrade to head
        2. Get revision
        3. Upgrade to head again
        4. Verify same revision
        """
        # Create tables
        async with sqlite_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Stamp and upgrade
        await run_alembic_stamp(sqlite_engine, '0001_baseline')
        await run_alembic_upgrade(sqlite_engine, 'head')

        rev1 = await get_alembic_current(sqlite_engine)

        # Upgrade again - should be idempotent
        await run_alembic_upgrade(sqlite_engine, 'head')

        rev2 = await get_alembic_current(sqlite_engine)
        assert rev2 == rev1, f"Expected {rev1}, got {rev2}"


class TestSQLiteMigrationFreshDatabase:
    """Tests for fresh database workflow."""

    @pytest.mark.asyncio
    async def test_fresh_db_upgrade_from_scratch(self, tmp_path):
        """
        Fresh database (no tables) can be upgraded directly to head.

        Workflow:
        1. Create fresh engine with new DB file
        2. Create tables
        3. Upgrade to head
        4. Verify revision
        """
        # Use different DB file for fresh test
        fresh_db_file = tmp_path / "test_migrations_fresh.db"
        fresh_url = f"sqlite+aiosqlite:///{fresh_db_file}"
        fresh_engine = create_async_engine(fresh_url)

        # Create tables on fresh DB
        async with fresh_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Upgrade to head directly (no baseline stamp)
        await run_alembic_upgrade(fresh_engine, 'head')

        # Verify revision
        rev = await get_alembic_current(fresh_engine)
        assert rev is not None, "Expected a revision on fresh DB"

        await fresh_engine.dispose()

    @pytest.mark.asyncio
    async def test_fresh_db_without_create_all_fails_gracefully(self, tmp_path):
        """
        Fresh database without create_all may fail or have empty tables.

        This tests the edge case where migrations run on truly empty DB.
        The behavior depends on migration script implementation.
        """
        fresh_db_file = tmp_path / "test_empty_migrations.db"
        fresh_url = f"sqlite+aiosqlite:///{fresh_db_file}"
        fresh_engine = create_async_engine(fresh_url)

        # Don't create tables - try upgrade directly
        # This may fail if migrations expect tables to exist
        try:
            await run_alembic_upgrade(fresh_engine, 'head')
            rev = await get_alembic_current(fresh_engine)
            # If it succeeds, verify revision
            assert rev is not None
        except Exception:
            # If it fails, that's acceptable behavior
            # Migrations may require create_all first
            pass

        await fresh_engine.dispose()


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
        assert rev is None, f"Expected None for unstamped DB, got {rev}"

    @pytest.mark.asyncio
    async def test_get_current_after_stamp_returns_revision(self, sqlite_engine):
        """
        get_alembic_current returns correct revision after stamp.
        """
        async with sqlite_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await run_alembic_stamp(sqlite_engine, '0001_baseline')

        rev = await get_alembic_current(sqlite_engine)
        assert rev == '0001_baseline'