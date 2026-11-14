"""Core DB publications → authenticated Box RPC → Runtime-owned artifact cache.

Host is the default. LANGBOT_ARTIFACT_CACHE_BACKEND selects docker/nsjail/e2b
for the single-session execution case; protocol failures stay on host. E2B
accepts the existing full E2B_* configuration or an explicitly supplied private
Core config path in LANGBOT_ARTIFACT_CACHE_E2B_CONFIG. No Core package path is
mounted, passed to Runtime, or materialized for preparation.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import uuid
import zipfile

from aiohttp.test_utils import TestServer
import pytest
import websockets
import yaml
from quart.datastructures import FileStorage

from langbot.pkg.box.service import BoxService
from langbot_plugin.box.backend import DockerBackend
from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.e2b_backend import E2BSandboxBackend
from langbot_plugin.box.errors import BoxError
from langbot_plugin.box.host_backend import HostProcessBackend
from langbot_plugin.box import models as box_models
from langbot_plugin.box.models import BoxSpec
from langbot_plugin.box.nsjail_backend import NsjailBackend
from langbot_plugin.box.runtime import BoxRuntime
from langbot_plugin.box.security import BOX_CONTROL_TOKEN_HEADER, BOX_INSTANCE_HEADER
from langbot_plugin.box.server import create_app
from langbot_plugin.box.tenancy import namespace_session_id
from langbot_plugin.entities.io.actions.enums import CommonAction
from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.runtime.security import PLUGIN_FILE_STORAGE_DIR_ENV
from tests.integration.skill import test_persistent_skill_replicas as persistence_tests

if not hasattr(box_models, 'BoxArtifactDescriptor'):
    pytest.skip('Runtime artifact caching requires the in-tree or updated SDK', allow_module_level=True)

BoxArtifactDescriptor = box_models.BoxArtifactDescriptor
E2BConnectionConfig = box_models.E2BConnectionConfig
_BACKEND = os.environ.get('LANGBOT_ARTIFACT_CACHE_BACKEND', 'host')
pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
replicas = persistence_tests.replicas


@pytest.fixture
def persistence_case(tmp_path):
    return SimpleNamespace(
        url=f'sqlite+aiosqlite:///{tmp_path / "core.db"}', options={}, content={'backend': 'database'}, minio=False
    )


async def _docker(*args):
    process = await asyncio.create_subprocess_exec(
        'docker', *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        output, error = await asyncio.wait_for(process.communicate(), 5)
    finally:
        if process.returncode is None:
            process.kill()
            await process.communicate()
    assert process.returncode == 0, error.decode(errors='replace')
    return output.decode().strip()


@pytest.fixture
async def artifact_box(replicas, tmp_path, monkeypatch):
    assert _BACKEND in {'host', 'docker', 'nsjail', 'e2b'}
    core = replicas.a
    context = core.context
    action_context = ActionContext(
        instance_uuid=context.instance_uuid,
        workspace_uuid=context.workspace_uuid,
        placement_generation=context.placement_generation,
    )
    logger = logging.getLogger(__name__)
    monkeypatch.delenv('LANGBOT_BOX_CONFIG', raising=False)
    monkeypatch.delenv('LANGBOT_BOX_INSTANCE_ID', raising=False)
    with tempfile.TemporaryDirectory(prefix='langbot-artifact-runtime-') as directory:
        runtime_root = Path(directory)
        transfers = runtime_root / 'transfers'
        monkeypatch.setenv(PLUGIN_FILE_STORAGE_DIR_ENV, str(transfers))
        config = {
            'backend': _BACKEND,
            'limits': {'max_sessions': 1, 'max_artifact_cache_bytes': 64 * 1024 * 1024, 'artifact_cache_ttl_sec': 1},
            'local': {'host_root': str(runtime_root / 'workspaces'), 'allowed_mount_roots': [str(runtime_root)]},
        }
        connection = None
        created_e2b = []
        if _BACKEND in {'docker', 'e2b'}:
            await _docker('image', 'inspect', 'python:3.12-alpine')
            backend = DockerBackend(logger)
            config['backend'] = 'docker'
        elif _BACKEND == 'nsjail':
            backend = NsjailBackend(logger, base_dir=str(runtime_root / 'nsjail'))
            config['nsjail'] = {'cgroup_v1_parent': os.environ.get('LANGBOT_NSJAIL_CGROUP_V1_PARENT', '')}
            build_args = backend._build_nsjail_args
            monkeypatch.setattr(
                backend,
                '_build_nsjail_args',
                lambda *args: [item for item in build_args(*args) if item != '--really_quiet'],
            )
        else:
            backend = HostProcessBackend(logger)
        backends = [backend]
        if _BACKEND == 'e2b':
            from e2b import AsyncSandbox

            path = os.environ.get('LANGBOT_ARTIFACT_CACHE_E2B_CONFIG')
            if path:
                connection = E2BConnectionConfig.model_validate(yaml.safe_load(Path(path).read_text())['box']['e2b'])
            else:
                connection = E2BConnectionConfig(
                    api_key=os.environ['E2B_API_KEY'],
                    api_url=os.environ['E2B_API_URL'],
                    sandbox_url=os.environ['E2B_SANDBOX_URL'],
                    template=os.environ.get('E2B_TEMPLATE') or 'base',
                )
            for name in ('E2B_API_KEY', 'E2B_API_URL', 'E2B_SANDBOX_URL', 'E2B_DOMAIN', 'E2B_TEMPLATE'):
                monkeypatch.delenv(name, raising=False)
            original_create = AsyncSandbox.create

            async def create_one(**kwargs):
                assert not created_e2b, 'This case creates one real E2B sandbox'
                kwargs.update(timeout=120, request_timeout=15)
                kwargs['metadata'] = {**kwargs.get('metadata', {}), 'artifact-validation': context.instance_uuid}
                sandbox = await original_create(**kwargs)
                created_e2b.append(sandbox)
                return sandbox

            monkeypatch.setattr(AsyncSandbox, 'create', create_one)
            backends.append(E2BSandboxBackend(logger))
        runtime = BoxRuntime(
            logger,
            backends=backends,
            instance_id=context.instance_uuid,
            data_dir=runtime_root / 'identity',
            session_ttl_sec=0,
        )
        runtime.init(config)
        token = 'artifact-control-' + uuid.uuid4().hex
        server = TestServer(create_app(runtime, control_token=token, trusted_instance_uuid=context.instance_uuid))
        info = None

        async def e2b_presence(expected):
            from e2b import AsyncSandbox
            from e2b.sandbox.sandbox_api import SandboxQuery, SandboxState

            pager = AsyncSandbox.list(
                query=SandboxQuery(
                    metadata={'artifact-validation': context.instance_uuid},
                    state=[SandboxState.RUNNING, SandboxState.PAUSED],
                ),
                limit=10,
                request_timeout=5,
                **connection.model_dump(exclude={'template'}),
            )
            found = False
            for _ in range(3):
                found |= any(item.sandbox_id == created_e2b[0].sandbox_id for item in await pager.next_items())
                if not pager.has_next:
                    break
            assert not pager.has_next and found == expected

        try:
            await runtime.initialize()
            if _BACKEND == 'nsjail':
                assert backend._cgroup_v1_available or backend._cgroup_v2_available
            if _BACKEND == 'e2b':
                assert runtime._backend is backend and backend.name == 'docker'
            await server.start_server()
            url = str(server.make_url('/rpc/ws')).replace('http://', 'ws://', 1)
            async with websockets.connect(
                url,
                additional_headers={BOX_CONTROL_TOKEN_HEADER: token, BOX_INSTANCE_HEADER: context.instance_uuid},
                proxy=None,
            ) as websocket:
                # Preserve the normal wire/file limits, including the >20 MiB artifact regression.
                handler = Handler(WebSocketConnection(websocket), file_storage_dir=tmp_path / 'core-transfers')
                handler_task = asyncio.create_task(handler.run())
                client = ActionRPCBoxClient(logger)
                client.set_handler(handler)
                core.app.instance_config.data['box'] = {
                    'enabled': True,
                    'file_transfer_mode': 'network',
                    'local': {'host_root': '', 'allowed_mount_roots': []},
                }
                service = BoxService(core.app, client=client)
                await service.initialize()
                assert service.enabled and not service.shares_filesystem_with_box
                chunks = []
                original_call = handler.call_action

                async def count_chunks(action, data, **kwargs):
                    if action == CommonAction.FILE_CHUNK:
                        chunks.append(data.get('chunk_size', 0))
                    return await original_call(action, data, **kwargs)

                monkeypatch.setattr(handler, 'call_action', count_chunks)
                session_open = False

                async def open_session(digest, command):
                    nonlocal info, session_open
                    spec = BoxSpec(
                        session_id='artifact-exec',
                        artifact_mounts=[{'content_digest': digest}],
                        backend='e2b' if connection else None,
                        e2b_config=connection,
                        image='python:3.12-alpine'
                        if _BACKEND == 'docker'
                        else connection.template
                        if connection
                        else 'rockchin/langbot-sandbox:latest',
                        cmd=command,
                        workdir=f'/opt/langbot-artifacts/{digest[7:]}',
                        network='off',
                        timeout_sec=5,
                        cpus=0.25,
                        memory_mb=128,
                        pids_limit=32,
                    )
                    await asyncio.wait_for(client.create_session(spec, action_context=action_context), 20)
                    session_open = True
                    session = runtime._sessions[namespace_session_id(action_context, 'artifact-exec')]
                    info = session.info
                    assert info.backend_name == _BACKEND
                    if connection is not None:
                        assert len(created_e2b) == 1 and session.backend.connection_config == connection
                        await e2b_presence(True)
                    elif _BACKEND == 'docker':
                        assert await _docker(
                            'container',
                            'ls',
                            '--all',
                            '--filter',
                            f'name=^/{info.backend_session_id}$',
                            '--format',
                            '{{.ID}}',
                        )
                    elif _BACKEND == 'nsjail':
                        assert Path(info.backend_session_id).is_dir()
                    print(
                        json.dumps(
                            {
                                'event': 'artifact_backend_created',
                                'instance': context.instance_uuid,
                                'backend': _BACKEND,
                                'id': info.backend_session_id,
                            }
                        ),
                        flush=True,
                    )
                    return spec

                async def close_session():
                    nonlocal session_open
                    if session_open:
                        await asyncio.wait_for(
                            client.delete_session('artifact-exec', action_context=action_context), 20
                        )
                        session_open = False

                box = SimpleNamespace(
                    core=core,
                    service=service,
                    client=client,
                    context=context,
                    action_context=action_context,
                    runtime=runtime,
                    handler=handler,
                    chunks=chunks,
                    transfers=transfers,
                    open_session=open_session,
                    close_session=close_session,
                    headers=persistence_tests._auth(replicas.token, context.workspace_uuid),
                )
                try:
                    yield box
                finally:
                    try:
                        await close_session()
                    finally:
                        await handler.close()
                        await asyncio.gather(handler_task, return_exceptions=True)
        finally:
            try:
                await server.close()
            finally:
                await runtime.shutdown()
                if created_e2b:
                    await e2b_presence(False)
                elif info is not None and _BACKEND == 'docker':
                    assert not await _docker(
                        'container',
                        'ls',
                        '--all',
                        '--filter',
                        f'name=^/{info.backend_session_id}$',
                        '--format',
                        '{{.ID}}',
                    )
                elif info is not None and _BACKEND == 'nsjail':
                    assert not Path(info.backend_session_id).exists()
                if info is not None:
                    print(
                        json.dumps(
                            {
                                'event': 'artifact_backend_removed',
                                'instance': context.instance_uuid,
                                'backend': _BACKEND,
                                'id': info.backend_session_id,
                            }
                        ),
                        flush=True,
                    )


async def _install(box, payload=None):
    response = await box.core.client.post(
        '/api/v1/skills/install/upload',
        headers=box.headers,
        files={'file': FileStorage(io.BytesIO(payload or persistence_tests._zip_package()), filename='probe.zip')},
    )
    installed = await persistence_tests._data(response)
    return installed['skills'][0]['revision']


async def _package(box, revision):
    package = await box.core.app.skill_repository.get_skill_package(box.context, persistence_tests._NAME, revision)
    descriptor = BoxArtifactDescriptor(
        content_digest=revision,
        manifest=package['manifest'],
        archive_size=package['size'],
        archive_sha256=package['sha256'],
    )
    return descriptor, package['content']


def _assert_no_core_package(box):
    assert not (box.core.root / 'skills/.database-cache').exists()


async def test_core_publications_execute_and_obey_runtime_cache_pins(artifact_box):
    box = artifact_box
    first = await _install(box)
    receipt = await asyncio.wait_for(
        box.service.prepare_skill_artifact(box.context, persistence_tests._NAME, first), 20
    )
    assert receipt['ready'] and box.chunks
    sent = len(box.chunks)
    assert await box.service.prepare_skill_artifact(box.context, persistence_tests._NAME, first) == receipt
    assert len(box.chunks) == sent
    _assert_no_core_package(box)
    command = 'python3 ' + receipt['mount_path'] + '/scripts/probe.py'
    spec = await box.open_session(first, command)
    result = await asyncio.wait_for(box.client.execute(spec, action_context=box.action_context), 20)
    assert result.ok and result.stdout.strip() == 'immutable replica bytes', result.stderr
    updated = await persistence_tests._data(
        await box.core.client.put(
            f'/api/v1/skills/{persistence_tests._NAME}',
            headers=box.headers,
            json={'base_revision': first, 'description': 'A newer unbound publication'},
        )
    )
    second = updated['skill']['revision']
    await box.service.prepare_skill_artifact(box.context, persistence_tests._NAME, second)
    one, _ = await _package(box, first)
    two, _ = await _package(box, second)
    await asyncio.sleep(1.1)
    await box.runtime.reap_artifact_cache()
    assert (await box.client.prepare_artifact(one, action_context=box.action_context))['ready']
    assert not (await box.client.prepare_artifact(two, action_context=box.action_context))['ready']
    await box.service.prepare_skill_artifact(box.context, persistence_tests._NAME, second)
    assert (await box.client.prepare_artifact(two, action_context=box.action_context))['ready']
    result = await box.client.execute(spec, action_context=box.action_context)
    assert result.ok and result.stdout.strip() == 'immutable replica bytes'
    await box.close_session()
    await asyncio.sleep(1.1)
    await box.runtime.reap_artifact_cache()
    assert not (await box.client.prepare_artifact(one, action_context=box.action_context))['ready']
    assert (await box.service.prepare_skill_artifact(box.context, persistence_tests._NAME, first))['ready']
    _assert_no_core_package(box)


@pytest.mark.skipif(_BACKEND != 'host', reason='protocol failures require no additional live sandbox')
async def test_bad_archive_retries_and_contexts_cannot_reuse_foreign_content(artifact_box):
    box = artifact_box
    revision = await _install(box)
    descriptor, content = await _package(box, revision)
    invalid = b'not a ZIP archive'
    bad = descriptor.model_copy(
        update={'archive_size': len(invalid), 'archive_sha256': hashlib.sha256(invalid).hexdigest()}
    )
    with pytest.raises((BoxError, ValueError)):
        await box.client.prepare_artifact(bad, invalid, action_context=box.action_context)
    assert not (await box.client.prepare_artifact(descriptor, action_context=box.action_context))['ready']
    assert (await box.client.prepare_artifact(descriptor, content, action_context=box.action_context))['ready']
    foreign = box.action_context.model_copy(update={'workspace_uuid': str(uuid.uuid4())})
    assert not (await box.client.prepare_artifact(descriptor, action_context=foreign))['ready']
    with pytest.raises(BoxError):
        await box.client.prepare_artifact(
            descriptor, action_context=foreign.model_copy(update={'instance_uuid': 'other'})
        )
    newer = box.action_context.model_copy(update={'placement_generation': 2})
    await box.client.prepare_artifact(descriptor, action_context=newer)
    with pytest.raises(BoxError):
        await box.client.prepare_artifact(descriptor, action_context=box.action_context)
    _assert_no_core_package(box)


@pytest.mark.skipif(_BACKEND != 'host', reason='ACK cancellation is covered once over real host RPC')
async def test_cancelled_artifact_transfer_cleans_and_retries(artifact_box, monkeypatch):
    box = artifact_box
    revision = await _install(box)
    descriptor, _ = await _package(box, revision)
    arrived, pause = asyncio.Event(), asyncio.Event()
    original = box.handler.call_action
    intercepted = False

    async def pause_first_chunk(action, data, **kwargs):
        nonlocal intercepted
        response = await original(action, data, **kwargs)
        if action == CommonAction.FILE_CHUNK and not intercepted:
            intercepted = True
            arrived.set()
            await pause.wait()
        return response

    monkeypatch.setattr(box.handler, 'call_action', pause_first_chunk)
    operation = asyncio.create_task(box.service.prepare_skill_artifact(box.context, persistence_tests._NAME, revision))
    try:
        await asyncio.wait_for(arrived.wait(), 5)
    finally:
        operation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(operation, 5)
        pause.set()
    assert not box.handler._transfer_stages
    assert not [path for path in box.transfers.rglob('*') if path.is_file() and not path.name.endswith('.lock')]
    assert not (await box.client.prepare_artifact(descriptor, action_context=box.action_context))['ready']
    assert (await box.service.prepare_skill_artifact(box.context, persistence_tests._NAME, revision))['ready']
    _assert_no_core_package(box)


@pytest.mark.skipif(_BACKEND != 'host', reason='large archive wire boundary needs only one host acceptance')
async def test_artifact_wire_accepts_more_than_workspace_file_limit(artifact_box):
    box = artifact_box
    source = io.BytesIO(persistence_tests._zip_package())
    output = io.BytesIO()
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in original.infolist():
            archive.writestr(entry, original.read(entry))
        # Each 7 MiB resource remains below the existing per-file limit. Mixed
        # entropy keeps the upload below 10 MiB and its compression ratio below 200.
        for index in range(3):
            content = b''.join(os.urandom(8192) + bytes(24576) for _ in range(224))
            archive.writestr(f'{persistence_tests._NAME}/references/large-{index}.bin', content)
    assert len(output.getvalue()) < 10 * 1024 * 1024
    revision = await _install(box, output.getvalue())
    descriptor, _ = await _package(box, revision)
    assert 20 * 1024 * 1024 < descriptor.archive_size < 64 * 1024 * 1024
    assert (
        await asyncio.wait_for(box.service.prepare_skill_artifact(box.context, persistence_tests._NAME, revision), 30)
    )['ready']
    sent = len(box.chunks)
    assert sent
    assert (await box.service.prepare_skill_artifact(box.context, persistence_tests._NAME, revision))['ready']
    assert len(box.chunks) == sent
    _assert_no_core_package(box)
