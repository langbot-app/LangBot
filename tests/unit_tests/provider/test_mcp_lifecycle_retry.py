"""Regression coverage for OAuth termination and per-connection retry budgets."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.provider.tools.loaders.mcp import MCPSessionStatus, RuntimeMCPSession
from langbot.pkg.provider.tools.loaders.mcp_stdio import MCPSessionErrorPhase


def _session() -> RuntimeMCPSession:
    context = ExecutionContext(instance_uuid='instance-a', workspace_uuid='workspace-a', placement_generation=1)
    ap = SimpleNamespace(
        logger=Mock(),
        workspace_service=SimpleNamespace(get_execution_binding=AsyncMock(return_value=context)),
    )
    return RuntimeMCPSession('retry-regression', {'uuid': 'srv-1', 'mode': 'stdio'}, True, ap, context)


@pytest.mark.asyncio
async def test_repeated_connected_box_failures_get_fresh_startup_budget(monkeypatch):
    """Actual CONNECTED transitions reset backoff, not lifetime failure counts."""
    session = _session()
    disconnects = session._MAX_RETRIES + 2
    monitor_calls = 0
    tasks_before = asyncio.all_tasks()

    async def monitor():
        nonlocal monitor_calls
        monitor_calls += 1
        if monitor_calls > disconnects:
            session._shutdown_event.set()

    monkeypatch.setattr(session, '_init_stdio_python_server', AsyncMock())
    monkeypatch.setattr(session, 'refresh', AsyncMock())
    monkeypatch.setattr(session._box_stdio_runtime, 'uses_box_stdio', lambda: True)
    monkeypatch.setattr(session._box_stdio_runtime, 'monitor_process_health', monitor)
    monkeypatch.setattr(session._box_stdio_runtime, '_managed_process_is_running', AsyncMock(return_value=False))
    cleanup = AsyncMock()
    monkeypatch.setattr(session, '_cleanup_box_stdio_session', cleanup)
    backoff = AsyncMock()
    monkeypatch.setattr(session, '_sleep_with_execution_fence', backoff)

    await asyncio.wait_for(session._lifecycle_loop_with_retry(), timeout=2)

    assert monitor_calls == disconnects + 1
    assert session._connection_generation == disconnects + 1
    assert session.status == MCPSessionStatus.CONNECTED
    assert session._shutdown_event.is_set()
    assert [call.args[0] for call in backoff.await_args_list] == [session._RETRY_DELAYS[0]] * disconnects
    assert cleanup.await_count == disconnects + 1
    assert not (asyncio.all_tasks() - tasks_before)


@pytest.mark.asyncio
async def test_startup_failures_without_connection_still_exhaust_budget(monkeypatch):
    session = _session()
    startup = AsyncMock(side_effect=RuntimeError('startup failed'))
    monkeypatch.setattr(session, '_init_stdio_python_server', startup)
    monkeypatch.setattr(session, '_cleanup_box_stdio_session', AsyncMock())
    backoff = AsyncMock()
    monkeypatch.setattr(session, '_sleep_with_execution_fence', backoff)

    await asyncio.wait_for(session._lifecycle_loop_with_retry(), timeout=2)

    assert session._connection_generation == 0
    assert startup.await_count == session._MAX_RETRIES + 1
    assert session.retry_count == session._MAX_RETRIES + 1
    assert session.status == MCPSessionStatus.ERROR
    assert session._ready_event.is_set()
    assert [call.args[0] for call in backoff.await_args_list] == session._RETRY_DELAYS


@pytest.mark.asyncio
async def test_oauth_is_terminal_even_after_connection_generation_changes(monkeypatch):
    """A new connection must not make an OAuth failure eligible for retry."""
    session = _session()

    async def oauth_failure():
        if lifecycle.await_count == 1:
            session._connection_generation += 1
        session.error_phase = MCPSessionErrorPhase.OAUTH_REQUIRED
        raise RuntimeError('authorization required')

    lifecycle = AsyncMock(side_effect=oauth_failure)
    monkeypatch.setattr(session, '_lifecycle_loop', lifecycle)
    backoff = AsyncMock()
    monkeypatch.setattr(session, '_sleep_with_execution_fence', backoff)

    await asyncio.wait_for(session._lifecycle_loop_with_retry(), timeout=2)

    lifecycle.assert_awaited_once()
    backoff.assert_not_awaited()
    assert session.retry_count == 1
    assert session.status == MCPSessionStatus.ERROR
    assert session.error_phase == MCPSessionErrorPhase.OAUTH_REQUIRED
    assert session._ready_event.is_set()
