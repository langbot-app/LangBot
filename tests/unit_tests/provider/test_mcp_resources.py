from __future__ import annotations

import asyncio
import base64
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from mcp import types as mcp_types
from mcp.shared.exceptions import McpError

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.provider.tools.loaders.mcp import (
    MCP_RESOURCE_CONTEXT_QUERY_KEY,
    MCP_RESOURCE_TRACE_QUERY_KEY,
    MCP_TOOL_CALL_TIMEOUT_DEFAULT_SECONDS,
    MCP_TOOL_LIST_RESOURCES,
    MCP_TOOL_READ_RESOURCE,
    MCPLoader,
    MCPSessionStatus,
    MCPToolCallTimeoutError,
    RuntimeMCPSession,
)
from langbot.pkg.telemetry import features as telemetry_features
from langbot.pkg.workspace.errors import WorkspaceGenerationMismatchError


TEST_EXECUTION_CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=1,
    query_uuid='query-a',
)


def _app() -> SimpleNamespace:
    return SimpleNamespace(
        logger=Mock(),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(
                return_value=SimpleNamespace(
                    instance_uuid='instance-a',
                    workspace_uuid='workspace-a',
                    placement_generation=1,
                )
            )
        ),
    )


def _connected_session(
    *,
    name: str = 'docs',
    uuid: str = 'srv-1',
    resources: list[dict] | None = None,
    templates: list[dict] | None = None,
    execution_context: ExecutionContext = TEST_EXECUTION_CONTEXT,
) -> RuntimeMCPSession:
    session = RuntimeMCPSession(
        name,
        {'uuid': uuid, 'mode': 'remote'},
        True,
        _app(),
        execution_context,
    )
    session.status = MCPSessionStatus.CONNECTED
    session.session = SimpleNamespace(read_resource=AsyncMock())
    session.resources = resources or [
        {
            'uri': 'file:///README.md',
            'name': 'README.md',
            'title': '',
            'description': '',
            'mime_type': 'text/markdown',
            'size': None,
            'icons': [],
            'annotations': {},
            '_meta': {},
        }
    ]
    session.resource_templates = templates or []
    return session


def _query(variables: dict | None = None, context: ExecutionContext = TEST_EXECUTION_CONTEXT) -> SimpleNamespace:
    return SimpleNamespace(
        instance_uuid=context.instance_uuid,
        workspace_uuid=context.workspace_uuid,
        placement_generation=context.placement_generation,
        bot_uuid=context.bot_uuid,
        pipeline_uuid=context.pipeline_uuid,
        query_uuid=context.query_uuid,
        variables=variables or {},
    )


def _register_session(loader: MCPLoader, session: RuntimeMCPSession) -> None:
    loader._register_session(
        session.execution_context,
        session.server_name,
        session,
    )


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request('POST', 'https://example.com/mcp')
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f'HTTP {status_code}', request=request, response=response)


def _tool_result(text: str = 'ok') -> mcp_types.CallToolResult:
    return mcp_types.CallToolResult(
        content=[mcp_types.TextContent(type='text', text=text)],
        isError=False,
    )


@pytest.mark.asyncio
async def test_invoke_mcp_tool_uses_configurable_request_timeout():
    session = RuntimeMCPSession(
        'slow-tools',
        {
            'uuid': 'srv-1',
            'mode': 'remote',
            'tool_call_timeout_sec': 900,
        },
        True,
        _app(),
        TEST_EXECUTION_CONTEXT,
    )
    session.session = SimpleNamespace(call_tool=AsyncMock(return_value=_tool_result()))

    result = await session.invoke_mcp_tool('render_video', {'quality': 'high'})

    assert result[0].text == 'ok'
    session.session.call_tool.assert_awaited_once_with(
        'render_video',
        {'quality': 'high'},
        read_timeout_seconds=timedelta(seconds=900),
    )


@pytest.mark.asyncio
async def test_invoke_mcp_tool_zero_timeout_disables_request_deadline():
    session = RuntimeMCPSession(
        'unbounded-tools',
        {
            'uuid': 'srv-1',
            'mode': 'remote',
            'tool_call_timeout_sec': 0,
        },
        True,
        _app(),
        TEST_EXECUTION_CONTEXT,
    )
    session.session = SimpleNamespace(call_tool=AsyncMock(return_value=_tool_result()))

    await session.invoke_mcp_tool('long_job', {})

    session.session.call_tool.assert_awaited_once_with(
        'long_job',
        {},
        read_timeout_seconds=None,
    )


@pytest.mark.asyncio
async def test_invoke_mcp_tool_timeout_is_not_retried_and_session_remains_usable():
    session = RuntimeMCPSession(
        'recoverable-tools',
        {
            'uuid': 'srv-1',
            'mode': 'remote',
            'tool_call_timeout_sec': 5,
        },
        True,
        _app(),
        TEST_EXECUTION_CONTEXT,
    )
    timeout = McpError(
        mcp_types.ErrorData(
            code=httpx.codes.REQUEST_TIMEOUT,
            message='Timed out while waiting for response to ClientRequest. Waited 5 seconds.',
        )
    )
    call_tool = AsyncMock(side_effect=[timeout, _tool_result('recovered')])
    session.session = SimpleNamespace(call_tool=call_tool)

    with pytest.raises(
        MCPToolCallTimeoutError,
        match="MCP tool 'long_job' on server 'recoverable-tools' timed out after 5 seconds",
    ):
        await session.invoke_mcp_tool('long_job', {})

    assert call_tool.await_count == 1
    second_result = await session.invoke_mcp_tool('health_check', {})
    assert second_result[0].text == 'recovered'
    assert call_tool.await_count == 2


@pytest.mark.parametrize('invalid_timeout', [-1, float('inf'), 1e300, True, 'not-a-number'])
def test_invalid_tool_call_timeout_falls_back_to_default(invalid_timeout):
    ap = _app()
    session = RuntimeMCPSession(
        'invalid-timeout',
        {
            'uuid': 'srv-1',
            'mode': 'remote',
            'tool_call_timeout_sec': invalid_timeout,
        },
        True,
        ap,
        TEST_EXECUTION_CONTEXT,
    )

    assert session.tool_call_timeout_sec == MCP_TOOL_CALL_TIMEOUT_DEFAULT_SECONDS
    ap.logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_remote_transport_falls_back_to_sse_for_compatible_http_status_in_exception_group():
    session = RuntimeMCPSession(
        'remote',
        {'uuid': 'srv-1', 'mode': 'remote', 'url': 'https://example.com/mcp'},
        True,
        _app(),
        TEST_EXECUTION_CONTEXT,
    )
    session._init_streamable_http_server = AsyncMock(
        side_effect=ExceptionGroup('transport failed', [_http_status_error(405)])
    )
    session._init_sse_server = AsyncMock()

    await session._init_remote_server()

    session._init_streamable_http_server.assert_awaited_once()
    session._init_sse_server.assert_awaited_once()


@pytest.mark.asyncio
async def test_remote_transport_does_not_fallback_for_auth_http_status():
    session = RuntimeMCPSession(
        'remote',
        {'uuid': 'srv-1', 'mode': 'remote', 'url': 'https://example.com/mcp'},
        True,
        _app(),
        TEST_EXECUTION_CONTEXT,
    )
    error = _http_status_error(403)
    session._init_streamable_http_server = AsyncMock(side_effect=error)
    session._init_sse_server = AsyncMock()

    with pytest.raises(httpx.HTTPStatusError):
        await session._init_remote_server()

    session._init_streamable_http_server.assert_awaited_once()
    session._init_sse_server.assert_not_awaited()


@pytest.mark.asyncio
async def test_read_resource_envelope_truncates_caches_and_records_trace():
    session = _connected_session()
    session.session.read_resource.return_value = mcp_types.ReadResourceResult(
        contents=[
            mcp_types.TextResourceContents(
                uri='file:///README.md',
                mimeType='text/markdown',
                text='abcdef',
            )
        ]
    )
    query = _query()

    first = await session.read_resource_envelope(
        'file:///README.md',
        max_bytes=4,
        source='ui_preview',
        query=query,
    )
    second = await session.read_resource_envelope(
        'file:///README.md',
        max_bytes=4,
        source='agent_tool',
        query=query,
    )

    assert first['contents'][0]['text'] == 'abcd'
    assert first['contents'][0]['bytes'] == 6
    assert first['truncated'] is True
    assert first['cache_hit'] is False
    assert second['cache_hit'] is True
    assert second['source'] == 'agent_tool'
    assert session.session.read_resource.await_count == 1

    traces = query.variables[MCP_RESOURCE_TRACE_QUERY_KEY]
    assert [trace['source'] for trace in traces] == ['ui_preview', 'agent_tool']
    assert traces[1]['cache_hit'] is True
    assert query.variables[telemetry_features.FEATURES_KEY]['mcp_resource_reads'] == {
        'ui_preview': 1,
        'agent_tool': 1,
    }


@pytest.mark.asyncio
async def test_read_resource_envelope_shares_byte_budget_across_text_contents():
    session = _connected_session()
    session.session.read_resource.return_value = mcp_types.ReadResourceResult(
        contents=[
            mcp_types.TextResourceContents(
                uri='file:///README.md#first',
                mimeType='text/plain',
                text='abc',
            ),
            mcp_types.TextResourceContents(
                uri='file:///README.md#second',
                mimeType='text/plain',
                text='def',
            ),
        ]
    )

    envelope = await session.read_resource_envelope('file:///README.md', max_bytes=4)

    assert [item['text'] for item in envelope['contents']] == ['abc', 'd']
    assert envelope['contents'][0]['truncated'] is False
    assert envelope['contents'][1]['truncated'] is True
    assert envelope['bytes'] == 6
    assert envelope['truncated'] is True


@pytest.mark.asyncio
async def test_read_resource_envelope_omits_binary_by_default():
    session = _connected_session(
        resources=[
            {
                'uri': 'file:///image.png',
                'name': 'image.png',
                'title': '',
                'description': '',
                'mime_type': 'image/png',
                'size': 4,
                'icons': [],
                'annotations': {},
                '_meta': {},
            }
        ]
    )
    session.session.read_resource.return_value = mcp_types.ReadResourceResult(
        contents=[
            mcp_types.BlobResourceContents(
                uri='file:///image.png',
                mimeType='image/png',
                blob=base64.b64encode(b'\x00\x01\x02\x03').decode(),
            )
        ]
    )

    envelope = await session.read_resource_envelope('file:///image.png')

    content = envelope['contents'][0]
    assert content['type'] == 'blob'
    assert content['blob'] is None
    assert content['bytes'] == 4
    assert content['binary_omitted'] is True
    assert envelope['truncated'] is True
    assert envelope['warnings'] == ['Binary resource content omitted from response.']


@pytest.mark.asyncio
async def test_read_resource_envelope_rejects_unlisted_uri():
    session = _connected_session()

    with pytest.raises(ValueError, match='Resource URI is not available'):
        await session.read_resource_envelope('file:///secret.txt')

    session.session.read_resource.assert_not_called()


def test_resource_uri_allowed_supports_listed_templates_conservatively():
    session = _connected_session(
        resources=[],
        templates=[
            {
                'uri_template': 'repo://{owner}/{repo}/file/{path}',
                'name': 'repository file',
                'title': '',
                'description': '',
                'mime_type': 'text/plain',
                'icons': [],
                'annotations': {},
                '_meta': {},
            }
        ],
    )

    assert session.resource_uri_allowed('repo://langbot-app/LangBot/file/src/main.py') is True
    assert session.resource_uri_allowed('repo://langbot-app/LangBot/issues/1') is False
    assert session.resource_uri_allowed('https://example.com/secret') is False


@pytest.mark.asyncio
async def test_mcp_loader_can_hide_synthetic_resource_tools():
    loader = MCPLoader(_app())
    session = _connected_session()
    _register_session(loader, session)

    with_resource_tools = await loader.get_tools(
        TEST_EXECUTION_CONTEXT,
        ['srv-1'],
        include_resource_tools=True,
    )
    without_resource_tools = await loader.get_tools(
        TEST_EXECUTION_CONTEXT,
        ['srv-1'],
        include_resource_tools=False,
    )

    assert {tool.name for tool in with_resource_tools} == {
        MCP_TOOL_LIST_RESOURCES,
        MCP_TOOL_READ_RESOURCE,
    }
    assert without_resource_tools == []


@pytest.mark.asyncio
async def test_mcp_loader_refuses_resource_tool_calls_when_agent_read_disabled():
    loader = MCPLoader(_app())
    session = _connected_session()
    _register_session(loader, session)
    query = _query(
        {
            '_pipeline_bound_mcp_servers': ['srv-1'],
            '_pipeline_mcp_resource_agent_read_enabled': False,
        }
    )

    result = await loader.invoke_tool(
        MCP_TOOL_READ_RESOURCE,
        {'server_name': 'docs', 'uri': 'file:///README.md'},
        query,
    )

    assert result[0].text == 'Error: MCP resource agent reads are disabled.'
    session.session.read_resource.assert_not_called()


@pytest.mark.asyncio
async def test_build_resource_context_for_query_uses_only_bound_attached_text_resources():
    loader = MCPLoader(_app())
    docs = _connected_session(name='docs', uuid='srv-1')
    docs.session.read_resource.return_value = mcp_types.ReadResourceResult(
        contents=[
            mcp_types.TextResourceContents(
                uri='file:///README.md',
                mimeType='text/markdown',
                text='LangBot MCP resource context',
            )
        ]
    )
    other = _connected_session(name='other', uuid='srv-2')
    other.session.read_resource.return_value = mcp_types.ReadResourceResult(
        contents=[
            mcp_types.TextResourceContents(
                uri='file:///README.md',
                mimeType='text/markdown',
                text='must not be injected',
            )
        ]
    )
    _register_session(loader, docs)
    _register_session(loader, other)
    query = _query(
        {
            '_pipeline_bound_mcp_servers': ['srv-1'],
            '_pipeline_mcp_resource_attachments': [
                {'server_uuid': 'srv-1', 'server_name': 'docs', 'uri': 'file:///README.md', 'mode': 'pinned'},
                {'server_uuid': 'srv-2', 'server_name': 'other', 'uri': 'file:///README.md', 'mode': 'pinned'},
            ],
        }
    )

    context = await loader.build_resource_context_for_query(query)

    assert '<mcp_resource ' in context
    assert 'server="docs"' in context
    assert 'LangBot MCP resource context' in context
    assert 'must not be injected' not in context
    assert query.variables[MCP_RESOURCE_CONTEXT_QUERY_KEY]['resource_count'] == 1
    docs.session.read_resource.assert_awaited_once()
    other.session.read_resource.assert_not_called()


def test_mcp_loader_session_keys_do_not_collide_between_workspaces():
    loader = MCPLoader(_app())
    workspace_b = ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-b',
        placement_generation=1,
        query_uuid='query-b',
    )
    session_a = _connected_session(name='docs', uuid='srv-a')
    session_b = _connected_session(
        name='docs',
        uuid='srv-b',
        execution_context=workspace_b,
    )
    _register_session(loader, session_a)
    _register_session(loader, session_b)

    assert len(loader.sessions) == 2
    assert loader.get_session(TEST_EXECUTION_CONTEXT, 'docs') is session_a
    assert loader.get_session(workspace_b, 'docs') is session_b
    assert loader.get_session(TEST_EXECUTION_CONTEXT, 'docs') is not loader.get_session(workspace_b, 'docs')


@pytest.mark.asyncio
async def test_mcp_tool_result_is_discarded_when_generation_changes_during_call():
    session = _connected_session()
    binding = SimpleNamespace(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=1,
    )
    session.ap.workspace_service.get_execution_binding.side_effect = [
        binding,
        binding,
        WorkspaceGenerationMismatchError('generation changed during tool call'),
    ]
    session.session = SimpleNamespace(call_tool=AsyncMock(return_value=SimpleNamespace(isError=False, content=[])))

    with pytest.raises(WorkspaceGenerationMismatchError):
        await session.invoke_mcp_tool('side_effecting_tool', {})

    session.session.call_tool.assert_awaited_once_with(
        'side_effecting_tool',
        {},
        read_timeout_seconds=timedelta(seconds=MCP_TOOL_CALL_TIMEOUT_DEFAULT_SECONDS),
    )


@pytest.mark.asyncio
async def test_mcp_resource_cache_is_not_served_to_stale_generation():
    session = _connected_session()
    session._resource_cache[('file:///README.md', 10, None, False)] = {
        'cached_at': 0,
        'envelope': {'contents': [{'type': 'text', 'text': 'stale'}]},
    }
    session.ap.workspace_service.get_execution_binding.side_effect = WorkspaceGenerationMismatchError(
        'stale generation'
    )

    with pytest.raises(WorkspaceGenerationMismatchError):
        await session.read_resource_envelope('file:///README.md', max_bytes=10)

    session.session.read_resource.assert_not_awaited()


@pytest.mark.asyncio
async def test_directory_projection_retires_idle_mcp_scope_without_db_poll():
    loader = MCPLoader(_app())
    sessions = []
    for index in range(100):
        context = ExecutionContext(
            instance_uuid='instance-a',
            workspace_uuid=f'workspace-{index}',
            placement_generation=1,
        )
        session = RuntimeMCPSession(
            f'server-{index}',
            {'uuid': f'srv-{index}', 'mode': 'remote'},
            True,
            loader.ap,
            context,
        )
        session.shutdown = AsyncMock()
        loader._register_session(context, session.server_name, session)
        sessions.append(session)

    loader.reconcile_execution_projection('instance-a', {})
    reconcile_task = loader._projection_reconcile_task
    assert reconcile_task is not None
    assert len(loader._pending_projection_retirements) == 100

    # A second projection coalesces into the same worker instead of creating
    # one timer or task per Workspace.
    loader.reconcile_execution_projection('instance-a', {})
    assert loader._projection_reconcile_task is reconcile_task

    await asyncio.wait_for(reconcile_task, timeout=1)

    assert loader.sessions == {}
    assert loader._scope_generations == {}
    assert loader._pending_projection_retirements == set()
    assert sum(session.shutdown.await_count for session in sessions) == 100
    loader.ap.workspace_service.get_execution_binding.assert_not_awaited()


@pytest.mark.asyncio
async def test_directory_projection_keeps_matching_and_unaffected_mcp_scopes():
    loader = MCPLoader(_app())
    matching = _connected_session()
    other_context = ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-b',
        placement_generation=1,
    )
    unaffected = _connected_session(
        name='other',
        uuid='srv-2',
        execution_context=other_context,
    )
    _register_session(loader, matching)
    _register_session(loader, unaffected)

    loader.reconcile_execution_projection(
        'instance-a',
        {'workspace-a': 1},
        affected_workspace_uuids={'workspace-a'},
    )
    await asyncio.sleep(0)

    assert loader.get_session(TEST_EXECUTION_CONTEXT, 'docs') is matching
    assert loader.get_session(other_context, 'other') is unaffected
    assert loader._projection_reconcile_task is None


@pytest.mark.asyncio
async def test_mcp_loader_shutdown_cancels_startup_tasks_and_closes_sessions_concurrently():
    loader = MCPLoader(_app())
    hosted_cancelled = asyncio.Event()

    async def pending_host():
        try:
            await asyncio.Event().wait()
        finally:
            hosted_cancelled.set()

    hosted_task = asyncio.create_task(pending_host())
    await asyncio.sleep(0)
    loader._hosted_mcp_tasks = [hosted_task]

    started: set[str] = set()
    all_started = asyncio.Event()

    class Session:
        def __init__(self, name: str):
            self.name = name
            self.server_name = name

        async def shutdown(self):
            started.add(self.name)
            if len(started) == 2:
                all_started.set()
            await all_started.wait()

    loader.sessions = {'one': Session('one'), 'two': Session('two')}

    await asyncio.wait_for(loader.shutdown(), timeout=1)

    assert hosted_cancelled.is_set()
    assert hosted_task.cancelled()
    assert started == {'one', 'two'}
    assert loader._hosted_mcp_tasks == []
    assert loader.sessions == {}


@pytest.mark.asyncio
async def test_completed_mcp_host_tasks_do_not_accumulate():
    loader = MCPLoader(_app())
    task = asyncio.create_task(asyncio.sleep(0))

    loader.track_hosted_task(task, TEST_EXECUTION_CONTEXT)
    await task
    await asyncio.sleep(0)

    assert loader._hosted_mcp_tasks == []
    assert loader._hosted_mcp_tasks_by_scope == {}
    assert loader._scope_generations == {}


@pytest.mark.asyncio
async def test_generation_advance_cancels_host_tasks_and_closes_old_sessions():
    loader = MCPLoader(_app())
    old_session = SimpleNamespace(
        server_name='old',
        shutdown=AsyncMock(),
    )
    loader._register_session(
        TEST_EXECUTION_CONTEXT,
        old_session.server_name,
        old_session,
    )

    async def pending_host():
        await asyncio.Event().wait()

    hosted_task = asyncio.create_task(pending_host())
    loader.track_hosted_task(hosted_task, TEST_EXECUTION_CONTEXT)
    await asyncio.sleep(0)
    next_context = ExecutionContext(
        instance_uuid=TEST_EXECUTION_CONTEXT.instance_uuid,
        workspace_uuid=TEST_EXECUTION_CONTEXT.workspace_uuid,
        placement_generation=2,
    )
    loader.ap.workspace_service.get_execution_binding = AsyncMock(
        return_value=SimpleNamespace(
            instance_uuid=next_context.instance_uuid,
            workspace_uuid=next_context.workspace_uuid,
            placement_generation=next_context.placement_generation,
        )
    )

    await loader._assert_execution_active(next_context)

    assert hosted_task.cancelled()
    old_session.shutdown.assert_awaited_once_with()
    assert loader.sessions == {}
    assert loader._session_keys_by_scope == {}
    assert loader._hosted_mcp_tasks_by_scope == {}
    assert loader._scope_generations == {}


def test_session_lookup_uses_scope_index_without_global_iteration():
    class NoGlobalIterationDict(dict):
        def __iter__(self):
            raise AssertionError('MCP lookup scanned every tenant session')

        def items(self):
            raise AssertionError('MCP lookup scanned every tenant session')

        def values(self):
            raise AssertionError('MCP lookup scanned every tenant session')

    loader = MCPLoader(_app())
    target_context = None
    target_session = None
    for index in range(1_000):
        context = ExecutionContext(
            instance_uuid='instance-a',
            workspace_uuid=f'workspace-{index}',
            placement_generation=1,
        )
        session = SimpleNamespace(server_name=f'server-{index}')
        loader._register_session(context, session.server_name, session)
        if index == 777:
            target_context = context
            target_session = session
    loader._sessions = NoGlobalIterationDict(loader._sessions)

    assert loader._sessions_for_context(target_context) == [target_session]


@pytest.mark.asyncio
async def test_mcp_startup_concurrency_is_instance_bounded():
    app = _app()
    app.instance_config = SimpleNamespace(data={'mcp': {'lifecycle_concurrency': 2}})
    loader = MCPLoader(app)
    active = 0
    maximum_active = 0
    release = asyncio.Event()

    async def fake_host(_context, _config):
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        if maximum_active == 2:
            release.set()
        await release.wait()
        await asyncio.sleep(0)
        active -= 1

    loader._host_mcp_server = fake_host

    await asyncio.gather(
        *(
            loader.host_mcp_server(
                TEST_EXECUTION_CONTEXT,
                {'name': f'server-{index}'},
            )
            for index in range(20)
        )
    )

    assert loader._lifecycle_concurrency == 2
    assert maximum_active == 2


@pytest.mark.asyncio
async def test_mcp_startup_dispatcher_does_not_create_every_server_task_at_once():
    app = _app()
    app.instance_config = SimpleNamespace(data={'mcp': {'lifecycle_concurrency': 2}})
    loader = MCPLoader(app)
    started = 0
    first_batch_started = asyncio.Event()
    release = asyncio.Event()

    async def fake_host(_context, _config):
        nonlocal started
        started += 1
        if started == 2:
            first_batch_started.set()
        await release.wait()

    loader.host_mcp_server = fake_host
    configs = [(TEST_EXECUTION_CONTEXT, {'name': f'server-{index}'}) for index in range(20)]

    dispatch_task = asyncio.create_task(loader._host_server_configs_bounded(configs))
    await asyncio.wait_for(first_batch_started.wait(), timeout=1)

    assert started == 2
    assert len(loader._hosted_mcp_tasks) == 2

    release.set()
    await dispatch_task
    await asyncio.sleep(0)

    assert started == 20
    assert loader._hosted_mcp_tasks == []
    assert loader._hosted_mcp_tasks_by_scope == {}


def test_invalid_mcp_lifecycle_concurrency_uses_safe_default():
    app = _app()
    app.instance_config = SimpleNamespace(data={'mcp': {'lifecycle_concurrency': True}})

    assert MCPLoader(app)._lifecycle_concurrency == 16
