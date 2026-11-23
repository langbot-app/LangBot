from __future__ import annotations

import httpx
import pytest

from langbot.libs.wechatpad_api.api import downloadpai
from langbot.libs.wechatpad_api.util import http_util


class _Response:
    headers = {}

    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks

    def iter_content(self, chunk_size=None):
        del chunk_size
        yield from self._chunks


def test_wechatpad_response_reader_is_bounded(monkeypatch):
    monkeypatch.setattr(http_util, '_MAX_WECHATPAD_RESPONSE_BYTES', 4)

    with pytest.raises(RuntimeError, match='exceeds the runtime limit'):
        http_util._read_requests_response_limited(_Response([b'1234', b'5']))


def test_wechatpad_response_reader_requires_json_object():
    with pytest.raises(RuntimeError, match='non-object'):
        http_util._read_requests_response_limited(_Response([b'[]']))


@pytest.mark.asyncio
async def test_wechatpad_media_reader_is_bounded(monkeypatch):
    monkeypatch.setattr(downloadpai, '_MAX_WECHATPAD_MEDIA_BYTES', 4)
    response = httpx.Response(200, content=b'oversized')

    with pytest.raises(RuntimeError, match='exceeds'):
        await downloadpai._read_media_limited(response)
