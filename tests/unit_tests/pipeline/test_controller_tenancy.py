from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from langbot.pkg.pipeline.controller import Controller
from langbot.pkg.workspace.errors import WorkspaceGenerationMismatchError


def _prepare_scheduler(mock_app):
    query_pool = MagicMock()
    query_pool.remove_query = AsyncMock(return_value=True)
    query_pool.__aenter__ = AsyncMock(return_value=query_pool)
    query_pool.__aexit__ = AsyncMock(return_value=None)
    query_pool.condition = SimpleNamespace(notify_all=Mock())
    mock_app.query_pool = query_pool

    session = SimpleNamespace(_semaphore=SimpleNamespace(release=Mock()))
    mock_app.sess_mgr.get_session = AsyncMock(return_value=session)
    mock_app.pipeline_mgr = SimpleNamespace(get_pipeline_by_uuid=AsyncMock())
    return query_pool, session


@pytest.mark.asyncio
async def test_controller_drops_stale_query_before_pipeline_lookup(
    mock_app,
    sample_query,
):
    query_pool, session = _prepare_scheduler(mock_app)
    mock_app.workspace_service.get_execution_binding.side_effect = WorkspaceGenerationMismatchError('stale generation')
    controller = Controller(mock_app)

    await controller._process_query(sample_query)

    mock_app.workspace_service.get_execution_binding.assert_awaited_once_with(
        'test-workspace',
        expected_generation=1,
    )
    mock_app.pipeline_mgr.get_pipeline_by_uuid.assert_not_awaited()
    query_pool.remove_query.assert_awaited_once_with(sample_query)
    session._semaphore.release.assert_called_once_with()
    query_pool.condition.notify_all.assert_called_once_with()


@pytest.mark.asyncio
async def test_controller_revalidates_generation_before_running_pipeline(
    mock_app,
    sample_query,
):
    query_pool, session = _prepare_scheduler(mock_app)
    runtime_pipeline = SimpleNamespace(run=AsyncMock())
    mock_app.pipeline_mgr.get_pipeline_by_uuid.return_value = runtime_pipeline
    controller = Controller(mock_app)

    await controller._process_query(sample_query)

    mock_app.workspace_service.get_execution_binding.assert_awaited_once_with(
        'test-workspace',
        expected_generation=1,
    )
    runtime_pipeline.run.assert_awaited_once_with(sample_query)
    query_pool.remove_query.assert_awaited_once_with(sample_query)
    session._semaphore.release.assert_called_once_with()
