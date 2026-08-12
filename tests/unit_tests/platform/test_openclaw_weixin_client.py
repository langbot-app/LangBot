from __future__ import annotations

import pytest

from langbot.libs.openclaw_weixin_api.client import (
    MAX_CDN_MEDIA_BYTES,
    OpenClawWeixinClient,
    _decrypt_cdn_payload,
    _encrypt_cdn_payload,
)
from langbot.libs.openclaw_weixin_api.types import ApiError


def test_cdn_crypto_helpers_round_trip():
    original = b'tenant-media' * 128

    aes_key_hex, _encoded_key, encrypted, _raw_md5 = _encrypt_cdn_payload(original)

    assert _decrypt_cdn_payload(encrypted, bytes.fromhex(aes_key_hex)) == original


@pytest.mark.asyncio
async def test_upload_media_rejects_oversized_input_before_network_access():
    client = OpenClawWeixinClient('https://example.invalid', 'token')

    with pytest.raises(ApiError, match='exceeds the size limit'):
        await client.upload_media(
            b'x' * (MAX_CDN_MEDIA_BYTES + 1),
            'recipient',
            3,
        )
