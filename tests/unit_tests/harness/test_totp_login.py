"""Second-factor sign-in over HTS1: the RPC contract and its error codes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

# ``harness.rpc`` is only importable once the application package graph exists
# (importing it first is a pre-existing circular import), so pull it in through
# the module the running server loads. ``harness.ws`` binds ``harness.rpc``.
from langbot.pkg.harness import ws  # noqa: F401
from langbot.pkg.entity.persistence.harness_oauth import HarnessDevice
from langbot.pkg.entity.persistence.harness_registration import HarnessRegistrationLink
from langbot.pkg.harness.oauth import HarnessOAuthService
from langbot.pkg.harness.rpc import HarnessRpc, RpcError


def _rpc():
    return HarnessRpc(SimpleNamespace())


async def _dispatch(method, params, service):
    """Dispatch one HTS1 method with the OAuth service stubbed out."""
    with patch('langbot.pkg.harness.rpc.HarnessOAuthService', return_value=service):
        return await _rpc()._dispatch('binding-1', 'device-1', {'method': method, 'params': params})


@pytest.mark.asyncio
async def test_password_accepts_an_optional_totp_code():
    service = SimpleNamespace(password_grant=AsyncMock(return_value={'access_token': 'at'}))
    result = await _dispatch(
        'oauth.password',
        {'email': 'a@example.test', 'password': 'pw', 'workspace_uuid': 'ws-1', 'totp_code': '123456'},
        service,
    )

    assert result == {'access_token': 'at'}
    _, payload = service.password_grant.await_args.args
    # The device comes from the verified channel, never from the request body.
    assert payload['device_id'] == 'device-1'
    assert payload['totp_code'] == '123456'


@pytest.mark.asyncio
async def test_password_without_a_totp_code_still_works():
    service = SimpleNamespace(password_grant=AsyncMock(return_value={'access_token': 'at'}))
    await _dispatch(
        'oauth.password',
        {'email': 'a@example.test', 'password': 'pw', 'workspace_uuid': 'ws-1'},
        service,
    )

    _, payload = service.password_grant.await_args.args
    assert 'totp_code' not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'params',
    [
        # A code pinning the channel device is not accepted: the channel wins.
        {'email': 'a@example.test', 'password': 'pw', 'workspace_uuid': 'ws-1', 'device_id': 'other'},
        {'email': 'a@example.test', 'password': 'pw', 'workspace_uuid': 'ws-1', 'totp_code': ''},
        {'email': 'a@example.test', 'password': 'pw', 'workspace_uuid': 'ws-1', 'totp_code': 'x' * 33},
        {'email': 'a@example.test', 'password': 'pw', 'workspace_uuid': 'ws-1', 'totp_code': 123456},
        {'email': 'a@example.test', 'password': 'pw'},
    ],
)
async def test_password_rejects_malformed_parameters(params):
    service = SimpleNamespace(password_grant=AsyncMock(return_value={}))
    with pytest.raises(RpcError) as raised:
        await _dispatch('oauth.password', params, service)

    assert str(raised.value) == 'invalid_request'
    service.password_grant.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'error, expected',
    [
        # A rejected code must stay distinguishable from a rejected password.
        ('totp_invalid_code', 'totp_invalid_code'),
        ('interaction_required', 'interaction_required'),
        ('invalid_grant', 'invalid_grant'),
        # Anything unmapped keeps the historical code.
        ('invalid_device', 'invalid_device'),
        ('something_new', 'invalid_grant'),
    ],
)
async def test_totp_errors_survive_the_reply_mapper(error, expected):
    """The reply mapper must not collapse a TOTP failure into ``invalid_grant``."""
    assert (error if error in _GRANT_ERRORS else 'invalid_grant') == expected


_GRANT_ERRORS = __import__('langbot.pkg.harness.rpc', fromlist=['_GRANT_ERRORS'])._GRANT_ERRORS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'error, expected',
    [
        ('TotpInvalidCodeError', 'totp_invalid_code'),
        # Anything unmapped keeps the historical code.
        ('PasswordMismatch', 'invalid_grant'),
    ],
)
async def test_authentication_failures_map_to_distinct_codes(tmp_path, error, expected):
    """A wrong code is reported as such rather than as a bad password."""
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "totp.db"}')
    raised_error = type(error, (Exception,), {})()

    async def authenticate(*args, **kwargs):
        raise raised_error

    ap = SimpleNamespace(user_service=SimpleNamespace(authenticate=authenticate))
    service = HarnessOAuthService.__new__(HarnessOAuthService)
    service.ap = ap
    service.engine = engine
    service.instance_uuid = 'instance-1'
    try:
        async with engine.begin() as conn:
            await conn.run_sync(HarnessDevice.__table__.create)
            await conn.run_sync(HarnessRegistrationLink.__table__.create)
            await conn.execute(
                HarnessRegistrationLink.__table__.insert().values(
                    id='binding-1',
                    instance_uuid='instance-1',
                    issuer_workspace_uuid='issuer',
                    created_by_account_uuid='admin-1',
                    token_hash='x' * 64,
                    kid='kid-1',
                    expires_at=999,
                    consumed_at=1,
                )
            )
            await conn.execute(
                HarnessDevice.__table__.insert().values(
                    id='device-1',
                    binding_id='binding-1',
                    device_kid='device-kid-1',
                    x25519_pub='a' * 44,
                    ed25519_pub='b' * 44,
                    created_at=0,
                )
            )
        with pytest.raises(ValueError) as raised:
            await service.password_grant(
                'binding-1',
                {
                    'grant_type': 'password',
                    'device_id': 'device-1',
                    'username': 'a@example.test',
                    'password': 'pw',
                    'workspace_uuid': 'ws-1',
                    'totp_code': '000000',
                },
            )
    finally:
        await engine.dispose()

    assert str(raised.value) == expected
