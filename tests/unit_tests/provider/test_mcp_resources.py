from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from mcp import types as mcp_types

from langbot.pkg.agent.runner.execution_context import project_mcp_resource_config
from langbot.pkg.provider.tools.errors import ToolExecutionDeniedError
from langbot.pkg.provider.tools.loaders.mcp import (
    MCP_RESOURCE_CONTEXT_QUERY_KEY,
    MCP_RESOURCE_TRACE_QUERY_KEY,
    MCP_READ_RESOURCE_SCHEMA,
    MCP_TOOL_LIST_RESOURCES,
    MCP_TOOL_READ_RESOURCE,
    MCPLoader,
    MCPSessionStatus,
    RuntimeMCPSession,
)
from langbot.pkg.telemetry import features as telemetry_features


def _app() -> SimpleNamespace:
    return SimpleNamespace(logger=Mock())


def _connected_session(
    *,
    name: str = 'docs',
    uuid: str = 'srv-1',
    resources: list[dict] | None = None,
    templates: list[dict] | None = None,
) -> RuntimeMCPSession:
    session = RuntimeMCPSession(name, {'uuid': uuid, 'mode': 'remote'}, True, _app())
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


def _query() -> SimpleNamespace:
    return SimpleNamespace(variables={})


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request('POST', 'https://example.com/mcp')
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f'HTTP {status_code}', request=request, response=response)


@pytest.mark.asyncio
async def test_remote_transport_falls_back_to_sse_for_compatible_http_status_in_exception_group():
    session = RuntimeMCPSession(
        'remote',
        {'uuid': 'srv-1', 'mode': 'remote', 'url': 'https://example.com/mcp'},
        True,
        _app(),
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
    loader.sessions = {'docs': session}

    with_resource_tools = await loader.get_tools(['srv-1'], include_resource_tools=True)
    without_resource_tools = await loader.get_tools(['srv-1'], include_resource_tools=False)

    assert {tool.name for tool in with_resource_tools} == {
        MCP_TOOL_LIST_RESOURCES,
        MCP_TOOL_READ_RESOURCE,
    }
    assert without_resource_tools == []


@pytest.mark.asyncio
async def test_mcp_loader_get_tool_returns_synthetic_resource_schema():
    loader = MCPLoader(_app())
    loader.sessions = {'docs': _connected_session()}

    tool = await loader.get_tool(MCP_TOOL_READ_RESOURCE)

    assert tool is not None
    assert tool.name == MCP_TOOL_READ_RESOURCE
    assert tool.parameters == MCP_READ_RESOURCE_SCHEMA


@pytest.mark.asyncio
@pytest.mark.parametrize('read_enabled', [False, 0, None, 'false'])
@pytest.mark.parametrize(
    ('tool_name', 'parameters'),
    [
        (MCP_TOOL_LIST_RESOURCES, {'server_name': 'docs'}),
        (MCP_TOOL_READ_RESOURCE, {'server_name': 'docs', 'uri': 'file:///README.md'}),
    ],
)
async def test_mcp_loader_refuses_resource_tool_calls_when_agent_read_disabled(
    read_enabled,
    tool_name,
    parameters,
):
    loader = MCPLoader(_app())
    session = _connected_session()
    loader.sessions = {'docs': session}
    query = SimpleNamespace(variables={'_pipeline_bound_mcp_servers': ['srv-1']})
    project_mcp_resource_config(
        query,
        {'mcp-resource-agent-read-enabled': read_enabled},
    )

    with pytest.raises(ToolExecutionDeniedError, match='MCP resource agent reads are disabled'):
        await loader.invoke_tool(tool_name, parameters, query)

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
    loader.sessions = {'docs': docs, 'other': other}
    query = SimpleNamespace(
        variables={
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('enabled_config', 'expected_enabled'),
    [
        pytest.param({}, True, id='missing'),
        pytest.param({'enabled': True}, True, id='true'),
        pytest.param({'enabled': False}, False, id='false'),
        pytest.param({'enabled': 0}, False, id='zero'),
        pytest.param({'enabled': None}, False, id='none'),
        pytest.param({'enabled': 'false'}, False, id='string-false'),
    ],
)
async def test_build_resource_context_attachment_enabled_fails_closed(enabled_config, expected_enabled):
    loader = MCPLoader(_app())
    session = _connected_session(name='docs', uuid='srv-1')
    session.session.read_resource.return_value = mcp_types.ReadResourceResult(
        contents=[
            mcp_types.TextResourceContents(
                uri='file:///README.md',
                mimeType='text/markdown',
                text='enabled attachment',
            )
        ]
    )
    loader.sessions = {'docs': session}
    attachment = {
        'server_uuid': 'srv-1',
        'server_name': 'docs',
        'uri': 'file:///README.md',
        'mode': 'pinned',
        **enabled_config,
    }
    query = SimpleNamespace(
        variables={
            '_pipeline_bound_mcp_servers': ['srv-1'],
            '_pipeline_mcp_resource_attachments': [attachment],
        }
    )

    context = await loader.build_resource_context_for_query(query)

    if expected_enabled:
        assert 'enabled attachment' in context
        session.session.read_resource.assert_awaited_once()
    else:
        assert context == ''
        session.session.read_resource.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('field_name', 'invalid_value'),
    [
        pytest.param('max_tokens', '100', id='string-tokens'),
        pytest.param('max_tokens', 0, id='zero-tokens'),
        pytest.param('max_tokens', -1, id='negative-tokens'),
        pytest.param('max_tokens', True, id='boolean-tokens'),
        pytest.param('max_bytes', '4096', id='string-bytes'),
        pytest.param('max_bytes', 0, id='zero-bytes'),
        pytest.param('max_bytes', -1, id='negative-bytes'),
        pytest.param('max_bytes', True, id='boolean-bytes'),
    ],
)
async def test_build_resource_context_invalid_attachment_limits_fail_closed(field_name, invalid_value):
    ap = _app()
    loader = MCPLoader(ap)
    session = _connected_session(name='docs', uuid='srv-1')
    loader.sessions = {'docs': session}
    query = SimpleNamespace(
        variables={
            '_pipeline_bound_mcp_servers': ['srv-1'],
            '_pipeline_mcp_resource_attachments': [
                {
                    'server_uuid': 'srv-1',
                    'server_name': 'docs',
                    'uri': 'file:///README.md',
                    'mode': 'pinned',
                    field_name: invalid_value,
                }
            ],
        }
    )

    context = await loader.build_resource_context_for_query(query)

    assert context == ''
    session.session.read_resource.assert_not_awaited()
    ap.logger.warning.assert_called_once()
