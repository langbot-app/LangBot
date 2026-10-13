"""Upgrade the immutable v4.10.11 ORM schema, not current metadata."""

import json

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.persistence.alembic_runner import run_alembic_upgrade
from tests.integration.persistence.test_migration_branch_convergence import (
    FIXTURES,
    _seed_common,
)


@pytest.fixture(params=['sqlite', 'postgresql'])
async def convergence_engine(request, tmp_path):
    import os
    import uuid
    from sqlalchemy.ext.asyncio import create_async_engine

    if request.param == 'sqlite':
        engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "release.db"}')
        try:
            yield engine
        finally:
            await engine.dispose()
        return
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL required for disposable PostgreSQL')
    name = 'release_audit_' + uuid.uuid4().hex
    admin = create_async_engine(url, isolation_level='AUTOCOMMIT')
    async with admin.connect() as conn:
        await conn.exec_driver_sql(f'CREATE DATABASE {name}')
    engine = create_async_engine(sa.engine.make_url(url).set(database=name))
    try:
        yield engine
    finally:
        await engine.dispose()
        async with admin.connect() as conn:
            await conn.exec_driver_sql(f'DROP DATABASE {name}')
        await admin.dispose()


@pytest.mark.asyncio
async def test_release_41011_upgrade(convergence_engine, monkeypatch):
    from langbot.pkg.utils import constants

    monkeypatch.setattr(constants, 'instance_id', 'migration-convergence')
    engine = convergence_engine
    fixture = json.loads((FIXTURES / 'release_4_10_11_schema.json').read_text())
    async with engine.begin() as conn:
        for statement in fixture['dialects'][engine.dialect.name]:
            await conn.exec_driver_sql(statement)
    # Apply the historical migrations too: pgvector is migration-owned,
    # not represented in ORM metadata.
    await run_alembic_upgrade(engine, fixture['revision'])
    await _seed_common(engine)
    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM metadata WHERE key='oss_workspace_uuid'"))
        await conn.execute(
            sa.text(
                "INSERT INTO metadata (key,value) VALUES ('oss_workspace_uuid', '41100000-0000-4000-8000-000000000001')"
            )
        )
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from langbot.pkg.persistence.mgr import PersistenceManager

    manager = PersistenceManager(SimpleNamespace(logger=MagicMock(), instance_uuid='migration-convergence'))
    manager.db = SimpleNamespace(engine=engine, get_engine=lambda: engine)
    await manager._initialize_managed_schema()
    async with engine.connect() as conn:
        assert await conn.scalar(sa.text('SELECT name FROM bots')) == 'Fixture bot'
        assert await conn.scalar(sa.text('SELECT name FROM legacy_pipelines')) == 'Fixture pipeline'
        bot = await conn.run_sync(lambda sync: sa.Table('bots', sa.MetaData(), autoload_with=sync))
        bindings = await conn.scalar(sa.select(bot.c.event_bindings))
        assert any(binding['target_uuid'] == 'pipeline-1' for binding in bindings)
        assert await conn.scalar(sa.select(bot.c.plugin_processors)) == []
        kb = await conn.run_sync(lambda sync: sa.Table('knowledge_bases', sa.MetaData(), autoload_with=sync))
        assert all(await conn.scalars(sa.select(kb.c.initialized)))
        if engine.dialect.name == 'sqlite':
            assert (await conn.exec_driver_sql('PRAGMA foreign_key_check')).all() == []
    async with engine.connect() as conn:

        def differences(sync):
            context = MigrationContext.configure(sync, opts={'compare_type': True})
            return compare_metadata(context, Base.metadata)

        diffs = await conn.run_sync(differences)

        def substantive(sync, diff):
            if isinstance(diff, list):
                return True
            if diff[0] not in ('add_table', 'add_column', 'add_index', 'add_constraint'):
                return False
            if diff[0] in ('add_index', 'add_constraint'):
                obj = diff[1]
                inspector = sa.inspect(sync)
                columns = [c.name for c in obj.columns]
                existing = inspector.get_indexes(obj.table.name) + inspector.get_unique_constraints(obj.table.name)
                if any(
                    item['column_names'] == columns and (diff[0] != 'add_constraint' or item.get('unique', True))
                    for item in existing
                ):
                    return False
                if (
                    diff[0] == 'add_constraint'
                    and inspector.get_pk_constraint(obj.table.name)['constrained_columns'] == columns
                ):
                    return False
            return True

        actionable = await conn.run_sync(lambda sync: [d for d in diffs if substantive(sync, d)])
        assert not actionable, repr(actionable)
    await manager._initialize_managed_schema()
    async with engine.connect() as conn:
        assert await conn.scalar(sa.text('SELECT name FROM bots')) == 'Fixture bot'
        assert await conn.scalar(sa.text('SELECT name FROM legacy_pipelines')) == 'Fixture pipeline'
        bot = await conn.run_sync(lambda sync: sa.Table('bots', sa.MetaData(), autoload_with=sync))
        bindings = await conn.scalar(sa.select(bot.c.event_bindings))
        assert any(binding['target_uuid'] == 'pipeline-1' for binding in bindings)
        assert await conn.scalar(sa.select(bot.c.plugin_processors)) == []
        kb = await conn.run_sync(lambda sync: sa.Table('knowledge_bases', sa.MetaData(), autoload_with=sync))
        assert all(await conn.scalars(sa.select(kb.c.initialized)))
        if engine.dialect.name == 'sqlite':
            assert (await conn.exec_driver_sql('PRAGMA foreign_key_check')).all() == []
