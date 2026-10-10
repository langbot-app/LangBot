"""Execution-view tests for the monitoring service.

Covers the unified agent-run + pipeline-query execution list, its rollup
summary, and single-execution traces.
"""

from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from langbot.pkg.api.http.service.monitoring import MonitoringService
from langbot.pkg.entity.persistence import agent_interaction as persistence_interaction
from langbot.pkg.entity.persistence import agent_run as persistence_agent_run
from langbot.pkg.entity.persistence import monitoring as persistence_monitoring
from langbot.pkg.entity.persistence import workspace as persistence_workspace  # noqa: F401
from langbot.pkg.entity.persistence.base import Base

WORKSPACE = 'workspace-1'


@pytest.mark.asyncio
@pytest.mark.parametrize('has_log', [False, True])
async def test_event_properties_survive_detail_snapshot_fallback(engine, service, has_log):
    import json
    from langbot.pkg.entity.persistence.event_log import EventLog

    data = {'member': {'id': 'u1', 'active': False}, 'count': 0, 'custom': {'reason': 'joined'}}
    async with AsyncSession(engine) as session:
        session.add(
            persistence_agent_run.AgentRun(
                run_id='custom-run',
                event_id='custom-event',
                workspace_id=WORKSPACE,
                runner_id='runner',
                status='completed',
                created_at=_dt(10),
                metadata_json=json.dumps(
                    {
                        'event_type': 'group.member_joined',
                        'input_event': data,
                        'input': {'text': '', 'contents': [], 'attachments': []},
                    }
                ),
            )
        )
        if has_log:
            session.add(
                EventLog(
                    event_id='custom-event',
                    event_type='group.member_joined',
                    source='webui',
                    workspace_id=WORKSPACE,
                    run_id='custom-run',
                    input_json='{"text":"","contents":[]}',
                    created_at=_dt(10),
                )
            )
            session.add(
                EventLog(
                    event_id='later-event',
                    event_type='message.received',
                    source='webui',
                    workspace_id=WORKSPACE,
                    run_id='custom-run',
                    input_json='{"text":"later"}',
                    created_at=_dt(10, 1),
                )
            )
        await session.commit()
    detail = await service.get_execution_detail(WORKSPACE, 'agent', 'custom-run')
    items = detail['pages']['inputs']['items']
    assert items[0]['content']['event']['member'] == data['member']
    assert items[0]['content']['event']['count'] == 0
    assert items[0]['content']['event']['custom'] == data['custom']
    if has_log:
        assert items[1]['content'] == {'text': 'later'}


def test_event_content_preserves_conflicting_custom_input_fields():
    from langbot.pkg.api.http.service.monitoring_execution_details import event_content

    assert event_content({'text': 'normalized'}, {'text': {'custom': False}}) == {
        'text': 'event',
        'event': {'text': {'custom': False}},
        'input': {'text': 'normalized'},
    }


class FakePersistenceManager:
    """Runs statements against a real in-memory SQLite engine."""

    def __init__(self, engine):
        self._engine = engine
        self._factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    def get_db_engine(self):
        return self._engine

    def tenant_uow(self, workspace_uuid):
        from langbot.pkg.persistence.tenant_uow import TenantUnitOfWork

        return TenantUnitOfWork(self._engine, workspace_uuid)

    async def execute_async(self, statement):
        # Match PersistenceManager's connection-level result shape.
        async with self._engine.connect() as connection:
            return await connection.execute(statement)

    @staticmethod
    def serialize_model(model, data):
        out = {}
        for column in model.__table__.columns:
            value = getattr(data, column.name)
            out[column.name] = value.isoformat() if isinstance(value, datetime.datetime) else value
        return out


@pytest.fixture
async def engine(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "monitoring_executions.db"}')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def service(engine):
    ap = SimpleNamespace(
        persistence_mgr=FakePersistenceManager(engine),
        instance_config=None,
    )
    return MonitoringService(ap)


def _dt(hour: int, minute: int = 0, second: int = 0) -> datetime.datetime:
    return datetime.datetime(2026, 1, 1, hour, minute, second)


async def _seed(engine) -> None:
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add_all(
            [
                persistence_agent_run.AgentRun(
                    run_id='run-done',
                    event_id='evt-1',
                    agent_id='agent-1',
                    binding_id='agent_agent-1_default',
                    runner_id='runner-1',
                    workspace_id=WORKSPACE,
                    bot_id='bot-1',
                    status='completed',
                    created_at=_dt(10),
                    started_at=_dt(10, 0, 1),
                    finished_at=_dt(10, 0, 3),
                    usage_json='{"total_tokens": 42}',
                ),
                persistence_agent_run.AgentRun(
                    run_id='run-failed',
                    binding_id='agent_agent-1_default',
                    runner_id='runner-1',
                    workspace_id=WORKSPACE,
                    bot_id='bot-1',
                    status='failed',
                    created_at=_dt(10, 5),
                ),
                persistence_agent_run.AgentRun(
                    run_id='run-debug',
                    event_id='debug:agent-1:e1',
                    agent_id='agent-1',
                    binding_id='debug:agent-1:runner-1',
                    runner_id='runner-1',
                    workspace_id=WORKSPACE,
                    bot_id='bot-1',
                    status='completed',
                    created_at=_dt(10, 6),
                    started_at=_dt(10, 6, 0),
                    finished_at=_dt(10, 6, 1),
                ),
                persistence_agent_run.AgentRunEvent(
                    run_id='run-done',
                    sequence=1,
                    type='run.completed',
                    data_json='{"message": {"role": "assistant", "content": "hi"}}',
                ),
                persistence_interaction.AgentInteraction(
                    interaction_id='int-1',
                    run_id='run-done',
                    binding_id='agent_agent-1_default',
                    runner_id='runner-1',
                    processor_type='agent',
                    processor_id='agent-1',
                    workspace_id=WORKSPACE,
                    status='pending',
                    request_json='{}',
                    callback_token_hash='hash-1',
                ),
            ]
        )
        for message in [
            dict(
                id='msg-user',
                timestamp=_dt(10, 2),
                session_id='session-1',
                message_content='{"chain": [{"type": "Plain", "text": "hello there"}]}',
                status='success',
                role='user',
            ),
            dict(
                id='msg-assistant',
                timestamp=_dt(10, 3),
                session_id='session-1',
                message_content='{"chain": [{"type": "Plain", "text": "reply"}]}',
                status='success',
                role='assistant',
            ),
            dict(
                id='msg-discarded',
                timestamp=_dt(10, 4),
                session_id='session-2',
                message_content='{"chain": [{"type": "Plain", "text": "ignored"}]}',
                status='discarded',
                role='user',
            ),
        ]:
            session.add(
                persistence_monitoring.MonitoringMessage(
                    workspace_uuid=WORKSPACE,
                    bot_id='bot-1',
                    bot_name='Bot One',
                    pipeline_id='pipeline-1',
                    pipeline_name='Pipeline One',
                    level='info',
                    **message,
                )
            )
        session.add_all(
            [
                persistence_monitoring.MonitoringLLMCall(
                    id='llm-1',
                    workspace_uuid=WORKSPACE,
                    timestamp=_dt(10, 2, 30),
                    model_name='gpt',
                    input_tokens=10,
                    output_tokens=20,
                    total_tokens=30,
                    duration=100,
                    status='success',
                    bot_id='bot-1',
                    bot_name='Bot One',
                    pipeline_id='pipeline-1',
                    pipeline_name='Pipeline One',
                    session_id='session-1',
                    message_id='msg-user',
                ),
                persistence_monitoring.MonitoringLLMCall(
                    id='llm-2',
                    workspace_uuid=WORKSPACE,
                    timestamp=_dt(10, 4, 30),
                    model_name='gpt',
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    duration=50,
                    status='success',
                    bot_id='bot-1',
                    bot_name='Bot One',
                    pipeline_id='pipeline-1',
                    pipeline_name='Pipeline One',
                    session_id='session-2',
                    message_id='msg-discarded',
                ),
            ]
        )
        session.add(
            persistence_monitoring.MonitoringSession(
                workspace_uuid=WORKSPACE,
                bot_id='bot-1',
                session_id='session-1',
                bot_name='Bot One',
                pipeline_id='pipeline-1',
                pipeline_name='Pipeline One',
                message_count=2,
                start_time=_dt(10, 2),
                last_activity=_dt(10, 5),
                is_active=True,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_executions_merge_and_order_both_sources(engine, service):
    await _seed(engine)

    result = await service.get_executions(WORKSPACE, limit=50)

    assert result['total'] == 5
    ids = [(item['source'], item['id']) for item in result['items']]
    # Assistant replies are outputs, not executions.
    assert ('pipeline', 'msg-assistant') not in ids
    # Newest first across both object types.
    assert ids == [
        ('agent', 'run-debug'),
        ('agent', 'run-failed'),
        ('pipeline', 'msg-discarded'),
        ('pipeline', 'msg-user'),
        ('agent', 'run-done'),
    ]

    by_id = {item['id']: item for item in result['items']}
    assert result['summary']['executions']['total'] == 5
    assert result['summary']['executions']['denominator'] == 4
    assert result['summary']['tokens']['calls'] == 2
    assert result['summary']['tokens']['calls_with_usage'] == 1
    assert by_id['run-done']['status_group'] == 'completed'
    assert by_id['run-failed']['status_group'] == 'failed'
    assert by_id['run-debug']['debug'] is True
    assert by_id['run-done']['debug'] is False
    assert by_id['run-done']['usage'] == {'total_tokens': 42}
    assert by_id['run-done']['duration_ms'] == 2000
    assert by_id['msg-user']['status_group'] == 'completed'
    assert by_id['msg-discarded']['status_group'] == 'ignored'
    assert by_id['msg-user']['title'] == 'hello there'
    assert by_id['msg-user']['target_id'] == 'pipeline-1'


@pytest.mark.asyncio
async def test_executions_source_status_and_paging(engine, service):
    await _seed(engine)

    only_agents = await service.get_executions(WORKSPACE, source='agent')
    assert {item['source'] for item in only_agents['items']} == {'agent'}
    assert only_agents['total'] == 3

    pipeline_only = await service.get_executions(WORKSPACE, source='pipeline')
    assert {item['source'] for item in pipeline_only['items']} == {'pipeline'}
    assert pipeline_only['total'] == 2

    # A single-object target selection narrows the union to that source.
    by_pipeline = await service.get_executions(WORKSPACE, pipeline_ids=['pipeline-1'])
    assert {item['source'] for item in by_pipeline['items']} == {'pipeline'}

    failed = await service.get_executions(WORKSPACE, statuses=['failed'])
    assert [item['id'] for item in failed['items']] == ['run-failed']

    # `ignored` only exists for pipeline queries: it must not widen the agent
    # filter back to "every status".
    ignored = await service.get_executions(WORKSPACE, statuses=['ignored'])
    assert [item['id'] for item in ignored['items']] == ['msg-discarded']

    debug_only = await service.get_executions(WORKSPACE, mode='debug')
    assert [item['id'] for item in debug_only['items']] == ['run-debug']

    first_page = await service.get_executions(WORKSPACE, limit=2)
    assert len(first_page['items']) == 2
    assert first_page['has_more'] is True
    second_page = await service.get_executions(WORKSPACE, limit=2, offset=2)
    assert first_page['items'][0]['id'] != second_page['items'][0]['id']


@pytest.mark.asyncio
async def test_execution_summary_uses_explicit_denominator(engine, service):
    await _seed(engine)

    summary = (await service.get_executions(WORKSPACE))['summary']
    executions = summary['executions']

    # completed = run-done + run-debug + msg-user; failed = run-failed.
    assert executions['by_source'] == {'agent': 3, 'pipeline': 2}
    assert executions['completed'] == 3
    assert executions['failed'] == 1
    assert executions['ignored'] == 1
    assert executions['denominator'] == 4
    assert executions['success_rate'] == 75.0
    assert executions['debug'] == 1
    assert executions['real'] == 4
    assert executions['waiting'] == 1
    assert executions['p50_duration_ms'] == 1000
    assert executions['p95_duration_ms'] == 2000
    # Only run-done and run-debug are completed runs with a start and a finish.
    assert executions['duration_sample'] == 2

    # Token coverage is explicit: llm-2 succeeded without usage.
    assert summary['tokens'] == {'total_tokens': 30, 'calls': 2, 'calls_with_usage': 1}


@pytest.mark.asyncio
async def test_overview_metrics_keep_message_rollup(engine, service):
    await _seed(engine)

    overview = await service.get_overview_metrics(WORKSPACE)

    assert overview['total_messages'] == 3
    assert overview['llm_calls'] == 2
    assert overview['model_calls'] == 2
    assert overview['active_sessions'] == 1


@pytest.mark.asyncio
async def test_execution_detail_for_agent_and_pipeline(engine, service):
    await _seed(engine)

    agent_detail = await service.get_execution_detail(WORKSPACE, 'agent', 'run-done')
    assert agent_detail['run']['run_id'] == 'run-done'
    assert agent_detail['events'][0]['type'] == 'run.completed'

    pipeline_detail = await service.get_execution_detail(WORKSPACE, 'pipeline', 'msg-user')
    assert pipeline_detail['message']['id'] == 'msg-user'
    assert [call['id'] for call in pipeline_detail['llm_calls']] == ['llm-1']
    assert pipeline_detail['tool_calls'] == []

    with pytest.raises(ValueError):
        await service.get_execution_detail(WORKSPACE, 'agent', 'missing-run')

    with pytest.raises(ValueError):
        await service.get_execution_detail(WORKSPACE, 'pipeline', 'missing-message')


@pytest.mark.asyncio
async def test_explicit_deliveries_context_and_tenant_isolation(engine, service):
    import sqlalchemy as sa

    await _seed(engine)
    async with AsyncSession(engine) as session:
        await session.execute(
            sa.update(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.id == 'msg-assistant')
            .values(parent_message_id='msg-user')
        )
        await session.commit()
    detail = await service.get_execution_detail(WORKSPACE, 'auto', 'msg-assistant')
    assert detail['row']['id'] == 'msg-user'
    assert [m['id'] for m in detail['pages']['deliveries']['items']] == ['msg-assistant']
    assert detail['pages']['inputs']['items'][0]['id'] == 'msg-user'
    assert detail['pages']['conversation']['items']
    with pytest.raises(ValueError, match='not found'):
        await service.get_execution_detail('another-workspace', 'auto', 'msg-assistant')


@pytest.mark.asyncio
async def test_legacy_replies_are_context_not_guessed_deliveries(engine, service):
    await _seed(engine)
    detail = await service.get_execution_detail(WORKSPACE, 'pipeline', 'msg-user')
    assert detail['legacy_context'] is True
    assert detail['pages']['deliveries']['items'] == []
    assert 'msg-assistant' in [m['id'] for m in detail['pages']['conversation']['items']]


@pytest.mark.asyncio
async def test_fanout_steering_orphans_and_paged_trace(engine, service):
    import json
    import sqlalchemy as sa
    from langbot.pkg.entity.persistence.event_log import EventLog
    from langbot.pkg.entity.persistence.transcript import Transcript

    await _seed(engine)
    async with AsyncSession(engine) as session:
        await session.execute(
            sa.update(persistence_agent_run.AgentRun)
            .where(persistence_agent_run.AgentRun.run_id == 'run-done')
            .values(
                conversation_id='shared',
                thread_id='thread-1',
                metadata_json=json.dumps({'processor_type': 'event_processor'}),
            )
        )
        session.add_all(
            [
                EventLog(
                    event_id='evt-1',
                    event_type='message.received',
                    source='platform',
                    workspace_id=WORKSPACE,
                    bot_id='bot-1',
                    input_json='{"text":"original input"}',
                    actor_name='Alice',
                    created_at=_dt(10),
                ),
                EventLog(
                    event_id='steer',
                    event_type='message.received',
                    source='platform',
                    workspace_id=WORKSPACE,
                    bot_id='bot-1',
                    run_id='run-done',
                    input_json='{"text":"additional input"}',
                    created_at=_dt(10, 1),
                ),
                EventLog(
                    event_id='unrouted',
                    event_type='group.member.joined',
                    source='platform',
                    workspace_id=WORKSPACE,
                    bot_id='bot-1',
                    metadata_json='{"status":"ignored"}',
                    created_at=_dt(10, 7),
                ),
                persistence_agent_run.AgentRun(
                    run_id='sibling',
                    event_id='evt-1',
                    workspace_id=WORKSPACE,
                    bot_id='bot-1',
                    runner_id='plugin',
                    status='completed',
                    created_at=_dt(10),
                ),
                Transcript(
                    transcript_id='output',
                    event_id='generated',
                    conversation_id='shared',
                    thread_id='thread-1',
                    workspace_id=WORKSPACE,
                    bot_id='bot-1',
                    role='assistant',
                    content='generated only',
                    run_id='run-done',
                    seq=1,
                ),
                Transcript(
                    transcript_id='other-thread',
                    event_id='other',
                    conversation_id='shared',
                    thread_id='thread-2',
                    workspace_id=WORKSPACE,
                    bot_id='bot-1',
                    role='user',
                    content='private other thread',
                    seq=2,
                ),
            ]
        )
        session.add_all(
            [
                persistence_agent_run.AgentRunEvent(run_id='run-done', sequence=i, type='message.delta', data_json='{}')
                for i in range(2, 206)
            ]
        )
        await session.commit()
    result = await service.get_executions(WORKSPACE)
    assert 'unrouted' in [r['id'] for r in result['items']]
    assert 'steer' not in [r['id'] for r in result['items']]
    ignored = await service.get_executions(WORKSPACE, statuses=['ignored'])
    assert 'unrouted' in [r['id'] for r in ignored['items']]
    detail = await service.get_execution_detail(WORKSPACE, 'agent', 'run-done')
    assert detail['row']['target_kind'] == 'event_processor'
    assert detail['row']['user_name'] == 'Alice'
    assert [i['id'] for i in detail['pages']['inputs']['items']] == ['evt-1', 'steer']
    assert detail['pages']['outputs']['items'][0]['content'] == 'generated only'
    assert [i['id'] for i in detail['pages']['related']['items']] == ['sibling']
    assert 'other-thread' not in [i['id'] for i in detail['pages']['conversation']['items']]
    assert len(detail['pages']['events']['items']) == 100
    assert detail['pages']['events']['has_more']
    final = await service.get_execution_detail(WORKSPACE, 'agent', 'run-done', section='events', offset=200)
    assert len(final['pages']['events']['items']) == 5
    assert not final['pages']['events']['has_more']
    orphan = await service.get_execution_detail(WORKSPACE, 'event', 'unrouted')
    assert orphan['pages']['deliveries']['items'] == []
    assert orphan['pages']['conversation']['items'] == []


@pytest.mark.asyncio
async def test_pipeline_runner_is_not_counted_twice(engine, service):
    import sqlalchemy as sa

    await _seed(engine)
    async with AsyncSession(engine) as session:
        await session.execute(
            sa.update(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.id == 'msg-user')
            .values(run_id='run-done')
        )
        await session.commit()
    result = await service.get_executions(WORKSPACE)
    assert result['total'] == 4
    assert result['summary']['executions']['total'] == 4
    assert 'run-done' not in [r['id'] for r in result['items']]
    detail = await service.get_execution_detail(WORKSPACE, 'pipeline', 'msg-user')
    assert detail['row']['duration_ms'] == 2000
    assert detail['events'][0]['type'] == 'run.completed'


@pytest.mark.asyncio
async def test_event_log_fanout_is_idempotent_and_cannot_cross_tenants(engine):
    from langbot.pkg.agent.runner.event_log_store import EventLogStore

    store = EventLogStore(engine)
    await store.append_event('event-id', 'message.received', 'platform', workspace_id=WORKSPACE, bot_id='bot')
    await store.append_event(
        'event-id',
        'message.received',
        'platform',
        workspace_id=WORKSPACE,
        bot_id='bot',
        run_id='first-run',
        input_json={'text': 'input', 'attachments': []},
    )
    await store.append_event(
        'event-id', 'message.received', 'platform', workspace_id=WORKSPACE, bot_id='bot', run_id='second-run'
    )
    event = await store.get_event('event-id')
    assert event['run_id'] == 'first-run'
    assert event['input_json']['text'] == 'input'
    with pytest.raises(Exception):
        await store.append_event('event-id', 'message.received', 'platform', workspace_id='other', bot_id='bot')


@pytest.mark.asyncio
async def test_processor_filter_scopes_each_kind_and_legacy_calls(engine, service):
    import json

    await _seed(engine)
    async with AsyncSession(engine) as session:
        session.add(
            persistence_agent_run.AgentRun(
                run_id='event-run',
                workspace_id=WORKSPACE,
                runner_id='event-runner',
                status='completed',
                created_at=_dt(11),
                metadata_json=json.dumps({'processor_type': 'event_processor', 'processor_id': 'event-processor-1'}),
            )
        )
        session.add(
            persistence_monitoring.MonitoringLLMCall(
                id='event-call',
                bot_id='bot-1',
                bot_name='Bot One',
                pipeline_name='Event Processor',
                session_id='session-event',
                input_tokens=6,
                output_tokens=6,
                duration=1,
                timestamp=_dt(11),
                workspace_uuid=WORKSPACE,
                model_name='model',
                message_id='event-run',
                pipeline_id='',
                status='success',
                total_tokens=12,
            )
        )
        await session.commit()
    for processor, expected in [
        ('agent-1', {'run-done', 'run-debug'}),
        ('pipeline-1', {'msg-user', 'msg-discarded'}),
        ('event-processor-1', {'event-run'}),
        ('missing', set()),
    ]:
        result = await service.get_executions(WORKSPACE, pipeline_ids=[processor])
        assert {row['id'] for row in result['items']} == expected
        assert result['total'] == result['summary']['executions']['total'] == len(expected)
    calls, total = await service.get_llm_calls(WORKSPACE, pipeline_ids=['event-processor-1'])
    assert total == 1
    assert [row['id'] for row in calls] == ['event-call']
    other = await service.get_executions('another-workspace', pipeline_ids=['event-processor-1'])
    assert other['total'] == 0


@pytest.mark.asyncio
async def test_execution_filters_also_scope_cards_calls_and_traffic(engine, service):
    import sqlalchemy as sa
    from langbot.pkg.api.http.service.monitoring_traffic import get_traffic_series

    await _seed(engine)
    async with AsyncSession(engine) as session:
        await session.execute(
            sa.update(persistence_monitoring.MonitoringLLMCall)
            .where(persistence_monitoring.MonitoringLLMCall.id == 'llm-1')
            .values(message_id='run-failed', pipeline_id='')
        )
        await session.commit()
    failed = await service.get_executions(WORKSPACE, statuses=['failed'])
    assert failed['total'] == failed['summary']['executions']['total'] == 1
    assert failed['summary']['executions']['waiting'] == 0
    calls, total = await service.get_llm_calls(WORKSPACE, execution_statuses=['failed'])
    assert total == 1 and calls[0]['id'] == 'llm-1'
    # A successful model call may belong to a failed execution.
    assert calls[0]['status'] == 'success'
    overview = await service.get_overview_metrics(WORKSPACE, execution_statuses=['failed'])
    assert overview['llm_calls'] == 1 and overview['total_messages'] == 0
    traffic = await get_traffic_series(service.ap, WORKSPACE, execution_statuses=['failed'])
    assert sum(p['llm_calls'] for p in traffic['points']) == 1
    assert sum(p['messages'] for p in traffic['points']) == 0

    debug = await service.get_executions(WORKSPACE, mode='debug')
    assert debug['total'] == debug['summary']['executions']['total'] == 1
    real = await service.get_executions(WORKSPACE, mode='real')
    assert real['total'] == real['summary']['executions']['total'] == 4
    traffic = await get_traffic_series(service.ap, WORKSPACE, mode='debug')
    assert sum(p['messages'] for p in traffic['points']) == 0


@pytest.mark.asyncio
async def test_pipeline_debug_is_consistent_across_rows_rollups_and_telemetry(engine, service):
    import sqlalchemy as sa
    from langbot.pkg.api.http.service.monitoring_traffic import get_traffic_series

    await _seed(engine)
    async with AsyncSession(engine) as session:
        await session.execute(
            sa.update(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.id == 'msg-user')
            .values(bot_id='websocket-proxy-bot')
        )
        await session.execute(
            sa.update(persistence_monitoring.MonitoringLLMCall)
            .where(persistence_monitoring.MonitoringLLMCall.id == 'llm-1')
            .values(message_id='msg-user', pipeline_id='pipeline-1')
        )
        await session.execute(
            sa.update(persistence_agent_run.AgentRun)
            .where(persistence_agent_run.AgentRun.run_id == 'run-done')
            .values(bot_id='websocket-proxy-bot')
        )
        await session.commit()
    debug = await service.get_executions(WORKSPACE, mode='debug')
    ids = {r['id'] for r in debug['items']}
    assert ids == {'msg-user', 'run-done', 'run-debug'}
    assert all(r['debug'] for r in debug['items'])
    assert debug['summary']['executions']['total'] == 3
    assert debug['summary']['executions']['debug'] == 3
    real = await service.get_executions(WORKSPACE, mode='real')
    assert not ids.intersection(r['id'] for r in real['items'])
    assert real['summary']['executions']['debug'] == 0
    filtered = await service.get_executions(WORKSPACE, pipeline_ids=['pipeline-1'], mode='debug')
    assert [r['id'] for r in filtered['items']] == ['msg-user']
    calls, total = await service.get_llm_calls(WORKSPACE, pipeline_ids=['pipeline-1'], mode='debug')
    assert total == 1 and calls[0]['id'] == 'llm-1'
    real_rows, real_calls = await service.get_llm_calls(WORKSPACE, pipeline_ids=['pipeline-1'], mode='real')
    assert real_calls == 1 and real_rows[0]['id'] == 'llm-2'
    traffic = await get_traffic_series(service.ap, WORKSPACE, mode='debug', pipeline_ids=['pipeline-1'])
    assert sum(p['llm_calls'] for p in traffic['points']) == 1
