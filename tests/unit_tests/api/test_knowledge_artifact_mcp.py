"""Knowledge Artifact MCP entrypoint preserves the application authorization boundary."""

import asyncio
import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from langbot.pkg.api.application.contracts import ApplicationAPIError, ApplicationAPIException
from langbot.pkg.api.authz import Permission
from langbot.pkg.api.mcp import server as mcp_server


@pytest.mark.asyncio
async def test_knowledge_artifact_mcp_routes_only_reference_and_trusted_context(monkeypatch):
    context = SimpleNamespace(workspace_uuid='workspace-1')
    authorized = []

    def authorize(permission):
        authorized.append(permission)
        return context

    monkeypatch.setattr(mcp_server, '_authorized', authorize)
    app = SimpleNamespace(application_api=SimpleNamespace(execute=AsyncMock(return_value=42)))
    app.persistence_mgr = SimpleNamespace(tenant_scope=lambda workspace_uuid: nullcontext())
    monkeypatch.setattr(mcp_server, 'get_request_context', lambda: SimpleNamespace(workspace_uuid='workspace-1'))
    monkeypatch.setattr(mcp_server, 'get_workspace_language', AsyncMock(return_value='en_US'))
    server = mcp_server.LangBotMCPServer(app)
    result = await server.mcp.call_tool(
        'add_knowledge_file_artifact', {'kb_uuid': 'kb-one', 'artifact_id': 'art_example'}
    )
    content = result.content if hasattr(result, 'content') else result[0]
    assert json.loads(content[0].text) == 42
    assert authorized == [Permission.RESOURCE_MANAGE]
    app.application_api.execute.assert_awaited_once_with(
        'knowledge.file.store_artifact',
        context,
        {'kb_uuid': 'kb-one', 'artifact_id': 'art_example', 'parser_plugin_id': None},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('cancelled', [False, True])
async def test_knowledge_artifact_mcp_preserves_errors_and_cancellation(monkeypatch, cancelled):
    monkeypatch.setattr(mcp_server, '_authorized', lambda permission: object())
    error = (
        asyncio.CancelledError()
        if cancelled
        else ApplicationAPIException(ApplicationAPIError('not_found', 'Resource not found', 404))
    )
    app = SimpleNamespace(application_api=SimpleNamespace(execute=AsyncMock(side_effect=error)))
    app.persistence_mgr = SimpleNamespace(tenant_scope=lambda workspace_uuid: nullcontext())
    monkeypatch.setattr(mcp_server, 'get_request_context', lambda: SimpleNamespace(workspace_uuid='workspace-1'))
    monkeypatch.setattr(mcp_server, 'get_workspace_language', AsyncMock(return_value='en_US'))
    server = mcp_server.LangBotMCPServer(app)
    with pytest.raises(
        asyncio.CancelledError if cancelled else ToolError, match=None if cancelled else 'Resource not found'
    ):
        await server.mcp.call_tool('add_knowledge_file_artifact', {'kb_uuid': 'kb-one', 'artifact_id': 'art_example'})
