"""Monitoring regressions through asyncpg, Cloud UoW guards, and migrated RLS.

TEST_POSTGRES_URL must identify a disposable PostgreSQL/pgvector test server
with permission to create databases and roles. Each run owns a fresh database;
no existing tables are dropped. Without that URL these tests are skipped.
"""

from __future__ import annotations

import logging
import os
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.service.monitoring import MonitoringService
from langbot.pkg.entity.persistence import monitoring as models
from langbot.pkg.entity.persistence.workspace import Workspace
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.persistence.tenant_uow import TenantScopeRequiredError
from langbot.pkg.pipeline.monitoring_helper import MonitoringHelper

pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.asyncio(loop_scope='module')]

WORKSPACE_A = '00000000-0000-0000-0000-00000000000a'
WORKSPACE_B = '00000000-0000-0000-0000-00000000000b'
RESOURCE = dict(bot_id='same-bot', bot_name='Bot', pipeline_id='same-pipeline', pipeline_name='Pipeline')
MONITORING_TABLES = tuple(
    table for table in models.MonitoringMessage.metadata.sorted_tables if table.name.startswith('monitoring_')
)


def _context(workspace_uuid):
    return ExecutionContext(
        instance_uuid='monitoring-postgres-test',
        workspace_uuid=workspace_uuid,
        placement_generation=1,
        bot_uuid=RESOURCE['bot_id'],
        pipeline_uuid=RESOURCE['pipeline_id'],
    )


def _application(url):
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
        logger=logging.getLogger('monitoring-postgres-test'),
    )


@pytest_asyncio.fixture(scope='module', loop_scope='module')
async def cloud_database():
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL not set')
    admin_url = sa.engine.make_url(url)
    admin = create_async_engine(admin_url, isolation_level='AUTOCOMMIT')
    suffix = uuid.uuid4().hex[:12]
    database_name = f'lb_monitoring_{suffix}'
    runtime_role = f'lb_monitoring_{suffix}'
    password = f'Test{uuid.uuid4().hex}'
    database_created = role_created = False
    release_manager = runtime_manager = None
    quote = admin.dialect.identifier_preparer.quote
    from langbot.pkg.persistence import mgr as mgr_module
    from langbot.pkg.persistence.databases.postgresql import PostgreSQLDatabaseManager
    from langbot.pkg.utils import constants

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(mgr_module.database, 'preregistered_managers', [PostgreSQLDatabaseManager])
        patch.setattr(constants, 'instance_id', 'monitoring-postgres-test')
        try:
            async with admin.connect() as conn:
                await conn.execute(sa.text(f'CREATE DATABASE {quote(database_name)}'))
                database_created = True
                await conn.execute(
                    sa.text(f"CREATE ROLE {quote(runtime_role)} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
                )
                role_created = True
            release_app = _application(admin_url.set(database=database_name))
            release_manager = PersistenceManager(release_app, mode=PersistenceMode.RELEASE_MIGRATION)
            release_app.persistence_mgr = release_manager
            await release_manager.initialize()
            async with release_manager.get_db_engine().begin() as conn:
                for workspace in (WORKSPACE_A, WORKSPACE_B):
                    await conn.execute(
                        sa.insert(Workspace).values(
                            uuid=workspace,
                            instance_uuid='monitoring-postgres-test',
                            name=workspace,
                            slug=workspace,
                            source='cloud_projection',
                        )
                    )
                tables = release_manager._runtime_business_table_names()
                quoted_tables = ', '.join(f'public.{quote(name)}' for name in tables)
                await conn.execute(
                    sa.text(f'GRANT CONNECT ON DATABASE {quote(database_name)} TO {quote(runtime_role)}')
                )
                await conn.execute(sa.text(f'GRANT USAGE ON SCHEMA public TO {quote(runtime_role)}'))
                await conn.execute(
                    sa.text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {quoted_tables} TO {quote(runtime_role)}')
                )
                await conn.execute(sa.text(f'GRANT SELECT ON public.alembic_version TO {quote(runtime_role)}'))
                sequences = await release_manager._runtime_business_sequence_names(conn, tables)
                if sequences:
                    names = ', '.join(f'public.{quote(name)}' for name in sequences)
                    await conn.execute(sa.text(f'GRANT USAGE, SELECT ON SEQUENCE {names} TO {quote(runtime_role)}'))
            runtime_app = _application(admin_url.set(database=database_name, username=runtime_role, password=password))
            runtime_manager = PersistenceManager(runtime_app, mode=PersistenceMode.CLOUD_RUNTIME)
            runtime_app.persistence_mgr = runtime_manager
            await runtime_manager.initialize()
            runtime_app.monitoring_service = MonitoringService(runtime_app)
            yield runtime_app, release_manager.get_db_engine()
        finally:
            if runtime_manager is not None:
                await runtime_manager.shutdown()
            if release_manager is not None:
                await release_manager.shutdown()
            async with admin.connect() as conn:
                if database_created:
                    await conn.execute(sa.text(f'DROP DATABASE {quote(database_name)} WITH (FORCE)'))
                if role_created:
                    await conn.execute(sa.text(f'DROP ROLE {quote(runtime_role)}'))
            await admin.dispose()


@pytest_asyncio.fixture(loop_scope='module')
async def service(cloud_database):
    application, admin = cloud_database
    async with admin.begin() as conn:
        for table in MONITORING_TABLES:
            await conn.execute(sa.delete(table))
    application.instance_config.data.pop('monitoring', None)
    return application.monitoring_service


async def _read(service, method, context, *args, **kwargs):
    # HTTP auth binds a tenant scope; exercise that same guard for service reads.
    async with service.ap.persistence_mgr.tenant_scope(context.workspace_uuid):
        return await getattr(service, method)(context, *args, **kwargs)


def _query(context, sender_id):
    return SimpleNamespace(
        _execution_context=context,
        launcher_type='person',
        launcher_id='same-user',
        sender_id=sender_id,
        message_chain=SimpleNamespace(model_dump=lambda: [{'type': 'Plain', 'text': 'hello'}]),
        resp_message_chain=[SimpleNamespace(model_dump=lambda: [{'type': 'Plain', 'text': 'reply'}])],
        message_event=SimpleNamespace(sender=SimpleNamespace(nickname='Alice')),
        variables={'public': 'value', '_private': 'hidden'},
    )


@pytest.mark.parametrize('user_id', [123456789, -100123456789, 0, None, '', '00123', '  opaque用户  '])
@pytest.mark.parametrize('record_type', ['message', 'session', 'feedback'])
async def test_optional_user_ids_round_trip_through_asyncpg(service, user_id, record_type):
    context = _context(WORKSPACE_A)
    expected = str(user_id) if isinstance(user_id, int) else user_id
    if record_type == 'message':
        record_id = await service.record_message(
            context,
            **RESOURCE,
            message_content='hello',
            session_id='same-session',
            user_id=user_id,
        )
        details = await _read(service, 'get_message_details', context, record_id)
        assert details['message']['user_id'] == expected
    elif record_type == 'session':
        await service.record_session_start(context, **RESOURCE, session_id='same-session', user_id=user_id)
        rows, total = await _read(service, 'get_sessions', context)
        assert total == 1
        assert rows[0]['user_id'] == expected
    else:
        await service.record_feedback(context, feedback_id='same-feedback', feedback_type=1, user_id=user_id)
        rows, total = await _read(service, 'get_feedback_list', context)
        assert total == 1
        assert rows[0]['user_id'] == expected


@pytest.mark.parametrize('user_id', [123456789, -100123456789])
async def test_query_lifecycle_persists_messages_session_and_llm_link(service, user_id, caplog):
    context = _context(WORKSPACE_A)
    query = _query(context, user_id)
    message_id = await MonitoringHelper.record_query_start(service.ap, query, **RESOURCE)
    assert message_id, caplog.text
    await MonitoringHelper.record_llm_call(
        service.ap,
        query,
        **RESOURCE,
        model_name='model',
        input_tokens=3,
        output_tokens=5,
        duration_ms=25,
        message_id=message_id,
    )
    await MonitoringHelper.record_query_success(service.ap, message_id, query)
    await MonitoringHelper.record_query_response(service.ap, query, **RESOURCE)
    rows, total = await _read(service, 'get_messages', context)
    assert total == 2
    assert {row['role'] for row in rows} == {'user', 'assistant'}
    assert {row['user_id'] for row in rows} == {str(user_id)}
    details = await _read(service, 'get_message_details', context, message_id)
    assert details['message']['status'] == 'success'
    assert details['message']['variables'] == '{"public": "value"}'
    assert details['llm_calls'][0]['message_id'] == message_id
    assert details['llm_stats']['total_tokens'] == 8
    sessions, total = await _read(service, 'get_sessions', context)
    assert total == 1
    assert sessions[0]['session_id'] == 'person_same-user'
    assert sessions[0]['user_id'] == str(user_id)
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


@pytest.mark.parametrize('user_id', [123, -123])
async def test_query_error_persists_error_message_and_linked_log(service, user_id, caplog):
    context = _context(WORKSPACE_A)
    message_id = await MonitoringHelper.record_query_error(
        service.ap,
        _query(context, user_id),
        **RESOURCE,
        error=ValueError('failed query'),
    )
    assert message_id, caplog.text
    details = await _read(service, 'get_message_details', context, message_id)
    assert details['message']['user_id'] == str(user_id)
    assert details['message']['status'] == 'error'
    assert details['errors'][0]['message_id'] == message_id
    assert details['errors'][0]['error_type'] == 'ValueError'


@pytest.mark.parametrize('user_id', [True, 1.5, b'123', ['123']])
@pytest.mark.parametrize('record_type', ['message', 'session', 'feedback'])
async def test_unsupported_user_ids_fail_at_the_write_boundary(service, user_id, record_type):
    context = _context(WORKSPACE_A)
    with pytest.raises(TypeError, match='user_id must be a string, integer, or None'):
        if record_type == 'message':
            await service.record_message(
                context,
                **RESOURCE,
                message_content='hello',
                session_id='session',
                user_id=user_id,
            )
        elif record_type == 'session':
            await service.record_session_start(context, **RESOURCE, session_id='session', user_id=user_id)
        else:
            await service.record_feedback(context, feedback_id='feedback', feedback_type=1, user_id=user_id)
    async with service.ap.persistence_mgr.tenant_scope(WORKSPACE_A):
        for model in (models.MonitoringMessage, models.MonitoringSession, models.MonitoringFeedback):
            count = await service.ap.persistence_mgr.execute_async(sa.select(sa.func.count()).select_from(model))
            assert count.scalar_one() == 0


async def test_session_analysis_aggregates_under_cloud_sql_guard(service):
    context = _context(WORKSPACE_A)
    await service.record_session_start(context, **RESOURCE, session_id='same-session')
    await service.record_message(context, **RESOURCE, session_id='same-session', message_content='hello')
    result = await _read(service, 'get_session_analysis', context, 'same-session')
    assert result['found'] is True
    assert result['message_stats'] == {'total': 1, 'success': 1, 'error': 0, 'pending': 0}
    assert result['llm_stats']['total_calls'] == 0
    assert result['tool_stats']['total_calls'] == 0
    assert result['session_duration_seconds'] == 0


async def test_rls_is_enforced_without_application_workspace_predicates(service, cloud_database):
    _, admin = cloud_database
    for workspace in (WORKSPACE_A, WORKSPACE_B):
        await service.record_message(
            _context(workspace), **RESOURCE, session_id='same-session', message_content=workspace
        )
    async with admin.connect() as conn:
        states = (
            await conn.execute(
                sa.text(
                    'SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class '
                    "WHERE relname LIKE 'monitoring_%' AND relkind = 'r'"
                )
            )
        ).all()
        assert len(states) == len(MONITORING_TABLES)
        assert all(enabled and forced for _, enabled, forced in states)
    engine = service.ap.persistence_mgr.get_db_engine()
    async with engine.connect() as conn:
        role = (
            await conn.execute(sa.text('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user'))
        ).one()
        assert role == (False, False)
        assert (await conn.execute(sa.select(models.MonitoringMessage.id))).all() == []
    for workspace in (WORKSPACE_A, WORKSPACE_B):
        async with service.ap.persistence_mgr.tenant_uow(workspace):
            rows = (
                await service.ap.persistence_mgr.execute_async(sa.select(models.MonitoringMessage.workspace_uuid))
            ).all()
            assert rows == [(workspace,)]
    with pytest.raises(TenantScopeRequiredError):
        await service.ap.persistence_mgr.execute_async(sa.select(models.MonitoringMessage.id))


async def test_traffic_series_aggregates_all_rows_under_cloud_rls(service):
    import datetime
    from langbot.pkg.api.http.service.monitoring_traffic import get_traffic_series

    context = _context(WORKSPACE_A)
    for workspace, count in ((WORKSPACE_A, 61), (WORKSPACE_B, 2)):
        async with service.ap.persistence_mgr.tenant_scope(workspace):
            await service.ap.persistence_mgr.execute_async(
                sa.insert(models.MonitoringMessage).values(
                    [
                        dict(
                            workspace_uuid=workspace,
                            id=f'{workspace}-m-{i}',
                            **RESOURCE,
                            session_id='shared',
                            message_content='test',
                            status='success',
                            level='info',
                            timestamp=datetime.datetime(2026, 9, 11, 1, 30),
                        )
                        for i in range(count)
                    ]
                )
            )
    async with service.ap.persistence_mgr.tenant_uow(WORKSPACE_A):
        result = await get_traffic_series(
            service.ap,
            context,
            bot_ids=[RESOURCE['bot_id']],
            start_time=datetime.datetime(2026, 9, 11),
            end_time=datetime.datetime(2026, 9, 12),
        )
    assert result['truncated'] is False
    assert sum(point['messages'] for point in result['points']) == 61
