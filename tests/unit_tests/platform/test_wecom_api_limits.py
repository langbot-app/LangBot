from __future__ import annotations

import pytest

from langbot.libs.wecom_api.api import (
    _EXTENDED_HTTP_TIMEOUT_SECONDS,
    _decode_media_base64_limited,
    WecomClient,
)


@pytest.mark.asyncio
async def test_wecom_extended_client_timeout_is_still_bounded() -> None:
    client = object.__new__(WecomClient)
    client._http_clients = {}

    try:
        async with client._http_client_context(unbounded_timeout=True) as http_client:
            assert http_client.timeout.read == _EXTENDED_HTTP_TIMEOUT_SECONDS
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_wecom_base64_decode_is_bounded(monkeypatch) -> None:
    import langbot.libs.wecom_api.api as wecom_api

    monkeypatch.setattr(wecom_api, '_MAX_MEDIA_BYTES', 4)

    with pytest.raises(ValueError, match='exceeds'):
        await _decode_media_base64_limited('MTIzNDU=')
