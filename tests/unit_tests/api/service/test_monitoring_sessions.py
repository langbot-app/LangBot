"""Bot-scoped session regressions exercised against real SQL databases."""

import datetime as dt
import logging
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.service.monitoring import MonitoringService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence import monitoring as models
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.pipeline.monitoring_helper import MonitoringHelper

from tests.integration.persistence.test_monitoring_postgres import cloud_database  # noqa: F401

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio(loop_scope='module')
async def test_postgres_upgrade_rls_and_concurrent_bot_counts(cloud_database):  # noqa: F811
    import asyncio
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from tests.integration.persistence.test_monitoring_postgres import WORKSPACE_A, _context, _read

    ap, admin = cloud_database
    service = ap.monitoring_service
    ctx = _context(WORKSPACE_A)
    await service.record_session_start(ctx, session_id='person_42', **resource('a'))
    for bot in ['a', 'b']:
        await service.record_message(ctx, session_id='person_42', message_content=bot, **resource(bot))
    async with admin.begin() as conn:

        def migrate(connection):
            migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0023_bot_scoped_sessions')
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                migration.upgrade()
            rls = connection.execute(
                sa.text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='monitoring_sessions'")
            ).one()
            assert tuple(rls) == (True, True)
            assert (
                connection.execute(
                    sa.text("SELECT count(*) FROM pg_policies WHERE tablename='monitoring_sessions'")
                ).scalar_one()
                == 1
            )

        await conn.run_sync(migrate)
    rows, total = await _read(service, 'get_sessions', ctx)
    assert total == 2
    assert {r['bot_id']: r['message_count'] for r in rows} == {'a': 1, 'b': 1}
    await asyncio.gather(*[service.record_session_start(ctx, session_id='race', **resource('a')) for _ in range(10)])
    result = await _read(service, 'get_session_analysis', ctx, 'race', bot_id='a')
    assert result['session']['message_count'] == 10
    assert not (await _read(service, 'get_session_analysis', ctx, 'person_42'))['found']
    assert (await _read(service, 'get_session_analysis', ctx, 'person_42', bot_id='b'))['message_stats']['total'] == 1


async def test_migration_reconstructs_collisions_and_preserves_indexes(service):
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    engine = service.ap.persistence_mgr.get_db_engine()
    async with engine.begin() as conn:

        def upgrade(connection):
            table = models.MonitoringSession.__table__
            table.drop(connection)
            metadata = sa.MetaData()
            legacy = table.to_metadata(metadata)
            legacy.primary_key._columns.remove(legacy.c.bot_id)
            legacy.c.bot_id.primary_key = False
            # Resolve the unchanged Workspace FK in copied metadata.
            Base.metadata.tables['workspaces'].to_metadata(metadata)
            legacy.create(connection)
            now = dt.datetime(2026, 1, 1)
            connection.execute(
                sa.insert(legacy).values(
                    workspace_uuid='workspace',
                    session_id='person_42',
                    **resource('a'),
                    message_count=99,
                    start_time=now,
                    last_activity=now,
                    is_active=True,
                )
            )
            for bot in ['a', 'b']:
                connection.execute(
                    sa.insert(models.MonitoringMessage).values(
                        id=bot,
                        workspace_uuid='workspace',
                        timestamp=now,
                        **resource(bot),
                        session_id='person_42',
                        message_content=bot,
                        role='user',
                        status='success',
                        level='info',
                    )
                )
            indexes = {i['name'] for i in sa.inspect(connection).get_indexes('monitoring_sessions')}
            migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0023_bot_scoped_sessions')
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()  # Fresh/already-upgraded schema is safe.
            assert sa.inspect(connection).get_pk_constraint('monitoring_sessions')['constrained_columns'] == [
                'workspace_uuid',
                'bot_id',
                'session_id',
            ]
            assert indexes <= {i['name'] for i in sa.inspect(connection).get_indexes('monitoring_sessions')}

        await conn.run_sync(upgrade)
    rows, total = await service.get_sessions(context())
    assert total == 2
    assert {r['bot_id']: r['message_count'] for r in rows} == {'a': 1, 'b': 1}
    assert {r['pipeline_id'] for r in rows} == {'a', 'b'}


def context(bot=None):
    return ExecutionContext(instance_uuid='test', workspace_uuid='workspace', placement_generation=1, bot_uuid=bot)


def resource(bot):
    return dict(bot_id=bot, bot_name=bot, pipeline_id=bot, pipeline_name=bot)


@pytest.fixture
async def service():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    class Persistence:
        serialize_model = PersistenceManager.serialize_model

        def get_db_engine(self):
            return engine

        async def execute_async(self, stmt):
            async with engine.begin() as conn:
                return await conn.execute(stmt)

    ap = SimpleNamespace(persistence_mgr=Persistence(), logger=logging.getLogger(__name__))
    ap.monitoring_service = MonitoringService(ap)
    yield ap.monitoring_service
    await engine.dispose()


async def test_helper_first_message_count_and_two_bot_isolation(service):
    for bot in ['a', 'b', 'a']:
        query = SimpleNamespace(
            _execution_context=context(bot),
            launcher_type='person',
            launcher_id=42,
            sender_id=42,
            message_chain=SimpleNamespace(model_dump=lambda: []),
        )
        assert await MonitoringHelper.record_query_start(service.ap, query, **resource(bot))
    rows, total = await service.get_sessions(context())
    assert total == 2
    assert {r['bot_id']: r['message_count'] for r in rows} == {'a': 2, 'b': 1}
    assert {r['pipeline_id'] for r in rows} == {'a', 'b'}
    assert {r['session_id'] for r in rows} == {'person_42'}


async def test_analysis_fails_closed_and_scopes_statistics(service):
    for bot in ['a', 'b']:
        await service.record_session_start(context(bot), session_id='person_42', **resource(bot))
        await service.record_message(context(bot), session_id='person_42', message_content=bot, **resource(bot))
    assert (await service.get_session_analysis(context(), 'person_42'))['found'] is False
    result = await service.get_session_analysis(context(), 'person_42', bot_id='b')
    assert result['message_stats']['total'] == 1
    assert result['session']['bot_id'] == 'b'


async def test_activity_requires_bot_and_upsert_counts_racing_first_queries(service):
    for _ in range(2):
        await service.record_session_start(context('a'), session_id='person_42', **resource('a'))
    with pytest.raises(ValueError, match='bot'):
        await service.update_session_activity(context(), 'person_42')
    assert await service.update_session_activity(context('a'), 'person_42')
    assert not await service.update_session_activity(context('b'), 'person_42')
    rows, _ = await service.get_sessions(context())
    assert rows[0]['message_count'] == 3


async def test_old_active_sessions_are_listed_exported_and_not_cleaned(service):
    for bot in ['a', 'b']:
        await service.record_session_start(context(bot), session_id='person_42', **resource(bot))
    old = dt.datetime(2000, 1, 1)
    await service.ap.persistence_mgr.execute_async(sa.update(models.MonitoringSession).values(start_time=old))
    await service.ap.persistence_mgr.execute_async(
        sa.update(models.MonitoringSession).where(models.MonitoringSession.bot_id == 'a').values(last_activity=old)
    )
    since = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(days=1)
    rows, total = await service.get_sessions(context(), start_time=since)
    assert total == 1 and rows[0]['bot_id'] == 'b'
    assert len(await service.export_sessions(context(), start_time=since)) == 1
    count = await service._delete_expired_in_batches(
        context(),
        models.MonitoringSession,
        models.MonitoringSession.last_activity,
        models.MonitoringSession.session_id,
        since,
        1,
        2,
    )
    assert count == 1
    rows, total = await service.get_sessions(context())
    assert total == 1 and rows[0]['bot_id'] == 'b'
