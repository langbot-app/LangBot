from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.agent.runner.errors import RunnerNotFoundError
from langbot.pkg.pipeline.controller import Controller
from langbot.pkg.pipeline.pool import QueryPool


def make_app():
    app = SimpleNamespace()
    app.instance_config = SimpleNamespace(data={'concurrency': {'pipeline': 10}})
    app.logger = MagicMock()
    app.pipeline_mgr = SimpleNamespace()
    app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock()
    app.sess_mgr = SimpleNamespace()
    app.sess_mgr.get_session = AsyncMock(return_value=SimpleNamespace())
    app.agent_run_orchestrator = SimpleNamespace()
    app.agent_run_orchestrator.try_claim_steering_from_query = AsyncMock()
    return app


def make_pipeline():
    return SimpleNamespace(
        pipeline_entity=SimpleNamespace(config={'ai': {'runner': {'id': 'plugin:test/runner/default'}}}),
        bound_plugins=['test/runner'],
        bound_mcp_servers=[],
    )


def make_query(query_id: int, pipeline_uuid: str):
    context = ExecutionContext(
        instance_uuid='instance-test',
        workspace_uuid='workspace-test',
        placement_generation=1,
        pipeline_uuid=pipeline_uuid,
    )
    return SimpleNamespace(
        query_id=query_id,
        pipeline_uuid=pipeline_uuid,
        variables={},
        _execution_context=context,
    )


@pytest.mark.asyncio
async def test_try_claim_steering_returns_false_when_runner_lookup_fails():
    app = make_app()
    app.pipeline_mgr.get_pipeline_by_uuid.return_value = make_pipeline()
    app.agent_run_orchestrator.try_claim_steering_from_query.side_effect = RunnerNotFoundError(
        'plugin:missing/runner/default'
    )
    controller = Controller(app)
    query = make_query(1, 'pipeline-001')

    claimed = await controller._try_claim_steering_before_session_slot(query)

    assert claimed is False
    app.logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_try_claim_steering_sets_pipeline_context_before_claiming():
    app = make_app()
    pipeline = make_pipeline()
    app.pipeline_mgr.get_pipeline_by_uuid.return_value = pipeline
    app.agent_run_orchestrator.try_claim_steering_from_query.return_value = True
    controller = Controller(app)
    query = make_query(2, 'pipeline-002')

    claimed = await controller._try_claim_steering_before_session_slot(query)

    assert claimed is True
    assert query.pipeline_config is pipeline.pipeline_entity.config
    assert query.variables['_pipeline_bound_plugins'] == ['test/runner']
    app.agent_run_orchestrator.try_claim_steering_from_query.assert_awaited_once_with(query)


@pytest.mark.asyncio
async def test_consumer_transfers_query_from_queue_to_running_task():
    app = make_app()
    app.query_pool = QueryPool()
    session = SimpleNamespace(_semaphore=asyncio.Semaphore(1))
    app.sess_mgr.get_session = AsyncMock(return_value=session)
    app.persistence_mgr = SimpleNamespace(mode=SimpleNamespace(value='oss'))
    app.workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(
            return_value=SimpleNamespace(
                instance_uuid='instance-test',
                workspace_uuid='workspace-test',
                placement_generation=1,
            )
        )
    )
    runtime_pipeline = SimpleNamespace(run=AsyncMock())
    app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(return_value=runtime_pipeline)

    worker_tasks = []
    task_created = asyncio.Event()

    def create_task(coro, **_kwargs):
        task = asyncio.create_task(coro)
        worker_tasks.append(task)
        task_created.set()
        return task

    app.task_mgr = SimpleNamespace(create_task=create_task)

    query = Mock()
    query.query_id = 0
    query.bot_uuid = 'bot-test'
    query.pipeline_uuid = 'pipeline-test'
    context = ExecutionContext(
        instance_uuid='instance-test',
        workspace_uuid='workspace-test',
        placement_generation=1,
    )
    with patch('langbot.pkg.pipeline.pool.pipeline_query.Query', return_value=query):
        query = await app.query_pool.add_query(
            bot_uuid='bot-test',
            launcher_type=Mock(),
            launcher_id='launcher-test',
            sender_id='sender-test',
            message_event=Mock(),
            message_chain=Mock(),
            adapter=Mock(),
            pipeline_uuid='pipeline-test',
            execution_context=context,
        )

    controller = Controller(app)
    consumer_task = asyncio.create_task(controller.consumer())
    try:
        await asyncio.wait_for(task_created.wait(), timeout=1)
        await asyncio.wait_for(worker_tasks[0], timeout=1)
    finally:
        consumer_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer_task

    runtime_pipeline.run.assert_awaited_once_with(query)
    assert app.query_pool.queries == []
    assert app.query_pool.cached_queries == {}
    assert app.query_pool.active_query_count_by_workspace == {}
    assert session._semaphore._value == 1
    assert controller.semaphore._value == 10
    app.logger.error.assert_not_called()
