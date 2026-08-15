from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.core.app import Application


@pytest.mark.asyncio
async def test_shutdown_closes_mcp_session_manager_once() -> None:
    app = Application()
    stop_session_manager = AsyncMock()
    app.platform_mgr = SimpleNamespace(shutdown=AsyncMock())
    app.tool_mgr = SimpleNamespace(shutdown=AsyncMock())
    app.model_mgr = SimpleNamespace(shutdown=AsyncMock())
    app.box_service = SimpleNamespace(shutdown=AsyncMock())
    app.plugin_connector = SimpleNamespace(aclose=AsyncMock())
    app.telemetry = SimpleNamespace(shutdown=AsyncMock())
    app.vector_db_mgr = SimpleNamespace(shutdown=AsyncMock())
    app.storage_mgr = SimpleNamespace(shutdown=AsyncMock())
    manifest_provider = SimpleNamespace(aclose=AsyncMock())
    app.deployment = SimpleNamespace(manifest_provider=manifest_provider)
    persistence_engine = SimpleNamespace(dispose=AsyncMock())
    app.persistence_mgr = SimpleNamespace(db=SimpleNamespace(engine=persistence_engine))
    app.http_ctrl = SimpleNamespace(mcp_mount=SimpleNamespace(stop_session_manager=stop_session_manager))

    await app.shutdown()
    await app.shutdown()

    stop_session_manager.assert_awaited_once()
    app.platform_mgr.shutdown.assert_awaited_once()
    app.tool_mgr.shutdown.assert_awaited_once()
    app.model_mgr.shutdown.assert_awaited_once()
    app.box_service.shutdown.assert_awaited_once()
    app.plugin_connector.aclose.assert_awaited_once()
    app.telemetry.shutdown.assert_awaited_once()
    app.vector_db_mgr.shutdown.assert_awaited_once()
    app.storage_mgr.shutdown.assert_awaited_once()
    manifest_provider.aclose.assert_awaited_once()
    persistence_engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispose_tracks_only_one_shutdown_task() -> None:
    app = Application()
    app.event_loop = asyncio.get_running_loop()

    app.dispose()
    shutdown_task = app._shutdown_task
    app.dispose()

    assert shutdown_task is not None
    assert app._shutdown_task is shutdown_task
    await shutdown_task

    app.dispose()
    assert app._shutdown_task is shutdown_task


@pytest.mark.asyncio
async def test_runtime_resource_stats_are_aggregate_and_constant_time() -> None:
    app = Application()
    app.event_loop = asyncio.get_running_loop()
    app.blocking_executor = SimpleNamespace(
        snapshot=lambda: {
            'inflight': 3,
            'running': 2,
            'pending': 1,
            'rejected_total': 4,
        }
    )
    app.task_mgr = SimpleNamespace(get_stats=lambda: {'total': 5, 'completed': 2})
    app.query_pool = SimpleNamespace(
        queries=[object()],
        cached_queries={},
        active_query_count_by_workspace={'workspace-a': 1},
    )
    app.model_mgr = SimpleNamespace(
        provider_dict={'provider': object()},
        llm_model_dict={},
        embedding_model_dict={},
        rerank_model_dict={},
    )
    app.platform_mgr = SimpleNamespace(_bots_by_key={})
    app.pipeline_mgr = SimpleNamespace(_pipelines_by_key={})
    app.rag_mgr = SimpleNamespace(knowledge_bases={})
    app.plugin_connector = SimpleNamespace(
        _known_desired_states={'installation': object()},
        _runtime_available=lambda: True,
    )
    app.persistence_mgr = SimpleNamespace(
        get_resource_stats=lambda: {
            'configured_capacity': 20,
            'checked_out': 3,
        }
    )
    app.directory_projection_service = SimpleNamespace(
        resource_snapshot=lambda: {
            'active_workspaces': 10,
            'max_active_workspaces': 1000,
        }
    )
    app.tool_mgr = SimpleNamespace(
        mcp_tool_loader=SimpleNamespace(
            _sessions={},
            _hosted_mcp_tasks=[],
            _host_dispatch_tasks=set(),
        )
    )
    app.telemetry = SimpleNamespace(send_tasks=[])

    stats = app.get_runtime_resource_stats()

    assert stats['asyncio_tasks'] >= 1
    assert stats['event_loop'] == {
        'running': False,
        'samples_total': 0,
        'last_lag_ms': 0,
        'recent_p95_lag_ms': 0,
        'recent_max_lag_ms': 0,
        'max_lag_ms': 0,
    }
    assert stats['blocking_executor']['rejected_total'] == 4
    assert stats['application_tasks'] == {
        'total': 5,
        'completed': 2,
    }
    assert stats['database_pool'] == {
        'configured_capacity': 20,
        'checked_out': 3,
    }
    assert stats['directory'] == {
        'active_workspaces': 10,
        'max_active_workspaces': 1000,
    }
    assert stats['query_pool'] == {
        'queued': 1,
        'cached': 0,
        'active_workspaces': 1,
    }
    assert stats['models']['providers'] == 1
    assert stats['runtimes']['plugin_installations'] == 1
    assert stats['runtimes']['plugin_runtime_connected'] is True
