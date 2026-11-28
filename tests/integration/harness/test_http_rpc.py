"""Exercise the TS client against the production routes and real account services."""

import asyncio
import json
import logging
import os
import secrets
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from hypercorn.asyncio.run import worker_serve
from hypercorn.config import Config
from hypercorn.utils import wrap_app
from quart import request, send_file
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.controller.groups.harness import HarnessRouterGroup
from langbot.pkg.api.http.controller.main import HTTPController
from langbot.pkg.api.http.service.user import UserService
from langbot.pkg.entity.persistence.harness_instance_key import HarnessInstanceKey, HarnessKeyAck
from langbot.pkg.entity.persistence.harness_oauth import HarnessDevice, HarnessOAuthGrant
from langbot.pkg.entity.persistence.harness_registration import HarnessBinding, HarnessRegistrationLink
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState, WorkspaceMembership
from langbot.pkg.harness import wiring
from langbot.pkg.harness.binding import HarnessBindings
from langbot.pkg.utils import constants
from langbot.pkg.workspace.collaboration import WorkspaceCollaborationService
from langbot.pkg.workspace.service import WorkspaceService


def https_config(cert, key):
    config = Config()
    config.bind = ['127.0.0.1:0']
    config.certfile = str(cert)
    config.keyfile = str(key)
    # Exercise HTTP/1.1 Upgrade, not Node's experimental RFC 8441 client.
    config.alpn_protocols = ['http/1.1']
    config.graceful_timeout = 2
    return config


def application(engine, origin, secret, *, space=False, browser=False):
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={
            'system': {'jwt': {'secret': secret, 'expire': 60}},
            'harness': {'enabled': True, 'instance_origin': origin, 'client_origin': 'https://harness.example'},
        }),
        deployment=SimpleNamespace(mode='oss'),
        persistence_mgr=SimpleNamespace(get_db_engine=lambda: engine),
        logger=logging.getLogger(__name__),
    )
    space_workspace = os.getenv('SPACE_TEST_WORKSPACE')
    if space:
        ap.instance_config.data['harness']['space_oauth'] = {
            'enabled': True, 'space_origin': os.environ['SPACE_TEST_ORIGIN'],
            'workspace_uuid': space_workspace, 'redirect_uri': os.environ['SPACE_TEST_CALLBACK'],
        }
    if browser:
        ap.instance_config.data['harness']['client_origin'] = origin

    async def execute(statement):
        async with engine.connect() as conn:
            return await conn.execute(statement)

    ap.persistence_mgr.execute_async = execute
    ap.workspace_service = WorkspaceService(ap)
    ap.workspace_collaboration_service = WorkspaceCollaborationService(ap, ap.workspace_service)
    ap.user_service = UserService(ap)
    return ap


async def serve(ap, config, sockets, stop=None):
    await wiring.install(ap)
    controller = HTTPController(ap)
    controller.register_harness_route()
    await HarnessRouterGroup(ap, controller.quart_app).initialize()
    if stop is None:
        print(json.dumps({'pid': os.getpid(), 'port': sockets.secure_sockets[0].getsockname()[1]}), flush=True)
    await worker_serve(wrap_app(controller.quart_app, config.wsgi_max_body_size, None), config,
                       sockets=sockets, shutdown_trigger=stop)


async def observer_worker(settings):
    constants.instance_id = 'rpc-test-instance'
    engine = create_async_engine(settings['url'], connect_args=settings['connect_args'])
    config = https_config(settings['cert'], settings['key'])
    try:
        await serve(application(engine, settings['origin'], settings['secret']), config, config.create_sockets())
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.parametrize('scenario', ['oauth', 'planned', 'planned-race', 'emergency', 'space', 'space-browser'])
async def test_typescript_http_rpc(tmp_path, monkeypatch, scenario):
    space = scenario.startswith('space')
    browser = scenario == 'space-browser'
    if space and not os.getenv('SPACE_TEST_ORIGIN'):
        pytest.skip('Start the Space cross-repository fixture')
    space_workspace = os.getenv('SPACE_TEST_WORKSPACE')
    if browser and not os.getenv('HARNESS_PLAYWRIGHT'):
        pytest.skip('Set HARNESS_PLAYWRIGHT to playwright-core/index.mjs')
    if browser:
        assert Path(os.environ['HARNESS_BROWSER_BUNDLE']).is_file()
    transport = os.getenv('HARNESS_TS_RPC_TRANSPORT')
    if not transport:
        pytest.skip('Set HARNESS_TS_RPC_TRANSPORT to the built Harness core rpc-transport.js')
    assert Path(transport).is_file()
    rotation_token = secrets.token_urlsafe(32)
    monkeypatch.setenv('LANGBOT_HARNESS_ROTATION_TOKEN', rotation_token)
    monkeypatch.setattr(constants, 'instance_id', 'rpc-test-instance')
    config = https_config(tmp_path / 'cert.pem', tmp_path / 'key.pem')
    subprocess.run(
        ['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
         '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1',
         '-keyout', config.keyfile, '-out', config.certfile],
        check=True, capture_output=True,
    )
    postgres = os.getenv('HARNESS_TEST_POSTGRES_URL')
    url = postgres or f'sqlite+aiosqlite:///{tmp_path / "rpc.db"}'
    schema = f'harness_rpc_{uuid.uuid4().hex}'
    connect_args = {'server_settings': {'search_path': schema}} if postgres else {}
    if postgres:
        assert sa.make_url(postgres).drivername == 'postgresql+asyncpg'
    engine = create_async_engine(url, connect_args=connect_args)
    sockets = config.create_sockets()
    origin = f'https://127.0.0.1:{sockets.secure_sockets[0].getsockname()[1]}'
    secret = secrets.token_hex(32)
    stop = asyncio.Event()
    server = None
    observer = None
    process = None
    try:
        ap = application(engine, origin, secret, space=space, browser=browser)
        async with engine.begin() as conn:
            if postgres:
                await conn.execute(sa.schema.CreateSchema(schema))
            for model in (User, Workspace, WorkspaceExecutionState, WorkspaceMembership, HarnessRegistrationLink,
                          HarnessBinding, HarnessInstanceKey, HarnessKeyAck, HarnessDevice, HarnessOAuthGrant):
                await conn.run_sync(model.__table__.create)
        email, password = 'harness-rpc@example.test', secrets.token_urlsafe(32)
        account = await ap.user_service.create_initial_account(email, password)
        assert await ap.user_service.authenticate(email, password)
        workspace = await ap.workspace_service.get_singleton_workspace()
        async with engine.begin() as conn:
            for workspace_id, name in (('shared', 'Shared Workspace'), ('private', 'Private Workspace')):
                await conn.execute(sa.insert(Workspace).values(
                    uuid=workspace_id, instance_uuid=constants.instance_id, name=name,
                    slug=workspace_id, source='cloud_projection',
                ))
                await conn.execute(sa.insert(WorkspaceExecutionState).values(
                    workspace_uuid=workspace_id, instance_uuid=constants.instance_id, source='cloud', active_generation=2,
                ))
            await conn.execute(sa.insert(WorkspaceMembership).values(
                workspace_uuid='shared', account_uuid=account.uuid, role='viewer',
            ))
            if space:
                await conn.execute(sa.update(User).where(User.uuid == account.uuid).values(
                    space_account_uuid=os.environ['SPACE_TEST_ACCOUNT'],
                ))
                await conn.execute(sa.insert(Workspace).values(
                    uuid=space_workspace, instance_uuid=constants.instance_id, name='Harness pilot',
                    slug='harness-pilot', source='cloud_projection',
                ))
                await conn.execute(sa.insert(WorkspaceExecutionState).values(
                    workspace_uuid=space_workspace, instance_uuid=constants.instance_id, source='cloud', active_generation=2,
                ))
                await conn.execute(sa.insert(WorkspaceMembership).values(
                    workspace_uuid=space_workspace, account_uuid=account.uuid, role='owner',
                ))
        await wiring.install(ap)
        bindings = HarnessBindings(ap)
        target_workspace = space_workspace if space else workspace.uuid
        issuer = SimpleNamespace(workspace_uuid=target_workspace, account_uuid=account.uuid)
        links = [await bindings.issue(issuer, label='RPC smoke', preferred_auth='space' if space else 'local')
                 for _ in range(2)]
        controller = HTTPController(ap)
        controller.register_harness_route()
        app = controller.quart_app
        await HarnessRouterGroup(ap, app).initialize()
        if space:
            membership_token = secrets.token_urlsafe(32)

            @app.post('/_test/membership/<status>')
            async def membership(status):
                assert request.headers.get('Authorization') == f'Bearer {membership_token}'
                assert status in ('active', 'removed')
                async with engine.begin() as conn:
                    await conn.execute(sa.update(WorkspaceMembership).where(
                        WorkspaceMembership.workspace_uuid == space_workspace,
                        WorkspaceMembership.account_uuid == account.uuid,
                    ).values(status=status))
                return '', 204
        if browser:
            @app.get('/_test/harness')
            async def browser_entry():
                return '<!doctype html><title>Harness OAuth fixture</title>'

            @app.get('/_test/core.js')
            async def core_module():
                return await send_file(Path(os.environ['HARNESS_BROWSER_BUNDLE']).resolve(), mimetype='text/javascript')

            @app.get('/_test/binding-count')
            async def binding_count():
                async with engine.connect() as conn:
                    return str(await conn.scalar(sa.select(sa.func.count()).select_from(HarnessBinding)))
        observer_origin = origin
        if not space and scenario != 'oauth':
            observer = await asyncio.create_subprocess_exec(
                sys.executable, str(Path(__file__).resolve()), stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
            observer.stdin.write(json.dumps(dict(url=url, connect_args=connect_args, origin=origin, secret=secret,
                                                  cert=config.certfile, key=config.keyfile)).encode() + b'\n')
            await observer.stdin.drain()
            observer.stdin.close()
            async with asyncio.timeout(15):
                ready = await observer.stdout.readline()
            assert ready, 'HTTPS observer exited before startup; see captured stderr'
            worker = json.loads(ready)
            assert worker['pid'] == observer.pid != os.getpid()
            observer_origin = f'https://127.0.0.1:{worker["port"]}'
            print(f'{scenario}: HTTPS PIDs {os.getpid()}, {observer.pid} ({engine.dialect.name})')
        server = asyncio.create_task(worker_serve(
            wrap_app(app, config.wsgi_max_body_size, None), config, sockets=sockets, shutdown_trigger=stop.wait,
        ))
        node_certs = tmp_path / 'node-certs.pem'
        node_certs.write_bytes(Path(config.certfile).read_bytes() + (
            Path(os.environ['SPACE_TEST_CERT']).read_bytes() if space else b''
        ))
        process = await asyncio.create_subprocess_exec(
            'node', str(Path(__file__).with_name('space-browser.mjs' if browser else 'http-rpc-smoke.mjs')),
            env={**os.environ, 'NODE_EXTRA_CA_CERTS': str(node_certs), 'HARNESS_RPC_TEST': json.dumps({
                'origin': origin, 'links': [link['url'] for link in links],
                'email': email, 'password': password, 'workspace': target_workspace,
                'browserAccountToken': await ap.user_service.generate_jwt_token(account),
                'scenario': scenario, 'rotationToken': rotation_token, 'observerOrigin': observer_origin,
                'membershipToken': membership_token if space else '',
            })}, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        async with asyncio.timeout(30):
            stdout, stderr = await process.communicate()
        print(stdout.decode(), end='')
        assert process.returncode == 0, stderr.decode()
        async with engine.connect() as conn:
            if space:
                grants = (await conn.execute(sa.select(HarnessOAuthGrant.__table__))).mappings().all()
                assert len(grants) == 1 and grants[0]['account_uuid'] == account.uuid
                assert grants[0]['workspace_uuid'] == space_workspace
                assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessBinding)) == 1
                assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessDevice).where(
                    HarnessDevice.account_uuid.is_not(None),
                )) == 1
                return
            if scenario != 'oauth':
                assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessBinding)) == 2
                retired = (await conn.execute(sa.select(HarnessInstanceKey).where(
                    HarnessInstanceKey.status == 'retired',
                ))).mappings().all()
                assert len(retired) == (2 if scenario == 'emergency' else 1)
                assert all(not key['priv_ciphertext'] for key in retired)
                assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessKeyAck)) == (
                    0 if scenario == 'emergency' else 2
                )
                return
            grants = (await conn.execute(sa.select(HarnessOAuthGrant.__table__))).mappings().all()
            assert len(grants) == 3
            assert all(grant['account_uuid'] == account.uuid for grant in grants)
            assert any(g['workspace_uuid'] == workspace.uuid and g['refresh_generation'] == 1
                       and g['revoked_at'] is not None for g in grants)
            assert any(g['workspace_uuid'] == 'shared' and g['refresh_generation'] == 1
                       and g['revoked_at'] is None for g in grants)
            assert await conn.scalar(sa.select(sa.func.count()).select_from(HarnessBinding)) == 1
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        try:
            if observer is not None and observer.returncode is None:
                observer.terminate()
                try:
                    await asyncio.wait_for(observer.wait(), 5)
                except TimeoutError:
                    observer.kill()
                    await observer.wait()
            if server is not None:
                stop.set()
                await server
        finally:
            for sock in sockets.secure_sockets:
                sock.close()
            try:
                if postgres:
                    async with engine.begin() as conn:
                        await conn.execute(sa.schema.DropSchema(schema, cascade=True, if_exists=True))
            finally:
                await engine.dispose()


if __name__ == '__main__':
    asyncio.run(observer_worker(json.load(sys.stdin)))
