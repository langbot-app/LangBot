from __future__ import annotations

from datetime import datetime
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.controller.groups.knowledge.migration import KnowledgeMigrationRouterGroup
from langbot.pkg.persistence.tenant_uow import _validate_scoped_statement_call
from langbot.pkg.workspace.errors import WorkspaceInvariantError, WorkspaceNotFoundError


CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=3,
)


@pytest.mark.asyncio
async def test_background_migration_propagates_generation_change_before_runtime_call():
    connector = SimpleNamespace(
        require_workspace_context=AsyncMock(side_effect=[CONTEXT, WorkspaceNotFoundError('Plugin resource not found')]),
        list_knowledge_engines=AsyncMock(return_value=[]),
    )
    router = object.__new__(KnowledgeMigrationRouterGroup)
    router.ap = SimpleNamespace(
        plugin_connector=connector,
        workspace_service=SimpleNamespace(
            get_local_execution_binding=AsyncMock(return_value=CONTEXT),
        ),
        logger=Mock(),
    )
    router._table_exists = AsyncMock(return_value=False)
    router._set_migration_flag = AsyncMock()
    task_context = SimpleNamespace(trace=Mock())

    with pytest.raises(WorkspaceNotFoundError, match='Plugin resource not found'):
        await router._execute_rag_migration(
            CONTEXT,
            task_context,
            install_plugin=False,
        )

    assert connector.require_workspace_context.await_count == 2
    connector.list_knowledge_engines.assert_not_awaited()
    router._set_migration_flag.assert_not_awaited()


@pytest.mark.asyncio
async def test_cloud_migration_is_rejected_before_legacy_table_access():
    router = object.__new__(KnowledgeMigrationRouterGroup)
    router.ap = SimpleNamespace(
        workspace_service=SimpleNamespace(
            get_local_execution_binding=AsyncMock(side_effect=WorkspaceInvariantError('not an OSS local workspace')),
        ),
        plugin_connector=SimpleNamespace(require_workspace_context=AsyncMock()),
        logger=Mock(),
    )
    router._table_exists = AsyncMock()
    router._set_migration_flag = AsyncMock()
    task_context = SimpleNamespace(trace=Mock())

    with pytest.raises(WorkspaceNotFoundError, match='migration is unavailable'):
        await router._execute_rag_migration(CONTEXT, task_context, install_plugin=False)

    router._table_exists.assert_not_awaited()
    router.ap.plugin_connector.require_workspace_context.assert_not_awaited()
    router._set_migration_flag.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('database_name, exists', [('postgresql', True), ('sqlite', False)])
async def test_legacy_table_discovery_uses_scoped_structured_queries(database_name: str, exists: bool):
    result = Mock()
    result.first.return_value = ('knowledge_bases_backup',) if exists else None
    execute_async = AsyncMock(return_value=result)
    router = object.__new__(KnowledgeMigrationRouterGroup)
    router.ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(
            db=SimpleNamespace(name=database_name),
            execute_async=execute_async,
        )
    )

    assert await router._table_exists('knowledge_bases_backup') is exists

    statement = execute_async.await_args.args[0]
    assert isinstance(statement, sqlalchemy.sql.selectable.SelectBase)
    _validate_scoped_statement_call((statement,), {})


@pytest.mark.asyncio
async def test_legacy_restore_emits_only_scoped_structured_statements():
    missing_table_result = Mock()
    missing_table_result.first.return_value = None
    existing_table_result = Mock()
    existing_table_result.first.return_value = ('knowledge_bases_backup',)
    backup_result = Mock()
    backup_result.keys.return_value = [
        'uuid',
        'name',
        'description',
        'emoji',
        'embedding_model_uuid',
        'top_k',
        'created_at',
        'updated_at',
    ]
    now = datetime.now()
    backup_result.fetchall.return_value = [
        ('kb-legacy', 'Legacy KB', 'Description', 'U0001f4da', 'embedding-model', 7, now, now)
    ]
    execute_async = AsyncMock(
        side_effect=[
            missing_table_result,
            existing_table_result,
            backup_result,
            Mock(),
            Mock(),
        ]
    )
    connector = SimpleNamespace(
        require_workspace_context=AsyncMock(return_value=CONTEXT),
        list_knowledge_engines=AsyncMock(return_value=[]),
        rag_on_kb_create=AsyncMock(),
    )
    router = object.__new__(KnowledgeMigrationRouterGroup)
    router.ap = SimpleNamespace(
        workspace_service=SimpleNamespace(
            get_local_execution_binding=AsyncMock(return_value=CONTEXT),
        ),
        plugin_connector=connector,
        persistence_mgr=SimpleNamespace(
            db=SimpleNamespace(name='sqlite'),
            execute_async=execute_async,
        ),
        rag_mgr=SimpleNamespace(load_knowledge_bases_from_db=AsyncMock()),
        logger=Mock(),
    )
    task_context = SimpleNamespace(trace=Mock())

    await router._execute_rag_migration(CONTEXT, task_context, install_plugin=False)

    statements = [call.args[0] for call in execute_async.await_args_list]
    assert any(isinstance(statement, sqlalchemy.sql.dml.Insert) for statement in statements)
    assert any(isinstance(statement, sqlalchemy.sql.dml.Update) for statement in statements)
    for statement in statements:
        assert not isinstance(statement, sqlalchemy.sql.elements.TextClause)
        _validate_scoped_statement_call((statement,), {})
    connector.rag_on_kb_create.assert_awaited_once_with(
        'langbot-team/LangRAG',
        'kb-legacy',
        {'embedding_model_uuid': 'embedding-model'},
    )


@pytest.mark.asyncio
async def test_legacy_restore_accepts_sqlite_string_dates_and_text_json_columns():
    engine = sqlalchemy.ext.asyncio.create_async_engine('sqlite+aiosqlite:///:memory:')
    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql(
                """
                CREATE TABLE knowledge_bases_backup (
                    uuid TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    emoji TEXT,
                    embedding_model_uuid TEXT,
                    top_k INTEGER,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
            await connection.exec_driver_sql(
                """
                CREATE TABLE external_knowledge_bases (
                    uuid TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    emoji TEXT,
                    plugin_author TEXT,
                    plugin_name TEXT,
                    retriever_config TEXT,
                    created_at DATETIME
                )
                """
            )
            await connection.exec_driver_sql(
                """
                CREATE TABLE knowledge_bases (
                    uuid TEXT PRIMARY KEY,
                    workspace_uuid TEXT NOT NULL,
                    name TEXT,
                    description TEXT,
                    emoji TEXT,
                    created_at DATETIME,
                    updated_at DATETIME,
                    knowledge_engine_plugin_id TEXT,
                    collection_id TEXT,
                    creation_settings TEXT,
                    retrieval_settings TEXT
                )
                """
            )
            await connection.exec_driver_sql(
                'CREATE TABLE workspace_metadata (workspace_uuid TEXT, key TEXT, value TEXT)'
            )
            legacy_timestamp = '2026-07-20 03:00:00.123456'
            await connection.exec_driver_sql(
                """
                INSERT INTO knowledge_bases_backup
                    (uuid, name, description, emoji, embedding_model_uuid, top_k, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    'kb-internal',
                    'Internal',
                    'Internal legacy KB',
                    'U0001f4da',
                    'embedding-model',
                    5,
                    legacy_timestamp,
                    legacy_timestamp,
                ),
            )
            await connection.exec_driver_sql(
                """
                INSERT INTO external_knowledge_bases
                    (uuid, name, description, emoji, plugin_author, plugin_name, retriever_config, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    'kb-external',
                    'External',
                    'External legacy KB',
                    'U0001f517',
                    'langbot-team',
                    'DifyDatasetsRetriever',
                    json.dumps({'api_base_url': 'https://example.invalid', 'top_k': 8}),
                    legacy_timestamp,
                ),
            )

            connector = SimpleNamespace(
                require_workspace_context=AsyncMock(return_value=CONTEXT),
                list_knowledge_engines=AsyncMock(return_value=[]),
                rag_on_kb_create=AsyncMock(),
            )
            router = object.__new__(KnowledgeMigrationRouterGroup)
            router.ap = SimpleNamespace(
                workspace_service=SimpleNamespace(
                    get_local_execution_binding=AsyncMock(return_value=CONTEXT),
                ),
                plugin_connector=connector,
                persistence_mgr=SimpleNamespace(
                    db=SimpleNamespace(name='sqlite'),
                    execute_async=connection.execute,
                ),
                rag_mgr=SimpleNamespace(load_knowledge_bases_from_db=AsyncMock()),
                logger=Mock(),
            )

            await router._execute_rag_migration(
                CONTEXT,
                SimpleNamespace(trace=Mock()),
                install_plugin=False,
            )

            restored = (
                await connection.exec_driver_sql(
                    """
                    SELECT uuid, created_at, updated_at, creation_settings, retrieval_settings
                    FROM knowledge_bases
                    ORDER BY uuid
                    """
                )
            ).all()
            assert [row.uuid for row in restored] == ['kb-external', 'kb-internal']
            assert all(row.created_at == legacy_timestamp for row in restored)
            assert all(row.updated_at == legacy_timestamp for row in restored)
            assert json.loads(restored[0].creation_settings)['api_base_url'] == 'https://example.invalid'
            assert json.loads(restored[0].retrieval_settings) == {'top_k': 8}
            assert json.loads(restored[1].creation_settings) == {'embedding_model_uuid': 'embedding-model'}
            assert json.loads(restored[1].retrieval_settings) == {'top_k': 5}
    finally:
        await engine.dispose()
