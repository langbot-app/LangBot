from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from mcp import types as mcp_types

from langbot.pkg.provider.tools.loaders.mcp import (
    MCP_RESOURCE_CONTEXT_QUERY_KEY,
    MCP_RESOURCE_TRACE_QUERY_KEY,
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
async def test_mcp_loader_refuses_resource_tool_calls_when_agent_read_disabled():
    loader = MCPLoader(_app())
    session = _connected_session()
    loader.sessions = {'docs': session}
    query = SimpleNamespace(
        variables={
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
