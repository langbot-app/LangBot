"""Contract tests for dialect-neutral persistence primitives and Stage 2 boundaries."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.application.contracts import ApplicationAPIException
from langbot.pkg.api.http.controller.groups.platform import bots as bots_controller_module
from langbot.pkg.api.http.service.bot import BotService
from langbot.pkg.command import builtin
from langbot.pkg.entity.persistence import user, workspace  # noqa: F401
from langbot.pkg.entity.persistence.artifact import Artifact
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.bot import Bot
from langbot.pkg.entity.persistence.event_log import EventLog
from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
from langbot.pkg.entity.persistence.monitoring import MonitoringLLMCall, MonitoringMessage, MonitoringSession
from langbot.pkg.persistence.dialect import (
    is_unique_violation,
    json_text,
    lock_rows_for_write,
    reserve_write_lock,
    resolve_dialect_name,
    table_exists_query,
    time_bucket,
    upsert_insert,
)
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.persistence.tenant_uow import TenantUnitOfWork, _validate_scoped_statement_call
from langbot.pkg.persistence.workspace_metadata import (
    delete_workspace_metadata,
    get_workspace_metadata,
    get_workspace_metadata_map,
    upsert_workspace_metadata,
)
from langbot.pkg.utils import execution_lease


def _compile(statement, dialect_name: str) -> str:
    dialect = postgresql.dialect() if dialect_name == 'postgresql' else sqlite.dialect()
    return str(statement.compile(dialect=dialect, compile_kwargs={'literal_binds': True}))


@pytest.mark.parametrize('dialect_name', ['sqlite', 'postgresql'])
def test_upsert_insert_compiles_for_both_dialects_and_passes_uow_validation(dialect_name: str):
    stmt = (
        upsert_insert(dialect_name, WorkspaceMetadata)
        .values(workspace_uuid='ws-1', key='k', value='v')
        .on_conflict_do_update(index_elements=['workspace_uuid', 'key'], set_={'value': 'v'})
    )
    _validate_scoped_statement_call((stmt,), {})
    sql = _compile(stmt, dialect_name)
    assert (
        'ON CONFLICT (workspace_uuid, "key") DO UPDATE SET value' in sql
        or 'ON CONFLICT (workspace_uuid, key) DO UPDATE SET value' in sql
    )


def test_upsert_insert_rejects_unsupported_dialect():
    with pytest.raises(ValueError, match='Unsupported database dialect'):
        upsert_insert('mysql', WorkspaceMetadata)


def test_resolve_dialect_name_supports_manager_engine_dialect_and_string():
    assert resolve_dialect_name('sqlite') == 'sqlite'
    assert resolve_dialect_name(postgresql.dialect()) == 'postgresql'
    assert resolve_dialect_name(SimpleNamespace(db=SimpleNamespace(name='postgresql'))) == 'postgresql'
    assert (
        resolve_dialect_name(SimpleNamespace(get_db_engine=lambda: SimpleNamespace(dialect=sqlite.dialect())))
        == 'sqlite'
    )
    with pytest.raises(ValueError, match='Unsupported database dialect target'):
        resolve_dialect_name(object())


@pytest.mark.parametrize(
    'dialect_name,bucket,iso_format,expected_fragment',
    [
        ('postgresql', 'hour', False, "date_trunc('hour'"),
        ('postgresql', 'day', True, "date_trunc('day'"),
        ('sqlite', 'hour', False, "strftime('%Y-%m-%d %H:00'"),
        ('sqlite', 'day', False, "strftime('%Y-%m-%d'"),
        ('sqlite', 'hour', True, "strftime('%Y-%m-%dT%H:00:00'"),
        ('sqlite', 'day', True, "strftime('%Y-%m-%dT00:00:00'"),
    ],
)
def test_time_bucket_contract_for_sqlite_and_postgresql(
    dialect_name: str,
    bucket: str,
    iso_format: bool,
    expected_fragment: str,
):
    expr = time_bucket(dialect_name, MonitoringMessage.timestamp, bucket=bucket, iso_format=iso_format)
    stmt = sa.select(expr)
    _validate_scoped_statement_call((stmt,), {})
    sql = _compile(stmt, dialect_name)
    assert expected_fragment in sql


def test_time_bucket_rejects_invalid_bucket_and_dialect():
    with pytest.raises(ValueError, match='Unsupported time bucket'):
        time_bucket('sqlite', MonitoringMessage.timestamp, bucket='week')
    with pytest.raises(ValueError, match='Unsupported database dialect'):
        time_bucket('oracle', MonitoringMessage.timestamp, bucket='hour')


@pytest.mark.parametrize('dialect_name', ['sqlite', 'postgresql'])
def test_json_text_contract_for_sqlite_and_postgresql(dialect_name: str):
    expr = json_text(dialect_name, EventLog.metadata_json, 'session_id')
    stmt = sa.select(expr)
    _validate_scoped_statement_call((stmt,), {})
    sql = _compile(stmt, dialect_name)
    if dialect_name == 'postgresql':
        assert 'CAST(event_log.metadata_json AS JSON)' in sql
    else:
        assert 'JSON_QUOTE' in sql or 'JSON_EXTRACT' in sql


@pytest.mark.parametrize('dialect_name', ['sqlite', 'postgresql'])
def test_table_exists_query_contract_for_sqlite_and_postgresql(dialect_name: str):
    stmt = table_exists_query(dialect_name, 'knowledge_bases_backup')
    _validate_scoped_statement_call((stmt,), {})
    sql = _compile(stmt, dialect_name)
    if dialect_name == 'postgresql':
        assert 'information_schema.tables' in sql
    else:
        assert 'sqlite_master' in sql


@pytest.mark.asyncio
async def test_reserve_write_lock_only_emits_update_on_sqlite():
    sqlite_executor = SimpleNamespace(execute=AsyncMock())
    await reserve_write_lock(
        sqlite_executor,
        'sqlite',
        Artifact,
        Artifact.workspace_uuid == 'ws-1',
        Artifact.id == '',
    )
    sqlite_executor.execute.assert_awaited_once()
    stmt = sqlite_executor.execute.await_args.args[0]
    _validate_scoped_statement_call((stmt,), {})
    assert str(stmt).startswith('UPDATE artifacts SET id=artifacts.id')

    pg_executor = SimpleNamespace(execute=AsyncMock())
    await reserve_write_lock(
        pg_executor,
        'postgresql',
        Artifact,
        Artifact.workspace_uuid == 'ws-1',
        Artifact.id == '',
    )
    pg_executor.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_lock_rows_for_write_emits_validated_update_for_both_dialects():
    executor = SimpleNamespace(execute=AsyncMock())
    await lock_rows_for_write(executor, Artifact, Artifact.workspace_uuid == 'ws-1', Artifact.id == 'art_1')
    executor.execute.assert_awaited_once()
    stmt = executor.execute.await_args.args[0]
    _validate_scoped_statement_call((stmt,), {})
    assert 'UPDATE artifacts SET id=artifacts.id' in _compile(stmt, 'sqlite')
    assert 'UPDATE artifacts SET id=artifacts.id' in _compile(stmt, 'postgresql')


@pytest.mark.asyncio
async def test_lock_helpers_reject_empty_where_predicates():
    executor = SimpleNamespace(execute=AsyncMock())
    with pytest.raises(ValueError, match='at least one WHERE predicate'):
        await lock_rows_for_write(executor, Artifact)
    with pytest.raises(ValueError, match='at least one WHERE predicate'):
        await reserve_write_lock(executor, 'sqlite', Artifact)
    with pytest.raises(ValueError, match='at least one WHERE predicate'):
        await reserve_write_lock(executor, 'postgresql', Artifact)
    executor.execute.assert_not_awaited()


def test_is_unique_violation_classifies_postgres_and_sqlite_errors():
    class _PGDiag:
        def __init__(self, constraint_name: str | None = None, message_detail: str | None = None):
            self.constraint_name = constraint_name
            self.message_detail = message_detail

    class _PGError(Exception):
        def __init__(
            self,
            sqlstate: str,
            constraint_name: str | None = None,
            *,
            diag_constraint: str | None = None,
            detail: str | None = None,
        ):
            super().__init__(f'pg error {sqlstate} {constraint_name or diag_constraint}')
            self.sqlstate = sqlstate
            self.constraint_name = constraint_name
            self.detail = detail
            self.diag = _PGDiag(diag_constraint, detail) if (diag_constraint or detail) else None

    class _SQLiteError(Exception):
        def __init__(self, code: int, name: str | None, msg: str):
            super().__init__(msg)
            self.sqlite_errorcode = code
            self.sqlite_errorname = name

    full_insert_sql = (
        'INSERT INTO bot_admins (id, workspace_uuid, bot_uuid, launcher_type, launcher_id) VALUES (?, ?, ?, ?, ?)'
    )
    target_columns = ('workspace_uuid', 'bot_uuid', 'launcher_type', 'launcher_id')

    pg_dup = IntegrityError(full_insert_sql, {}, _PGError('23505', 'uq_bot_admin'))
    assert is_unique_violation(pg_dup, constraints=('uq_bot_admin',)) is True
    assert is_unique_violation(pg_dup, constraints=('uq_other',)) is False

    # Case-insensitive diag.constraint_name match
    pg_diag_dup = IntegrityError(full_insert_sql, {}, _PGError('23505', diag_constraint='UQ_BOT_ADMIN'))
    assert is_unique_violation(pg_diag_dup, constraints=('uq_bot_admin',)) is True

    # Same-table PG PK collision must not match target constraint or columns via [SQL: ...]
    pg_pk_dup = IntegrityError(
        full_insert_sql,
        {'launcher_id': 'uq_bot_admin'},
        _PGError('23505', diag_constraint='bot_admins_pkey', detail='Key (id)=(1) already exists.'),
    )
    assert is_unique_violation(pg_pk_dup, constraints=('uq_bot_admin',), columns=target_columns) is False
    assert is_unique_violation(pg_pk_dup, columns=target_columns) is False

    pg_detail_cols = IntegrityError(
        full_insert_sql,
        {},
        _PGError(
            '23505',
            detail='Key (workspace_uuid, bot_uuid, launcher_type, launcher_id)=(ws, b, person, a) already exists.',
        ),
    )
    assert is_unique_violation(pg_detail_cols, columns=target_columns) is True

    pg_fk = IntegrityError(full_insert_sql, {}, _PGError('23503', 'fk_bot_admins_workspace_bot'))
    assert is_unique_violation(pg_fk, constraints=('uq_bot_admin',)) is False
    assert is_unique_violation(pg_fk) is False

    sqlite_dup = IntegrityError(
        full_insert_sql,
        {},
        _SQLiteError(
            2067,
            'SQLITE_CONSTRAINT_UNIQUE',
            'UNIQUE constraint failed: bot_admins.workspace_uuid, bot_admins.bot_uuid, bot_admins.launcher_type, bot_admins.launcher_id',
        ),
    )
    assert is_unique_violation(sqlite_dup, constraints=('uq_bot_admin',), columns=target_columns) is True
    assert is_unique_violation(sqlite_dup, columns=('nonexistent_col',)) is False

    # Counterexample 1: same-table SQLite PK collision (1555) must NOT match via [SQL: ...]
    sqlite_pk_dup = IntegrityError(
        full_insert_sql,
        {'launcher_id': 'uq_bot_admin'},
        _SQLiteError(1555, 'SQLITE_CONSTRAINT_PRIMARYKEY', 'UNIQUE constraint failed: bot_admins.id'),
    )
    assert is_unique_violation(sqlite_pk_dup, constraints=('uq_bot_admin',), columns=target_columns) is False

    # Counterexample 2: parameter pollution with generic sqlite_code == 19 (no errorname) must NOT match
    polluted_params = {
        'launcher_id': (
            'UNIQUE constraint failed: bot_admins.workspace_uuid, bot_admins.bot_uuid, '
            'bot_admins.launcher_type, bot_admins.launcher_id uq_bot_admin'
        )
    }
    sqlite_generic_fk = IntegrityError(
        full_insert_sql,
        polluted_params,
        _SQLiteError(19, None, 'FOREIGN KEY constraint failed'),
    )
    assert is_unique_violation(sqlite_generic_fk, constraints=('uq_bot_admin',), columns=target_columns) is False
    assert is_unique_violation(sqlite_generic_fk) is False

    # Counterexample 3: fallback path without sqlite_code/sqlstate must still ignore [parameters: ...]
    fallback_fk = IntegrityError(
        full_insert_sql,
        polluted_params,
        RuntimeError('FOREIGN KEY constraint failed'),
    )
    assert is_unique_violation(fallback_fk, constraints=('uq_bot_admin',), columns=target_columns) is False

    sqlite_fk = IntegrityError(
        full_insert_sql,
        {},
        _SQLiteError(787, 'SQLITE_CONSTRAINT_FOREIGNKEY', 'FOREIGN KEY constraint failed'),
    )
    assert is_unique_violation(sqlite_fk) is False


@pytest.mark.asyncio
async def test_workspace_metadata_does_not_synthesize_execute_async_on_mock_uow():
    from unittest.mock import MagicMock

    uow = MagicMock()
    uow.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: 'zh_Hans'))
    value = await get_workspace_metadata(uow, 'ws-1', 'message_language')
    assert value == 'zh_Hans'
    uow.execute.assert_awaited_once()
    assert 'execute_async' not in uow.__dict__


@pytest.mark.asyncio
async def test_workspace_metadata_kv_helpers_and_table_exists_on_sqlite():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        mgr = PersistenceManager(SimpleNamespace(instance_config=SimpleNamespace(data={})))
        mgr.db = SimpleNamespace(name='sqlite', get_engine=lambda: engine)

        assert await mgr.table_exists('workspace_metadata') is True
        assert await mgr.table_exists('nonexistent_legacy_table') is False

        async with mgr.tenant_uow('ws-1') as uow:
            assert await get_workspace_metadata(uow, 'ws-1', 'k1') is None
            await upsert_workspace_metadata(uow, 'ws-1', 'k1', 'v1')
            await upsert_workspace_metadata(uow, 'ws-1', 'k2', 'v2')
            await upsert_workspace_metadata(uow, 'ws-1', 'k1', 'v1-updated')
            assert await get_workspace_metadata(uow, 'ws-1', 'k1') == 'v1-updated'
            assert await get_workspace_metadata_map(uow, 'ws-1', ('k1', 'k2')) == {'k1': 'v1-updated', 'k2': 'v2'}

        # Also works directly against PersistenceManager.execute_async
        await upsert_workspace_metadata(mgr, 'ws-1', 'k3', 'v3')
        assert await get_workspace_metadata(mgr, 'ws-1', 'k3') == 'v3'

        async with mgr.tenant_uow('ws-1') as uow:
            await delete_workspace_metadata(uow, 'ws-1', ('k1', 'k3'))
            assert await get_workspace_metadata_map(uow, 'ws-1', ('k1', 'k2', 'k3')) == {'k2': 'v2'}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_builtin_status_and_usage_use_tenant_uow_on_real_sqlite():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                sa.insert(MonitoringSession).values(
                    workspace_uuid='ws-1',
                    session_id='person_alice',
                    bot_id='bot-1',
                    bot_name='Bot 1',
                    pipeline_id='pipe-1',
                    pipeline_name='Pipe 1',
                    message_count=7,
                    start_time=datetime.datetime(2026, 11, 1),
                    last_activity=datetime.datetime(2026, 11, 1),
                    is_active=True,
                )
            )
            await conn.execute(
                sa.insert(MonitoringLLMCall).values(
                    id='call-1',
                    workspace_uuid='ws-1',
                    timestamp=datetime.datetime(2026, 11, 1),
                    model_name='gpt-test',
                    status='success',
                    duration=10,
                    bot_id='bot-1',
                    bot_name='Bot 1',
                    pipeline_id='pipe-1',
                    pipeline_name='Pipe 1',
                    session_id='person_alice',
                    input_tokens=10,
                    output_tokens=20,
                    total_tokens=30,
                )
            )

        mgr = PersistenceManager(SimpleNamespace(instance_config=SimpleNamespace(data={})))
        mgr.db = SimpleNamespace(name='sqlite', get_engine=lambda: engine)

        uow_calls: list[str] = []

        def tracking_tenant_uow(ws_uuid: str):
            uow_calls.append(ws_uuid)
            return mgr.tenant_uow(ws_uuid)

        # Expose only tenant_uow so any bare get_db_engine().connect() bypass fails.
        scoped_only_mgr = SimpleNamespace(tenant_uow=tracking_tenant_uow)

        app = SimpleNamespace(
            persistence_mgr=scoped_only_mgr,
            model_mgr=SimpleNamespace(runtime_llm_models_for_workspace=lambda ws: {}),
            runner_registry=SimpleNamespace(get=AsyncMock(return_value=None)),
        )
        bot = SimpleNamespace(
            ap=app,
            execution_context=SimpleNamespace(workspace_uuid='ws-1'),
            bot_entity=SimpleNamespace(name='Bot 1', command_settings={}),
        )
        query = SimpleNamespace(
            launcher_type=SimpleNamespace(value='person'),
            launcher_id='alice',
            bot_uuid='bot-1',
        )
        event = SimpleNamespace(sender=SimpleNamespace(id='alice'), _selected_route={})

        usage_reply = await builtin.execute_builtin(bot, event, None, 'usage', 'usage', query, None, False)
        status_reply = await builtin.execute_builtin(bot, event, None, 'status', 'status', query, None, False)

        assert 'Messages: 7' in usage_reply
        assert 'Tokens: 30' in usage_reply
        assert 'Messages: 7' in status_reply
        assert uow_calls == ['ws-1', 'ws-1']
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_execution_lease_reconcile_uses_tenant_uow(monkeypatch):
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        entered: list[str] = []

        class _SpyUoW(TenantUnitOfWork):
            async def __aenter__(self):
                entered.append(self.workspace_uuid)
                return await super().__aenter__()

        monkeypatch.setattr(execution_lease, 'TenantUnitOfWork', _SpyUoW)
        changed = await execution_lease.reconcile_execution_leases(
            engine,
            'ws-lease',
            now=datetime.datetime(2026, 11, 1),
            owner_id='host-1',
        )
        assert changed == 0
        assert entered == ['ws-lease', 'ws-lease']
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_bot_admin_duplicate_translates_to_409_without_leaking_driver_error():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                sa.insert(workspace.Workspace).values(
                    uuid='ws-1',
                    instance_uuid='inst-1',
                    name='WS 1',
                    slug='ws-1',
                )
            )
            await conn.execute(
                sa.insert(Bot).values(
                    uuid='bot-1',
                    workspace_uuid='ws-1',
                    name='Bot 1',
                    description='',
                    adapter='http',
                    adapter_config={},
                    enable=False,
                )
            )

        mgr = PersistenceManager(SimpleNamespace(instance_config=SimpleNamespace(data={})))
        mgr.db = SimpleNamespace(name='sqlite', get_engine=lambda: engine)
        service = BotService(SimpleNamespace(persistence_mgr=mgr))

        admin_id = await service.add_bot_admin('ws-1', 'bot-1', 'person', 'alice')
        assert isinstance(admin_id, int)

        with pytest.raises(ApplicationAPIException) as exc_info:
            await service.add_bot_admin('ws-1', 'bot-1', 'person', 'alice')
        assert exc_info.value.error.status_code == 409
        assert exc_info.value.error.code == 'bot_admin_exists'
        assert 'sqlite' not in exc_info.value.error.message.lower()
        assert 'constraint' not in exc_info.value.error.message.lower()

        # Verify controller module does not import IntegrityError directly
        assert not hasattr(bots_controller_module, 'IntegrityError')
    finally:
        await engine.dispose()
