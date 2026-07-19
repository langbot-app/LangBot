from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.persistence.tenant_uow import PersistenceScopeKind
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
async def test_cloud_controller_releases_database_connection_during_pipeline_wait(
    tmp_path,
    mock_app,
    sample_query,
):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "pipeline-short-scope.db"}')
    table = sa.Table('pipeline_scope_probe', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
    manager = PersistenceManager(object(), mode=PersistenceMode.CLOUD_RUNTIME)
    manager.db = SimpleNamespace(get_engine=lambda: engine)
    checked_out = 0

    def on_checkout(*_args):
        nonlocal checked_out
        checked_out += 1

    def on_checkin(*_args):
        nonlocal checked_out
        checked_out -= 1

    sa.event.listen(engine.sync_engine, 'checkout', on_checkout)
    sa.event.listen(engine.sync_engine, 'checkin', on_checkin)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(table.metadata.create_all)

        _prepare_scheduler(mock_app)
        mock_app.persistence_mgr = manager
        pipeline_waiting = asyncio.Event()
        release_pipeline = asyncio.Event()

        async def get_binding(*_args, **_kwargs):
            assert manager.current_scope().kind is PersistenceScopeKind.WORKSPACE
            assert manager.current_session() is None
            await manager.execute_async(sa.select(table.c.id))
            assert manager.current_session() is None
            return SimpleNamespace(
                instance_uuid='test-instance',
                workspace_uuid='test-workspace',
                placement_generation=1,
            )

        async def run_pipeline(_query):
            await manager.execute_async(sa.select(table.c.id))
            assert manager.current_session() is None
            pipeline_waiting.set()
            await release_pipeline.wait()
            assert manager.current_scope().kind is PersistenceScopeKind.WORKSPACE
            assert manager.current_session() is None

        runtime_pipeline = SimpleNamespace(run=AsyncMock(side_effect=run_pipeline))

        async def get_pipeline(*_args, **_kwargs):
            await manager.execute_async(sa.select(table.c.id))
            assert manager.current_session() is None
            return runtime_pipeline

        mock_app.workspace_service.get_execution_binding = AsyncMock(side_effect=get_binding)
        mock_app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(side_effect=get_pipeline)
        controller = Controller(mock_app)

        task = asyncio.create_task(controller._process_query(sample_query))
        await asyncio.wait_for(pipeline_waiting.wait(), timeout=2)
        assert checked_out == 0
        assert not task.done()
        release_pipeline.set()
        await asyncio.wait_for(task, timeout=2)
        assert checked_out == 0
        runtime_pipeline.run.assert_awaited_once_with(sample_query)
    finally:
        await engine.dispose()


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
