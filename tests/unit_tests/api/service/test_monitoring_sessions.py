"""Bot-scoped session regressions exercised against real SQL databases."""

import datetime as dt
import contextvars
import logging
from collections import Counter
from itertools import permutations
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.service.monitoring import MonitoringService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence import monitoring as models
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.persistence.session_summary_backfill import SessionSummaryBackfill
from langbot.pkg.persistence.session_summary_contract import SessionSummaryChange
from langbot.pkg.persistence.session_summary_writer import SessionSummaryWriter, message_summary_change
from langbot.pkg.pipeline.monitoring_helper import MonitoringHelper

from tests.integration.persistence.test_monitoring_postgres import cloud_database  # noqa: F401

pytestmark = [pytest.mark.asyncio, pytest.mark.session_summary]


@pytest.mark.asyncio(loop_scope='module')
@pytest.mark.postgres
@pytest.mark.contract('monitoring_sessions')
async def test_postgres_upgrade_rls_and_concurrent_bot_counts(cloud_database):  # noqa: F811
    import asyncio
    import importlib
    import json
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from langbot.pkg.entity.persistence.event_log import EventLog
    from tests.integration.persistence.test_monitoring_postgres import WORKSPACE_A, _context, _read

    ap, admin = cloud_database
    service = ap.monitoring_service
    ctx = _context(WORKSPACE_A)
    for bot in ['a', 'b']:
        await service.record_message(ctx, session_id='person_42', message_content=bot, **resource(bot))
    async with admin.begin() as conn:

        def migrate(connection):
            migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0023_bot_scoped_sessions')
            summaries = importlib.import_module('langbot.pkg.persistence.alembic.versions.0040_session_summaries')
            # Recreate the pre-0023 collision: one summary, two bots' message histories.
            connection.execute(sa.delete(models.MonitoringSession).where(models.MonitoringSession.bot_id == 'b'))
            with Operations.context(MigrationContext.configure(connection)):
                summaries.downgrade()
                migration.downgrade()
                migration.upgrade()
                summaries.upgrade()
            # Recreating a table in this downgrade test also recreates its grants.
            role = connection.dialect.identifier_preparer.quote(ap.persistence_mgr.get_db_engine().url.username)
            connection.execute(
                sa.text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON monitoring_session_receipts TO {role}')
            )
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
    async with admin.begin() as conn:
        await conn.execute(
            sa.insert(EventLog).values(
                workspace_id=WORKSPACE_A,
                bot_id='legacy-ingress',
                event_id='legacy-ingress-event',
                event_type='message.received',
                source='platform',
                conversation_id='legacy-ingress-session',
                actor_id='42',
                actor_name='Alice',
                metadata_json=json.dumps(
                    {'routes': [{'status': 'failed'}, {'target_uuid': 'agent-first', 'target_type': 'agent'}]}
                ),
            )
        )
    backfill = SessionSummaryBackfill(service._summary_session, 'postgresql')
    while not await backfill.run_batch(WORKSPACE_A):
        pass
    rebuilt = (await _read(service, 'get_sessions', ctx, bot_ids=['legacy-ingress']))[0][0]
    assert (rebuilt['user_id'], rebuilt['user_name'], rebuilt['pipeline_id'], rebuilt['message_count']) == (
        '42',
        'Alice',
        'agent-first',
        1,
    )
    await service.record_ingress_event(
        ctx,
        event_id='legacy-ingress-event',
        event_type='message.received',
        bot_id='legacy-ingress',
        bot_name='',
        platform=None,
        payload={},
        conversation_id='legacy-ingress-session',
    )
    replayed = (await _read(service, 'get_sessions', ctx, bot_ids=['legacy-ingress']))[0][0]
    assert replayed == rebuilt
    await asyncio.gather(
        *[service.record_message(ctx, session_id='race', message_content='hello', **resource('a')) for _ in range(10)]
    )
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


def session_counts_from_facts(messages, ingresses):
    """Count distinct records and unmatched platform inputs, without projection state."""
    counts = Counter((m['bot_id'], m['session_id']) for m in messages.values())
    covered = {
        (message['bot_id'], alias)
        for identity, message in messages.items()
        if message['role'] != 'assistant'
        for alias in (identity, message['event_id'])
        if alias is not None
    }
    counts.update(
        (event['bot_id'], event['session_id'])
        for identity, event in ingresses.items()
        if (event['bot_id'], identity) not in covered
    )
    return dict(counts)


async def replay_summary_message(service, workspace, identity):
    """Replay a persisted source through the production projection entrypoint."""
    async with service._summary_session(workspace) as session:
        row = (
            (
                await session.execute(
                    sa.select(*models.MonitoringMessage.__table__.columns).where(
                        models.MonitoringMessage.workspace_uuid == workspace, models.MonitoringMessage.id == identity
                    )
                )
            )
            .mappings()
            .one()
        )
        await service._summary_writer().apply_once(session, message_summary_change(workspace, row))


async def rebuild_summaries(service, *, batch_size=100):
    """Initialize summaries from source history, without existing projection state."""
    from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
    from langbot.pkg.persistence.session_summary_backfill import CURSOR_KEY

    async with service.ap.persistence_mgr.get_db_engine().begin() as connection:
        await connection.execute(sa.delete(models.MonitoringSessionReceipt))
        await connection.execute(sa.delete(models.MonitoringSession))
        await connection.execute(sa.delete(WorkspaceMetadata).where(WorkspaceMetadata.key == CURSOR_KEY))
    while not await SessionSummaryBackfill(service._summary_session, 'sqlite').run_batch('workspace', batch_size):
        pass


@pytest.fixture
async def service():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    class Persistence:
        serialize_model = PersistenceManager.serialize_model
        active_transaction = contextvars.ContextVar('summary-test-transaction', default=None)

        def tenant_uow(self, workspace):
            from langbot.pkg.persistence.tenant_uow import TenantUnitOfWork

            return TenantUnitOfWork(engine, workspace, active_transaction=self.active_transaction)

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


@pytest.mark.parametrize('user_id', ['alice-id', 'bob-id', None, ''])
@pytest.mark.parametrize('user_name', [None, ''])
@pytest.mark.parametrize('backfill', [False, True])
async def test_summary_does_not_inherit_missing_nicknames(service, user_id, user_name, backfill):
    await service.record_message(
        context('a'),
        **resource('a'),
        session_id='group_42',
        message_content='one',
        user_id='alice-id',
        user_name='Alice Display',
    )
    await service.record_message(
        context('a'),
        **resource('a'),
        session_id='group_42',
        message_content='two',
        user_id=user_id,
        user_name=user_name,
    )
    if backfill:
        await rebuild_summaries(service)
    rows, total = await service.get_sessions(context())
    assert total == 1 and rows[0]['message_count'] == 2
    assert rows[0]['user_id'] == user_id
    assert rows[0]['user_name'] == user_name
    assert (await service.get_sessions(context(), user_query='Alice Display'))[1] == 0


@pytest.mark.contract('summary_accounting')
@pytest.mark.parametrize('order', list(permutations(range(3))))
@pytest.mark.parametrize('users', [('alice', 'alice', 'alice'), ('alice', 'bob', 'alice')])
@pytest.mark.parametrize('missing_name', [None, ''])
async def test_missing_nickname_is_consistent_after_out_of_order_writes(service, order, users, missing_name):
    writer = SessionSummaryWriter('sqlite')
    for index in order:
        change = SessionSummaryChange(
            workspace='workspace',
            bot_id='a',
            session_id='group_42',
            source_key=f'message:{index}',
            timestamp=dt.datetime(2026, 1, index + 1),
            bot_name='Bot',
            user_id=users[index],
            user_name=('Alice', 'Alicia' if users[1] == 'alice' else 'Bob', missing_name)[index],
        )
        async with service._summary_session('workspace') as session:
            await session.execute(
                sa.insert(models.MonitoringMessage).values(
                    id=str(index),
                    workspace_uuid=change.workspace,
                    bot_id=change.bot_id,
                    bot_name=change.bot_name,
                    session_id=change.session_id,
                    timestamp=change.timestamp,
                    pipeline_id='',
                    pipeline_name='',
                    user_id=change.user_id,
                    user_name=change.user_name,
                    role='user',
                    message_content='hello',
                    status='success',
                    level='info',
                )
            )
            await writer.apply_once(session, change)
    rows, total = await service.get_sessions(context())
    assert total == 1 and rows[0]['user_id'] == 'alice' and rows[0]['message_count'] == 3
    assert rows[0]['user_name'] == missing_name
    assert (await service.get_sessions(context(), user_query='Alicia'))[1] == 0
    assert (await service.get_sessions(context(), user_query='alice'))[1] == 1
    await rebuild_summaries(service)
    assert (await service.get_sessions(context()))[0] == rows


@pytest.mark.contract('summary_backfill')
@pytest.mark.parametrize('ingress_first', [False, True])
@pytest.mark.parametrize('missing_name', [None, ''])
async def test_covered_ingress_nickname_is_consistent_after_backfill(service, ingress_first, missing_name):
    async def ingress():
        await service.record_ingress_event(
            context('a'),
            event_id='nickname-event',
            event_type='message.received',
            bot_id='a',
            bot_name='Bot',
            platform='test',
            payload={},
            actor_id='alice',
            actor_name='Alice Display',
            conversation_id='person_alice',
        )

    if ingress_first:
        await ingress()
    await service.record_message(
        context('a'),
        **resource('a'),
        session_id='person_alice',
        message_content='hello',
        event_id='nickname-event',
        user_id='alice',
        user_name=missing_name,
    )
    if not ingress_first:
        await ingress()
    rows, total = await service.get_sessions(context())
    assert total == 1 and rows[0]['message_count'] == 1
    identity = rows[0]['user_id'], rows[0]['user_name']
    assert identity == ('alice', missing_name)
    assert (await service.get_sessions(context(), user_query='Alice Display'))[1] == 0
    assert (await service.get_sessions(context(), user_query='alice'))[1] == 1
    await rebuild_summaries(service)
    rebuilt, total = await service.get_sessions(context())
    assert total == 1 and (rebuilt[0]['user_id'], rebuilt[0]['user_name']) == identity
    assert rebuilt[0]['message_count'] == 1


@pytest.mark.contract('summary_backfill')
@pytest.mark.parametrize('order', list(permutations(('covered', 'messages', 'open'))))
@pytest.mark.parametrize('first_route', ['failed', 'skipped', 'no_target'])
@pytest.mark.parametrize('empty_metadata', [False, True])
async def test_live_replay_and_legacy_initialization_agree(service, order, first_route, empty_metadata):
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from langbot.pkg.entity.persistence.event_log import EventLog
    from langbot.pkg.entity.persistence.workspace import Workspace

    engine = service.ap.persistence_mgr.get_db_engine()
    async with engine.begin() as connection:
        await connection.execute(
            sa.insert(Workspace).values(uuid='workspace', instance_uuid='test', name='W', slug='w')
        )

    targets = [
        {'target_uuid': 'agent-first', 'target_type': 'agent'},
        {'target_uuid': 'agent-second', 'target_type': 'agent'},
    ]
    routes = (
        [RuntimeError('primary failed'), *targets]
        if first_route == 'failed'
        else [{'status': 'skipped'}, *targets]
        if first_route == 'skipped'
        else [{'status': 'failed'}]
    )
    ingress = dict(
        event_type='message.received',
        bot_id='a',
        bot_name='' if empty_metadata else 'Bot',
        platform=None if empty_metadata else 'test',
        payload={},
        conversation_id='group_42',
    )
    for source in order:
        if source == 'covered':
            await service.record_ingress_event(
                context('a'), **ingress, event_id='covered', actor_id='alice', actor_name='Alice'
            )
        elif source == 'messages':
            await service.record_message(
                context('a'),
                bot_id='a',
                bot_name='Bot',
                pipeline_id='pipeline',
                pipeline_name='Pipeline',
                session_id='group_42',
                message_content='input',
                event_id='covered',
                platform='test',
                user_id='bob',
                user_name=None,
            )
            await service.record_message(
                context('a'),
                bot_id='a',
                bot_name='Bot',
                pipeline_id='assistant',
                pipeline_name='Assistant',
                session_id='group_42',
                message_content='output',
                event_id='covered',
                platform='test',
                user_id='bot',
                user_name='Assistant',
                role='assistant',
            )
        else:
            # Updates to the same fact may fill identities, then omit or conflict
            # with them. Projection must follow the row that actually persisted.
            await service.record_ingress_event(context('a'), **ingress, event_id='open', routes=routes)
            await service.record_ingress_event(
                context('a'), **ingress, event_id='open', actor_id='carol', actor_name='Carol'
            )
            await service.record_ingress_event(context('a'), **ingress, event_id='open', status='completed')
            await service.record_ingress_event(
                context('a'), **ingress, event_id='open', actor_id='intruder', actor_name='Wrong Actor'
            )

    async with engine.connect() as connection:
        received = (
            await connection.execute(sa.select(EventLog.created_at).where(EventLog.event_id == 'open'))
        ).scalar_one()
        user_time = (
            await connection.execute(
                sa.select(models.MonitoringMessage.timestamp).where(models.MonitoringMessage.role == 'user')
            )
        ).scalar_one()
    latest_is_ingress = received > user_time
    expected_user = ('carol', 'Carol') if latest_is_ingress else ('bob', None)
    expected_display = ('', None) if latest_is_ingress and empty_metadata else ('Bot', 'test')
    expected_pipeline = (
        (('agent-first', 'agent') if first_route != 'no_target' else ('', ''))
        if latest_is_ingress
        else ('pipeline', 'Pipeline')
    )
    live, total = await service.get_sessions(context())
    assert total == 1
    assert (live[0]['user_id'], live[0]['user_name']) == expected_user
    assert (live[0]['bot_name'], live[0]['platform']) == expected_display
    assert (live[0]['pipeline_id'], live[0]['pipeline_name']) == expected_pipeline
    assert live[0]['message_count'] == 3
    # Covered ingress may retain an earlier observed start time. Counts and
    # selected metadata, unlike this monotonic observation, must be replayable.
    fields = (
        'bot_id',
        'session_id',
        'bot_name',
        'platform',
        'user_id',
        'user_name',
        'pipeline_id',
        'pipeline_name',
        'message_count',
    )
    expected = {field: live[0][field] for field in fields}
    await rebuild_summaries(service, batch_size=1)
    rebuilt, total = await service.get_sessions(context())
    assert total == 1 and {field: rebuilt[0][field] for field in fields} == expected

    def migrate_legacy(connection):
        migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0040_session_summaries')
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            connection.execute(
                sa.update(models.MonitoringSession).values(
                    bot_name='Old Bot',
                    platform='old',
                    user_id='stale',
                    user_name='Stale User',
                    pipeline_id='stale',
                    pipeline_name='Stale Processor',
                    message_count=77,
                    last_activity=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(seconds=1),
                )
            )
            migration.upgrade()

    async with engine.begin() as connection:
        await connection.run_sync(migrate_legacy)
    # Recreate the worker after every committed page to exercise durable resume.
    while not await SessionSummaryBackfill(service._summary_session, 'sqlite').run_batch('workspace', 1):
        pass
    migrated, total = await service.get_sessions(context())
    assert total == 1
    assert {field: migrated[0][field] for field in fields if field != 'message_count'} == {
        field: value for field, value in expected.items() if field != 'message_count'
    }
    assert migrated[0]['message_count'] == 77
    assert await SessionSummaryBackfill(service._summary_session, 'sqlite').run_batch('workspace', 1)
    assert (await service.get_sessions(context()))[0] == migrated


@pytest.mark.contract('summary_backfill')
@pytest.mark.parametrize('order', list(permutations(range(3))))
@pytest.mark.parametrize('kind', ['events', 'messages', 'mixed'])
async def test_fixed_facts_agree_across_arrival_replay_and_initialization(service, order, kind):
    import importlib
    import json
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from langbot.pkg.entity.persistence.event_log import EventLog
    from langbot.pkg.entity.persistence.workspace import Workspace
    from langbot.pkg.persistence.session_summary_writer import ingress_summary_change, message_summary_change

    timestamp = dt.datetime(2026, 1, 1)
    sources = []
    for index, (identity, user, name) in enumerate(
        (('Z', 'old', 'Old'), ('a', 'winner', None), ('z', 'other', 'Other'))
    ):
        is_message = kind == 'messages' or (kind == 'mixed' and index == 2)
        assistant = is_message and index == 2
        occurred = timestamp + dt.timedelta(seconds=(1 if assistant else -1) if index == 2 else 0)
        if is_message:
            model = models.MonitoringMessage
            fact = dict(
                workspace_uuid='workspace',
                id=identity,
                bot_id='a',
                session_id='fixed',
                timestamp=occurred,
                bot_name='Bot',
                platform='test',
                pipeline_id=identity,
                pipeline_name=identity,
                user_id=user,
                user_name=name,
                role='assistant' if assistant else 'user',
                event_id=None,
                message_content='hello',
                status='success',
                level='info',
            )
        else:
            model = EventLog
            fact = dict(
                workspace_id='workspace',
                event_id=identity,
                bot_id='a',
                conversation_id='fixed',
                event_time=occurred,
                created_at=timestamp + dt.timedelta(microseconds=index),
                source='platform',
                event_type='message.received',
                actor_id=user,
                actor_name=name,
                metadata_json=json.dumps(
                    {
                        'bot_name': 'Bot',
                        'platform': 'test',
                        'routes': [{'target_uuid': identity, 'target_type': identity}],
                    }
                ),
            )
        sources.append((model, fact, message_summary_change if is_message else ingress_summary_change))

    async def project(index, *, persist=False):
        model, fact, mapping = sources[index]
        async with service._summary_session('workspace') as session:
            if persist:
                await session.execute(sa.insert(model).values(**fact))
            identity = (
                model.id == fact['id'] if model is models.MonitoringMessage else model.event_id == fact['event_id']
            )
            row = (await session.execute(sa.select(*model.__table__.columns).where(identity))).mappings().one()
            await SessionSummaryWriter('sqlite').apply_once(session, mapping('workspace', row))

    async with service.ap.persistence_mgr.get_db_engine().begin() as connection:
        await connection.execute(
            sa.insert(Workspace).values(uuid='workspace', instance_uuid='test', name='W', slug='w')
        )
    for index in order:
        await project(index, persist=True)
    rows, total = await service.get_sessions(context())
    assert total == 1 and rows[0]['message_count'] == 3
    assert (rows[0]['user_id'], rows[0]['user_name'], rows[0]['pipeline_id']) == ('winner', None, 'a')
    if kind != 'messages':
        # The winning fact may be completed without changing its timestamp or credit.
        await service.record_ingress_event(
            context('a'),
            event_id='a',
            event_type='message.received',
            bot_id='a',
            bot_name='Bot',
            platform='test',
            payload={},
            conversation_id='fixed',
            actor_id='winner',
            actor_name='Winner',
            routes=[{'target_uuid': 'completed', 'target_type': 'agent'}],
        )
        rows, _ = await service.get_sessions(context())
        assert (rows[0]['user_name'], rows[0]['pipeline_id'], rows[0]['message_count']) == ('Winner', 'completed', 3)
    for replay in (order, tuple(reversed(order))):
        for index in replay:
            await project(index)
        assert (await service.get_sessions(context()))[0] == rows
    await rebuild_summaries(service, batch_size=1)
    assert (await service.get_sessions(context()))[0] == rows

    def migrate(connection):
        migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0040_session_summaries')
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            migration.upgrade()

    async with service.ap.persistence_mgr.get_db_engine().begin() as connection:
        await connection.run_sync(migrate)
    while not await SessionSummaryBackfill(service._summary_session, 'sqlite').run_batch('workspace', 1):
        pass
    assert (await service.get_sessions(context()))[0] == rows
    for index in reversed(order):
        await project(index)
    assert (await service.get_sessions(context()))[0] == rows


@pytest.mark.parametrize('backfill', [False, True])
async def test_discarded_messages_replace_the_entire_snapshot(service, backfill):
    discarded = {**resource('a'), 'pipeline_id': '__discard__', 'pipeline_name': 'Discarded'}
    await service.record_message(
        context('a'),
        **discarded,
        session_id='group_42',
        message_content='first',
        status='discarded',
    )
    assert (await service.get_sessions(context()))[0][0]['pipeline_id'] == '__discard__'
    await service.record_message(
        context('a'),
        **resource('a'),
        session_id='group_42',
        message_content='processed',
    )
    before = (await service.get_sessions(context()))[0][0]['last_activity']
    await service.record_message(
        context('a'),
        **discarded,
        session_id='group_42',
        message_content='ignored',
        status='discarded',
    )
    if backfill:
        await rebuild_summaries(service)
    assert (await service.get_sessions(context(), pipeline_ids=['a'])) == ([], 0)
    rows, total = await service.get_sessions(context(), pipeline_ids=['__discard__'])
    assert total == 1 and rows[0]['message_count'] == 3
    assert (rows[0]['pipeline_id'], rows[0]['pipeline_name']) == ('__discard__', 'Discarded')
    assert rows[0]['last_activity'] >= before


@pytest.mark.contract('summary_accounting')
@pytest.mark.parametrize('order', list(permutations(range(3))))
@pytest.mark.parametrize(
    'roles', [('user', 'user'), ('assistant', 'user'), ('user', 'assistant'), ('assistant', 'assistant')]
)
async def test_whole_snapshot_is_independent_of_arrival_order(service, order, roles):
    writer = SessionSummaryWriter('sqlite')
    changes = [
        SessionSummaryChange(
            workspace='workspace',
            bot_id='a',
            session_id='group_42',
            source_key=f'message:{index}',
            timestamp=dt.datetime(2026, 1, index + 1),
            bot_name='Bot',
            pipeline_id=pipeline,
            pipeline_name=f'Pipeline {pipeline}',
            role=role,
            user_id=str(index),
            user_name=f'User {index}',
        )
        for index, (pipeline, role) in enumerate(zip(('a', 'b', '__discard__'), (*roles, 'user')))
    ]
    for index in order:
        change = changes[index]
        async with service._summary_session('workspace') as session:
            await session.execute(
                sa.insert(models.MonitoringMessage).values(
                    workspace_uuid=change.workspace,
                    id=str(index),
                    bot_id=change.bot_id,
                    session_id=change.session_id,
                    timestamp=change.timestamp,
                    bot_name=change.bot_name,
                    pipeline_id=change.pipeline_id,
                    pipeline_name=change.pipeline_name,
                    role=change.role,
                    user_id=change.user_id,
                    user_name=change.user_name,
                    message_content='hello',
                    status='discarded' if change.pipeline_id == '__discard__' else 'success',
                    level='info',
                )
            )
            await writer.apply_once(session, change)
    expected_pipeline = '__discard__'
    rows, total = await service.get_sessions(context(), pipeline_ids=[expected_pipeline])
    assert total == 1
    row = rows[0]
    assert row['pipeline_name'] == f'Pipeline {expected_pipeline}'
    assert (row['user_id'], row['user_name'], row['message_count']) == ('2', 'User 2', 3)
    assert row['last_activity'] == '2026-01-03T00:00:00'
    await rebuild_summaries(service)
    assert (await service.get_sessions(context()))[0] == rows


async def test_analysis_fails_closed_and_scopes_statistics(service):
    for bot in ['a', 'b']:
        await service.record_message(context(bot), session_id='person_42', message_content=bot, **resource(bot))
    assert (await service.get_session_analysis(context(), 'person_42'))['found'] is False
    result = await service.get_session_analysis(context(), 'person_42', bot_id='b')
    assert result['message_stats']['total'] == 1
    assert result['session']['bot_id'] == 'b'


async def test_single_message_analysis_without_tool_calls(service):
    from langbot.pkg.api.http.controller.groups.monitoring import validate_monitoring_window
    from werkzeug.exceptions import BadRequest

    await service.record_message(context('a'), session_id='person_42', message_content='hi', **resource('a'))
    row = (await service.ap.persistence_mgr.execute_async(sa.select(models.MonitoringMessage.timestamp))).one()
    timestamp = row.timestamp
    validate_monitoring_window(timestamp, timestamp, allow_point_window=True)
    result = await service.get_session_analysis(
        context(), 'person_42', bot_id='a', start_time=timestamp, end_time=timestamp
    )
    assert result['found'] is True
    assert result['message_stats']['total'] == 1
    assert result['tool_calls'] == []
    for start, end in [
        (timestamp + dt.timedelta(seconds=1), timestamp),
        (timestamp, timestamp + dt.timedelta(days=366)),
    ]:
        with pytest.raises(BadRequest):
            validate_monitoring_window(start, end, allow_point_window=True)
    with pytest.raises(BadRequest):
        validate_monitoring_window(timestamp, timestamp)


async def test_old_active_sessions_are_listed_exported_and_not_cleaned(service):
    for bot in ['a', 'b']:
        await service.record_message(context(bot), session_id='person_42', message_content='hello', **resource(bot))
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
    # Receipts are expired in bounded batches before their summaries.
    assert count == 0
    await service.ap.persistence_mgr.execute_async(
        sa.delete(models.MonitoringSessionReceipt).where(models.MonitoringSessionReceipt.bot_id == 'a')
    )
    assert (
        await service._delete_expired_in_batches(
            context(),
            models.MonitoringSession,
            models.MonitoringSession.last_activity,
            models.MonitoringSession.session_id,
            since,
            1,
            2,
        )
        == 1
    )
    rows, total = await service.get_sessions(context())
    assert total == 1 and rows[0]['bot_id'] == 'b'


async def test_bot_session_summary_never_sorts_inline_message_payloads(service):
    engine = service.ap.persistence_mgr.get_db_engine()
    payload = 'historical inline media ' * 16384
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    async with engine.begin() as connection:
        await connection.execute(
            sa.insert(models.MonitoringMessage),
            [
                dict(
                    id=f'message-{index}',
                    workspace_uuid='workspace',
                    session_id='group_42',
                    **resource('a'),
                    timestamp=now + dt.timedelta(seconds=index),
                    role='user' if index == 0 else 'assistant',
                    message_content=payload,
                    variables=payload,
                    status='success',
                    level='info',
                    user_id='user',
                    user_name='User',
                    platform='test',
                )
                for index in range(2)
            ],
        )

    def reject_payload_reads(connection, cursor, statement, parameters, context, executemany):
        assert 'monitoring_messages.message_content' not in statement
        assert 'monitoring_messages.variables' not in statement

    sa.event.listen(engine.sync_engine, 'before_cursor_execute', reject_payload_reads)
    try:
        backfill = SessionSummaryBackfill(service._summary_session, 'sqlite')
        while not await backfill.run_batch('workspace', batch_size=1):
            pass
        rows, total = await service.get_sessions(context('a'), bot_ids=['a'])
    finally:
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', reject_payload_reads)

    assert total == 1
    assert rows[0]['session_id'] == 'group_42'
    assert rows[0]['message_count'] == 2
    assert rows[0]['user_name'] == 'User'
    messages, total = await service.get_messages(context('a'), bot_ids=['a'], session_ids=['group_42'])
    assert total == 2
    assert all(message['message_content'] == payload and message['variables'] == payload for message in messages)


@pytest.mark.contract('reader_sql')
async def test_interactive_list_cannot_read_history_or_repair_missing_summaries(service):
    """SQLite itself rejects historical reads, even through joins or subqueries."""
    import sqlite3

    engine = service.ap.persistence_mgr.get_db_engine()
    now = dt.datetime(2026, 1, 1)
    async with engine.begin() as connection:
        await connection.execute(
            sa.insert(models.MonitoringMessage),
            [
                dict(
                    id=str(i),
                    workspace_uuid='workspace',
                    session_id='unrepaired',
                    **resource('a'),
                    timestamp=now,
                    role='user',
                    message_content='large history' * 1000,
                    status='success',
                    level='info',
                )
                for i in range(1000)
            ],
        )
    await service.record_message(
        context('a'), **resource('a'), session_id='live', message_content='hello', user_name='Alice', user_id='42'
    )

    def authorize(action, table, column, database, trigger):
        if action == sqlite3.SQLITE_READ and table != 'monitoring_sessions':
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    async def set_authorizer(callback):
        async with engine.connect() as connection:
            await connection.run_sync(
                lambda sync: sync.connection.dbapi_connection.run_async(
                    lambda raw: raw._execute(raw._conn.set_authorizer, callback)
                )
            )

    await set_authorizer(authorize)
    try:
        for filters in (
            {},
            {'bot_ids': ['a']},
            {'pipeline_ids': ['a']},
            {'user_query': 'alice'},
            {'start_time': now, 'end_time': dt.datetime(2099, 1, 1), 'is_active': True},
        ):
            rows, total = await service.get_sessions(context(), **filters)
            assert total == 1 and rows[0]['session_id'] == 'live'
            assert (
                not {
                    'source_count',
                    'metadata_role',
                    'metadata_timestamp',
                    'metadata_source_key',
                    'base_snapshot',
                }
                & rows[0].keys()
            )
        rows, total = await service.get_sessions(context(), limit=1, offset=1)
        assert total == 1 and rows == []
    finally:
        await set_authorizer(None)


async def test_conversation_detail_dedup_uses_point_indexes(service):
    """The detail view retains ingress history without the old quadratic anti-join."""
    source = service._conversation_message_source('workspace', ['a'])
    query = sa.select(sa.func.count()).select_from(source).where(source.c.session_id == 'person_42')
    engine = service.ap.persistence_mgr.get_db_engine()
    sql = query.compile(dialect=engine.dialect, compile_kwargs={'literal_binds': True})
    async with engine.connect() as connection:
        plan = '\n'.join(row[3] for row in await connection.execute(sa.text(f'EXPLAIN QUERY PLAN {sql}')))
    assert 'ix_monitoring_messages_summary_event' in plan
    assert 'ix_agent_run_summary_event' in plan
    assert 'sqlite_autoindex_monitoring_messages_1' in plan


async def test_conversation_page_does_not_materialize_old_payloads(service):
    """A small page must work even when historical rows exceed SQLite's read limit."""
    import sqlite3

    from langbot.pkg.entity.persistence.event_log import EventLog

    engine = service.ap.persistence_mgr.get_db_engine()
    now = dt.datetime(2026, 1, 2)
    payload = 'historical payload ' * 16384
    messages = [
        dict(
            id=f'old-{index}',
            workspace_uuid='workspace',
            **resource('a'),
            session_id='group_42',
            timestamp=now - dt.timedelta(days=1),
            message_content=payload,
            variables=payload,
            role='user',
            status='success',
            level='info',
        )
        for index in range(16)
    ]
    for identity in ('new-a', 'new-b', 'new-c'):
        messages.append(
            dict(
                id=identity,
                workspace_uuid='workspace',
                **resource('a'),
                session_id='group_42',
                timestamp=now,
                message_content=identity,
                variables='{"delivery":true}',
                role='assistant' if identity == 'new-c' else 'user',
                status='success',
                level='info',
            )
        )
    async with engine.begin() as connection:
        await connection.execute(sa.insert(models.MonitoringMessage), messages)
        await connection.execute(
            sa.insert(EventLog),
            [
                dict(
                    event_id=identity,
                    workspace_id='workspace',
                    bot_id='a',
                    event_type='message.received',
                    source='platform',
                    conversation_id='group_42',
                    event_time=now + dt.timedelta(seconds=1),
                    input_json='{"text":"ingress"}',
                    metadata_json='{"bot_name":"A","routes":[{"target_uuid":"pipeline"}]}',
                )
                for identity in ('new-a', 'new-c')
            ],
        )

    async def set_read_limit(limit):
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync: sync.connection.dbapi_connection.run_async(
                    lambda raw: raw._execute(raw._conn.setlimit, sqlite3.SQLITE_LIMIT_LENGTH, limit)
                )
            )

    previous_limit = await set_read_limit(65536)
    try:
        first, total = await service.get_messages(context(), bot_ids=['a'], session_ids=['group_42'], limit=2)
        assert total == 20
        # A delivery and an uncovered ingress may share the same public ID.
        assert [(row['id'], row['role']) for row in first] == [('new-c', 'user'), ('new-c', 'assistant')]
        assert first[0]['message_content'] == '{"text":"ingress"}'
        assert first[0]['pipeline_id'] == 'pipeline'
        assert first[1]['variables'] == '{"delivery":true}'
        second, second_total = await service.get_messages(
            context(), bot_ids=['a'], session_ids=['group_42'], limit=2, offset=2
        )
        assert second_total == total
        assert [row['id'] for row in second] == ['new-b', 'new-a']
        empty, empty_total = await service.get_messages(
            context(), bot_ids=['a'], session_ids=['group_42'], limit=2, offset=100
        )
        assert empty == [] and empty_total == total
    finally:
        await set_read_limit(previous_limit)


@pytest.mark.parametrize('bot_ids', [['a'], ['a', 'b']])
async def test_conversation_page_scopes_sources_and_time_window(service, bot_ids):
    """Pagination preserves tenant filters, event resolution and deduplication."""
    from langbot.pkg.entity.persistence.agent_run import AgentRun
    from langbot.pkg.entity.persistence.event_log import EventLog

    engine = service.ap.persistence_mgr.get_db_engine()
    now = dt.datetime(2026, 1, 2)
    async with engine.begin() as connection:
        await connection.execute(
            sa.insert(models.MonitoringMessage),
            [
                dict(
                    id=identity,
                    workspace_uuid=workspace,
                    **resource(bot),
                    session_id=session,
                    timestamp=now,
                    message_content=identity,
                    event_id='linked-event' if identity == 'a-message' else None,
                    role='user',
                    status='success',
                    level='info',
                )
                for identity, workspace, bot, session in [
                    ('a-message', 'workspace', 'a', 'group_42'),
                    ('b-message', 'workspace', 'b', 'group_42'),
                    ('foreign-message', 'other', 'a', 'group_42'),
                    ('other-session', 'workspace', 'a', 'group_other'),
                ]
            ],
        )
        await connection.execute(
            sa.insert(EventLog),
            [
                dict(
                    event_id=identity,
                    workspace_id=workspace,
                    bot_id=bot,
                    event_type='message.received',
                    source='platform',
                    conversation_id=conversation,
                    event_time=timestamp,
                    input_json='{"chat_type":"group","chat_id":"42"}',
                )
                for identity, workspace, bot, conversation, timestamp in [
                    ('linked-event', 'workspace', 'a', 'group_42', now),
                    ('a-message', 'workspace', 'b', 'group_42', now),
                    ('json-conversation', 'workspace', 'a', None, now),
                    ('runner-conversation', 'workspace', 'a', None, now),
                    ('foreign-event', 'other', 'a', 'group_42', now),
                    ('outside-window', 'workspace', 'a', 'group_42', now + dt.timedelta(seconds=1)),
                ]
            ],
        )
        await connection.execute(
            sa.insert(AgentRun).values(
                run_id='run',
                runner_id='runner',
                workspace_id='workspace',
                bot_id='a',
                event_id='runner-conversation',
                conversation_id='group_other',
                status='completed',
            )
        )

    filters = dict(bot_ids=bot_ids, session_ids=['group_42'], start_time=now, end_time=now)
    expected = [('a', 'json-conversation'), ('a', 'a-message')]
    if 'b' in bot_ids:
        expected = [('a', 'json-conversation'), ('b', 'b-message'), ('b', 'a-message'), ('a', 'a-message')]
    paginated = []
    for offset in range(len(expected) + 1):
        rows, total = await service.get_messages(context(), **filters, limit=1, offset=offset)
        assert total == len(expected)
        assert all('_source' not in row for row in rows)
        paginated.extend((row['bot_id'], row['id']) for row in rows)
    assert paginated == expected


@pytest.mark.asyncio(loop_scope='module')
@pytest.mark.postgres
async def test_postgres_conversation_page_hydrates_only_own_workspace(cloud_database):  # noqa: F811
    from langbot.pkg.entity.persistence.event_log import EventLog
    from tests.integration.persistence.test_monitoring_postgres import WORKSPACE_A, WORKSPACE_B, _context, _read

    ap, admin = cloud_database
    now = dt.datetime(2026, 1, 2)
    async with admin.begin() as connection:
        for workspace, suffix in ((WORKSPACE_A, 'a'), (WORKSPACE_B, 'b')):
            await connection.execute(
                sa.insert(models.MonitoringMessage).values(
                    id=f'page-message-{suffix}',
                    workspace_uuid=workspace,
                    **resource('page-bot'),
                    session_id='page-session',
                    timestamp=now,
                    message_content=workspace,
                    variables='{"delivery":true}',
                    role='assistant',
                    status='success',
                    level='info',
                )
            )
            await connection.execute(
                sa.insert(EventLog).values(
                    event_id=f'page-message-{suffix}',
                    workspace_id=workspace,
                    bot_id='page-bot',
                    event_type='message.received',
                    source='platform',
                    conversation_id='page-session',
                    event_time=now,
                    input_json=f'{{"text":"{workspace}"}}',
                )
            )
    for workspace, suffix in ((WORKSPACE_A, 'a'), (WORKSPACE_B, 'b')):
        page = []
        for offset in range(3):
            rows, total = await _read(
                ap.monitoring_service,
                'get_messages',
                _context(workspace),
                bot_ids=['page-bot'],
                session_ids=['page-session'],
                limit=1,
                offset=offset,
            )
            assert total == 2
            page.extend(rows)
        assert [(row['id'], row['role']) for row in page] == [
            (f'page-message-{suffix}', 'user'),
            (f'page-message-{suffix}', 'assistant'),
        ]
        assert all(row['workspace_uuid'] == workspace and workspace in row['message_content'] for row in page)


async def test_ingress_credit_is_replaced_but_distinct_message_rows_count(service):
    from langbot.pkg.entity.persistence.event_log import EventLog

    ingress = dict(
        event_id='event',
        event_type='message.received',
        bot_id='a',
        bot_name='Bot',
        platform='test',
        payload={'text': 'hello'},
        actor_id='42',
        actor_name='Alice',
        conversation_id='person_42',
    )
    await service.record_ingress_event(context('a'), **ingress)
    await service.record_message(
        context('a'),
        **resource('a'),
        session_id='person_42',
        message_content='hello',
        event_id='event',
        user_id='42',
        user_name='Alice',
    )
    await service.record_ingress_event(
        context('a'), **ingress, routes=[{'target_uuid': 'a', 'target_type': 'pipeline'}]
    )
    await service.record_message(
        context('a'), **resource('a'), session_id='person_42', message_content='hello', event_id='event', user_id='42'
    )
    await service.record_message(
        context('a'),
        **resource('a'),
        session_id='person_42',
        message_content='reply',
        event_id='event',
        role='assistant',
        user_name='Bot',
    )
    rows, total = await service.get_sessions(context())
    assert total == 1 and rows[0]['message_count'] == 3
    assert rows[0]['user_name'] is None
    engine = service.ap.persistence_mgr.get_db_engine()
    async with engine.connect() as connection:
        assert (await connection.execute(sa.select(sa.func.count()).select_from(EventLog))).scalar_one() == 1
        assert (
            await connection.execute(sa.select(sa.func.count()).select_from(models.MonitoringMessage))
        ).scalar_one() == 3


@pytest.mark.parametrize('has_ingress', [False, True])
async def test_late_runner_event_identity_does_not_double_count_after_backfill(service, has_ingress):
    if has_ingress:
        await service.record_ingress_event(
            context('a'),
            event_id='later-event',
            event_type='message.received',
            bot_id='a',
            bot_name='Bot',
            platform='test',
            payload={},
            conversation_id='person_42',
        )
    message = await service.record_message(
        context('a'), **resource('a'), session_id='person_42', message_content='hello'
    )
    await service.link_execution_message(context('a'), message, 'run', 'later-event')
    await service.link_execution_message(context('a'), message, 'run', 'later-event')
    backfill = SessionSummaryBackfill(service._summary_session, 'sqlite')
    while not await backfill.run_batch('workspace', batch_size=1):
        pass
    rows, total = await service.get_sessions(context())
    assert total == 1 and rows[0]['message_count'] == 1


@pytest.mark.parametrize('source', ['message', 'ingress'])
@pytest.mark.contract('summary_atomicity')
async def test_source_and_summary_rollback_together(service, monkeypatch, source):
    from langbot.pkg.entity.persistence.event_log import EventLog

    original = SessionSummaryWriter.apply_once

    async def fail_after_write(self, session, change, **kwargs):
        await original(self, session, change, **kwargs)
        raise RuntimeError('interrupted')

    monkeypatch.setattr(SessionSummaryWriter, 'apply_once', fail_after_write)
    with pytest.raises(RuntimeError, match='interrupted'):
        if source == 'message':
            await service.record_message(context('a'), **resource('a'), session_id='person_42', message_content='hello')
        else:
            await service.record_ingress_event(
                context('a'),
                event_id='event',
                event_type='message.received',
                bot_id='a',
                bot_name='Bot',
                platform='test',
                payload={},
                conversation_id='person_42',
            )
    async with service.ap.persistence_mgr.get_db_engine().connect() as connection:
        for model in (models.MonitoringMessage, EventLog, models.MonitoringSession, models.MonitoringSessionReceipt):
            assert (await connection.execute(sa.select(sa.func.count()).select_from(model))).scalar_one() == 0


class _ServicesReady(Exception):
    """Stop the real startup path after initialization, before runtime tasks."""


@pytest.fixture
def starting_application(service):
    from langbot.pkg.core.app import Application
    from langbot.pkg.persistence.mgr import PersistenceMode

    application = Application()
    application.persistence_mgr = service.ap.persistence_mgr
    application.persistence_mgr.mode = PersistenceMode.OSS_COMPAT
    application.monitoring_service = service
    application.logger = service.ap.logger
    application.workspace_service = SimpleNamespace(
        list_active_execution_bindings=AsyncMock(return_value=[SimpleNamespace(workspace_uuid='workspace')])
    )
    application.event_loop_monitor = SimpleNamespace(start=Mock(side_effect=_ServicesReady))
    return application


@pytest.fixture
async def migrated_summary_history(service):
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from langbot.pkg.entity.persistence.event_log import EventLog
    from langbot.pkg.entity.persistence.workspace import Workspace
    from langbot.pkg.persistence.session_summary_backfill import BATCH_SIZE

    async with service.ap.persistence_mgr.get_db_engine().begin() as connection:
        await connection.execute(
            sa.insert(Workspace).values(uuid='workspace', instance_uuid='test', name='W', slug='w')
        )
        await connection.execute(
            sa.insert(models.MonitoringMessage),
            [
                dict(
                    id=f'old-{i:03d}',
                    workspace_uuid='workspace',
                    **resource('a'),
                    session_id='person_42',
                    timestamp=dt.datetime(2026, 1, 1),
                    event_id=f'event-{i}',
                    role='user',
                    message_content='historical',
                    status='success',
                    level='info',
                )
                for i in range(BATCH_SIZE + 1)
            ],
        )
        await connection.execute(
            sa.insert(EventLog),
            [
                dict(
                    workspace_id='workspace',
                    bot_id='a',
                    event_id=event_id,
                    event_type='message.received',
                    source='platform',
                    conversation_id='person_42',
                    created_at=dt.datetime(2026, 1, 1),
                    input_json='{}',
                )
                for event_id in ['event-0', 'unmatched']
            ],
        )

        def migrate(sync_connection):
            migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0040_session_summaries')
            with Operations.context(MigrationContext.configure(sync_connection)):
                migration.downgrade()
                migration.upgrade()

        await connection.run_sync(migrate)
    return BATCH_SIZE + 2


@pytest.mark.contract('summary_backfill')
async def test_startup_initializes_migrated_history_and_continues_in_same_process(
    service, starting_application, migrated_summary_history
):
    application = starting_application
    with pytest.raises(_ServicesReady):
        await application.run()
    application.event_loop_monitor.start.assert_called_once()
    rows, total = await service.get_sessions(context())
    assert total == 1 and rows[0]['message_count'] == migrated_summary_history
    # Producers can write immediately after this startup, without another run().
    await service.record_message(context('a'), session_id='person_42', message_content='live', **resource('a'))
    assert (await service.get_sessions(context()))[0][0]['message_count'] == migrated_summary_history + 1


@pytest.mark.contract('summary_backfill')
async def test_startup_failure_keeps_services_stopped_and_resumes_committed_batches(
    service, starting_application, migrated_summary_history, monkeypatch
):
    from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
    from langbot.pkg.persistence.session_summary_backfill import BATCH_SIZE, CURSOR_KEY

    application = starting_application
    original = SessionSummaryWriter.apply_once

    async def fail_second_page(self, session, change, **kwargs):
        await original(self, session, change, **kwargs)
        if change.source_key == f'message:old-{BATCH_SIZE:03d}':
            raise RuntimeError('interrupted initialization')

    with monkeypatch.context() as patch:
        patch.setattr(SessionSummaryWriter, 'apply_once', fail_second_page)
        with pytest.raises(RuntimeError, match='interrupted initialization'):
            await application.run()
    application.event_loop_monitor.start.assert_not_called()
    async with service._summary_session('workspace') as session:
        assert (await session.execute(sa.select(models.MonitoringSession.message_count))).scalar_one() == BATCH_SIZE
        value = (
            await session.execute(sa.select(WorkspaceMetadata.value).where(WorkspaceMetadata.key == CURSOR_KEY))
        ).scalar_one()
        assert f'old-{BATCH_SIZE - 1:03d}' in value
    with pytest.raises(_ServicesReady):
        await application.run()
    application.event_loop_monitor.start.assert_called_once()
    assert (await service.get_sessions(context()))[0][0]['message_count'] == migrated_summary_history


@pytest.mark.contract('summary_backfill')
@pytest.mark.parametrize('completed', [False, True])
async def test_startup_skips_history_for_fresh_or_completed_initialization(
    service, starting_application, completed, monkeypatch
):
    from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
    from langbot.pkg.persistence.session_summary_backfill import CURSOR_KEY

    if completed:
        async with service._summary_session('workspace') as session:
            await session.execute(
                sa.insert(WorkspaceMetadata).values(
                    workspace_uuid='workspace', key=CURSOR_KEY, value='{"source": "done"}'
                )
            )
    batch = AsyncMock(side_effect=AssertionError('completed or fresh startup must not scan history'))
    monkeypatch.setattr(SessionSummaryBackfill, 'run_batch', batch)
    with pytest.raises(_ServicesReady):
        await starting_application.run()
    batch.assert_not_awaited()


@pytest.mark.contract('summary_backfill')
async def test_cloud_startup_keeps_manual_initialization_gate(
    starting_application, migrated_summary_history, monkeypatch
):
    from langbot.pkg.persistence.mgr import PersistenceMode

    starting_application.persistence_mgr.mode = PersistenceMode.CLOUD_RUNTIME
    batch = AsyncMock(side_effect=AssertionError('Cloud startup must not initialize with other writers active'))
    monkeypatch.setattr(SessionSummaryBackfill, 'run_batch', batch)
    with pytest.raises(RuntimeError, match='offline initialization'):
        await starting_application.run()
    starting_application.event_loop_monitor.start.assert_not_called()
    batch.assert_not_awaited()


@pytest.mark.contract('summary_backfill')
async def test_backfill_resumes_without_payload_reads_or_recounting_live_events(service):
    from langbot.pkg.entity.persistence.event_log import EventLog
    from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
    from langbot.pkg.persistence.session_summary_backfill import CURSOR_KEY

    now = dt.datetime(2026, 1, 1)
    engine = service.ap.persistence_mgr.get_db_engine()
    async with engine.begin() as connection:
        await connection.execute(
            sa.insert(models.MonitoringMessage),
            [
                dict(
                    id=f'old-{i}',
                    workspace_uuid='workspace',
                    session_id='person_42',
                    **resource('a'),
                    timestamp=now,
                    event_id=f'event-{i}',
                    role='user',
                    message_content='historical',
                    status='success',
                    level='info',
                )
                for i in range(3)
            ],
        )
        await connection.execute(
            sa.insert(EventLog),
            [
                dict(
                    event_id=f'event-{i}',
                    source='platform',
                    event_type='message.received',
                    bot_id='a',
                    workspace_id='workspace',
                    conversation_id='person_42',
                    created_at=now,
                    input_json='{}',
                )
                for i in range(4)
            ],
        )
    backfill = SessionSummaryBackfill(service._summary_session, 'sqlite')
    assert not await backfill.run_batch('workspace', batch_size=1)
    # Live projection is forbidden until all historical receipts are initialized.
    with pytest.raises(RuntimeError, match='offline initialization'):
        await service.record_message(
            context('a'), **resource('a'), session_id='person_42', message_content='live', event_id='new-event'
        )
    # Recreate the worker to prove progress is durable, not an in-memory offset.
    backfill = SessionSummaryBackfill(service._summary_session, 'sqlite')
    for _ in range(20):
        if await backfill.run_batch('workspace', batch_size=1):
            break
    else:
        pytest.fail('bounded backfill did not finish')
    await service.record_message(
        context('a'), **resource('a'), session_id='person_42', message_content='live', event_id='new-event'
    )
    rows, total = await service.get_sessions(context())
    assert total == 1 and rows[0]['message_count'] == 5
    assert await backfill.run_batch('workspace')
    assert (await service.get_sessions(context()))[0] == rows
    async with engine.connect() as connection:
        cursor = (
            await connection.execute(
                sa.select(WorkspaceMetadata.value).where(
                    WorkspaceMetadata.workspace_uuid == 'workspace',
                    WorkspaceMetadata.key == CURSOR_KEY,
                )
            )
        ).scalar_one()
        assert cursor == '{"source": "done"}'


async def test_summary_metadata_and_activity_are_stable_under_out_of_order_replays(service):
    from dataclasses import replace

    writer = SessionSummaryWriter('sqlite')
    base = SessionSummaryChange(
        workspace='workspace',
        bot_id='a',
        session_id='person_42',
        source_key='old',
        timestamp=dt.datetime(2026, 1, 1),
        bot_name='Bot',
        user_name='Old user',
    )
    changes = [
        replace(base, source_key='reply', role='assistant', timestamp=dt.datetime(2026, 1, 4), user_name='Bot'),
        replace(base, source_key='new', timestamp=dt.datetime(2026, 1, 3), user_name='New user'),
        base,
        base,
    ]
    async with service._summary_session('workspace') as session:
        for change in changes:
            await writer.apply_once(session, change)
        await session.execute(sa.update(models.MonitoringSession).values(is_active=False))
        await writer.apply_once(session, base, backfill=True)
    rows, _ = await service.get_sessions(context())
    assert rows[0]['message_count'] == 3 and rows[0]['user_name'] == 'New user'
    assert rows[0]['start_time'] == '2026-01-01T00:00:00'
    assert rows[0]['last_activity'] == '2026-01-04T00:00:00'
    assert rows[0]['is_active'] is False


async def test_backfill_preserves_legacy_counts_and_rolls_back_cursor_on_failure(service, monkeypatch):
    from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
    from langbot.pkg.persistence.session_summary_backfill import CURSOR_KEY

    await service.record_message(context('a'), session_id='legacy', message_content='seed', **resource('a'))
    engine = service.ap.persistence_mgr.get_db_engine()
    async with engine.begin() as connection:
        await connection.execute(sa.update(models.MonitoringSession).values(message_count=99))
        await connection.execute(
            sa.insert(models.MonitoringMessage).values(
                id='history',
                workspace_uuid='workspace',
                session_id='legacy',
                **resource('a'),
                timestamp=dt.datetime(2026, 1, 1),
                role='user',
                message_content='old',
                status='success',
                level='info',
            )
        )
    original = SessionSummaryWriter.apply_once

    async def fail(self, session, change, **kwargs):
        await original(self, session, change, **kwargs)
        raise RuntimeError('failed batch')

    backfill = SessionSummaryBackfill(service._summary_session, 'sqlite')
    with monkeypatch.context() as patch:
        patch.setattr(SessionSummaryWriter, 'apply_once', fail)
        with pytest.raises(RuntimeError, match='failed batch'):
            await backfill.run_batch('workspace', batch_size=1)
    async with engine.connect() as connection:
        assert not (
            await connection.execute(
                sa.select(WorkspaceMetadata.value).where(
                    WorkspaceMetadata.key == CURSOR_KEY,
                )
            )
        ).first()
        assert (await connection.execute(sa.select(models.MonitoringSession.source_count))).scalar_one() == 1
    while not await backfill.run_batch('workspace', batch_size=1):
        pass
    assert (await service.get_sessions(context()))[0][0]['message_count'] == 99
    with pytest.raises(ValueError, match='batch_size'):
        await backfill.run_batch('workspace', batch_size=101)


@pytest.mark.contract('summary_accounting')
@pytest.mark.parametrize('order', ['ingress_first', 'message_first', 'late_link'])
async def test_group_ingress_is_replaced_by_distinct_topic_messages(service, order):
    ingress = dict(
        event_id='topic-event',
        event_type='message.received',
        bot_id='a',
        bot_name='Bot',
        platform='test',
        payload={},
        conversation_id='group_42',
    )

    async def messages():
        for _ in range(2):
            identity = await service.record_message(
                context('a'),
                **resource('a'),
                session_id='group_42#7',
                message_content='input',
                event_id=None if order == 'late_link' else 'topic-event',
            )
            if order == 'late_link':
                await service.link_execution_message(context('a'), identity, 'run', 'topic-event')
                await service.link_execution_message(context('a'), identity, 'run', 'topic-event')

    if order in {'ingress_first', 'late_link'}:
        await service.record_ingress_event(context('a'), **ingress)
    await messages()
    for status in ['running', 'completed', 'completed']:
        await service.record_ingress_event(context('a'), **ingress, status=status)
    rows, total = await service.get_sessions(context())
    assert total == 1 and rows[0]['session_id'] == 'group_42#7' and rows[0]['message_count'] == 2


@pytest.mark.contract('summary_fact_equivalence')
@pytest.mark.parametrize('order', list(permutations(('ingress', 'first', 'second'))))
@pytest.mark.parametrize('late_link', [False, True])
async def test_summary_counts_follow_facts_at_every_step(service, order, late_link):
    messages, ingresses = {}, {}

    async def check():
        rows, total = await service.get_sessions(context())
        expected = session_counts_from_facts(messages, ingresses)
        assert total == len(expected)
        assert {(row['bot_id'], row['session_id']): row['message_count'] for row in rows} == expected
        return rows

    async def ingress(identity='shared', session_id='group_42'):
        await service.record_ingress_event(
            context('a'),
            event_id=identity,
            event_type='message.received',
            bot_id='a',
            bot_name='Bot',
            platform='test',
            payload={},
            conversation_id=session_id,
        )
        ingresses[identity] = dict(bot_id='a', session_id=session_id)
        await check()

    async def message(bot, session_id, role='user'):
        event_id = None if late_link and role == 'user' and bot == 'a' else 'shared'
        identity = await service.record_message(
            context(bot), **resource(bot), session_id=session_id, message_content='input', role=role, event_id=event_id
        )
        messages[identity] = dict(bot_id=bot, session_id=session_id, role=role, event_id=event_id)
        await check()
        if event_id is None:
            for _ in range(2):
                await service.link_execution_message(context(bot), identity, 'run', 'shared')
                messages[identity]['event_id'] = 'shared'
                await check()
        for _ in range(2):
            await replay_summary_message(service, 'workspace', identity)
            await check()
        return identity

    assistant = await message('a', 'group_42#1', 'assistant')
    await message('b', 'group_42')
    identities = {}
    for operation in order:
        if operation == 'ingress':
            await ingress()
        else:
            identities[operation] = await message('a', 'group_42#1' if operation == 'first' else 'group_42#2')
    # Legacy message IDs cover ingress too; an assistant ID must never cover it.
    await ingress(identities['first'])
    await ingress(assistant, 'native')
    for _ in range(2):
        await ingress()
    live = await check()
    await rebuild_summaries(service, batch_size=1)
    assert await check() == live
    for identity in reversed(messages):
        await replay_summary_message(service, 'workspace', identity)
        assert await check() == live
    await ingress()
    assert await check() == live


@pytest.mark.contract('summary_atomicity')
async def test_late_link_rolls_back_source_and_credit_transfer(service, monkeypatch):
    await service.record_ingress_event(
        context('a'),
        event_id='late',
        event_type='message.received',
        bot_id='a',
        bot_name='Bot',
        platform='test',
        payload={},
        conversation_id='group_42',
    )
    identity = await service.record_message(
        context('a'),
        **resource('a'),
        session_id='group_42#7',
        message_content='input',
    )
    original = SessionSummaryWriter.link_event

    async def fail(self, *args):
        await original(self, *args)
        raise RuntimeError('interrupted link')

    with monkeypatch.context() as patch:
        patch.setattr(SessionSummaryWriter, 'link_event', fail)
        with pytest.raises(RuntimeError, match='interrupted link'):
            await service.link_execution_message(context('a'), identity, 'run', 'late')
    async with service.ap.persistence_mgr.get_db_engine().connect() as connection:
        assert (await connection.execute(sa.select(models.MonitoringMessage.event_id))).scalar_one() is None
    rows, total = await service.get_sessions(context())
    assert total == 2 and sum(row['message_count'] for row in rows) == 2
    await service.link_execution_message(context('a'), identity, 'run', 'late')
    rows, total = await service.get_sessions(context())
    assert total == 1 and rows[0]['session_id'] == 'group_42#7' and rows[0]['message_count'] == 1


async def test_historical_ingress_replay_after_initialization_does_not_increment(service):
    from langbot.pkg.entity.persistence.event_log import EventLog

    engine = service.ap.persistence_mgr.get_db_engine()
    now = dt.datetime(2026, 1, 1)
    async with engine.begin() as connection:
        await connection.execute(
            sa.insert(models.MonitoringSession).values(
                workspace_uuid='workspace',
                **resource('a'),
                session_id='person_42',
                message_count=1,
                start_time=now,
                last_activity=now,
                is_active=True,
            )
        )
        await connection.execute(
            sa.insert(EventLog).values(
                event_id='historical-event',
                event_type='message.received',
                source='platform',
                workspace_id='workspace',
                bot_id='a',
                conversation_id='person_42',
                created_at=now,
            )
        )
    backfill = SessionSummaryBackfill(service._summary_session, 'sqlite')
    while not await backfill.run_batch('workspace', 1):
        pass
    for _ in range(2):
        await service.record_ingress_event(
            context('a'),
            event_id='historical-event',
            event_type='message.received',
            bot_id='a',
            bot_name='Bot',
            platform='test',
            payload={},
            conversation_id='person_42',
        )
    assert (await service.get_sessions(context()))[0][0]['message_count'] == 1


@pytest.mark.contract('summary_retention')
async def test_active_session_receipts_expire_in_bounded_tenant_scoped_batches(service):
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    for index in range(5):
        await service.record_message(
            context('a'),
            **resource('a'),
            session_id='active',
            message_content=str(index),
            role='assistant',
        )
    receipt = models.MonitoringSessionReceipt
    engine = service.ap.persistence_mgr.get_db_engine()
    async with engine.begin() as connection:
        await connection.execute(sa.update(receipt).values(timestamp=dt.datetime(2000, 1, 1)))
        await connection.execute(
            sa.insert(receipt).values(
                workspace_uuid='foreign',
                bot_id='a',
                source_key='event:foreign',
                role='event',
                timestamp=dt.datetime(2000, 1, 1),
            )
        )

    deleted = await service.cleanup_expired_records(context(), retention_days=1, batch_size=2, max_batches_per_table=1)
    assert deleted['monitoring_session_receipts'] == 2 and sum(deleted.values()) == 2
    for expected in [2, 1, 0]:
        assert (
            await service._delete_expired_in_batches(
                context(),
                receipt,
                receipt.timestamp,
                receipt.source_key,
                now,
                2,
                1,
            )
            == expected
        )
    async with engine.connect() as connection:
        assert (await connection.execute(sa.select(receipt.workspace_uuid))).scalars().all() == ['foreign']
    assert (await service.get_sessions(context()))[0][0]['message_count'] == 5


@pytest.mark.parametrize('oversized', [False, True])
async def test_bad_legacy_metadata_does_not_advance_backfill_cursor(service, oversized):
    from langbot.pkg.entity.persistence.event_log import EventLog
    from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
    from langbot.pkg.persistence.session_summary_backfill import CURSOR_KEY, JSON_LIMIT

    engine = service.ap.persistence_mgr.get_db_engine()
    async with engine.begin() as connection:
        await connection.execute(
            sa.insert(EventLog).values(
                event_id='bad-legacy',
                event_type='message.received',
                source='platform',
                workspace_id='workspace',
                bot_id='a',
                created_at=dt.datetime(2026, 1, 1),
                input_json='x' * (JSON_LIMIT + 1) if oversized else '{invalid-json',
            )
        )
    backfill = SessionSummaryBackfill(service._summary_session, 'sqlite')
    assert not await backfill.run_batch('workspace')
    with pytest.raises((ValueError, sa.exc.DBAPIError)):
        await backfill.run_batch('workspace')
    async with engine.connect() as connection:
        value = (
            await connection.execute(
                sa.select(WorkspaceMetadata.value).where(
                    WorkspaceMetadata.key == CURSOR_KEY,
                )
            )
        ).scalar_one()
        assert value == '{"source": "events"}'
        assert (
            await connection.execute(sa.select(sa.func.count()).select_from(models.MonitoringSession))
        ).scalar_one() == 0


async def test_offline_command_initializes_and_resumes_existing_database(tmp_path, monkeypatch):
    from langbot.pkg.entity.persistence.workspace import Workspace
    from langbot.pkg.persistence.session_summary_backfill import _main, CURSOR_KEY
    from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata

    database = tmp_path / 'offline-summary.db'
    url = f'sqlite+aiosqlite:///{database}'
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(
                sa.insert(Workspace).values(
                    uuid='workspace',
                    instance_uuid='i',
                    name='W',
                    slug='w',
                )
            )
            await connection.execute(
                sa.insert(WorkspaceMetadata).values(
                    workspace_uuid='workspace',
                    key=CURSOR_KEY,
                    value='{"source": "messages"}',
                )
            )
            await connection.execute(
                sa.insert(models.MonitoringMessage).values(
                    id='historical',
                    workspace_uuid='workspace',
                    **resource('a'),
                    session_id='history',
                    timestamp=dt.datetime(2026, 1, 1),
                    message_content='input',
                    role='user',
                    status='success',
                    level='info',
                )
            )
        monkeypatch.setenv('SUMMARY_TEST_DATABASE_URL', url)
        args = SimpleNamespace(database_url_env='SUMMARY_TEST_DATABASE_URL', workspace=['workspace'])
        await _main(args)
        await _main(args)
        async with engine.connect() as connection:
            assert (await connection.execute(sa.select(models.MonitoringSession.message_count))).scalar_one() == 1
            assert (await connection.execute(sa.select(WorkspaceMetadata.value))).scalar_one() == '{"source": "done"}'
    finally:
        await engine.dispose()


async def test_backfill_skips_unrelated_event_payloads(service):
    from langbot.pkg.entity.persistence.event_log import EventLog

    engine = service.ap.persistence_mgr.get_db_engine()
    async with engine.begin() as connection:
        await connection.execute(
            sa.insert(EventLog).values(
                event_id='unrelated',
                event_type='tool.call.completed',
                source='runner',
                workspace_id='workspace',
                bot_id='a',
                created_at=dt.datetime(2026, 1, 1),
                input_json='{broken',
                metadata_json='{broken',
            )
        )
    backfill = SessionSummaryBackfill(service._summary_session, 'sqlite')
    while not await backfill.run_batch('workspace', 1):
        pass
    assert (await service.get_sessions(context()))[1] == 0


@pytest.mark.contract('reader_scale')
async def test_list_database_work_is_independent_of_historical_payload_volume(service):
    await service.record_message(context('a'), **resource('a'), session_id='live', message_content='input')
    engine = service.ap.persistence_mgr.get_db_engine()
    steps = []

    async def measure():
        counter = [0]

        def progress():
            counter[0] += 1
            return 0

        async def install(callback):
            async with engine.connect() as connection:
                await connection.run_sync(
                    lambda sync: sync.connection.dbapi_connection.run_async(
                        lambda raw: raw.set_progress_handler(callback, 1)
                    )
                )

        await install(progress)
        try:
            assert (await service.get_sessions(context()))[1] == 1
        finally:
            await install(None)
        steps.append(counter[0])

    await measure()
    async with engine.begin() as connection:
        await connection.execute(
            sa.insert(models.MonitoringMessage),
            [
                dict(
                    id=f'scale-{i}',
                    workspace_uuid='workspace',
                    **resource('a'),
                    session_id='unrepaired',
                    timestamp=dt.datetime(2026, 1, 1),
                    message_content='x' * 8192,
                    variables='y' * 8192,
                    role='user',
                    status='success',
                    level='info',
                )
                for i in range(1000)
            ],
        )
    await measure()
    assert steps[1] <= steps[0] + 20, steps


@pytest.mark.asyncio(loop_scope='module')
@pytest.mark.postgres
@pytest.mark.contract('monitoring_sessions')
@pytest.mark.contract('summary_postgres')
@pytest.mark.contract('summary_fact_equivalence')
async def test_postgres_concurrent_writes_match_source_facts(cloud_database):  # noqa: F811
    import asyncio
    from tests.integration.persistence.test_monitoring_postgres import WORKSPACE_A, _context, _read

    ap, _admin = cloud_database
    service = ap.monitoring_service
    ctx = _context(WORKSPACE_A)
    bot, event_id = 'fact-equivalence', 'fact-equivalence-event'
    messages, ingresses = {}, {}

    async def check():
        rows, total = await _read(service, 'get_sessions', ctx, bot_ids=[bot])
        expected = session_counts_from_facts(messages, ingresses)
        assert total == len(expected)
        assert {(row['bot_id'], row['session_id']): row['message_count'] for row in rows} == expected

    async def ingress(identity):
        await service.record_ingress_event(
            ctx,
            event_id=identity,
            event_type='message.received',
            bot_id=bot,
            bot_name='Bot',
            platform='test',
            payload={},
            conversation_id='group',
        )

    for identity in (event_id, event_id + '-unhandled'):
        await ingress(identity)
        ingresses[identity] = dict(bot_id=bot, session_id='group')
    await check()
    # A rolled-back message must not consume an existing ingress credit.
    with pytest.raises(RuntimeError, match='rollback'):
        async with ap.persistence_mgr.tenant_uow(WORKSPACE_A):
            await service.record_message(
                ctx, **resource(bot), session_id='rolled-back', message_content='input', event_id=event_id
            )
            raise RuntimeError('rollback')
    await check()

    async def message(index):
        role = 'assistant' if index % 3 == 0 else 'user'
        late = role == 'user' and index % 2 == 1
        session_id = f'topic-{index % 2}'
        identity = await service.record_message(
            ctx,
            **resource(bot),
            session_id=session_id,
            message_content='input',
            role=role,
            event_id=None if late else event_id,
        )
        if late:
            for _ in range(2):
                await service.link_execution_message(ctx, identity, f'run-{index}', event_id)
        await replay_summary_message(service, WORKSPACE_A, identity)
        return identity, dict(bot_id=bot, session_id=session_id, role=role, event_id=event_id)

    async with asyncio.timeout(12):
        results = await asyncio.gather(
            *(message(index) for index in range(8)),
            *(ingress(event_id) for _ in range(3)),
        )
    messages.update(result for result in results if result is not None)
    await check()
    for identity in messages:
        await replay_summary_message(service, WORKSPACE_A, identity)
    for identity in ingresses:
        await ingress(identity)
    await check()


@pytest.mark.asyncio(loop_scope='module')
@pytest.mark.postgres
@pytest.mark.contract('monitoring_sessions')
@pytest.mark.contract('summary_postgres')
async def test_postgres_delayed_write_cannot_split_a_newer_snapshot(cloud_database, monkeypatch):  # noqa: F811
    import asyncio
    from tests.integration.persistence.test_monitoring_postgres import WORKSPACE_A, _context, _read

    ap, _admin = cloud_database
    service = ap.monitoring_service
    ctx = _context(WORKSPACE_A)
    args = dict(bot_id='processor-race', bot_name='Bot', session_id='group_race', message_content='hello')
    await service.record_message(ctx, **args, pipeline_id='a', pipeline_name='Pipeline A')
    normal_ready, discard_done = asyncio.Event(), asyncio.Event()
    original = SessionSummaryWriter.apply_once
    timestamps = {}

    async def pause_normal(self, session, change, **kwargs):
        if change.bot_id == args['bot_id']:
            timestamps[change.pipeline_id] = change.timestamp
            if change.pipeline_id == 'b':
                normal_ready.set()
                await asyncio.wait_for(discard_done.wait(), timeout=5)
        return await original(self, session, change, **kwargs)

    monkeypatch.setattr(SessionSummaryWriter, 'apply_once', pause_normal)
    normal = asyncio.create_task(
        service.record_message(ctx, **args, pipeline_id='b', pipeline_name='Pipeline B', user_id='bob')
    )
    try:
        await asyncio.wait_for(normal_ready.wait(), timeout=5)
        await service.record_message(
            ctx, **args, pipeline_id='__discard__', pipeline_name='Discarded', user_id='carol', status='discarded'
        )
        discard_done.set()
        await asyncio.wait_for(normal, timeout=5)
        assert timestamps['b'] < timestamps['__discard__']
        rows, total = await _read(service, 'get_sessions', ctx, bot_ids=[args['bot_id']])
        assert total == 1
        assert (rows[0]['pipeline_id'], rows[0]['pipeline_name']) == ('__discard__', 'Discarded')
        assert (rows[0]['user_id'], rows[0]['message_count']) == ('carol', 3)
    finally:
        discard_done.set()
        if not normal.done():
            normal.cancel()
        await asyncio.gather(normal, return_exceptions=True)


@pytest.mark.asyncio(loop_scope='module')
@pytest.mark.postgres
@pytest.mark.contract('monitoring_sessions')
@pytest.mark.contract('summary_postgres')
@pytest.mark.parametrize('transfer_kind', ['message', 'late_link'])
async def test_postgres_topic_transfer_and_group_message_commit_together(
    cloud_database,  # noqa: F811
    monkeypatch,
    transfer_kind,
):
    """Exercise the receipt FK lock against deletion/recreation of its summary."""
    import asyncio
    from tests.integration.persistence.test_monitoring_postgres import WORKSPACE_A, _context, _read

    ap, admin = cloud_database
    service = ap.monitoring_service
    ctx = _context(WORKSPACE_A)
    args = dict(bot_id=f'transfer-race-{transfer_kind}', bot_name='Bot', pipeline_id='', pipeline_name='')
    event_id = args['bot_id'] + '-event'
    await service.record_ingress_event(
        ctx,
        event_id=event_id,
        event_type='message.received',
        bot_id=args['bot_id'],
        bot_name='Bot',
        platform='test',
        payload={},
        conversation_id='group_42',
    )
    if transfer_kind == 'late_link':
        message_id = await service.record_message(
            ctx,
            **args,
            session_id='group_42#7',
            message_content='topic input',
        )
    transfer_ready, normal_attempted, normal_receipt_ready, deletion_entered = (asyncio.Event() for _ in range(4))
    normal_pid = None
    transfer_task = normal_task = None
    engine = ap.persistence_mgr.get_db_engine()

    def observe_sql(connection, cursor, sql, parameters, execution, executemany):
        nonlocal normal_pid
        statement = getattr(execution.compiled, 'statement', None)
        if getattr(getattr(statement, 'table', None), 'name', None) != 'monitoring_sessions':
            return
        if asyncio.current_task() is normal_task and (
            getattr(statement, 'is_insert', False) or getattr(statement, '_for_update_arg', None) is not None
        ):
            normal_pid = connection.connection.driver_connection.get_server_pid()
            normal_attempted.set()
        if asyncio.current_task() is transfer_task and getattr(statement, 'is_delete', False):
            deletion_entered.set()

    original = SessionSummaryWriter._refresh

    async def interleave(self, *positional, **kwargs):
        if asyncio.current_task() is transfer_task:
            transfer_ready.set()
            await normal_attempted.wait()
            # A correct writer blocks before acquiring the receipt FK lock.
            # The old writer reaches its counter update with that lock held.
            async with admin.connect() as connection:
                connection = await connection.execution_options(isolation_level='AUTOCOMMIT')
                async with asyncio.timeout(5):
                    while not normal_receipt_ready.is_set():
                        if await connection.scalar(
                            sa.text("SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid=:pid"),
                            {'pid': normal_pid},
                        ):
                            break
                        await asyncio.sleep(0.01)
        elif asyncio.current_task() is normal_task:
            normal_receipt_ready.set()
            await deletion_entered.wait()
        return await original(self, *positional, **kwargs)

    async def normal_message():
        await transfer_ready.wait()
        return await service.record_message(ctx, **args, session_id='group_42', message_content='group input')

    async def transfer():
        if transfer_kind == 'late_link':
            await service.link_execution_message(ctx, message_id, 'transfer-race-run', event_id)
            return message_id
        return await service.record_message(
            ctx,
            **args,
            session_id='group_42#7',
            message_content='topic input',
            event_id=event_id,
        )

    monkeypatch.setattr(SessionSummaryWriter, '_refresh', interleave)
    sa.event.listen(engine.sync_engine, 'before_cursor_execute', observe_sql)
    try:
        transfer_task = asyncio.create_task(transfer())
        normal_task = asyncio.create_task(normal_message())
        results = await asyncio.wait_for(
            asyncio.gather(transfer_task, normal_task, return_exceptions=True),
            timeout=12,
        )
        assert all(isinstance(result, str) and result for result in results), results
    finally:
        deletion_entered.set()
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', observe_sql)
        for task in (transfer_task, normal_task):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(
            *(task for task in (transfer_task, normal_task) if task is not None), return_exceptions=True
        )

    rows, total = await _read(service, 'get_sessions', ctx, bot_ids=[args['bot_id']])
    assert total == 2 and {row['session_id']: row['message_count'] for row in rows} == {
        'group_42': 1,
        'group_42#7': 1,
    }
    async with admin.connect() as connection:
        assert (
            await connection.scalar(
                sa.select(sa.func.count())
                .select_from(models.MonitoringMessage)
                .where(
                    models.MonitoringMessage.bot_id == args['bot_id'],
                )
            )
            == 2
        )


@pytest.mark.asyncio(loop_scope='module')
@pytest.mark.postgres
@pytest.mark.contract('monitoring_sessions')
@pytest.mark.contract('summary_postgres')
async def test_postgres_summary_dedup_rollback_backfill_and_receipt_rls(cloud_database):  # noqa: F811
    import asyncio
    from tests.integration.persistence.test_monitoring_postgres import WORKSPACE_A, WORKSPACE_B, _context, _read

    ap, admin = cloud_database
    service = ap.monitoring_service
    ctx = _context(WORKSPACE_A)
    args = dict(
        bot_id='receipt-bot',
        bot_name='Bot',
        pipeline_id='',
        pipeline_name='',
        session_id='receipt-session',
        message_content='hello',
        event_id='receipt-event',
    )
    await asyncio.gather(*[service.record_message(ctx, **args) for _ in range(10)])
    await service.record_ingress_event(
        ctx,
        event_id='receipt-event',
        event_type='message.received',
        bot_id='receipt-bot',
        bot_name='Bot',
        platform='test',
        payload={},
        conversation_id='receipt-session',
    )
    late_message = await service.record_message(ctx, **{**args, 'event_id': None})
    await service.link_execution_message(ctx, late_message, 'late-run', 'receipt-event')
    rows, total = await _read(service, 'get_sessions', ctx, bot_ids=['receipt-bot'])
    assert total == 1 and rows[0]['message_count'] == 11
    with pytest.raises(RuntimeError, match='rollback'):
        async with ap.persistence_mgr.tenant_uow(WORKSPACE_A):
            await service.record_message(ctx, **{**args, 'event_id': 'rolled-back', 'session_id': 'rolled-back'})
            raise RuntimeError('rollback')
    assert (await _read(service, 'get_sessions', ctx, bot_ids=['receipt-bot']))[1] == 1
    # The same deduplication key is independent in another Workspace.
    await service.record_message(_context(WORKSPACE_B), **args)
    for workspace in (WORKSPACE_A, WORKSPACE_B):
        async with ap.persistence_mgr.tenant_uow(workspace) as uow:
            receipts = (
                (
                    await uow.session.execute(
                        sa.select(models.MonitoringSessionReceipt).where(
                            models.MonitoringSessionReceipt.bot_id == 'receipt-bot',
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert receipts and all(receipt.workspace_uuid == workspace for receipt in receipts)
        rows, total = await _read(service, 'get_sessions', _context(workspace), bot_ids=['receipt-bot'])
        assert total == 1 and rows[0]['message_count'] == (11 if workspace == WORKSPACE_A else 1)
    backfill = SessionSummaryBackfill(service._summary_session, 'postgresql')
    for _ in range(20):
        if await backfill.run_batch(WORKSPACE_A):
            break
    else:
        pytest.fail('PostgreSQL backfill did not finish')
    assert (await _read(service, 'get_sessions', ctx, bot_ids=['receipt-bot']))[0][0]['message_count'] == 11
    async with admin.begin() as connection:
        rls = (
            await connection.execute(
                sa.text(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='monitoring_session_receipts'"
                )
            )
        ).one()
        assert tuple(rls) == (True, True)
        await connection.execute(
            sa.delete(models.MonitoringSession).where(
                models.MonitoringSession.bot_id == 'receipt-bot',
            )
        )
        assert not (
            await connection.execute(
                sa.select(models.MonitoringSessionReceipt).where(
                    models.MonitoringSessionReceipt.bot_id == 'receipt-bot',
                    models.MonitoringSessionReceipt.session_id.is_not(None),
                )
            )
        ).first()


@pytest.mark.asyncio(loop_scope='module')
@pytest.mark.postgres
@pytest.mark.contract('summary_postgres')
@pytest.mark.parametrize('reverse', [False, True])
async def test_postgres_fixed_timestamp_ingress_replay_and_backfill(cloud_database, reverse):  # noqa: F811
    import json
    from langbot.pkg.entity.persistence.event_log import EventLog
    from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
    from langbot.pkg.persistence.session_summary_backfill import CURSOR_KEY
    from tests.integration.persistence.test_monitoring_postgres import WORKSPACE_A, _context, _read

    ap, admin = cloud_database
    service = ap.monitoring_service
    ctx = _context(WORKSPACE_A)
    bot = f'tie-{reverse}'
    timestamp = dt.datetime(2026, 1, 1)
    identities = [f'{bot}-Z', f'{bot}-a']
    async with admin.begin() as connection:
        for index, event_id in enumerate(identities):
            await connection.execute(
                sa.insert(EventLog).values(
                    workspace_id=WORKSPACE_A,
                    bot_id=bot,
                    event_id=event_id,
                    event_type='message.received',
                    source='platform',
                    conversation_id='fixed',
                    event_time=timestamp,
                    created_at=timestamp + dt.timedelta(microseconds=index),
                    actor_id='winner' if index else 'old',
                    actor_name=None if index else 'Old',
                    metadata_json=json.dumps({'routes': [{'target_uuid': event_id, 'target_type': 'agent'}]}),
                )
            )

    async def replay(event_id, **kwargs):
        await service.record_ingress_event(
            ctx,
            event_id=event_id,
            event_type='message.received',
            bot_id=bot,
            bot_name='',
            platform=None,
            payload={},
            conversation_id='fixed',
            **kwargs,
        )

    for event_id in identities[:: -1 if reverse else 1]:
        await replay(event_id)
    rows, total = await _read(service, 'get_sessions', ctx, bot_ids=[bot])
    assert total == 1 and rows[0]['message_count'] == 2
    assert (rows[0]['user_id'], rows[0]['user_name'], rows[0]['pipeline_id']) == ('winner', None, identities[1])
    await replay(
        identities[1],
        actor_id='winner',
        actor_name='Winner',
        routes=[{'target_uuid': 'completed', 'target_type': 'agent'}],
    )
    expected = (await _read(service, 'get_sessions', ctx, bot_ids=[bot]))[0]
    assert (expected[0]['user_name'], expected[0]['pipeline_id']) == ('Winner', 'completed')
    for event_id in reversed(identities):
        await replay(event_id)
    assert (await _read(service, 'get_sessions', ctx, bot_ids=[bot]))[0] == expected
    async with admin.begin() as connection:
        for model in (models.MonitoringSessionReceipt, models.MonitoringSession):
            await connection.execute(sa.delete(model).where(model.workspace_uuid == WORKSPACE_A, model.bot_id == bot))
        await connection.execute(
            sa.delete(WorkspaceMetadata).where(
                WorkspaceMetadata.workspace_uuid == WORKSPACE_A, WorkspaceMetadata.key == CURSOR_KEY
            )
        )
    while not await SessionSummaryBackfill(service._summary_session, 'postgresql').run_batch(WORKSPACE_A):
        pass
    assert (await _read(service, 'get_sessions', ctx, bot_ids=[bot]))[0] == expected
    await replay(identities[0])
    assert (await _read(service, 'get_sessions', ctx, bot_ids=[bot]))[0] == expected
