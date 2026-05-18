"""
Unit tests for N8nServiceAPIRunner._process_response

Tests cover four scenarios:
- Stream adapter + n8n stream format  (type:item/end)
- Stream adapter + n8n plain JSON
- Non-stream adapter + n8n stream format
- Non-stream adapter + n8n plain JSON
"""

from __future__ import annotations

import json
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

# Break the circular import chain before importing n8nsvapi:
#   n8nsvapi → runner → app → pipelinemgr → all runners → runner (partially init)
_mock_runner = MagicMock()
_mock_runner.runner_class = lambda name: (lambda cls: cls)  # no-op decorator
_mock_runner.RequestRunner = object
_mocked_imports = {
    'langbot.pkg.provider.runner': _mock_runner,
    'langbot.pkg.core.app': MagicMock(),
}
_original_imports = {name: sys.modules.get(name) for name in _mocked_imports}
sys.modules.update(_mocked_imports)

import pytest  # noqa: E402
import langbot_plugin.api.entities.builtin.provider.message as provider_message  # noqa: E402
from langbot.pkg.provider.runners.n8nsvapi import N8nServiceAPIRunner  # noqa: E402

for _name, _original in _original_imports.items():
    if _original is None:
        sys.modules.pop(_name, None)
    else:
        sys.modules[_name] = _original


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_runner(output_key: str = 'response') -> N8nServiceAPIRunner:
    ap = Mock()
    ap.logger = Mock()
    pipeline_config = {
        'ai': {
            'n8n-service-api': {
                'webhook-url': 'http://test-n8n/webhook',
                'output-key': output_key,
                'auth-type': 'none',
            }
        }
    }
    return N8nServiceAPIRunner(ap, pipeline_config)


def make_mock_response(chunks: list[bytes | str], status: int = 200):
    """Build a minimal aiohttp.ClientResponse mock with iter_chunked support."""
    response = Mock()
    response.status = status

    async def iter_chunked(size):
        for chunk in chunks:
            yield chunk

    response.content = Mock()
    response.content.iter_chunked = iter_chunked
    return response


async def collect_chunks(runner: N8nServiceAPIRunner, chunks: list[bytes | str]):
    """Run _process_response and collect all yielded MessageChunks."""
    response = make_mock_response(chunks)
    result = []
    async for chunk in runner._process_response(response):
        result.append(chunk)
    return result


# ---------------------------------------------------------------------------
# _process_response: stream format (type:item/end)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_format_single_item():
    """Single item + end in one chunk yields final chunk with full content."""
    runner = make_runner()
    data = b'{"type":"item","content":"hello"}{"type":"end"}'

    chunks = await collect_chunks(runner, [data])

    assert len(chunks) == 1
    assert chunks[0].is_final is True
    assert chunks[0].content == 'hello'
    assert chunks[0].msg_sequence == 1


@pytest.mark.asyncio
async def test_stream_format_multi_item_accumulates():
    """Multiple items accumulate into full_content."""
    runner = make_runner()
    chunks_data = [
        b'{"type":"item","content":"foo"}',
        b'{"type":"item","content":"bar"}',
        b'{"type":"end"}',
    ]

    chunks = await collect_chunks(runner, chunks_data)

    assert len(chunks) == 1
    assert chunks[0].is_final is True
    assert chunks[0].content == 'foobar'
    assert chunks[0].msg_sequence == 1


@pytest.mark.asyncio
async def test_stream_format_batches_every_8_items():
    """Every 8th item triggers an intermediate yield before the final."""
    runner = make_runner()
    items = [f'{{"type":"item","content":"{i}"}}' for i in range(8)]
    items.append('{"type":"end"}')
    data = ''.join(items).encode()

    chunks = await collect_chunks(runner, [data])

    assert len(chunks) == 2
    assert chunks[0].is_final is False
    assert chunks[0].content == '01234567'
    assert chunks[0].msg_sequence == 1
    assert chunks[1].is_final is True
    assert chunks[1].content == '01234567'
    assert chunks[1].msg_sequence == 2


@pytest.mark.asyncio
async def test_stream_format_split_across_network_chunks():
    """JSON split across multiple network chunks is reassembled correctly."""
    runner = make_runner()
    part1 = b'{"type":"item","con'
    part2 = b'tent":"world"}{"type":"end"}'

    chunks = await collect_chunks(runner, [part1, part2])

    assert len(chunks) == 1
    assert chunks[0].is_final is True
    assert chunks[0].content == 'world'


@pytest.mark.asyncio
async def test_stream_format_no_spurious_empty_yield():
    """chunk_idx==0 guard prevents spurious empty yield before any item is received."""
    runner = make_runner()
    # Send some non-stream JSON first, then stream
    data = b'{"type":"item","content":"x"}{"type":"end"}'

    chunks = await collect_chunks(runner, [data])

    assert len(chunks) == 1
    assert chunks[0].content == 'x'


# ---------------------------------------------------------------------------
# _process_response: plain JSON fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_plain_json_with_output_key():
    """Plain JSON with matching output_key extracts value via output_key."""
    runner = make_runner(output_key='response')
    data = json.dumps({'response': 'hello world'}).encode()

    chunks = await collect_chunks(runner, [data])

    assert len(chunks) == 1
    assert chunks[0].is_final is True
    assert chunks[0].content == 'hello world'


@pytest.mark.asyncio
async def test_plain_json_output_key_not_found():
    """Plain JSON without output_key falls back to entire JSON string."""
    runner = make_runner(output_key='response')
    payload = {'other_key': 'hello'}
    data = json.dumps(payload).encode()

    chunks = await collect_chunks(runner, [data])

    assert len(chunks) == 1
    assert chunks[0].is_final is True
    assert json.loads(chunks[0].content) == payload


@pytest.mark.asyncio
async def test_plain_json_output_key_empty_string():
    """output_key present but value is empty string — returns empty string, not whole JSON."""
    runner = make_runner(output_key='response')
    data = json.dumps({'response': ''}).encode()

    chunks = await collect_chunks(runner, [data])

    assert len(chunks) == 1
    assert chunks[0].is_final is True
    assert chunks[0].content == ''


@pytest.mark.asyncio
async def test_plain_json_non_dict_response():
    """Plain JSON array falls back to raw text."""
    runner = make_runner()
    data = b'["a", "b"]'

    chunks = await collect_chunks(runner, [data])

    assert len(chunks) == 1
    assert chunks[0].is_final is True
    assert chunks[0].content == '["a", "b"]'


@pytest.mark.asyncio
async def test_invalid_json_returns_raw_text():
    """Non-JSON response returns raw text as-is."""
    runner = make_runner()
    data = b'plain text response'

    chunks = await collect_chunks(runner, [data])

    assert len(chunks) == 1
    assert chunks[0].is_final is True
    assert chunks[0].content == 'plain text response'


# ---------------------------------------------------------------------------
# _call_webhook: output type depends on is_stream
# ---------------------------------------------------------------------------

def make_query(is_stream: bool):
    """Build a minimal Query mock."""
    query = Mock()
    query.adapter = AsyncMock()
    query.adapter.is_stream_output_supported = AsyncMock(return_value=is_stream)

    session = Mock()
    session.using_conversation = Mock()
    session.using_conversation.uuid = 'test-uuid'
    session.launcher_type = Mock()
    session.launcher_type.value = 'person'
    session.launcher_id = '12345'
    query.session = session

    query.user_message = Mock()
    query.user_message.content = 'hi'
    query.variables = {}
    return query


def make_http_session_mock(response_bytes: bytes, status: int = 200):
    """Mock httpclient.get_session() returning a session whose post() yields response_bytes."""
    mock_response = make_mock_response([response_bytes], status=status)
    mock_response.status = status

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session = Mock()
    mock_session.post = Mock(return_value=mock_cm)
    return mock_session


@pytest.mark.asyncio
async def test_call_webhook_nonstream_adapter_plain_json():
    """Non-stream adapter + plain JSON → single Message with output_key value."""
    runner = make_runner(output_key='response')
    query = make_query(is_stream=False)
    http_session = make_http_session_mock(json.dumps({'response': 'result text'}).encode())

    with patch('langbot.pkg.provider.runners.n8nsvapi.httpclient.get_session', return_value=http_session):
        results = []
        async for msg in runner._call_webhook(query):
            results.append(msg)

    assert len(results) == 1
    assert isinstance(results[0], provider_message.Message)
    assert results[0].content == 'result text'


@pytest.mark.asyncio
async def test_call_webhook_stream_adapter_stream_format():
    """Stream adapter + stream format → MessageChunks, last is_final."""
    runner = make_runner()
    query = make_query(is_stream=True)
    data = b'{"type":"item","content":"hi"}{"type":"end"}'
    http_session = make_http_session_mock(data)

    with patch('langbot.pkg.provider.runners.n8nsvapi.httpclient.get_session', return_value=http_session):
        results = []
        async for msg in runner._call_webhook(query):
            results.append(msg)

    assert all(isinstance(r, provider_message.MessageChunk) for r in results)
    assert results[-1].is_final is True
    assert results[-1].content == 'hi'


@pytest.mark.asyncio
async def test_call_webhook_stream_adapter_plain_json():
    """Stream adapter + plain JSON → single MessageChunk with is_final=True."""
    runner = make_runner(output_key='response')
    query = make_query(is_stream=True)
    data = json.dumps({'response': 'fallback'}).encode()
    http_session = make_http_session_mock(data)

    with patch('langbot.pkg.provider.runners.n8nsvapi.httpclient.get_session', return_value=http_session):
        results = []
        async for msg in runner._call_webhook(query):
            results.append(msg)

    assert all(isinstance(r, provider_message.MessageChunk) for r in results)
    assert results[-1].is_final is True
    assert results[-1].content == 'fallback'


@pytest.mark.asyncio
async def test_call_webhook_nonstream_adapter_stream_format():
    """Non-stream adapter + stream format → single Message with accumulated content."""
    runner = make_runner()
    query = make_query(is_stream=False)
    data = b'{"type":"item","content":"foo"}{"type":"item","content":"bar"}{"type":"end"}'
    http_session = make_http_session_mock(data)

    with patch('langbot.pkg.provider.runners.n8nsvapi.httpclient.get_session', return_value=http_session):
        results = []
        async for msg in runner._call_webhook(query):
            results.append(msg)

    assert len(results) == 1
    assert isinstance(results[0], provider_message.Message)
    assert results[0].content == 'foobar'
