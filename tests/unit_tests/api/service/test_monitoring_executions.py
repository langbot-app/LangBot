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


@pytest.mark.asyncio
@pytest.mark.parametrize('napcat', [True, False])
@pytest.mark.parametrize('source', ['agent', 'pipeline'])
async def test_execution_details_refresh_existing_images_through_shared_catalog(engine, service, napcat, source):
    import json
    from unittest.mock import AsyncMock
    import sqlalchemy as sa
    from langbot.pkg.entity.persistence.event_log import EventLog
    from langbot.pkg.entity.persistence.transcript import Transcript
    from langbot.pkg.entity.persistence.resource_url import ResourceURL
    from langbot.pkg.platform.adapters.aiocqhttp.image_urls import OneBotImageURLs

    old = 'https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=existing&rkey=expired'
    new = old.replace('expired', 'renewed')
    chain = [{'type': 'Source', 'id': 42}, {'type': 'Image', 'image_id': 'pic.jpg', 'url': old}]
    content = {'content': [{'type': 'image_url', 'image_url': {'url': old}}]}
    await _seed(engine)
    async with AsyncSession(engine) as session:
        await session.execute(
            sa.update(persistence_agent_run.AgentRun)
            .where(persistence_agent_run.AgentRun.run_id == 'run-done')
            .values(conversation_id='session-1')
        )
        await session.execute(
            sa.update(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.id == 'msg-user')
            .values(message_content=json.dumps(chain))
        )
        await session.execute(
            sa.update(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.id == 'msg-assistant')
            .values(message_content=json.dumps(chain), parent_message_id='msg-user')
        )
        session.add(
            EventLog(
                event_id='evt-1',
                event_type='message.received',
                source='platform',
                workspace_id=WORKSPACE,
                bot_id='bot-1',
                input_json=json.dumps(content),
                metadata_json=json.dumps({'input_event': {'message_chain': chain}}),
            )
        )
        session.add(
            Transcript(
                transcript_id='image-output',
                event_id='evt-1',
                workspace_id=WORKSPACE,
                bot_id='bot-1',
                conversation_id='session-1',
                role='assistant',
                run_id='run-done',
                seq=1,
                content_json=json.dumps(content),
                attachment_refs_json=json.dumps([chain[1]]),
            )
        )
        await session.commit()

    async with engine.begin() as db:
        await db.execute(sa.update(ResourceURL).values(created_at=_dt(10)))

    async def action(name, **params):
        if name == 'get_version_info':
            return {'app_name': 'NapCat.Onebot' if napcat else 'standard-peer'}
        if napcat:
            assert name == 'nc_get_rkey'
            return [{'type': 20, 'time': 1, 'ttl': 10**12, 'rkey': 'renewed'}]
        assert name == 'get_msg' and params == {'message_id': 42}
        return {'message': [{'type': 'image', 'data': {'file': 'pic.jpg', 'url': new}}]}

    peer = SimpleNamespace(closed=False, call_action=AsyncMock(side_effect=action))
    peer.image_urls = OneBotImageURLs(peer)
    bot = SimpleNamespace(
        workspace_uuid=WORKSPACE,
        enable=True,
        bot_entity=SimpleNamespace(adapter='onebot-v11'),
        adapter=SimpleNamespace(bot=SimpleNamespace(connection=peer)),
    )
    service.ap.platform_mgr = SimpleNamespace(resolve_public_bot=AsyncMock(return_value=bot))
    identity = 'run-done' if source == 'agent' else 'msg-user'
    detail = await service.get_execution_detail(WORKSPACE, source, identity)
    for section in ('inputs', 'conversation'):
        assert new in json.dumps(detail['pages'][section]['items'])
        assert old not in json.dumps(detail['pages'][section]['items'])
    if source == 'agent':
        assert new in json.dumps(detail['pages']['outputs']['items'])
    else:
        assert new in json.dumps(detail['pages']['deliveries']['items'])
    await service.get_execution_detail(WORKSPACE, source, identity, section='conversation')
    assert peer.call_action.await_count == 2
    async with engine.connect() as db:
        assert new in (await db.execute(sa.select(EventLog.input_json))).scalar_one()
        assert new in (await db.execute(sa.select(Transcript.content_json))).scalar_one()
        raw = (await db.execute(sa.text('SELECT input_json FROM event_log'))).scalar_one()
        assert 'langbot-resource://' in raw and old not in raw and new not in raw


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
@pytest.mark.parametrize('filtered', [False, True])
@pytest.mark.parametrize(
    ('mode', 'statuses', 'expected'),
    [
        ('real', None, (3, 2, 1)),
        ('debug', None, (0, 0, 0)),
        ('all', ['completed'], (2, 1, 1)),
        ('real', ['completed'], (2, 1, 1)),
        ('real', ['failed'], (0, 0, 0)),
        ('debug', ['completed'], (0, 0, 0)),
    ],
)
async def test_overview_execution_filters_do_not_read_historical_payload_pages(
    engine, service, mode, statuses, expected, filtered
):
    """Execution membership must read root and link metadata without accessing wide history rows."""
    import re
    import sqlalchemy as sa

    await _seed(engine)
    message = persistence_monitoring.MonitoringMessage
    payload = 'historical payload ' * 65536
    async with engine.begin() as connection:
        await connection.execute(sa.update(message).values(message_content=payload, variables=payload))
        await connection.execute(
            sa.update(message).where(message.id == 'msg-assistant').values(parent_message_id='msg-user')
        )
        # Vary status selectivity so the planner cannot hide table reads behind a tiny fixture.
        await connection.execute(
            sa.insert(message),
            [
                dict(
                    id=f'unlinked-{index}',
                    workspace_uuid=WORKSPACE,
                    timestamp=_dt(12),
                    bot_id='bot-1',
                    bot_name='Bot',
                    pipeline_id='pipeline-1',
                    pipeline_name='Pipeline',
                    session_id='session-1',
                    message_content='unlinked assistant output',
                    role='assistant',
                    status=('success', 'error', 'discarded', 'skipped', 'rejected', 'running', 'pending')[index % 7],
                    level='info',
                )
                for index in range(64)
            ],
        )
        await connection.exec_driver_sql('ANALYZE')

    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('SELECT'):
            statements.append((statement, parameters))

    sa.event.listen(engine.sync_engine, 'before_cursor_execute', capture)
    try:
        filters = (
            dict(bot_ids=['bot-1'], pipeline_ids=['pipeline-1'], start_time=_dt(9), end_time=_dt(11))
            if filtered
            else {}
        )
        overview = await service.get_overview_metrics(WORKSPACE, execution_statuses=statuses, mode=mode, **filters)
    finally:
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', capture)

    assert (overview['total_messages'], overview['llm_calls'], overview['active_sessions']) == expected
    checked_accesses = 0
    async with engine.connect() as connection:
        for sql, parameters in statements:
            # Discover aliases from the executed SQL rather than pinning an alias or index name.
            sources = {message.__tablename__, *re.findall(r'FROM monitoring_messages AS (\w+)', sql)}
            plan = (await connection.exec_driver_sql('EXPLAIN QUERY PLAN ' + sql, parameters)).all()
            accesses = [
                row[3] for row in plan if row[3].split()[0] in {'SEARCH', 'SCAN'} and row[3].split()[1] in sources
            ]
            assert accesses, plan
            assert all('COVERING INDEX' in access for access in accesses), plan
            checked_accesses += len(accesses)
    assert checked_accesses > 0


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
async def test_detail_overview_does_not_query_collapsed_sections(engine, service, monkeypatch):
    await _seed(engine)
    page = service._execution_page
    converters = []

    async def capture(workspace, statement, convert, offset, limit):
        converters.append(convert.__name__)
        return await page(workspace, statement, convert, offset, limit)

    async def reject_history(*args, **kwargs):
        pytest.fail('Collapsed conversation history must not be loaded')

    monkeypatch.setattr(service, '_execution_page', capture)
    monkeypatch.setattr(service, '_conversation_message_page', reject_history)
    detail = await service.get_execution_detail(WORKSPACE, 'pipeline', 'msg-user', section='overview')

    assert set(detail['pages']) == {'inputs', 'outputs', 'deliveries', 'errors'}
    assert detail['pages']['inputs']['items'][0]['id'] == 'msg-user'
    assert len(converters) == 4
    assert 'events' not in detail


@pytest.mark.asyncio
async def test_conversation_pages_identities_from_covering_index_before_payloads(engine, service):
    import sqlalchemy as sa

    await _seed(engine)
    message = persistence_monitoring.MonitoringMessage
    payload = 'historical inline media ' * 4096
    async with engine.begin() as connection:
        await connection.execute(
            sa.insert(message),
            [
                dict(
                    id=f'history-{index:02d}',
                    workspace_uuid=workspace,
                    bot_id=bot,
                    bot_name='Bot',
                    pipeline_id='pipeline',
                    pipeline_name='Pipeline',
                    session_id='session-1',
                    timestamp=_dt(12),
                    role='user',
                    message_content=payload,
                    variables=payload,
                    status='success',
                    level='info',
                )
                for index, (workspace, bot) in enumerate(
                    [(WORKSPACE, 'bot-1')] * 5 + [(WORKSPACE, 'other-bot'), ('other-workspace', 'bot-1')]
                )
            ],
        )
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('SELECT'):
            statements.append((statement, parameters))

    sa.event.listen(engine.sync_engine, 'before_cursor_execute', capture)
    try:
        first = await service.get_execution_detail(WORKSPACE, 'pipeline', 'msg-user', section='conversation', limit=2)
        second = await service.get_execution_detail(
            WORKSPACE, 'pipeline', 'msg-user', section='conversation', limit=2, offset=2
        )
    finally:
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', capture)

    page = first['pages']['conversation']
    assert [row['id'] for row in page['items']] == ['history-04', 'history-03']
    assert page['has_more'] and page['next_offset'] == 2
    assert all(row['content'] == payload for row in page['items'])
    assert [row['id'] for row in second['pages']['conversation']['items']] == ['history-02', 'history-01']
    identities = [(sql, params) for sql, params in statements if sql.startswith('SELECT monitoring_messages.id \n')]
    assert len(identities) == 2
    async with engine.connect() as connection:
        for sql, params in identities:
            assert 'message_content' not in sql and 'variables' not in sql
            plan = (await connection.exec_driver_sql('EXPLAIN QUERY PLAN ' + sql, params)).all()
            assert any('COVERING INDEX ix_monitoring_messages_conversation_page' in row[3] for row in plan), plan
            assert not any('TEMP B-TREE' in row[3] for row in plan), plan
        payload_queries = [(sql, params) for sql, params in statements if 'JOIN monitoring_messages ON' in sql]
        assert len(payload_queries) == 2
        assert {value for value in payload_queries[0][1] if str(value).startswith('history-')} == {
            'history-04',
            'history-03',
        }
        for sql, params in payload_queries:
            plan = (await connection.exec_driver_sql('EXPLAIN QUERY PLAN ' + sql, params)).all()
            assert any('sqlite_autoindex_monitoring_messages_1 (id=?)' in row[3] for row in plan), plan


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


@pytest.mark.asyncio
async def test_inflight_excludes_unowned_and_expired_messages_without_rewriting_history(engine, service):
    import sqlalchemy as sa

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    Message = persistence_monitoring.MonitoringMessage
    async with AsyncSession(engine) as session:
        for message_id, owner, expiry, timestamp in [
            ('legacy', None, None, _dt(1)),
            ('recent-unowned', None, now + datetime.timedelta(minutes=1), now),
            ('expired', 'stopped-host', now - datetime.timedelta(seconds=1), _dt(1)),
            ('long-running', 'live-host', now + datetime.timedelta(minutes=1), _dt(1)),
        ]:
            session.add(
                Message(
                    id=message_id,
                    workspace_uuid=WORKSPACE,
                    timestamp=timestamp,
                    bot_id='bot',
                    bot_name='Bot',
                    pipeline_id='pipeline',
                    pipeline_name='Pipeline',
                    session_id='session',
                    message_content='historical message',
                    status='pending',
                    level='info',
                    execution_owner_id=owner,
                    execution_lease_expires_at=expiry,
                )
            )
        session.add(
            persistence_agent_run.AgentRun(
                run_id='remote-queue',
                workspace_id=WORKSPACE,
                runner_id='runner',
                status='queued',
                queue_name='remote',
                created_at=_dt(1),
            )
        )
        await session.commit()
    # A previous connection must not reintroduce unowned pending rows either.
    snapshot = await service.get_inflight_snapshot(WORKSPACE, [{'source': 'pipeline', 'id': 'legacy'}])
    assert snapshot['active_total'] == 2
    assert {row['id'] for row in snapshot['items']} == {'long-running', 'remote-queue'}
    async with AsyncSession(engine) as session:
        statuses = (await session.execute(sa.select(Message.status))).scalars().all()
    assert statuses == ['pending'] * 4


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['all', 'pipeline'])
@pytest.mark.parametrize('statuses', [['running'], ['running', 'queued']])
async def test_active_inflight_count_and_page_use_the_indexed_lease_range(engine, service, source, statuses):
    import sqlalchemy as sa

    await _seed(engine)
    async with engine.begin() as connection:
        await connection.execute(
            sa.update(persistence_monitoring.MonitoringMessage)
            .where(persistence_monitoring.MonitoringMessage.id == 'msg-user')
            .values(status='pending', message_content='historical payload ' * 8192)
        )
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('SELECT '):
            statements.append((statement, parameters))

    sa.event.listen(engine.sync_engine, 'before_cursor_execute', capture)
    try:
        result = await service.get_executions(
            WORKSPACE, statuses=statuses, source=source, include_summary=False, for_inflight=True
        )
    finally:
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', capture)

    assert result == {'items': [], 'total': 0, 'has_more': False}
    assert len(statements) == 2  # Both COUNT and the sorted page must skip historical payloads.
    async with engine.connect() as connection:
        for statement, parameters in statements:
            plan = (await connection.exec_driver_sql('EXPLAIN QUERY PLAN ' + statement, parameters)).all()
            assert any(
                'ix_monitoring_messages_workspace_status_lease' in row[3] and 'execution_lease_expires_at>?' in row[3]
                for row in plan
            ), plan


@pytest.mark.asyncio
async def test_empty_inflight_snapshot_skips_linked_history_and_clears_tracking(engine, service, monkeypatch):
    import sqlalchemy as sa
    from langbot.pkg.utils.inflight import inflight_hub

    await _seed(engine)
    monkeypatch.setattr(inflight_hub, 'run_workspaces', {'finished-run': WORKSPACE, 'other-run': 'other-workspace'})
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    sa.event.listen(engine.sync_engine, 'before_cursor_execute', capture)
    try:
        snapshot = await service.get_inflight_snapshot(WORKSPACE)
    finally:
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', capture)

    assert snapshot == {'items': [], 'active_total': 0, 'truncated': False}
    assert inflight_hub.run_workspaces == {'other-run': 'other-workspace'}
    assert not any('JOIN monitoring_messages ON' in query or 'FROM agent_run_event' in query for query in statements)


@pytest.mark.asyncio
async def test_inflight_never_loads_payloads_in_active_recent_or_terminal_rows(engine, service, monkeypatch):
    import json
    import sqlalchemy as sa
    from langbot.pkg.entity.persistence.event_log import EventLog

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    payload = json.dumps({'text': 'full input', 'attachment': 'x' * (2 * 1024 * 1024)})
    async with AsyncSession(engine) as session:
        for message_id, status, timestamp in [
            ('active-message', 'pending', _dt(1)),
            ('recent-message', 'success', now),
            ('finished-message', 'success', _dt(1)),
        ]:
            session.add(
                persistence_monitoring.MonitoringMessage(
                    id=message_id,
                    workspace_uuid=WORKSPACE,
                    timestamp=timestamp,
                    bot_id='bot',
                    bot_name='Bot',
                    pipeline_id='pipeline',
                    pipeline_name='Pipeline',
                    session_id='session',
                    message_content=payload,
                    variables=payload,
                    status=status,
                    level='info',
                    event_id=message_id,
                    run_id='linked-run' if status == 'pending' else None,
                    execution_owner_id='host' if status == 'pending' else None,
                    execution_lease_expires_at=now + datetime.timedelta(minutes=1) if status == 'pending' else None,
                )
            )
            session.add(
                EventLog(
                    event_id=message_id,
                    workspace_id=WORKSPACE,
                    event_type='message.received',
                    source='platform',
                    input_summary='small summary',
                    input_json=payload,
                    metadata_json=json.dumps({'platform': 'test', 'unused_payload': payload}),
                )
            )
        for run_id in ['linked-run', 'standalone-run']:
            session.add(
                persistence_agent_run.AgentRun(
                    run_id=run_id,
                    workspace_id=WORKSPACE,
                    runner_id='runner',
                    status='running',
                    created_at=_dt(1),
                    authorization_json=payload,
                    metadata_json=json.dumps(
                        {'event_type': 'message.received', 'agent_name': 'Agent', 'input': {'text': payload}}
                    ),
                )
            )
        await session.commit()

    linkage_queries = []

    def reject_payload_reads(connection, cursor, statement, parameters, context, executemany):
        for column in [
            'monitoring_messages.message_content',
            'monitoring_messages.variables',
            'agent_run.authorization_json',
            'event_log.input_json',
        ]:
            assert column not in statement
        if statement.startswith('SELECT agent_run.run_id,') and 'monitoring_messages.id AS message_id' in statement:
            linkage_queries.append((statement, parameters))

    deserialize = service._deserialize_json

    def bounded_metadata(raw):
        assert not raw or len(raw) < 10000
        return deserialize(raw)

    monkeypatch.setattr(service, '_deserialize_json', bounded_metadata)
    sa.event.listen(engine.sync_engine, 'before_cursor_execute', reject_payload_reads)
    try:
        snapshot = await service.get_inflight_snapshot(WORKSPACE, [{'source': 'pipeline', 'id': 'finished-message'}])
        rows = {row['id']: row for row in snapshot['items']}
        assert rows['active-message']['input_preview'] == 'small summary'
        assert rows['recent-message']['status_group'] == 'completed'
        assert rows['finished-message']['status_group'] == 'completed'
        assert rows['standalone-run']['target_name'] == 'Agent'
        assert snapshot['active_total'] == 2
    finally:
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', reject_payload_reads)
    assert linkage_queries
    async with engine.connect() as connection:
        for statement, parameters in linkage_queries:
            plan = (await connection.exec_driver_sql('EXPLAIN QUERY PLAN ' + statement, parameters)).all()
            message_lookups = [row[3] for row in plan if 'SEARCH monitoring_messages' in row[3]]
            assert message_lookups and all('(id=?)' in lookup for lookup in message_lookups), plan


@pytest.mark.asyncio
async def test_inflight_snapshot_is_scoped_and_keeps_terminal_transition(engine, service):
    import sqlalchemy as sa
    from unittest.mock import AsyncMock

    service._get_execution_summary = AsyncMock(side_effect=AssertionError('No dashboard aggregates'))
    service._get_token_coverage = AsyncMock(side_effect=AssertionError('No dashboard aggregates'))
    async with AsyncSession(engine) as session:
        for workspace, run_id in [(WORKSPACE, 'flight-visible'), ('other-workspace', 'flight-secret')]:
            session.add(
                persistence_agent_run.AgentRun(
                    run_id=run_id,
                    workspace_id=workspace,
                    runner_id='runner',
                    status='running',
                    created_at=_dt(1),
                )
            )
        session.add(persistence_agent_run.AgentRunEvent(run_id='flight-visible', sequence=1, type='tool.started'))
        await session.commit()
    # SSE loaders execute after the HTTP handler's tenant scope has exited.
    # Cloud persistence rejects implicit execute_async calls in that context.
    from contextlib import asynccontextmanager

    original_execute = service.ap.persistence_mgr.execute_async
    unscoped_execute = AsyncMock(side_effect=AssertionError('Cloud persistence requires an explicit tenant scope'))

    @asynccontextmanager
    async def tenant_scope(workspace):
        assert workspace == WORKSPACE
        service.ap.persistence_mgr.execute_async = original_execute
        try:
            yield
        finally:
            service.ap.persistence_mgr.execute_async = unscoped_execute

    service.ap.persistence_mgr.tenant_scope = tenant_scope
    service.ap.persistence_mgr.execute_async = unscoped_execute
    snapshot = await service.get_inflight_snapshot(WORKSPACE)
    rows = {r['id']: r for r in snapshot['items']}
    assert 'flight-secret' not in rows
    assert rows['flight-visible']['progress_event'] == 'tool.started'
    async with AsyncSession(engine) as session:
        await session.execute(
            sa.update(persistence_agent_run.AgentRun)
            .where(persistence_agent_run.AgentRun.run_id == 'flight-visible')
            .values(status='completed')
        )
        await session.commit()
    next_snapshot = await service.get_inflight_snapshot(WORKSPACE, [rows['flight-visible']])
    assert next(r for r in next_snapshot['items'] if r['id'] == 'flight-visible')['status_group'] == 'completed'


@pytest.mark.asyncio
async def test_inflight_viewers_share_work_and_cleanup():
    import asyncio
    from unittest.mock import AsyncMock
    from langbot.pkg.utils.inflight import InflightHub

    hub = InflightHub()
    loader = AsyncMock(return_value={'items': []})
    first = hub.watch('one', loader)
    second = hub.watch('one', loader)
    assert (await anext(first))['kind'] == 'snapshot'
    assert (await anext(second))['kind'] == 'snapshot'
    assert loader.await_count == 1
    other_loader = AsyncMock(return_value={'items': ['private']})
    other = hub.watch('two', other_loader)
    assert (await anext(other))['data']['items'] == ['private']
    hub.track('one', ['run'])
    hub.notify_run('run', 'tool.started')
    loader.return_value = {'items': ['updated']}
    frame = await asyncio.wait_for(anext(first), 2)
    assert frame['data']['items'] == ['updated']
    assert (await anext(second)) == frame
    await first.aclose()
    assert 'one' in hub.channels
    await second.aclose()
    assert 'one' not in hub.channels and 'run' not in hub.run_workspaces
    await other.aclose()
    assert not hub.channels


@pytest.mark.asyncio
async def test_inflight_snapshot_failure_is_logged_and_recovers(caplog):
    import asyncio
    from unittest.mock import AsyncMock
    from langbot.pkg.utils.inflight import InflightHub

    hub = InflightHub()
    snapshot = {'items': [], 'active_total': 0, 'truncated': False}
    loader = AsyncMock(side_effect=[RuntimeError('snapshot database failure'), snapshot])
    stream = hub.watch('workspace', loader)
    try:
        assert await asyncio.wait_for(anext(stream), 2) == {'kind': 'unavailable'}
        errors = [
            record for record in caplog.records if record.message == 'Failed to load in-flight monitoring snapshot'
        ]
        assert len(errors) == 1
        assert errors[0].exc_info[0] is RuntimeError
        hub.notify('workspace')
        assert await asyncio.wait_for(anext(stream), 2) == {'kind': 'snapshot', 'data': snapshot}
    finally:
        await stream.aclose()
    assert not hub.channels
