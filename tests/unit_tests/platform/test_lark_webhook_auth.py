"""Exercise both webhook entry points without contacting Lark."""

import hashlib
import json
from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.platform.adapters.lark.adapter import LarkAdapter
from langbot.pkg.platform.sources.lark import LarkAdapter as LegacyLarkAdapter


@pytest.fixture(params=[LarkAdapter, LegacyLarkAdapter], ids=['native', 'legacy'])
def adapter(request):
    instance = SimpleNamespace(
        config={'verification-token': 'test-token'},
        logger=SimpleNamespace(error=AsyncMock()),
        cipher=SimpleNamespace(decrypt_string=Mock()),
        _dispatch_eba_event=AsyncMock(),
        listeners={},
        app_ticket=None,
    )
    for name in ['_verify_webhook_signature', '_verify_webhook_token', 'get_event_type', 'handle_unified_webhook']:
        setattr(instance, name, MethodType(getattr(request.param, name), instance))
    instance._webhook_event = lambda data: data.get('event', {})
    return instance


def callback(payload, signing_key=None):
    body = json.dumps(payload).encode()
    headers = {}
    if signing_key:
        headers = {
            'X-Lark-Request-Timestamp': '1714000000',
            'X-Lark-Request-Nonce': 'test-nonce',
            'X-Lark-Signature': hashlib.sha256(('1714000000test-nonce' + signing_key).encode() + body).hexdigest(),
        }
    return SimpleNamespace(get_data=AsyncMock(return_value=body), headers=headers)


@pytest.mark.asyncio
async def test_plaintext_challenge(adapter):
    result = await adapter.handle_unified_webhook(
        '',
        '',
        callback(
            {
                'type': 'url_verification',
                'token': 'test-token',
                'challenge': 'challenge-value',
            }
        ),
    )
    assert result == {'challenge': 'challenge-value'}
    adapter.cipher.decrypt_string.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('schema', ['1.0', '2.0'])
async def test_plaintext_authenticated_event(adapter, schema):
    payload = {'event': {'type': 'app_ticket', 'app_ticket': 'new-ticket'}, 'token': 'test-token'}
    if schema == '2.0':
        payload = {
            'schema': schema,
            'header': {'event_type': 'app_ticket', 'token': 'test-token'},
            'event': {'app_ticket': 'new-ticket'},
        }
    await adapter.handle_unified_webhook('', '', callback(payload))
    assert adapter.app_ticket == 'new-ticket'


@pytest.mark.asyncio
@pytest.mark.parametrize('token', [None, '', 'wrong', 123, {}, '非ASCII'])
@pytest.mark.parametrize('schema', ['1.0', '2.0'])
async def test_reject_invalid_token(adapter, token, schema):
    payload = {'type': 'url_verification', 'token': token, 'challenge': 'must-not-return'}
    if schema == '2.0':
        payload = {
            'schema': schema,
            'header': {'event_type': 'app_ticket', 'token': token},
            'event': {'app_ticket': 'must-not-set'},
            'token': 'test-token',
        }
    result = await adapter.handle_unified_webhook('', '', callback(payload))
    assert result[1] == 403
    assert adapter.app_ticket is None
    adapter._dispatch_eba_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_reject_unconfigured_credentials(adapter):
    adapter.config = {}
    result = await adapter.handle_unified_webhook('', '', callback({'type': 'url_verification', 'token': ''}))
    assert result[1] == 403


@pytest.mark.asyncio
@pytest.mark.parametrize('signing_key', [None, 'wrong-key'])
async def test_encrypted_mode_never_falls_back_to_token(adapter, signing_key):
    adapter.config['encrypt-key'] = 'configured-key'
    result = await adapter.handle_unified_webhook(
        '',
        '',
        callback(
            {
                'type': 'url_verification',
                'token': 'test-token',
                'challenge': 'must-not-return',
            },
            signing_key,
        ),
    )
    assert result[1] == 403
    adapter.cipher.decrypt_string.assert_not_called()


@pytest.mark.asyncio
async def test_signed_encrypted_challenge(adapter):
    adapter.config['encrypt-key'] = 'configured-key'
    adapter.cipher.decrypt_string.return_value = json.dumps({'type': 'url_verification', 'challenge': 'accepted'})
    result = await adapter.handle_unified_webhook('', '', callback({'encrypt': 'ciphertext'}, 'configured-key'))
    assert result == {'challenge': 'accepted'}
    adapter.cipher.decrypt_string.assert_called_once_with('ciphertext')


@pytest.mark.asyncio
async def test_plaintext_mode_rejects_encrypted_envelope(adapter):
    result = await adapter.handle_unified_webhook('', '', callback({'encrypt': 'ciphertext', 'token': 'test-token'}))
    assert result[1] == 403
    adapter.cipher.decrypt_string.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('body', [b'{', b'[]', b'null', b'"text"', b'\xff'])
async def test_invalid_json_body(adapter, body):
    result = await adapter.handle_unified_webhook('', '', SimpleNamespace(get_data=AsyncMock(return_value=body)))
    assert result[1] == 400
