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


class FakePersistenceManager:
    """Runs statements against a real in-memory SQLite engine."""

    def __init__(self, engine):
        self._engine = engine
        self._factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    def get_db_engine(self):
        return self._engine

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
