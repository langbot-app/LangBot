from __future__ import annotations

import pytest

from langbot.libs.openclaw_weixin_api.client import (
    MAX_CDN_MEDIA_BYTES,
    OpenClawWeixinClient,
    _decrypt_cdn_payload,
    _encrypt_cdn_payload,
)
from langbot.libs.openclaw_weixin_api.types import ApiError


def test_cdn_crypto_helpers_round_trip(monkeypatch):
    # AES-128-ECB with PKCS7 padding, independently generated using OpenSSL.
    key = bytes.fromhex('2b7e151628aed2a6abf7158809cf4f3c')
    original = bytes.fromhex('6bc1bee22e409f96e93d7e117393172a')
    expected_ciphertext = bytes.fromhex('3ad77bb40d7a3660a89ecaf32466ef97a254be88e037ddd9d79fb6411c3f9df8')
    monkeypatch.setattr('langbot.libs.openclaw_weixin_api.client.os.urandom', lambda size: key)

    aes_key_hex, encoded_key, encrypted, raw_md5 = _encrypt_cdn_payload(original)

    assert aes_key_hex == '2b7e151628aed2a6abf7158809cf4f3c'
    assert encoded_key == 'MmI3ZTE1MTYyOGFlZDJhNmFiZjcxNTg4MDljZjRmM2M='
    assert encrypted == expected_ciphertext
    assert raw_md5 == 'f2ecfb66e72f88f217e659ac75b1075f'
    assert _decrypt_cdn_payload(expected_ciphertext, key) == original


@pytest.mark.asyncio
async def test_upload_media_rejects_oversized_input_before_network_access():
    client = OpenClawWeixinClient('https://example.invalid', 'token')

    with pytest.raises(ApiError, match='exceeds the size limit'):
        await client.upload_media(
            b'x' * (MAX_CDN_MEDIA_BYTES + 1),
            'recipient',
            3,
        )


def test_voice_item_serialization_includes_encode_type_and_playtime():
    from langbot.libs.openclaw_weixin_api.client import _message_item_to_dict
    from langbot.libs.openclaw_weixin_api.types import CDNMedia, MessageItem, VoiceItem

    media = CDNMedia(encrypt_query_param='param', aes_key='key', encrypt_type=1)
    item = MessageItem(
        type=MessageItem.VOICE,
        voice_item=VoiceItem(media=media, playtime=4500, encode_type=6),
    )
    d = _message_item_to_dict(item)

    assert d['type'] == MessageItem.VOICE
    assert 'voice_item' in d
    assert d['voice_item']['playtime'] == 4500
    assert d['voice_item']['encode_type'] == 6
    assert d['voice_item']['media']['encrypt_query_param'] == 'param'

