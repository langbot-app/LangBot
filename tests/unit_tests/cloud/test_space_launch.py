from __future__ import annotations

import base64
import json
import time
import uuid
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from langbot.pkg.cloud.launch import SpaceLaunchError, SpaceLaunchService


pytestmark = pytest.mark.asyncio


INSTANCE_UUID = 'instance-test'
ACCOUNT_UUID = '11111111-1111-4111-8111-111111111111'
WORKSPACE_UUID = '22222222-2222-4222-8222-222222222222'
KEY_ID = 'space-key-1'


def _base64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def _sign(private_key: Ed25519PrivateKey, claims: dict, *, key_id: str = KEY_ID) -> str:
    header = {'alg': 'EdDSA', 'kid': key_id, 'typ': 'langbot-control-plane+jwt'}
    encoded_header = _base64url(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    encoded_claims = _base64url(json.dumps(claims, separators=(',', ':')).encode('utf-8'))
    signing_input = f'{encoded_header}.{encoded_claims}'
    return f'{signing_input}.{_base64url(private_key.sign(signing_input.encode("ascii")))}'


def _claims(*, now: int, jti: str | None = None, workspace_uuid: str = WORKSPACE_UUID) -> dict:
    return {
        'iss': 'langbot-space',
        'aud': 'langbot-cloud-runtime',
        'sub': f'langbot-instance:{INSTANCE_UUID}',
        'jti': jti or str(uuid.uuid4()),
        'iat': now,
        'nbf': now - 5,
        'exp': now + 90,
        'instance_uuid': INSTANCE_UUID,
        'kind': 'workspace.launch',
        'payload': {
            'account_uuid': ACCOUNT_UUID,
            'workspace_uuid': workspace_uuid,
        },
    }


def _service(private_key: Ed25519PrivateKey, *, now: int) -> SpaceLaunchService:
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    app = SimpleNamespace(
        deployment=SimpleNamespace(multi_workspace_enabled=True, verification_key_id=KEY_ID),
        workspace_service=SimpleNamespace(instance_uuid=INSTANCE_UUID),
        instance_config=SimpleNamespace(
            data={
                'space': {
                    'launch': {
                        'control_plane_public_key': _base64url(public_key),
                    }
                }
            }
        ),
    )
    return SpaceLaunchService(app, wall_time=lambda: now)


async def test_consumes_valid_workspace_launch_assertion_once():
    private_key = Ed25519PrivateKey.generate()
    now = int(time.time())
    service = _service(private_key, now=now)
    token = _sign(private_key, _claims(now=now))

    launch = await service.consume_assertion(token, expected_workspace_uuid=WORKSPACE_UUID)

    assert launch == {'account_uuid': ACCOUNT_UUID, 'workspace_uuid': WORKSPACE_UUID}
    with pytest.raises(SpaceLaunchError, match='already been consumed'):
        await service.consume_assertion(token, expected_workspace_uuid=WORKSPACE_UUID)


async def test_replay_cache_does_not_scan_all_live_assertions(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    now = int(time.time())
    service = _service(private_key, now=now)
    for index in range(512):
        await service._consume_jti(f'jti-{index}', now + 90)

    class NoGlobalIterationDict(dict):
        def __iter__(self):
            raise AssertionError('replay admission scanned all live assertions')

        def keys(self):
            raise AssertionError('replay admission scanned all live assertions')

        def items(self):
            raise AssertionError('replay admission scanned all live assertions')

        def values(self):
            raise AssertionError('replay admission scanned all live assertions')

    guarded_jtis = NoGlobalIterationDict(service._consumed_jtis)
    monkeypatch.setattr(service, '_consumed_jtis', guarded_jtis)

    await service._consume_jti('jti-new', now + 90)

    assert len(guarded_jtis) == 513


async def test_replay_cache_fails_closed_at_capacity(monkeypatch):
    from langbot.pkg.cloud import launch

    private_key = Ed25519PrivateKey.generate()
    now = int(time.time())
    service = _service(private_key, now=now)
    monkeypatch.setattr(launch, '_CONSUMED_JTI_MAX_ENTRIES', 2)
    await service._consume_jti('jti-1', now + 90)
    await service._consume_jti('jti-2', now + 90)

    with pytest.raises(SpaceLaunchError, match='replay cache capacity'):
        await service._consume_jti('jti-3', now + 90)
    with pytest.raises(SpaceLaunchError, match='already been consumed'):
        await service._consume_jti('jti-1', now + 90)


async def test_rejects_expired_wrong_workspace_and_wrong_instance_assertions():
    private_key = Ed25519PrivateKey.generate()
    now = int(time.time())
    service = _service(private_key, now=now)

    expired = _claims(now=now)
    expired['exp'] = now - 60
    with pytest.raises(SpaceLaunchError, match='expired'):
        await service.consume_assertion(_sign(private_key, expired), expected_workspace_uuid=WORKSPACE_UUID)

    wrong_workspace = _sign(private_key, _claims(now=now, workspace_uuid='33333333-3333-4333-8333-333333333333'))
    with pytest.raises(SpaceLaunchError, match='another Workspace'):
        await service.consume_assertion(wrong_workspace, expected_workspace_uuid=WORKSPACE_UUID)

    wrong_instance = _claims(now=now)
    wrong_instance['instance_uuid'] = 'other-instance'
    with pytest.raises(SpaceLaunchError, match='instance UUID'):
        await service.consume_assertion(_sign(private_key, wrong_instance), expected_workspace_uuid=WORKSPACE_UUID)


async def test_rejects_invalid_signature_and_non_cloud_mode():
    private_key = Ed25519PrivateKey.generate()
    now = int(time.time())
    token = _sign(private_key, _claims(now=now))
    service = _service(Ed25519PrivateKey.generate(), now=now)
    with pytest.raises(SpaceLaunchError, match='signature'):
        await service.consume_assertion(token, expected_workspace_uuid=WORKSPACE_UUID)

    oss_service = _service(private_key, now=now)
    oss_service.ap.deployment.multi_workspace_enabled = False
    with pytest.raises(SpaceLaunchError, match='verified Cloud mode'):
        await oss_service.consume_assertion(token, expected_workspace_uuid=WORKSPACE_UUID)
