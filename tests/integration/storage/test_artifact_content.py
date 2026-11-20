"""Authorized HTTP and native MCP Artifact content, over real persistence."""
# ruff: noqa: F811

import base64
import io
import json

from mcp import types
import pytest
from quart.datastructures import FileStorage

from langbot.pkg.api.mcp.context import bind_request_context, reset_request_context
from langbot.pkg.api.mcp.server import LangBotMCPServer
from tests.integration.storage.test_artifacts import (
    artifact_replicas,  # noqa: F401 -- pytest fixture
    persistence_case,  # noqa: F401 -- fixture dependency
    replicas,  # noqa: F401
    _data,
)
from tests.utils.artifact_media import text_pdf

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def upload(case, name, value, mime):
    return await _data(
        await case.a.client.post(
            '/api/v1/artifacts',
            headers=case.headers,
            files={
                'file': FileStorage(io.BytesIO(value), filename=name, content_type=mime),
            },
        )
    )


async def test_http_text_ranges_and_cross_core_mcp_image(artifact_replicas):
    case = artifact_replicas
    text = '甲乙😀丁戊'
    metadata = await upload(case, 'note.txt', text.encode(), 'text/plain')
    path = '/api/v1/artifacts/' + metadata['id'] + '/read'
    response = await case.b.client.get(path + '?offset=1&max_chars=2', headers=case.headers)
    assert response.headers['Cache-Control'] == 'private, no-store'
    first = await _data(response)
    result = json.loads(first[0]['text'])
    assert result['text'] == '乙😀' and result['next_offset'] == 3 and result['truncated'] is True
    assert (await case.b.client.get(path)).status_code == 401
    assert (await case.b.client.get(path + '?offset=-1', headers=case.headers)).status_code == 400
    assert (await case.b.client.get(path + '?mode=pages', headers=case.headers)).status_code == 415
    png = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZkAAAAASUVORK5CYII='
    )
    image = await upload(case, 'pixel.png', png, 'image/png')
    server = LangBotMCPServer(case.b.app)
    token = bind_request_context(case.context)
    try:
        response = await server.mcp.call_tool('read_artifact_content', {'artifact_id': image['id']})
    finally:
        reset_request_context(token)
    blocks = response.content if isinstance(response, types.CallToolResult) else response[0]
    assert blocks[0].type == 'text'
    assert blocks[1].type == 'image' and blocks[1].mimeType == 'image/png'
    assert base64.b64decode(blocks[1].data) == png
    assert base64.b64encode(png).decode() not in blocks[0].text


async def test_truncated_native_pdf_is_not_delivered_as_model_content(artifact_replicas):
    case = artifact_replicas
    content = text_pdf('Truncated file on disk')[:-45]
    metadata = await upload(case, 'report.pdf', content, 'application/pdf')
    path = '/api/v1/artifacts/' + metadata['id']
    for mode in ('native', 'text'):
        response = await case.b.client.get(path + f'/read?mode={mode}', headers=case.headers)
        assert response.status_code == 422
        assert (await response.get_json())['code'] == 'artifact_pdf_unreadable'
    # Decode failures do not make the original bytes inaccessible to their owner.
    response = await case.b.client.get(path + '/content', headers=case.headers)
    assert response.status_code == 200 and await response.get_data() == content
