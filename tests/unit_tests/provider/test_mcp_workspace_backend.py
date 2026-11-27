from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.provider.tools.loaders.mcp import MCPLoader, RuntimeMCPSession


@pytest.mark.asyncio
async def test_parallel_tasks_have_pinned_mcp_sessions_and_distinct_processes(monkeypatch):
    context = ExecutionContext(
        instance_uuid='instance', workspace_uuid='workspace', placement_generation=1, query_uuid='task'
    )
    ap = SimpleNamespace(
        logger=Mock(),
        instance_config=SimpleNamespace(data={}),
        box_service=SimpleNamespace(enabled=True, backend_supports_managed_processes=AsyncMock(return_value=True)),
    )
    loader = MCPLoader(ap)
    base = RuntimeMCPSession('server', {'uuid': 'server-id', 'mode': 'stdio'}, True, ap, context)
    base.sandbox_backend = 'docker'
    loader._register_session(context, 'server', base)
    started, stopped = [], []

    async def start(self):
        started.append(self)

    async def shutdown(self):
        stopped.append(self)

    monkeypatch.setattr(RuntimeMCPSession, 'start', start)
    monkeypatch.setattr(RuntimeMCPSession, 'shutdown', shutdown)
    first_entered, finish_first = asyncio.Event(), asyncio.Event()

    async def first_task():
        async with loader.task_sandbox_scope(context, 'e2b'):
            selected = loader.get_session(context, 'server')
            first_entered.set()
            await finish_first.wait()
            assert selected is loader.get_session(context, 'server')
            assert selected not in stopped
            return selected

    task = asyncio.create_task(first_task())
    await first_entered.wait()
    import dataclasses

    second_context = dataclasses.replace(context, query_uuid='second-task')
    async with loader.task_sandbox_scope(second_context, 'e2b'):
        second = loader.get_session(second_context, 'server')
        import contextvars

        assert contextvars.Context().run(loader.get_session, second_context, 'server') is second
        assert second is not base
    assert second in stopped and base not in stopped
    finish_first.set()
    first = await task
    assert first._box_stdio_runtime.process_id != second._box_stdio_runtime.process_id
    assert first.sandbox_backend == second.sandbox_backend == 'e2b'
    assert loader.get_session(context, 'server') is base
    async with loader.task_sandbox_scope(context, 'docker'):
        assert loader.get_session(context, 'server') is base
    assert base not in stopped


@pytest.mark.asyncio
async def test_unbound_or_unsupported_stdio_does_not_block_tasks(monkeypatch):
    context = ExecutionContext(instance_uuid='instance', workspace_uuid='workspace', placement_generation=1)
    ap = SimpleNamespace(
        logger=Mock(),
        instance_config=SimpleNamespace(data={}),
        box_service=SimpleNamespace(enabled=True, backend_supports_managed_processes=AsyncMock(return_value=False)),
    )
    loader = MCPLoader(ap)
    base = RuntimeMCPSession('server', {'uuid': 'id', 'mode': 'stdio'}, True, ap, context)
    base.sandbox_backend = 'docker'
    loader._register_session(context, 'server', base)
    start = AsyncMock(side_effect=AssertionError('must not launch unsupported or unbound server'))
    monkeypatch.setattr(RuntimeMCPSession, 'start', start)
    async with loader.task_sandbox_scope(context, 'e2b', tool_names=[]):
        assert loader.get_session(context, 'server') is None
    async with loader.task_sandbox_scope(context, 'e2b'):
        assert loader.get_session(context, 'server') is None
    start.assert_not_awaited()
    assert loader.get_session(context, 'server') is base


@pytest.mark.asyncio
async def test_switch_recovers_stdio_when_previous_backend_never_loaded_tools(monkeypatch):
    context = ExecutionContext(instance_uuid='instance', workspace_uuid='workspace', placement_generation=1)
    ap = SimpleNamespace(
        logger=Mock(),
        instance_config=SimpleNamespace(data={}),
        box_service=SimpleNamespace(enabled=True, backend_supports_managed_processes=AsyncMock(return_value=True)),
    )
    loader = MCPLoader(ap)
    base = RuntimeMCPSession('server', {'uuid': 'id', 'mode': 'stdio'}, True, ap, context)
    base.sandbox_backend = 'e2b'
    loader._register_session(context, 'server', base)

    async def start(self):
        self.functions = [SimpleNamespace(name='expected_tool')]

    monkeypatch.setattr(RuntimeMCPSession, 'start', start)
    monkeypatch.setattr(RuntimeMCPSession, 'shutdown', AsyncMock())
    async with loader.task_sandbox_scope(context, 'docker', tool_names=['expected_tool']):
        selected = loader.get_session(context, 'server')
        assert selected is not base
        assert selected.sandbox_backend == 'docker'
        assert selected.get_tools()[0].name == 'expected_tool'


@pytest.mark.asyncio
async def test_e2b_credentials_and_template_are_pinned_per_task(monkeypatch):
    context = ExecutionContext(
        instance_uuid='instance', workspace_uuid='workspace', placement_generation=1, query_uuid='task'
    )
    ap = SimpleNamespace(
        logger=Mock(),
        instance_config=SimpleNamespace(data={}),
        box_service=SimpleNamespace(enabled=True, backend_supports_managed_processes=AsyncMock(return_value=True)),
    )
    loader = MCPLoader(ap)
    old = {'revision': 'old', 'config': {'template': 'old-template', 'api_key': 'old-key'}}
    new = {'revision': 'new', 'config': {'template': 'new-template', 'api_key': 'new-key'}}
    base = RuntimeMCPSession(
        'server',
        {'uuid': 'id', 'mode': 'stdio', '_sandbox_backend': 'e2b', '_sandbox_limits': {}, '_sandbox_e2b_config': old},
        True,
        ap,
        context,
    )
    loader._register_session(context, 'server', base)
    monkeypatch.setattr(RuntimeMCPSession, 'start', AsyncMock())
    monkeypatch.setattr(RuntimeMCPSession, 'shutdown', AsyncMock())
    async with loader.task_sandbox_scope(context, 'e2b', limits_selection={}, e2b_selection=new):
        selected = loader.get_session(context, 'server')
        assert selected is not base
        handle = selected._box_stdio_runtime._build_workspace()
        assert handle.selected_e2b_config == new
        assert selected._build_box_session_id() != base._build_box_session_id()
        assert base.sandbox_e2b_config == old
    async with loader.task_sandbox_scope(context, 'e2b', limits_selection={}, e2b_selection=old):
        assert loader.get_session(context, 'server') is base


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['_sandbox_backend', '_sandbox_e2b_config', '_sandbox_limits', '_sandbox_task_id'])
async def test_public_mcp_config_cannot_override_host_sandbox_selection(field):
    context = ExecutionContext(instance_uuid='instance', workspace_uuid='workspace', placement_generation=1)
    ap = SimpleNamespace(logger=Mock(), instance_config=SimpleNamespace(data={}))
    loader = MCPLoader(ap)
    loader._assert_execution_active = AsyncMock(return_value=context)
    config = {'name': 'untrusted', 'mode': 'stdio', 'enable': True, 'extra_args': {field: 'host'}}
    with pytest.raises(ValueError, match='reserved for the Host'):
        await loader.load_mcp_server(context, config)
    config['extra_args'] = {'command': 'python3', 'args': ['-V']}
    session = await loader.load_mcp_server(context, config)
    assert session.sandbox_backend is None
    assert session.sandbox_e2b_config is None and session.sandbox_limits is None
