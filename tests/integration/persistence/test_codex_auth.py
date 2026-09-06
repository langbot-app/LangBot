"""Deterministic OAuth tests using real SQLite CAS writes, never live credentials."""

import asyncio
import base64
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.authz import Permission
from langbot.pkg.api.http.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from langbot.pkg.entity.persistence.model import CodexCredential
from langbot.pkg.persistence.alembic_runner import run_alembic_stamp, run_alembic_upgrade
from langbot.pkg.provider.modelmgr.codex_auth import CodexAuth, _tokens, validate_config
from langbot.pkg.workspace.errors import WorkspaceNotFoundError


def context(workspace='w', user='u', principal=PrincipalType.ACCOUNT, permitted=True):
    return RequestContext(
        'i',
        0,
        'r',
        'user_token',
        PrincipalContext(principal, account_uuid=user),
        WorkspaceContext(
            workspace, 'm', 'owner', frozenset({Permission.PROVIDER_SECRET_MANAGE} if permitted else set())
        ),
    )


def jwt(**claims):
    return 'test.' + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=') + '.test'


def token_response(**extra):
    return {
        'access_token': jwt(**{'https://api.openai.com/auth': {'chatgpt_account_id': 'account'}}),
        'refresh_token': 'refresh-secret',
        'expires_in': 3600,
        **extra,
    }


@pytest_asyncio.fixture
async def auth(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "codex.db"}')

    @sa.event.listens_for(engine.sync_engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')

    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                'CREATE TABLE model_providers (uuid VARCHAR(255) PRIMARY KEY, workspace_uuid VARCHAR(36) NOT NULL, requester TEXT, UNIQUE(workspace_uuid, uuid))'
            )
        )
        await conn.execute(
            sa.text(
                "INSERT INTO model_providers VALUES ('p','w','openai-codex'), ('other','other','openai-codex'), ('api','w','openai-chat-completions')"
            )
        )
    await run_alembic_stamp(engine, '0021_merge_reasoning_config')
    await run_alembic_upgrade(engine, '0022_codex_credentials')

    async def execute(statement):
        async with engine.begin() as conn:
            return await conn.execute(statement)

    service = CodexAuth(SimpleNamespace(persistence_mgr=SimpleNamespace(execute_async=execute)))
    service.engine = engine
    await execute(
        sa.insert(CodexCredential).values(provider_uuid='p', workspace_uuid='w', payload={}, version=0, lease_until=0)
    )
    try:
        yield service
    finally:
        await engine.dispose()


async def seed(auth, payload):
    await auth.ap.persistence_mgr.execute_async(sa.update(CodexCredential).values(payload=payload))


@pytest.mark.asyncio
async def test_migration_upgrade_repeat_fk_cascade(auth):
    await run_alembic_upgrade(auth.engine, '0022_codex_credentials')
    await run_alembic_stamp(auth.engine, '0021_merge_reasoning_config')
    await run_alembic_upgrade(auth.engine, '0022_codex_credentials')
    with pytest.raises(sa.exc.IntegrityError):
        await auth.ap.persistence_mgr.execute_async(
            sa.insert(CodexCredential).values(
                provider_uuid='other', workspace_uuid='w', payload={}, version=0, lease_until=0
            )
        )
    await auth.ap.persistence_mgr.execute_async(sa.text("DELETE FROM model_providers WHERE uuid='p'"))
    assert await auth._read('w', 'p') is None
    from langbot.pkg.persistence.alembic_runner import run_alembic_downgrade

    await run_alembic_downgrade(auth.engine, '0021_merge_reasoning_config')
    async with auth.engine.connect() as conn:
        assert 'codex_credentials' not in await conn.run_sync(lambda sync: sa.inspect(sync).get_table_names())
    await run_alembic_upgrade(auth.engine, '0022_codex_credentials')
    async with auth.engine.connect() as conn:
        assert 'codex_credentials' in await conn.run_sync(lambda sync: sa.inspect(sync).get_table_names())


@pytest.mark.asyncio
async def test_device_pacing_exchange_secrecy_and_user_binding(auth):
    auth._post = AsyncMock(
        side_effect=[
            httpx.Response(200, json={'device_auth_id': 'device-secret', 'usercode': 'CODE', 'interval': '5'}),
            httpx.Response(200, json={'authorization_code': 'code-secret', 'code_verifier': 'verifier-secret'}),
            httpx.Response(200, json=token_response()),
        ]
    )
    start = await auth.start(context(), 'p')
    assert set(start) == {'authorization_id', 'user_code', 'interval', 'expires_at', 'verification_uri'}
    assert 'device-secret' not in json.dumps(start)
    attempt = start['authorization_id']
    with pytest.raises(WorkspaceNotFoundError):
        await auth.poll(context(user='attacker'), 'p', attempt)
    assert (await auth.poll(context(), 'p', attempt))['status'] == 'pending'
    assert auth._post.await_count == 1
    row = await auth._read('w', 'p')
    row['payload']['pending']['next_poll_at'] = 0
    await seed(auth, row['payload'])
    assert await auth.poll(context(), 'p', attempt) == {'status': 'connected'}
    assert await auth.poll(context(), 'p', attempt) == {'status': 'connected'}
    exchange = auth._post.call_args.kwargs['data']
    assert exchange['grant_type'] == 'authorization_code'
    assert exchange['redirect_uri'] == 'https://auth.openai.com/deviceauth/callback'
    assert exchange['code_verifier'] == 'verifier-secret'
    status = await auth.status(context(), 'p')
    assert set(status) == {'status', 'connected', 'expires_at'}
    assert 'secret' not in json.dumps(status)
    await auth.disconnect(context(), 'p')
    assert (await auth._read('w', 'p'))['payload'] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'ctx,provider,error',
    [
        (context('other'), 'p', WorkspaceNotFoundError),
        (context(principal=PrincipalType.API_KEY), 'p', ValueError),
        (context(permitted=False), 'p', ValueError),
        (context(), 'api', ValueError),
    ],
)
async def test_auth_tenant_principal_permission_guards(auth, ctx, provider, error):
    auth._post = AsyncMock()
    with pytest.raises(error):
        await auth.start(ctx, provider)
    auth._post.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_cross_instance_single_flight_and_rotation(auth):
    old = _tokens(token_response())
    old['expires_at'] = 0
    await seed(auth, {'tokens': old})
    entered, release = asyncio.Event(), asyncio.Event()

    async def refresh(*args, **kwargs):
        entered.set()
        await release.wait()
        return httpx.Response(200, json=token_response(refresh_token='rotated-secret'))

    auth._post = AsyncMock(side_effect=refresh)
    other = CodexAuth(auth.ap)
    other._post = auth._post
    first = asyncio.create_task(auth.access('w', 'p'))
    await entered.wait()
    second = asyncio.create_task(other.access('w', 'p'))
    release.set()
    a, b = await asyncio.gather(first, second)
    assert a == b
    assert a['refresh_token'] == 'rotated-secret'
    assert auth._post.await_count == 1
    assert (await auth._read('w', 'p'))['payload']['tokens'] == a


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'status,error,invalid',
    [
        (400, 'invalid_grant', True),
        (401, 'refresh_token_reused', True),
        (429, 'limited', False),
        (500, 'secret-upstream-body', False),
        (403, 'permission_denied', False),
    ],
)
async def test_refresh_errors_are_safe_and_transient_preserves_tokens(auth, status, error, invalid):
    old = _tokens(token_response())
    old['expires_at'] = 0
    await seed(auth, {'tokens': old})
    auth._post = AsyncMock(
        return_value=httpx.Response(status, json={'error': error, 'access_token': 'secret-upstream-body'})
    )
    with pytest.raises(ValueError) as caught:
        await auth.access('w', 'p')
    assert 'secret' not in str(caught.value)
    payload = (await auth._read('w', 'p'))['payload']
    assert bool(payload.get('invalid')) == invalid
    assert ('tokens' not in payload) if invalid else payload['tokens'] == old


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel', [False, True])
async def test_disconnect_or_cancel_fences_inflight_exchange(auth, cancel):
    old = _tokens(token_response())
    await seed(
        auth,
        {
            'tokens': old,
            'pending': {
                'authorization_id': 'attempt',
                'account_uuid': 'u',
                'expires_at': time.time() + 100,
                'next_poll_at': 0,
                'interval': 5,
                'device_auth_id': 'device',
                'user_code': 'code',
            },
        },
    )
    entered, release = asyncio.Event(), asyncio.Event()

    async def post(path, **kwargs):
        if path.endswith('/token') and path != '/oauth/token':
            return httpx.Response(200, json={'authorization_code': 'code', 'code_verifier': 'verifier'})
        entered.set()
        await release.wait()
        return httpx.Response(200, json=token_response())

    auth._post = post
    task = asyncio.create_task(auth.poll(context(), 'p', 'attempt'))
    await entered.wait()
    if cancel:
        await auth.cancel(context(), 'p', 'attempt')
    else:
        await auth.disconnect(context(), 'p')
    release.set()
    with pytest.raises(ValueError, match='cancelled or replaced'):
        await task
    payload = (await auth._read('w', 'p'))['payload']
    assert payload == ({'tokens': old} if cancel else {})


@pytest.mark.asyncio
@pytest.mark.parametrize('status,interval', [(403, 5), (404, 5), (429, 10)])
async def test_device_pending_and_backoff(auth, status, interval):
    await seed(
        auth,
        {
            'pending': {
                'authorization_id': 'attempt',
                'account_uuid': 'u',
                'expires_at': time.time() + 100,
                'next_poll_at': 0,
                'interval': 5,
                'device_auth_id': 'device',
                'user_code': 'code',
            }
        },
    )
    auth._post = AsyncMock(return_value=httpx.Response(status))
    assert await auth.poll(context(), 'p', 'attempt') == {'status': 'pending', 'interval': interval}
    assert await auth.poll(context(), 'p', 'attempt') == {'status': 'pending', 'interval': interval}
    assert auth._post.await_count == 1


@pytest.mark.asyncio
async def test_device_replacement_expiry_and_idempotent_cancel(auth):
    auth._post = AsyncMock(return_value=httpx.Response(200, json={'device_auth_id': 'device', 'user_code': 'CODE'}))
    first = await auth.start(context(), 'p')
    second = await auth.start(context(), 'p')
    assert first['authorization_id'] != second['authorization_id']
    assert await auth.poll(context(), 'p', first['authorization_id']) == {'status': 'expired'}
    await auth.cancel(context(), 'p', first['authorization_id'])
    payload = (await auth._read('w', 'p'))['payload']
    assert payload['pending']['authorization_id'] == second['authorization_id']
    payload['pending']['expires_at'] = 0
    await seed(auth, payload)
    assert await auth.poll(context(), 'p', second['authorization_id']) == {'status': 'expired'}
    assert 'pending' not in (await auth._read('w', 'p'))['payload']


@pytest.mark.asyncio
async def test_device_accepts_issuer_iso_expiry(auth):
    from datetime import datetime, timezone

    expires = datetime.fromtimestamp(time.time() + 600, timezone.utc).isoformat().replace('+00:00', 'Z')
    auth._post = AsyncMock(
        return_value=httpx.Response(200, json={'device_auth_id': 'device', 'user_code': 'CODE', 'expires_at': expires})
    )
    result = await auth.start(context(), 'p')
    assert time.time() < result['expires_at'] < time.time() + 900


@pytest.mark.asyncio
async def test_device_expires_in_fallback(auth):
    auth._post = AsyncMock(
        return_value=httpx.Response(200, json={'device_auth_id': 'device', 'user_code': 'CODE', 'expires_in': 60})
    )
    result = await auth.start(context(), 'p')
    assert time.time() < result['expires_at'] <= time.time() + 60


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel_reads_before_refresh', [False, True])
async def test_cancel_pending_relogin_waits_for_existing_refresh(auth, cancel_reads_before_refresh):
    old = _tokens(token_response())
    old['expires_at'] = 0
    await seed(auth, {'tokens': old, 'pending': {'authorization_id': 'attempt', 'account_uuid': 'u'}})
    entered, release, cancel_read = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def refresh(*args, **kwargs):
        entered.set()
        await release.wait()
        return httpx.Response(200, json=token_response(refresh_token='rotated-secret'))

    other = CodexAuth(auth.ap)
    original_read = other._read

    async def read(workspace, provider):
        row = await original_read(workspace, provider)
        cancel_read.set()
        if cancel_reads_before_refresh:
            await entered.wait()
        return row

    other._read = read
    auth._post = refresh
    if cancel_reads_before_refresh:
        cancelling = asyncio.create_task(other.cancel(context(), 'p', 'attempt'))
        await cancel_read.wait()
    refreshing = asyncio.create_task(auth.access('w', 'p'))
    await entered.wait()
    if not cancel_reads_before_refresh:
        cancelling = asyncio.create_task(other.cancel(context(), 'p', 'attempt'))
    await cancel_read.wait()
    await asyncio.sleep(0.05)
    try:
        assert not cancelling.done(), 'Cancellation must not revoke the refresh lease'
    finally:
        release.set()
        results = await asyncio.gather(refreshing, cancelling, return_exceptions=True)
    assert not any(isinstance(result, Exception) for result in results)
    payload = (await auth._read('w', 'p'))['payload']
    assert payload['tokens']['refresh_token'] == 'rotated-secret'
    assert 'pending' not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['save', 'cancel', 'disconnect', 'acquire', 'release', 'read'])
async def test_credential_database_errors_never_expose_secrets(auth, operation):
    import traceback

    markers = ['ACCESS-MARKER', 'REFRESH-MARKER', 'DEVICE-MARKER', 'VERIFIER-MARKER']
    payload = {
        'tokens': {'access_token': markers[0], 'refresh_token': markers[1]},
        'pending': {
            'authorization_id': 'attempt',
            'account_uuid': 'u',
            'device_auth_id': markers[2],
            'code_verifier': markers[3],
        },
    }
    await seed(auth, payload)
    if operation == 'read':
        auth.ap.persistence_mgr.execute_async = AsyncMock(
            side_effect=sa.exc.StatementError(
                'failure', 'SELECT credentials', {'payload': payload}, RuntimeError(markers[0])
            )
        )
    else:
        column = 'payload' if operation in ('save', 'cancel', 'disconnect') else 'lease_owner'
        condition = ' WHEN NEW.lease_owner IS NULL' if operation == 'release' else ''
        # Trigger errors can themselves contain secrets, even for parameter-free writes.
        await auth.ap.persistence_mgr.execute_async(
            sa.text(
                f'CREATE TRIGGER reject_write BEFORE UPDATE OF {column} ON codex_credentials{condition} '
                f"BEGIN SELECT RAISE(ABORT, '{' '.join(markers)}'); END"
            )
        )
    with pytest.raises(ValueError, match='credential storage') as caught:
        if operation == 'save':
            async with auth._lease('w', 'p') as owner:
                await auth._save('w', 'p', owner, payload)
        elif operation == 'cancel':
            await auth.cancel(context(), 'p', 'attempt')
        elif operation == 'disconnect':
            await auth.disconnect(context(), 'p')
        elif operation == 'read':
            await auth._read('w', 'p')
        else:
            async with auth._lease('w', 'p'):
                pass
    rendered = ''.join(traceback.format_exception(caught.value))
    assert all(marker not in rendered for marker in markers)
    assert caught.value.__suppress_context__


@pytest.mark.asyncio
async def test_credential_serialization_failure_is_sanitized(auth):
    import traceback

    class Secret:
        def __repr__(self):
            return 'SERIALIZATION-SECRET'

    with pytest.raises(ValueError, match='credential storage') as caught:
        async with auth._lease('w', 'p') as owner:
            await auth._save('w', 'p', owner, {'tokens': {'refresh_token': Secret()}})
    assert 'SERIALIZATION-SECRET' not in ''.join(traceback.format_exception(caught.value))
    assert caught.value.__suppress_context__


def test_token_refresh_fallback_and_config_validation():
    old = _tokens(token_response())
    refreshed = _tokens({'access_token': 'opaque-access', 'expires_in': 3600}, old)
    assert refreshed['refresh_token'] == old['refresh_token']
    assert refreshed['connection_id'] == old['connection_id']
    for expiry in [float('nan'), float('inf'), -1, 'bad']:
        with pytest.raises(ValueError):
            _tokens(token_response(expires_in=expiry))
    data = {'requester': 'openai-codex'}
    validate_config(data)
    assert data['api_keys'] == []
    for update in [{'base_url': 'https://evil.invalid'}, {'api_keys': ['secret']}]:
        with pytest.raises(ValueError):
            validate_config({**data, **update})
    ordinary = {'requester': 'openai-chat-completions', 'api_keys': ['key'], 'base_url': 'https://custom.invalid'}
    before = dict(ordinary)
    validate_config(ordinary)
    assert ordinary == before
