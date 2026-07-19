from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from langbot.pkg.agent.runner.errors import RunnerNotFoundError
from langbot.pkg.pipeline.controller import Controller


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


@pytest.mark.asyncio
async def test_try_claim_steering_returns_false_when_runner_lookup_fails():
    app = make_app()
    app.pipeline_mgr.get_pipeline_by_uuid.return_value = make_pipeline()
    app.agent_run_orchestrator.try_claim_steering_from_query.side_effect = RunnerNotFoundError(
        'plugin:missing/runner/default'
    )
    controller = Controller(app)
    query = SimpleNamespace(query_id=1, pipeline_uuid='pipeline-001', variables={})

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
    query = SimpleNamespace(query_id=2, pipeline_uuid='pipeline-002', variables={})

    claimed = await controller._try_claim_steering_before_session_slot(query)

    assert claimed is True
    assert query.pipeline_config is pipeline.pipeline_entity.config
    assert query.variables['_pipeline_bound_plugins'] == ['test/runner']
    app.agent_run_orchestrator.try_claim_steering_from_query.assert_awaited_once_with(query)
