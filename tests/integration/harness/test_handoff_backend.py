"""Backend-only coverage for the TOTP browser handoff state machine.

``test_handoff_browser.py`` drives the real UI and needs a built Harness Web
bundle. These cases exercise the same Core paths without a browser, so the
handoff has runnable coverage where the private web build is unavailable.
"""

import base64
import json
import os
import secrets
import time
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.service import totp
from langbot.pkg.entity.persistence.harness_instance_key import HarnessInstanceKey, HarnessKeyAck
from langbot.pkg.entity.persistence.harness_oauth import HarnessDevice, HarnessHandoff, HarnessOAuthGrant
from langbot.pkg.entity.persistence.harness_registration import HarnessBinding, HarnessRegistrationLink
from langbot.pkg.entity.persistence.totp import TotpCredential, TotpRecoveryCode
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState, WorkspaceMembership
from langbot.pkg.harness.binding import HarnessBindings
from langbot.pkg.harness.handoff import HandoffRequired, HarnessHandoffs
from langbot.pkg.harness.oauth import HarnessOAuthService
from langbot.pkg.utils import constants
from langbot.pkg.workspace.errors import WorkspaceNotFoundError

from test_http_rpc import application

MODELS = (
    User,
    Workspace,
    WorkspaceExecutionState,
    WorkspaceMembership,
    TotpCredential,
    TotpRecoveryCode,
    HarnessRegistrationLink,
    HarnessBinding,
    HarnessInstanceKey,
    HarnessKeyAck,
    HarnessDevice,
    HarnessOAuthGrant,
    HarnessHandoff,
)


async def _setup(tmp_path, monkeypatch):
    """One enrolled-instance account, two devices, and a TOTP credential."""
    monkeypatch.setattr(constants, 'instance_id', 'handoff-unit-instance')
    # HARNESS_TEST_POSTGRES_URL runs these against a real server in a disposable
    # schema; without it they stay on SQLite.
    postgres = os.getenv('HARNESS_TEST_POSTGRES_URL')
    if postgres:
        assert sa.make_url(postgres).drivername == 'postgresql+asyncpg'
        schema = f'harness_handoff_{uuid.uuid4().hex}'
        engine = create_async_engine(postgres, connect_args={'server_settings': {'search_path': schema}})
        async with engine.begin() as conn:
            await conn.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS {schema}'))
    else:
        engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "handoff.db"}')
    ap = application(engine, 'https://127.0.0.1:5399', secrets.token_hex(32))
    ap.totp_service = totp.TotpService(ap)
    async with engine.begin() as conn:
        for model in MODELS:
            await conn.run_sync(model.__table__.create)

    email, password = 'handoff@example.test', secrets.token_urlsafe(32)
    account = await ap.user_service.create_initial_account(email, password)
    ap.test_password = password
    workspace = await ap.workspace_service.get_singleton_workspace()
    await ap.totp_service.begin_enrollment(account.uuid, email)
    credential = await ap.totp_service.get_credential(account.uuid)
    secret = ap.totp_service._decrypt_secret(credential.secret_ciphertext, credential.key_version).decode()
    key = totp._decode_secret(secret)
    await ap.totp_service.confirm_enrollment(account.uuid, totp._hotp(key, totp._totp_counter(30) - 1, 6))

    bindings = HarnessBindings(ap)
    issuer = type('Issuer', (), {'workspace_uuid': workspace.uuid, 'account_uuid': account.uuid})()
    service = HarnessOAuthService(ap)
    devices = []
    # Each enrollment token is single use, so every device needs its own link.
    for index in range(2):
        link = await bindings.issue(issuer, label='Local instance', preferred_auth='local')
        enrollment = await bindings.redeem(_link_token(link))
        enrolled = await service.register_device(
            link['id'],
            enrollment['enrollment_token'],
            {
                'device_kid': f'kid-{index}',
                'x25519_pub': 'A' * 43 + '=',
                'ed25519_pub': 'B' * 43 + '=',
                'platform': 'test',
            },
        )
        devices.append({**enrolled, 'binding_id': link['id']})
    return ap, engine, account, workspace, credential, key, service, devices, await _serving_kid(engine)


async def _serving_kid(engine):
    """The instance key kid currently serving this instance."""
    async with engine.connect() as conn:
        from langbot.pkg.harness.binding import _KEY

        return await conn.scalar(sa.select(_KEY.c.kid).limit(1))


def _link_token(link):
    """The enrollment token rides in the URL fragment as base64url JSON."""
    fragment = link['url'].split('#', 1)[1]
    padded = fragment + '=' * (-len(fragment) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))['token']


def _code(key):
    return totp._hotp(key, totp._totp_counter(30), 6)


@pytest.mark.asyncio
async def test_issue_requires_an_enrolled_totp_credential(tmp_path, monkeypatch):
    ap, engine, account, workspace, credential, key, service, devices, kid = await _setup(tmp_path, monkeypatch)
    try:
        handoffs = HarnessHandoffs(ap)
        async with engine.begin() as conn:
            await conn.execute(sa.update(TotpCredential).values(confirmed_at=None))
        with pytest.raises(ValueError) as raised:
            await handoffs.issue(devices[0]['binding_id'], devices[0]['device_id'], account, workspace.uuid)
        assert str(raised.value) == 'invalid_grant'
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_issue_requires_a_workspace_membership(tmp_path, monkeypatch):
    """An account with no membership in the workspace gets no ticket.

    ``issue`` resolves the membership before it touches the credential, and that
    lookup raises ``WorkspaceNotFoundError`` (not ``ValueError``) for an outsider.
    """
    ap, engine, account, workspace, credential, key, service, devices, kid = await _setup(tmp_path, monkeypatch)
    try:
        handoffs = HarnessHandoffs(ap)
        other = type('Account', (), {'uuid': 'someone-else'})()
        with pytest.raises(WorkspaceNotFoundError):
            await handoffs.issue(devices[0]['binding_id'], devices[0]['device_id'], other, workspace.uuid)
        async with engine.connect() as conn:
            assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessHandoff)) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_full_approve_then_single_use_redemption(tmp_path, monkeypatch):
    ap, engine, account, workspace, credential, key, service, devices, kid = await _setup(tmp_path, monkeypatch)
    try:
        handoffs = HarnessHandoffs(ap)
        binding, device = devices[0]['binding_id'], devices[0]['device_id']
        details = await handoffs.issue(binding, device, account, workspace.uuid)
        ticket = details['handoff_ticket']

        assert details['expires_in'] == 180
        assert ticket in details['handoff_url']
        assert await handoffs.preview(ticket) is not None

        # Polling before approval reports pending, not a grant.
        with pytest.raises(ValueError) as raised:
            await handoffs.poll(service, ticket, binding, device, kid)
        assert str(raised.value) == 'authorization_pending'

        assert await handoffs.decide(ticket, code=_code(key)) == 'approved'
        result = await handoffs.poll(service, ticket, binding, device, kid)
        assert result['access_token'] and result['workspace_uuid'] == workspace.uuid

        # The ticket is single use: a second redemption cannot mint another grant.
        with pytest.raises(ValueError) as raised:
            await handoffs.poll(service, ticket, binding, device, kid)
        assert str(raised.value) == 'invalid_grant'
        async with engine.connect() as conn:
            assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessOAuthGrant)) == 1
            assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessBinding)) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancel_creates_no_binding_or_grant(tmp_path, monkeypatch):
    ap, engine, account, workspace, credential, key, service, devices, kid = await _setup(tmp_path, monkeypatch)
    try:
        handoffs = HarnessHandoffs(ap)
        binding, device = devices[0]['binding_id'], devices[0]['device_id']
        ticket = (await handoffs.issue(binding, device, account, workspace.uuid))['handoff_ticket']

        assert await handoffs.decide(ticket) == 'cancelled'
        with pytest.raises(ValueError):
            await handoffs.poll(service, ticket, binding, device, kid)
        async with engine.connect() as conn:
            assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessOAuthGrant)) == 0
            assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessBinding)) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_expired_ticket_redeems_nothing(tmp_path, monkeypatch):
    ap, engine, account, workspace, credential, key, service, devices, kid = await _setup(tmp_path, monkeypatch)
    try:
        handoffs = HarnessHandoffs(ap)
        binding, device = devices[0]['binding_id'], devices[0]['device_id']
        ticket = (await handoffs.issue(binding, device, account, workspace.uuid))['handoff_ticket']
        assert await handoffs.decide(ticket, code=_code(key)) == 'approved'
        async with engine.begin() as conn:
            await conn.execute(sa.update(HarnessHandoff).values(expires_at=int(time.time()) - 1))

        assert await handoffs.preview(ticket) is None
        with pytest.raises(ValueError):
            await handoffs.poll(service, ticket, binding, device, kid)
        async with engine.connect() as conn:
            assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessOAuthGrant)) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_another_registered_device_cannot_redeem(tmp_path, monkeypatch):
    ap, engine, account, workspace, credential, key, service, devices, kid = await _setup(tmp_path, monkeypatch)
    try:
        handoffs = HarnessHandoffs(ap)
        binding = devices[0]['binding_id']
        ticket = (await handoffs.issue(binding, devices[0]['device_id'], account, workspace.uuid))['handoff_ticket']
        assert await handoffs.decide(ticket, code=_code(key)) == 'approved'

        # Same ticket, different device on the same binding.
        with pytest.raises(ValueError) as raised:
            await handoffs.poll(service, ticket, binding, devices[1]['device_id'], kid)
        assert str(raised.value) == 'invalid_grant'
        async with engine.connect() as conn:
            assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessOAuthGrant)) == 0

        # The initiating device can still redeem it afterwards.
        result = await handoffs.poll(service, ticket, binding, devices[0]['device_id'], kid)
        assert result['access_token']
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_wrong_code_is_rejected_and_counted_against_the_attempt_cap(tmp_path, monkeypatch):
    ap, engine, account, workspace, credential, key, service, devices, kid = await _setup(tmp_path, monkeypatch)
    try:
        handoffs = HarnessHandoffs(ap)
        binding, device = devices[0]['binding_id'], devices[0]['device_id']
        ticket = (await handoffs.issue(binding, device, account, workspace.uuid))['handoff_ticket']

        assert await handoffs.decide(ticket, code='000000') == 'invalid'
        assert await handoffs.decide(ticket, code=_code(key)) == 'approved'
        async with engine.connect() as conn:
            # Each decide() consumes one guess, so a wrong then a right code is two.
            assert (await conn.execute(sa.select(HarnessHandoff))).mappings().one()['attempts'] == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_a_second_ticket_for_the_same_account_is_refused(tmp_path, monkeypatch):
    ap, engine, account, workspace, credential, key, service, devices, kid = await _setup(tmp_path, monkeypatch)
    try:
        handoffs = HarnessHandoffs(ap)
        binding, device = devices[0]['binding_id'], devices[0]['device_id']
        await handoffs.issue(binding, device, account, workspace.uuid)

        with pytest.raises(ValueError) as raised:
            await handoffs.issue(binding, device, account, workspace.uuid)
        assert str(raised.value) == 'handoff_already_pending'
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_password_grant_raises_handoff_for_a_second_factor_account(tmp_path, monkeypatch):
    """The HTS1 password grant must hand off, not fail, when TOTP is enrolled."""
    ap, engine, account, workspace, credential, key, service, devices, kid = await _setup(tmp_path, monkeypatch)
    try:
        with pytest.raises(HandoffRequired) as raised:
            await service.password_grant(
                devices[0]['binding_id'],
                {
                    'grant_type': 'password',
                    'device_id': devices[0]['device_id'],
                    'username': account.user,
                    'password': ap.test_password,
                    'workspace_uuid': workspace.uuid,
                },
            )
        assert raised.value.details['handoff_ticket']
        async with engine.connect() as conn:
            assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessOAuthGrant)) == 0
    finally:
        await engine.dispose()


def _link_kid(link):
    """The enrollment link carries the instance key kid it was issued against."""
    return link['kid']
    return link['kid']
