from __future__ import annotations

import json
import logging
import pathlib
import sqlite3

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.persistence import alembic_runner
from langbot.pkg.persistence.mgr import PersistenceManager

from .resource_migration_support import create_legacy_resource_schema


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _manager(engine) -> PersistenceManager:
    database = type('Database', (), {'get_engine': lambda self: engine})()
    application = type('Application', (), {})()
    application.logger = logging.getLogger('sqlite-migration-backup-test')
    manager = PersistenceManager(application)
    manager.db = database
    return manager


def _manifest_payloads(backup_directory) -> list[dict]:
    return [json.loads(path.read_text(encoding='utf-8')) for path in sorted(backup_directory.glob('*.json'))]


def _assert_verified_backup(payload: dict) -> None:
    backup_path = pathlib.Path(payload['backup_path'])
    with sqlite3.connect(f'{backup_path.as_uri()}?mode=ro', uri=True) as connection:
        assert connection.execute('PRAGMA quick_check').fetchall() == [('ok',)]
        assert connection.execute('SELECT version_num FROM alembic_version').fetchone()[0] == payload['source_revision']


async def test_tenancy_migrations_retain_verified_boundary_backups(tmp_path):
    database_path = tmp_path / 'legacy-with-backups.db'
    engine = create_async_engine(f'sqlite+aiosqlite:///{database_path}')
    try:
        await create_legacy_resource_schema(engine, instance_uuid='backup-success')
        await alembic_runner.run_alembic_stamp(engine, '0008_mcp_resource_prefs')

        await _manager(engine)._run_alembic_migrations()

        assert await alembic_runner.get_alembic_current(engine) == alembic_runner.get_alembic_head()
        payloads = _manifest_payloads(tmp_path / 'migration-backups')
        assert len(payloads) == 2
        assert {
            (payload['source_revision'], payload['target_revision'], payload['status']) for payload in payloads
        } == {
            ('0008_mcp_resource_prefs', '0009_workspace_tenancy', 'migration_succeeded'),
            ('0009_workspace_tenancy', '0010_scope_resources', 'migration_succeeded'),
        }
        for payload in payloads:
            _assert_verified_backup(payload)
    finally:
        await engine.dispose()


async def test_failed_tenancy_migration_restores_backup_and_revision(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / 'legacy-fault-injection.db'
    engine = create_async_engine(f'sqlite+aiosqlite:///{database_path}')
    real_upgrade = alembic_runner.run_alembic_upgrade

    async def injected_upgrade(async_engine, revision='head'):
        if revision != '0010_scope_resources':
            return await real_upgrade(async_engine, revision)
        async with async_engine.begin() as connection:
            await connection.execute(sa.text('CREATE TABLE injected_partial_migration (value TEXT NOT NULL)'))
        await alembic_runner.run_alembic_stamp(async_engine, '0010_scope_resources')
        raise RuntimeError('injected migration failure after a fake revision stamp')

    try:
        await create_legacy_resource_schema(engine, instance_uuid='backup-failure')
        await alembic_runner.run_alembic_stamp(engine, '0008_mcp_resource_prefs')
        monkeypatch.setattr(alembic_runner, 'run_alembic_upgrade', injected_upgrade)

        with pytest.raises(RuntimeError, match='injected migration failure'):
            await _manager(engine)._run_alembic_migrations()

        assert await alembic_runner.get_alembic_current(engine) == '0009_workspace_tenancy'
        async with engine.connect() as connection:
            tables = set(
                await connection.run_sync(lambda sync_connection: sa.inspect(sync_connection).get_table_names())
            )
        assert 'injected_partial_migration' not in tables

        payloads = _manifest_payloads(tmp_path / 'migration-backups')
        restored = [payload for payload in payloads if payload['target_revision'] == '0010_scope_resources']
        assert len(restored) == 1
        assert restored[0]['status'] == 'restored_after_failure'
        assert restored[0]['source_revision'] == '0009_workspace_tenancy'
        _assert_verified_backup(restored[0])

        monkeypatch.setattr(alembic_runner, 'run_alembic_upgrade', real_upgrade)
        await _manager(engine)._run_alembic_migrations()
        assert await alembic_runner.get_alembic_current(engine) == alembic_runner.get_alembic_head()
    finally:
        await engine.dispose()
