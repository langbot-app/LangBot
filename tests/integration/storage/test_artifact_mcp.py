"""Exercise registered MCP tools against real Artifact services and persistence."""
# ruff: noqa: F811

from __future__ import annotations

import base64
from dataclasses import replace
import hashlib
import json
import uuid

from mcp.server.fastmcp.exceptions import ToolError
import pytest

from langbot.pkg.api.context import PrincipalContext, PrincipalType
from langbot.pkg.api.mcp.context import bind_request_context, reset_request_context
from langbot.pkg.api.mcp.server import LangBotMCPServer
from langbot.pkg.storage.artifacts import MAX_ARTIFACT_BYTES
from tests.integration.storage.test_artifacts import (
    artifact_replicas,  # noqa: F401 -- real authenticated service fixture
    persistence_case,  # noqa: F401 -- fixture dependency of replicas
    replicas,  # noqa: F401 -- fixture dependency of artifact_replicas
)


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_BODY = b'MCP Artifact exact bytes\x00\xff\n'


async def _call(server, context, tool, **arguments):
    token = bind_request_context(context)
    try:
        result = await server.mcp.call_tool(tool, arguments)
        content = result.content if hasattr(result, 'content') else result[0]
    finally:
        reset_request_context(token)
    assert len(content) == 1 and content[0].type == 'text'
    return json.loads(content[0].text)


async def test_mcp_artifact_lifecycle_and_exact_download(artifact_replicas):
    case = artifact_replicas
    server = LangBotMCPServer(case.a.app)
    other_core = LangBotMCPServer(case.b.app)
    created = await _call(
        server,
        case.context,
        'create_artifact',
        filename='mcp-report.bin',
        content_base64=base64.b64encode(_BODY).decode('ascii'),
    )
    artifact_id = created['id']
    assert created['name'] == 'mcp-report.bin'
    assert created['size'] == len(_BODY)
    assert created['digest'] == hashlib.sha256(_BODY).hexdigest()
    assert created['lifecycle'] == 'temporary'
    assert await _call(other_core, case.context, 'get_artifact', artifact_id=artifact_id) == created
    downloaded = await _call(other_core, case.context, 'read_artifact', artifact_id=artifact_id)
    assert downloaded['metadata'] == created
    assert downloaded['encoding'] == 'base64'
    assert base64.b64decode(downloaded['content'], validate=True) == _BODY
    retained = await _call(server, case.context, 'retain_artifact', artifact_id=artifact_id)
    assert retained['lifecycle'] == 'persistent' and retained['expires_at'] is None
    with pytest.raises(ToolError, match='Artifact is still in use'):
        await _call(server, case.context, 'delete_artifact', artifact_id=artifact_id)
    assert (
        await case.a.client.delete(
            '/api/v1/artifacts/' + artifact_id,
            headers=case.headers,
        )
    ).status_code == 409
    released = await _call(server, case.context, 'release_artifact', artifact_id=artifact_id)
    assert released['lifecycle'] == 'temporary' and released['expires_at'] is not None
    assert await _call(server, case.context, 'delete_artifact', artifact_id=artifact_id) == {
        'id': artifact_id,
        'deleted': True,
    }
    with pytest.raises(ToolError, match='Resource not found'):
        await _call(other_core, case.context, 'read_artifact', artifact_id=artifact_id)


async def test_mcp_rejects_foreign_principals_and_invalid_uploads(artifact_replicas):
    case = artifact_replicas
    server = LangBotMCPServer(case.a.app)
    created = await _call(
        server,
        case.context,
        'create_artifact',
        filename='private.bin',
        content_base64=base64.b64encode(_BODY).decode('ascii'),
    )
    foreign = replace(
        case.context,
        principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid=str(uuid.uuid4())),
    )
    for tool in ('get_artifact', 'read_artifact', 'retain_artifact', 'release_artifact', 'delete_artifact'):
        with pytest.raises(ToolError, match='Resource not found') as denied:
            await _call(server, foreign, tool, artifact_id=created['id'])
        assert 'private.bin' not in str(denied.value)
        assert created['digest'] not in str(denied.value)
    with pytest.raises(ToolError, match='Artifact exceeds the read size limit'):
        await _call(server, case.context, 'read_artifact', artifact_id=created['id'], max_bytes=1)
    with pytest.raises(ToolError, match='Invalid base64 file content'):
        await _call(server, case.context, 'create_artifact', filename='invalid.bin', content_base64='%%%')
    # An invalid, excessive string must hit the pre-decode size check rather than the decoder.
    encoded_limit = 4 * ((MAX_ARTIFACT_BYTES + 2) // 3)
    with pytest.raises(ToolError, match='Artifact exceeds the size limit'):
        await _call(
            server,
            case.context,
            'create_artifact',
            filename='oversized.bin',
            content_base64='!' * (encoded_limit + 1),
        )
    assert (await _call(server, case.context, 'get_artifact', artifact_id=created['id'])) == created


async def test_mcp_fixed_skill_reference_uses_shared_reader_and_permissions(artifact_replicas):
    from tests.integration.storage.test_skill_artifacts import _install
    from tests.integration.skill.test_persistent_skill_replicas import _NAME, _GUIDE

    case = artifact_replicas
    revision = await _install(case)
    server = LangBotMCPServer(case.a.app)
    created = await _call(
        server,
        case.context,
        'create_skill_resource_artifact',
        skill_name=_NAME,
        revision=revision,
        path='references/guide.md',
    )
    assert created['source'] == 'skill_resource'
    raw = await _call(server, case.context, 'read_artifact', artifact_id=created['id'])
    assert base64.b64decode(raw['content']) == _GUIDE.encode()
    rendered = await _call(server, case.context, 'read_artifact_content', artifact_id=created['id'], max_chars=7)
    assert rendered['text'] == _GUIDE[:7]
    foreign = replace(case.context, principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid=str(uuid.uuid4())))
    with pytest.raises(ToolError, match='Resource not found'):
        await _call(server, foreign, 'read_artifact_content', artifact_id=created['id'])
    denied = replace(case.context, workspace=replace(case.context.workspace, permissions=frozenset()))
    with pytest.raises(ToolError):
        await _call(
            server,
            denied,
            'create_skill_resource_artifact',
            skill_name=_NAME,
            revision=revision,
            path='references/guide.md',
        )
