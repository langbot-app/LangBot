"""Cross-repository TCP smoke test using the published TypeScript client."""

import asyncio
import base64
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from hypercorn.asyncio.run import worker_serve
from hypercorn.config import Config
from hypercorn.utils import wrap_app
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.controller.main import HTTPController
from langbot.pkg.api.http.service.totp import _derive_wrapping_key
from langbot.pkg.api.http.service.user import UserService
from langbot.pkg.entity.persistence.agent import Agent
from langbot.pkg.entity.persistence.harness_instance_key import HarnessInstanceKey
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceMembership
from langbot.pkg.harness.crypto.transport import HarnessTransportFactory
from langbot.pkg.platform.adapters.harness.adapter import HarnessAdapter
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain


def b64(data):
    return base64.b64encode(data).decode()


@pytest.mark.integration
async def test_typescript_chat_over_network(tmp_path):
    transport = os.getenv('HARNESS_TS_TRANSPORT')
    if not transport:
        pytest.skip('Set HARNESS_TS_TRANSPORT to the built Harness core transport.js')
    assert Path(transport).is_file()
    server_x, client_x = [x25519.X25519PrivateKey.generate() for _ in range(2)]
    server_ed, client_ed = [ed25519.Ed25519PrivateKey.generate() for _ in range(2)]
    secret = 'integration-test-instance-secret-32-bytes'
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "harness.db"}')
    bundle = json.dumps({'x25519': b64(server_x.private_bytes_raw()), 'ed25519': b64(server_ed.private_bytes_raw())})
    account = User(
        uuid='account',
        user='person@example.test',
        normalized_email='person@example.test',
        status='active',
        projection_revision=0,
    )
    async with engine.begin() as db:
        for model in (User, Workspace, WorkspaceMembership, Agent, HarnessInstanceKey):
            await db.run_sync(model.__table__.create)
        await db.execute(
            User.__table__.insert().values(
                uuid=account.uuid,
                user=account.user,
                normalized_email=account.normalized_email,
                status='active',
                password='',
            )
        )
        await db.execute(
            Workspace.__table__.insert().values(
                uuid='workspace', instance_uuid='instance', name='Workspace', slug='workspace'
            )
        )
        await db.execute(
            WorkspaceMembership.__table__.insert().values(
                uuid='membership', workspace_uuid='workspace', account_uuid='account', status='active', role='viewer'
            )
        )
        await db.execute(Agent.__table__.insert().values(uuid='agent', workspace_uuid='workspace', name='Agent'))
        await db.execute(
            HarnessInstanceKey.__table__.insert().values(
                kid='server-kid',
                x25519_pub=b64(server_x.public_key().public_bytes_raw()),
                ed25519_pub=b64(server_ed.public_key().public_bytes_raw()),
                priv_ciphertext=Fernet(_derive_wrapping_key(secret, 1)).encrypt(bundle.encode()).decode(),
            )
        )

    async def execute(statement):
        async with engine.connect() as db:
            return await db.execute(statement)

    workspace_access = SimpleNamespace(
        workspace=SimpleNamespace(uuid='workspace'),
        execution=SimpleNamespace(instance_uuid='instance', placement_generation=1),
        membership=SimpleNamespace(uuid='membership', role='viewer', projection_revision=0),
    )
    adapter = HarnessAdapter.model_construct(config={}, logger=SimpleNamespace(), listeners={})
    dispatches = []

    async def dispatch(event, processor):
        assert processor == 'agent'
        dispatches.append((event.chat_id, event.source_platform_object['harness_connection_id']))
        await adapter.reply_message(event, MessageChain([Plain(text='pong')]))

    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={'system': {'jwt': {'secret': secret, 'expire': 60}}}),
        workspace_service=SimpleNamespace(instance_uuid='instance'),
        workspace_collaboration_service=SimpleNamespace(
            resolve_account_workspace=AsyncMock(return_value=workspace_access)
        ),
        persistence_mgr=SimpleNamespace(get_db_engine=lambda: engine, execute_async=execute),
        bot_service=SimpleNamespace(
            ensure_harness_processor_bot=AsyncMock(
                return_value=SimpleNamespace(enable=True, adapter=adapter, dispatch_harness_message=dispatch)
            )
        ),
        logger=logging.getLogger(__name__),
    )
    ap.user_service = UserService(ap)
    ap.harness_transport_factory = HarnessTransportFactory(
        ap,
        AsyncMock(
            return_value={
                'x25519_pub': b64(client_x.public_key().public_bytes_raw()),
                'ed25519_pub': b64(client_ed.public_key().public_bytes_raw()),
            }
        ),
    )
    token = await ap.user_service.generate_jwt_token(account)
    controller = HTTPController(ap)
    controller.register_harness_route()
    config = Config()
    config.bind = ['127.0.0.1:0']
    sockets = config.create_sockets()
    port = sockets.insecure_sockets[0].getsockname()[1]
    stop = asyncio.Event()
    server = asyncio.create_task(
        worker_serve(
            wrap_app(controller.quart_app, config.wsgi_max_body_size, None),
            config,
            sockets=sockets,
            shutdown_trigger=stop.wait,
        )
    )
    env = {
        **os.environ,
        'HARNESS_TEST_FIXTURE': json.dumps(
            {
                'url': f'ws://127.0.0.1:{port}/api/v1/harness/ws?harness_id=client&device_kid=device',
                'token': token,
                'serverX': b64(server_x.public_key().public_bytes_raw()),
                'serverEd': b64(server_ed.public_key().public_bytes_raw()),
                'clientX': b64(client_x.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())),
                'clientEd': b64(client_ed.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())),
            }
        ),
    }
    try:
        process = await asyncio.create_subprocess_exec(
            'node', str(Path(__file__).with_name('client-smoke.mjs')), env=env, stderr=asyncio.subprocess.PIPE
        )
        async with asyncio.timeout(12):
            _, stderr = await process.communicate()
        assert process.returncode == 0, stderr.decode()
        assert ap.workspace_collaboration_service.resolve_account_workspace.await_count == 5
        assert ap.bot_service.ensure_harness_processor_bot.await_args.args[1] == 'agent'
        first, second = dispatches
        assert first[0] == second[0]
        assert first[1] != second[1]
    finally:
        stop.set()
        await server
        await engine.dispose()
