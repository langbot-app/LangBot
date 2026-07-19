from __future__ import annotations

import hashlib
import json
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity import persistence
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.persistence.alembic_runner import run_alembic_stamp, run_alembic_upgrade
from langbot.pkg.utils import importutil

from .resource_migration_support import TENANT_TABLES, create_legacy_resource_schema


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _inspect(engine, callback):
    async with engine.connect() as conn:
        return await conn.run_sync(callback)


async def test_legacy_sqlite_resources_are_backfilled_and_contracted(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "legacy-resources.db"}')
    try:
        await create_legacy_resource_schema(engine, instance_uuid='resource-migration-test')
        await run_alembic_stamp(engine, '0008_mcp_resource_prefs')
        await run_alembic_upgrade(engine, 'head')

        async with engine.connect() as conn:
            workspace_uuid = await conn.scalar(sa.text("SELECT uuid FROM workspaces WHERE source = 'local'"))
            assert workspace_uuid is not None
            for table_name in TENANT_TABLES:
                count, distinct_workspaces = (
                    await conn.execute(sa.text(f'SELECT COUNT(*), COUNT(DISTINCT workspace_uuid) FROM {table_name}'))
                ).one()
                assert count == 1, table_name
                assert distinct_workspaces == 1, table_name
                assert (
                    await conn.scalar(
                        sa.text(f'SELECT COUNT(*) FROM {table_name} WHERE workspace_uuid != :workspace_uuid'),
                        {'workspace_uuid': workspace_uuid},
                    )
                    == 0
                )

            api_key = (
                (await conn.execute(sa.text('SELECT key_hash, scopes, status, created_by_account_uuid FROM api_keys')))
                .mappings()
                .one()
            )
            assert api_key['key_hash'] == hashlib.sha256(b'lbk_legacy-secret').hexdigest()
            stored_scopes = api_key['scopes']
            if isinstance(stored_scopes, str):
                stored_scopes = json.loads(stored_scopes)
            assert stored_scopes == ['*']
            assert api_key['status'] == 'active'
            assert api_key['created_by_account_uuid'] is not None
            assert await conn.scalar(sa.text('SELECT normalized_email FROM users')) == 'owner@example.com'
            legacy_kb = (
                (
                    await conn.execute(
                        sa.text(
                            'SELECT collection_id, legacy_vector_collection FROM knowledge_bases WHERE uuid = :uuid'
                        ),
                        {'uuid': 'kb-1'},
                    )
                )
                .mappings()
                .one()
            )
            assert legacy_kb['collection_id'] == 'collection-1'
            assert legacy_kb['legacy_vector_collection'] == 1
            assert (
                await conn.scalar(
                    sa.text(
                        'SELECT COUNT(*) FROM metadata '
                        "WHERE key IN ('wizard_status', 'wizard_progress', 'rag_plugin_migration_needed')"
                    )
                )
                == 0
            )
            assert (
                await conn.scalar(
                    sa.text('SELECT COUNT(*) FROM workspace_metadata WHERE workspace_uuid = :workspace_uuid'),
                    {'workspace_uuid': workspace_uuid},
                )
                == 3
            )

        api_columns = await _inspect(
            engine,
            lambda conn: {column['name'] for column in sa.inspect(conn).get_columns('api_keys')},
        )
        assert 'key' not in api_columns
        assert {'uuid', 'key_hash', 'scopes', 'status', 'expires_at', 'last_used_at'} <= api_columns
        for table_name in TENANT_TABLES:
            columns = await _inspect(
                engine,
                lambda conn, name=table_name: {column['name']: column for column in sa.inspect(conn).get_columns(name)},
            )
            assert columns['workspace_uuid']['nullable'] is False, table_name
            if table_name == 'knowledge_bases':
                assert columns['legacy_vector_collection']['nullable'] is False

        pk_columns = {
            table_name: tuple(
                (
                    await _inspect(
                        engine,
                        lambda conn, name=table_name: sa.inspect(conn).get_pk_constraint(name),
                    )
                )['constrained_columns']
            )
            for table_name in ('binary_storages', 'plugin_settings', 'monitoring_sessions')
        }
        assert pk_columns == {
            'binary_storages': ('workspace_uuid', 'unique_key'),
            'plugin_settings': ('workspace_uuid', 'plugin_author', 'plugin_name'),
            'monitoring_sessions': ('workspace_uuid', 'session_id'),
        }

        pipeline_run_foreign_keys = await _inspect(
            engine,
            lambda conn: sa.inspect(conn).get_foreign_keys('pipeline_run_records'),
        )
        assert any(
            tuple(foreign_key['constrained_columns']) == ('workspace_uuid', 'pipeline_uuid')
            and foreign_key['referred_table'] == 'legacy_pipelines'
            and tuple(foreign_key['referred_columns']) == ('workspace_uuid', 'uuid')
            for foreign_key in pipeline_run_foreign_keys
        )
    finally:
        await engine.dispose()


async def test_legacy_vector_marker_backfill_resumes_from_nullable_expand_step(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "legacy-vector-retry.db"}')
    try:
        await create_legacy_resource_schema(engine, instance_uuid='legacy-vector-retry')
        async with engine.begin() as conn:
            await conn.execute(sa.text('ALTER TABLE knowledge_bases ADD COLUMN legacy_vector_collection BOOLEAN NULL'))
        await run_alembic_stamp(engine, '0008_mcp_resource_prefs')
        await run_alembic_upgrade(engine, 'head')

        async with engine.connect() as conn:
            assert (
                await conn.scalar(
                    sa.text('SELECT legacy_vector_collection FROM knowledge_bases WHERE uuid = :uuid'),
                    {'uuid': 'kb-1'},
                )
                == 1
            )
        columns = await _inspect(
            engine,
            lambda conn: {column['name']: column for column in sa.inspect(conn).get_columns('knowledge_bases')},
        )
        assert columns['legacy_vector_collection']['nullable'] is False
    finally:
        await engine.dispose()


async def test_sqlite_scoped_keys_allow_cross_workspace_but_reject_same_workspace(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "scoped-keys.db"}')
    try:
        await create_legacy_resource_schema(engine, instance_uuid='scoped-key-test')
        await run_alembic_stamp(engine, '0008_mcp_resource_prefs')
        await run_alembic_upgrade(engine, 'head')

        second_workspace_uuid = str(uuid.uuid4())
        async with engine.begin() as conn:
            await conn.execute(sa.text('PRAGMA foreign_keys=ON'))
            first_workspace_uuid = await conn.scalar(sa.text("SELECT uuid FROM workspaces WHERE source = 'local'"))
            await conn.execute(
                sa.text(
                    'INSERT INTO workspaces '
                    '(uuid, instance_uuid, name, slug, type, status, source, projection_revision) '
                    "VALUES (:uuid, 'scoped-key-test', 'Second', 'second', 'team', 'active', "
                    "'cloud_projection', 0)"
                ),
                {'uuid': second_workspace_uuid},
            )
            await conn.execute(
                sa.text(
                    'INSERT INTO mcp_servers (uuid, workspace_uuid, name, enable, updated_at) '
                    "VALUES ('mcp-2', :workspace_uuid, 'shared-name', 1, CURRENT_TIMESTAMP)"
                ),
                {'workspace_uuid': second_workspace_uuid},
            )
            await conn.execute(
                sa.text(
                    'INSERT INTO plugin_settings '
                    '(workspace_uuid, plugin_author, plugin_name, enabled) '
                    "VALUES (:workspace_uuid, 'author', 'plugin', 1)"
                ),
                {'workspace_uuid': second_workspace_uuid},
            )
            await conn.execute(
                sa.text(
                    'INSERT INTO binary_storages '
                    '(workspace_uuid, unique_key, key, owner_type, owner) '
                    "VALUES (:workspace_uuid, 'plugin:demo:key', 'key', 'plugin', 'demo')"
                ),
                {'workspace_uuid': second_workspace_uuid},
            )
            await conn.execute(
                sa.text(
                    'INSERT INTO monitoring_sessions '
                    '(workspace_uuid, session_id, bot_id, last_activity, is_active) '
                    "VALUES (:workspace_uuid, 'session-1', 'bot-2', CURRENT_TIMESTAMP, 1)"
                ),
                {'workspace_uuid': second_workspace_uuid},
            )

        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(sa.text('PRAGMA foreign_keys=ON'))
                await conn.execute(
                    sa.text(
                        'INSERT INTO mcp_servers (uuid, workspace_uuid, name, enable, updated_at) '
                        "VALUES ('mcp-duplicate', :workspace_uuid, 'shared-name', 1, CURRENT_TIMESTAMP)"
                    ),
                    {'workspace_uuid': first_workspace_uuid},
                )

        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(sa.text('PRAGMA foreign_keys=ON'))
                await conn.execute(
                    sa.text(
                        'INSERT INTO llm_models (uuid, workspace_uuid, name, provider_uuid) '
                        "VALUES ('cross-workspace-model', :workspace_uuid, 'model', 'provider-1')"
                    ),
                    {'workspace_uuid': second_workspace_uuid},
                )

        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(sa.text('PRAGMA foreign_keys=ON'))
                await conn.execute(
                    sa.text(
                        'INSERT INTO pipeline_run_records '
                        '(uuid, workspace_uuid, pipeline_uuid, created_at) '
                        "VALUES ('cross-workspace-run', :workspace_uuid, 'pipeline-1', CURRENT_TIMESTAMP)"
                    ),
                    {'workspace_uuid': second_workspace_uuid},
                )

        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text(
                        'INSERT INTO mcp_servers (uuid, name, enable, updated_at) '
                        "VALUES ('unscoped-mcp', 'unscoped', 1, CURRENT_TIMESTAMP)"
                    )
                )
    finally:
        await engine.dispose()


async def test_fresh_sqlite_schema_matches_resource_tenancy_contract(tmp_path):
    importutil.import_modules_in_pkg(persistence)
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "fresh-resources.db"}')
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await run_alembic_stamp(engine, '0001_baseline')
        await run_alembic_upgrade(engine, 'head')

        tables = await _inspect(engine, lambda conn: set(sa.inspect(conn).get_table_names()))
        assert set(TENANT_TABLES) | {'workspace_metadata'} <= tables
        for table_name in TENANT_TABLES:
            columns = await _inspect(
                engine,
                lambda conn, name=table_name: {column['name']: column for column in sa.inspect(conn).get_columns(name)},
            )
            assert columns['workspace_uuid']['nullable'] is False, table_name
            if table_name == 'knowledge_bases':
                assert columns['legacy_vector_collection']['nullable'] is False
    finally:
        await engine.dispose()
