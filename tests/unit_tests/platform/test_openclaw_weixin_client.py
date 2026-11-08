from __future__ import annotations

import asyncio
import base64

import pytest

from langbot.libs.openclaw_weixin_api import client as client_module

from langbot.libs.openclaw_weixin_api.client import (
    MAX_CDN_MEDIA_BYTES,
    OpenClawWeixinClient,
    _decrypt_cdn_payload,
    _encrypt_cdn_payload,
)
from langbot.libs.openclaw_weixin_api.types import ApiError, GetUploadUrlResponse


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
        voice_item=VoiceItem(
            media=media,
            playtime=4500,
            encode_type=6,
            bits_per_sample=16,
            sample_rate=24000,
            size=1024,
        ),
    )
    d = _message_item_to_dict(item)

    assert d['type'] == MessageItem.VOICE
    assert 'voice_item' in d
    assert d['voice_item']['playtime'] == 4500
    assert d['voice_item']['encode_type'] == 6
    assert d['voice_item']['bits_per_sample'] == 16
    assert d['voice_item']['sample_rate'] == 24000
    assert d['voice_item']['size'] == 1024
    assert d['voice_item']['media']['encrypt_query_param'] == 'param'


@pytest.mark.asyncio
async def test_inbound_voice_conversion_to_voice_component():
    import langbot_plugin.api.entities.builtin.platform.message as platform_message
    from langbot.libs.openclaw_weixin_api.types import CDNMedia, MessageItem, VoiceItem, WeixinMessage
    from langbot.pkg.platform.sources.openclaw_weixin import OpenClawWeixinMessageConverter

    fake_silk_data = b'\x02#!SILK_V3' + b'\x05\x00abcde' * 50
    item = MessageItem(
        type=MessageItem.VOICE,
        voice_item=VoiceItem(
            media=CDNMedia(encrypt_query_param='param', aes_key='key'),
            playtime=1000,
            _downloaded_bytes=fake_silk_data,
        ),
    )
    msg = WeixinMessage(
        message_id=1,
        from_user_id='user1',
        to_user_id='bot1',
        item_list=[item],
    )

    converter = OpenClawWeixinMessageConverter()
    chain = await converter.target2yiri(msg)

    assert len(chain) == 1
    voice = chain[0]
    assert isinstance(voice, platform_message.Voice)
    assert voice.length == 1
    assert voice.base64.startswith('data:audio/silk;base64,')
    b64_payload = voice.base64.split(',', 1)[1]
    assert base64.b64decode(b64_payload) == fake_silk_data


# ---------------------------------------------------------------------------
# CDN upload endpoint selection and retry (langbot-app/LangBot#2890)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status: int, headers: dict | None = None):
        self.status = status
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append({'url': url, 'data': data})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _make_client(monkeypatch, upload_resp: GetUploadUrlResponse, outcomes):
    client = OpenClawWeixinClient('https://example.invalid', 'token')
    session = _FakeSession(outcomes)
    upload_requests = []

    async def fake_get_session():
        return session

    async def fake_get_upload_url(**kwargs):
        upload_requests.append(kwargs)
        return upload_resp

    async def no_sleep(_):
        return None

    monkeypatch.setattr(client, '_get_session', fake_get_session)
    monkeypatch.setattr(client, 'get_upload_url', fake_get_upload_url)
    monkeypatch.setattr(client_module.asyncio, 'sleep', no_sleep)
    return client, session, upload_requests


def _ok(param='download-param'):
    return _FakeResponse(200, {'x-encrypted-param': param})


@pytest.mark.asyncio
async def test_upload_media_prefers_upload_full_url_and_keeps_signature(monkeypatch):
    full_url = 'https://cdn.example.com/c2c/upload?sig=a%2Bb%3D&filekey=abc'
    client, session, _ = _make_client(
        monkeypatch,
        GetUploadUrlResponse(upload_param='legacy-param', upload_full_url=f'  {full_url}  '),
        [_ok()],
    )

    media = await client.upload_media(b'image-bytes', 'recipient', 1)

    assert media.encrypt_query_param == 'download-param'
    assert len(session.calls) == 1
    assert str(session.calls[0]['url']) == full_url


@pytest.mark.asyncio
async def test_upload_media_accepts_full_url_without_upload_param(monkeypatch):
    client, session, _ = _make_client(
        monkeypatch,
        GetUploadUrlResponse(upload_full_url='https://cdn.example.com/upload?x=1'),
        [_ok()],
    )

    await client.upload_media(b'image-bytes', 'recipient', 1)

    assert str(session.calls[0]['url']) == 'https://cdn.example.com/upload?x=1'


@pytest.mark.asyncio
async def test_upload_media_falls_back_to_legacy_url_when_full_url_blank(monkeypatch):
    client, session, upload_requests = _make_client(
        monkeypatch,
        GetUploadUrlResponse(upload_param='a+b/c=', upload_full_url='   '),
        [_ok()],
    )

    await client.upload_media(b'image-bytes', 'recipient', 1)

    filekey = upload_requests[0]['filekey']
    assert str(session.calls[0]['url']) == (
        f'{client_module.CDN_BASE_URL}/upload?encrypted_query_param=a%2Bb%2Fc%3D&filekey={filekey}'
    )


@pytest.mark.asyncio
async def test_upload_media_requires_some_upload_url(monkeypatch):
    client, session, _ = _make_client(monkeypatch, GetUploadUrlResponse(), [])

    with pytest.raises(ApiError, match='Failed to get upload URL'):
        await client.upload_media(b'image-bytes', 'recipient', 1)
    assert session.calls == []


@pytest.mark.asyncio
async def test_upload_media_retries_server_errors_and_timeouts_with_same_payload(monkeypatch):
    client, session, upload_requests = _make_client(
        monkeypatch,
        GetUploadUrlResponse(upload_full_url='https://cdn.example.com/upload'),
        [_FakeResponse(500), asyncio.TimeoutError(), _ok('recovered')],
    )

    media = await client.upload_media(b'image-bytes', 'recipient', 1)

    assert media.encrypt_query_param == 'recovered'
    assert len(upload_requests) == 1
    assert len(session.calls) == 3
    assert len({bytes(call['data']) for call in session.calls}) == 1
    assert len({str(call['url']) for call in session.calls}) == 1


@pytest.mark.asyncio
async def test_upload_media_gives_up_after_max_attempts(monkeypatch):
    client, session, _ = _make_client(
        monkeypatch,
        GetUploadUrlResponse(upload_full_url='https://cdn.example.com/upload'),
        [_FakeResponse(500)] * client_module.CDN_UPLOAD_MAX_ATTEMPTS,
    )

    with pytest.raises(ApiError, match='HTTP 500') as exc_info:
        await client.upload_media(b'image-bytes', 'recipient', 1)
    assert exc_info.value.status == 500
    assert len(session.calls) == client_module.CDN_UPLOAD_MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_upload_media_does_not_retry_client_errors(monkeypatch):
    client, session, _ = _make_client(
        monkeypatch,
        GetUploadUrlResponse(upload_full_url='https://cdn.example.com/upload'),
        [_FakeResponse(403, {'x-error-message': 'forbidden'}), _ok()],
    )

    with pytest.raises(ApiError, match='HTTP 403'):
        await client.upload_media(b'image-bytes', 'recipient', 1)
    assert len(session.calls) == 1


@pytest.mark.asyncio
async def test_upload_media_does_not_log_signed_url_or_keys(monkeypatch, caplog):
    secret_url = 'https://cdn.example.com/upload?sig=SECRET-SIGNATURE'
    client, _, _ = _make_client(
        monkeypatch,
        GetUploadUrlResponse(upload_full_url=secret_url),
        [_FakeResponse(502), _ok()],
    )

    with caplog.at_level('DEBUG', logger='openclaw-weixin-sdk'):
        media = await client.upload_media(b'image-bytes', 'recipient', 1)

    assert 'SECRET-SIGNATURE' not in caplog.text
    assert media.aes_key not in caplog.text


@pytest.mark.asyncio
async def test_inbound_file_conversion_to_file_component():
    """#2835: file messages were collapsed to a `[File: name]` placeholder so
    the Runner received no attachment at all."""

    import langbot_plugin.api.entities.builtin.platform.message as platform_message
    from langbot.libs.openclaw_weixin_api.types import CDNMedia, FileItem, MessageItem, WeixinMessage
    from langbot.pkg.platform.sources.openclaw_weixin import OpenClawWeixinMessageConverter

    payload = b'%PDF-1.4\nplaintext\n'
    item = MessageItem(
        type=MessageItem.FILE,
        file_item=FileItem(
            media=CDNMedia(encrypt_query_param='param', aes_key='key'),
            file_name='report.pdf',
            len=str(len(payload)),
            _downloaded_bytes=payload,
        ),
    )
    msg = WeixinMessage(message_id=1, from_user_id='user1', to_user_id='bot1', item_list=[item])

    chain = await OpenClawWeixinMessageConverter().target2yiri(msg)

    assert len(chain) == 1
    file_component = chain[0]
    assert isinstance(file_component, platform_message.File)
    assert file_component.name == 'report.pdf'
    assert file_component.size == len(payload)
    assert base64.b64decode(file_component.base64) == payload


@pytest.mark.asyncio
async def test_inbound_file_without_download_keeps_the_name():
    import langbot_plugin.api.entities.builtin.platform.message as platform_message
    from langbot.libs.openclaw_weixin_api.types import FileItem, MessageItem, WeixinMessage
    from langbot.pkg.platform.sources.openclaw_weixin import OpenClawWeixinMessageConverter

    item = MessageItem(
        type=MessageItem.FILE,
        file_item=FileItem(file_name='report.pdf', len='2048'),
    )
    msg = WeixinMessage(message_id=1, from_user_id='user1', to_user_id='bot1', item_list=[item])

    chain = await OpenClawWeixinMessageConverter().target2yiri(msg)

    assert isinstance(chain[0], platform_message.File)
    assert chain[0].name == 'report.pdf'
    assert chain[0].size == 2048
    assert not chain[0].base64
