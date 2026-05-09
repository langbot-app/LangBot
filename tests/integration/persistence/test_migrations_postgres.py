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

import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.persistence.alembic_runner import (
    run_alembic_upgrade,
    run_alembic_stamp,
    get_alembic_current,
)


pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.fixture
def postgres_url():
    """Get PostgreSQL URL from environment."""
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip("TEST_POSTGRES_URL not set")
    return url


@pytest.fixture
async def postgres_engine(postgres_url):
    """Create async PostgreSQL engine."""
    engine = create_async_engine(postgres_url, isolation_level="AUTOCOMMIT")
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
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        except Exception:
            pass

    yield

    async with postgres_engine.begin() as conn:
        try:
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        except Exception:
            pass


class TestPostgreSQLMigrationBaseline:
    """Tests for baseline stamp workflow on PostgreSQL."""

    @pytest.mark.asyncio
    async def test_postgres_baseline_stamp_sets_revision(
        self, postgres_engine, clean_tables, clean_alembic_version
    ):
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
    async def test_postgres_baseline_stamp_on_empty_db(
        self, postgres_engine, clean_tables, clean_alembic_version
    ):
        """
        Stamp on empty database (no tables) still sets revision.

        This is an edge case - stamping without tables.
        """
        # Don't create tables - stamp directly
        await run_alembic_stamp(postgres_engine, '0001_baseline')

        rev = await get_alembic_current(postgres_engine)
        assert rev == '0001_baseline'


class TestPostgreSQLMigrationUpgrade:
    """Tests for upgrade to head workflow on PostgreSQL."""

    @pytest.mark.asyncio
    async def test_postgres_upgrade_from_baseline_to_head(
        self, postgres_engine, clean_tables, clean_alembic_version
    ):
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
        assert rev is not None, "Expected a revision after upgrade"
        # Head should be the latest migration (0003 for current state)
        assert rev.startswith('0003'), f"Expected head to be 0003_*, got {rev}"

    @pytest.mark.asyncio
    async def test_postgres_upgrade_idempotent(
        self, postgres_engine, clean_tables, clean_alembic_version
    ):
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
        assert rev2 == rev1, f"Expected {rev1}, got {rev2}"


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
        assert rev is None, f"Expected None for unstamped DB, got {rev}"

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