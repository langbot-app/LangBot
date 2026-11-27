"""Exercise the TS client against the production routes and real account services."""

import asyncio
import json
import logging
import os
import secrets
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from hypercorn.asyncio.run import worker_serve
from hypercorn.config import Config
from hypercorn.utils import wrap_app
from quart import Quart
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.controller.groups.harness import HarnessRouterGroup
from langbot.pkg.api.http.service.user import UserService
from langbot.pkg.entity.persistence.harness_instance_key import HarnessInstanceKey
from langbot.pkg.entity.persistence.harness_oauth import HarnessDevice, HarnessOAuthGrant
from langbot.pkg.entity.persistence.harness_registration import HarnessBinding, HarnessRegistrationLink
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState, WorkspaceMembership
from langbot.pkg.harness import wiring
from langbot.pkg.harness.binding import HarnessBindings
from langbot.pkg.utils import constants
from langbot.pkg.workspace.collaboration import WorkspaceCollaborationService
from langbot.pkg.workspace.service import WorkspaceService


@pytest.mark.integration
async def test_typescript_http_rpc(tmp_path, monkeypatch):
    transport = os.getenv('HARNESS_TS_RPC_TRANSPORT')
    if not transport:
        pytest.skip('Set HARNESS_TS_RPC_TRANSPORT to the built Harness core rpc-transport.js')
    assert Path(transport).is_file()
    monkeypatch.setattr(constants, 'instance_id', 'rpc-test-instance')
    config = Config()
    config.bind = ['127.0.0.1:0']
    config.certfile = str(tmp_path / 'cert.pem')
    config.keyfile = str(tmp_path / 'key.pem')
    subprocess.run(
        ['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
         '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1',
         '-keyout', config.keyfile, '-out', config.certfile],
        check=True, capture_output=True,
    )
    sockets = config.create_sockets()
    origin = f'https://127.0.0.1:{sockets.secure_sockets[0].getsockname()[1]}'
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "rpc.db"}')
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={
            'system': {'jwt': {'secret': secrets.token_hex(32), 'expire': 60}},
            'harness': {'enabled': True, 'instance_origin': origin, 'client_origin': 'https://harness.example'},
        }),
        deployment=SimpleNamespace(mode='oss'),
        persistence_mgr=SimpleNamespace(get_db_engine=lambda: engine),
        logger=logging.getLogger(__name__),
    )

    async def execute(statement):
        async with engine.connect() as conn:
            return await conn.execute(statement)

    ap.persistence_mgr.execute_async = execute
    ap.workspace_service = WorkspaceService(ap)
    ap.workspace_collaboration_service = WorkspaceCollaborationService(ap, ap.workspace_service)
    ap.user_service = UserService(ap)
    stop = asyncio.Event()
    server = None
    process = None
    try:
        async with engine.begin() as conn:
            for model in (User, Workspace, WorkspaceExecutionState, WorkspaceMembership, HarnessRegistrationLink,
                          HarnessBinding, HarnessInstanceKey, HarnessDevice, HarnessOAuthGrant):
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
        await wiring.install(ap)
        bindings = HarnessBindings(ap)
        issuer = SimpleNamespace(workspace_uuid=workspace.uuid, account_uuid=account.uuid)
        links = [await bindings.issue(issuer, label='RPC smoke', preferred_auth='local') for _ in range(2)]
        app = Quart(__name__)
        await HarnessRouterGroup(ap, app).initialize()
        server = asyncio.create_task(worker_serve(
            wrap_app(app, config.wsgi_max_body_size, None), config, sockets=sockets, shutdown_trigger=stop.wait,
        ))
        process = await asyncio.create_subprocess_exec(
            'node', str(Path(__file__).with_name('http-rpc-smoke.mjs')),
            env={**os.environ, 'NODE_EXTRA_CA_CERTS': config.certfile, 'HARNESS_RPC_TEST': json.dumps({
                'origin': origin, 'links': [link['url'] for link in links],
                'email': email, 'password': password, 'workspace': workspace.uuid,
            })}, stderr=asyncio.subprocess.PIPE,
        )
        async with asyncio.timeout(30):
            _, stderr = await process.communicate()
        assert process.returncode == 0, stderr.decode()
        async with engine.connect() as conn:
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
        if server is not None:
            stop.set()
            await server
        else:
            for sock in sockets.secure_sockets:
                sock.close()
        await engine.dispose()
