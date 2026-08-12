from __future__ import annotations

import pytest

from langbot.libs.deerflow_api.client import (
    ERROR_BODY_MAX_BYTES,
    _read_error_body,
)
from langbot.libs.deerflow_api.errors import DeerFlowAPIError
from langbot.pkg.provider.runners.langflowapi import (
    _MAX_LANGFLOW_LINE_CHARS,
    _MAX_LANGFLOW_RESPONSE_BYTES,
    _iter_limited_lines,
    _read_limited_response,
)


class _ChunkedResponse:
    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks

    async def aiter_bytes(self, chunk_size=None):
        del chunk_size
        for chunk in self._chunks:
            yield chunk


@pytest.mark.asyncio
async def test_langflow_rejects_oversized_stream_event():
    response = _ChunkedResponse([b'x' * (_MAX_LANGFLOW_LINE_CHARS + 1)])

    with pytest.raises(ValueError, match='event exceeds'):
        await anext(_iter_limited_lines(response))


@pytest.mark.asyncio
async def test_langflow_rejects_oversized_blocking_response():
    response = _ChunkedResponse([b'x' * (_MAX_LANGFLOW_RESPONSE_BYTES + 1)])

    with pytest.raises(ValueError, match='response exceeds'):
        await _read_limited_response(response)


@pytest.mark.asyncio
async def test_deerflow_rejects_oversized_error_body():
    response = _ChunkedResponse([b'x' * (ERROR_BODY_MAX_BYTES + 1)])

    with pytest.raises(DeerFlowAPIError, match='response exceeds'):
        await _read_error_body(response)
