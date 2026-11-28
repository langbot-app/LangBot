"""Run the shared Harness UI against the real Core TOTP, HTS1 and WSS routes."""

import asyncio
import json
import os
import secrets
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from hypercorn.asyncio.run import worker_serve
from hypercorn.utils import wrap_app
from quart import request, send_file, send_from_directory
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.controller.groups.harness import HarnessRouterGroup
from langbot.pkg.api.http.controller.main import HTTPController
from langbot.pkg.api.http.service import totp
from langbot.pkg.entity.persistence.harness_instance_key import HarnessInstanceKey, HarnessKeyAck
from langbot.pkg.entity.persistence.harness_oauth import HarnessDevice, HarnessHandoff, HarnessOAuthGrant
from langbot.pkg.entity.persistence.harness_registration import HarnessBinding, HarnessRegistrationLink
from langbot.pkg.entity.persistence.totp import TotpCredential, TotpRecoveryCode
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState, WorkspaceMembership
from langbot.pkg.harness import wiring
from langbot.pkg.harness.binding import HarnessBindings
from langbot.pkg.harness.oauth import HarnessOAuthService
from langbot.pkg.utils import constants

from test_http_rpc import application, https_config


@pytest.mark.integration
@pytest.mark.parametrize('scenario', ['approve', 'cancel', 'expire', 'other-device'])
async def test_handoff_chromium(tmp_path, monkeypatch, scenario):
    if not os.getenv('HARNESS_WEB_DIST'):
        pytest.skip('Set HARNESS_WEB_DIST to the built Harness Web app')
    dist = Path(os.environ['HARNESS_WEB_DIST']).resolve()
    bundle = Path(os.environ['HARNESS_HANDOFF_TEST_BUNDLE']).resolve()
    assert (dist / 'index.html').is_file() and bundle.is_file()
    monkeypatch.setattr(constants, 'instance_id', 'handoff-test-instance')
    config = https_config(tmp_path / 'cert.pem', tmp_path / 'key.pem')
    subprocess.run(
        ['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
         '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1',
         '-keyout', config.keyfile, '-out', config.certfile], check=True, capture_output=True,
    )
    sockets = config.create_sockets()
    origin = f'https://127.0.0.1:{sockets.secure_sockets[0].getsockname()[1]}'
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "handoff.db"}')
    ap = application(engine, origin, secrets.token_hex(32))
    ap.instance_config.data['harness']['client_origin'] = origin
    ap.totp_service = totp.TotpService(ap)
    async with engine.begin() as conn:
        for model in (User, Workspace, WorkspaceExecutionState, WorkspaceMembership, TotpCredential, TotpRecoveryCode,
                      HarnessRegistrationLink, HarnessBinding, HarnessInstanceKey, HarnessKeyAck, HarnessDevice,
                      HarnessOAuthGrant, HarnessHandoff):
            await conn.run_sync(model.__table__.create)

    email, password = 'handoff@example.test', secrets.token_urlsafe(32)
    account = await ap.user_service.create_initial_account(email, password)
    workspace = await ap.workspace_service.get_singleton_workspace()
    await ap.totp_service.begin_enrollment(account.uuid, email)
    credential = await ap.totp_service.get_credential(account.uuid)
    secret = ap.totp_service._decrypt_secret(credential.secret_ciphertext, credential.key_version).decode()
    key = totp._decode_secret(secret)
    await ap.totp_service.confirm_enrollment(account.uuid, totp._hotp(key, totp._totp_counter(30) - 1, 6))
    await wiring.install(ap)
    bindings = HarnessBindings(ap)
    issuer = SimpleNamespace(workspace_uuid=workspace.uuid, account_uuid=account.uuid)
    links = [await bindings.issue(issuer, label='Local TOTP instance', preferred_auth='local') for _ in range(2)]
    controller = HTTPController(ap)
    controller.register_harness_route()
    app = controller.quart_app
    await HarnessRouterGroup(ap, app).initialize()
    probe_key = secrets.token_urlsafe(32)
    issued = {}
    issue_grant = HarnessOAuthService._issue_grant

    async def observe_grant(self, *args):
        result = await issue_grant(self, *args)
        issued.update(result)
        return result

    monkeypatch.setattr(HarnessOAuthService, '_issue_grant', observe_grant)

    @app.get('/_test/core.js')
    async def client_probe():
        return await send_file(bundle, mimetype='text/javascript')

    @app.post('/_test/<action>')
    async def browser_probe(action):
        assert request.headers.get('Authorization') == f'Bearer {probe_key}'
        if action == 'expire':
            async with engine.begin() as conn:
                assert (await conn.execute(sa.update(HarnessHandoff).values(expires_at=int(time.time()) - 1))).rowcount == 1
        if action == 'code':
            return {'code': totp._hotp(key, totp._totp_counter(30), 6)}
        if action == 'grant':
            return {'token': issued['access_token']}
        async with engine.connect() as conn:
            return {model.__tablename__: await conn.scalar(sa.select(sa.func.count()).select_from(model))
                    for model in (HarnessBinding, HarnessOAuthGrant)}

    @app.get('/')
    async def index():
        return await send_from_directory(dist, 'index.html')

    @app.get('/assets/<path:filename>')
    async def asset(filename):
        return await send_from_directory(dist / 'assets', filename)

    stop = asyncio.Event()
    server = asyncio.create_task(worker_serve(wrap_app(app, config.wsgi_max_body_size, None), config,
                                                sockets=sockets, shutdown_trigger=stop.wait))
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            'node', str(Path(__file__).with_name('handoff-browser.mjs')),
            env={**os.environ, 'HARNESS_TOTP_TEST': json.dumps(dict(origin=origin, email=email, password=password,
                  links=[link['url'] for link in links], scenario=scenario, probe=probe_key, workspace=workspace.uuid,
                  account=account.uuid))},
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        async with asyncio.timeout(35):
            stdout, stderr = await process.communicate()
        assert process.returncode == 0, stderr.decode()
        print(stdout.decode(), end='')
        async with engine.connect() as conn:
            expected = int(scenario == 'approve')
            assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessBinding)) == expected
            assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessOAuthGrant)) == expected
            assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessDevice).where(
                HarnessDevice.account_uuid.is_not(None),
            )) == expected
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        stop.set()
        await server
        await engine.dispose()
