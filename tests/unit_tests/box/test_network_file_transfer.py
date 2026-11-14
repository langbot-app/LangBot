"""Core attachment operations over real Box WebSocket RPC without shared paths."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import base64
import logging
import json
import os
import shutil
import shlex
from pathlib import Path
from types import SimpleNamespace
import uuid

from aiohttp.test_utils import TestServer
import pytest
import websockets

from langbot_plugin.api.entities.builtin.platform.message import File
from langbot_plugin.box.backend import DockerBackend
from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.e2b_backend import E2BSandboxBackend
from langbot_plugin.box.errors import BoxError
from langbot_plugin.box.nsjail_backend import NsjailBackend
from langbot_plugin.box.runtime import BoxRuntime
from langbot_plugin.box.security import BOX_CONTROL_TOKEN_HEADER, BOX_INSTANCE_HEADER
from langbot_plugin.box.server import create_app
from langbot_plugin.box.tenancy import namespace_session_id
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.runtime.security import PLUGIN_FILE_STORAGE_DIR_ENV
from langbot.pkg.box.runner import RunnerBoxService, exported_message
from langbot.pkg.box.service import BoxService
from tests.unit_tests.box.test_box_service import _ACTION_CONTEXT, _CONTEXT, make_app, make_query


HostProcessBackend = pytest.importorskip('langbot_plugin.box.host_backend').HostProcessBackend


pytestmark = pytest.mark.skipif(
    any(not callable(getattr(ActionRPCBoxClient, name, None)) for name in ('prepare_artifact', 'cleanup_run_files')),
    reason='requires the in-tree or released Box network workspace APIs',
)


_CONTENT = bytes(range(256)) * 8192
_TOKEN = 'core-network-file-transfer-control-token'


def _decode(value):
    return base64.b64decode(value.split(';base64,')[-1])


async def _command(box, command):
    result = await box.service.execute_tool({'command': command, 'timeout_sec': 5}, box.query)
    assert result['ok'], result['stderr']
    return result['stdout']


async def _require_existing_docker_image():
    process = await asyncio.create_subprocess_exec(
        'docker',
        'image',
        'inspect',
        'python:3.12-alpine',
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(process.communicate(), timeout=5)
    finally:
        if process.returncode is None:
            process.kill()
            await process.communicate()
    assert process.returncode == 0, 'Docker tests require an existing python:3.12-alpine image'


@pytest.fixture
async def network_files(tmp_path, monkeypatch):
    backend_name = os.environ.get('LANGBOT_CORE_NETWORK_BACKEND', 'host')
    if backend_name not in {'host', 'docker', 'nsjail', 'e2b'}:
        pytest.fail('LANGBOT_CORE_NETWORK_BACKEND must select host, docker, nsjail or e2b')
    monkeypatch.delenv('LANGBOT_BOX_CONFIG', raising=False)
    monkeypatch.delenv('LANGBOT_BOX_INSTANCE_ID', raising=False)
    monkeypatch.setenv(PLUGIN_FILE_STORAGE_DIR_ENV, str(tmp_path / 'runtime-transfers'))
    logger = logging.getLogger(__name__)
    instance_uuid = 'core-network-files-' + uuid.uuid4().hex
    context = replace(_CONTEXT, instance_uuid=instance_uuid)
    action_context = _ACTION_CONTEXT.model_copy(update={'instance_uuid': instance_uuid})
    created_e2b = []
    e2b_connection = None
    runtime_workspace_root = str(tmp_path / 'runtime-workspace-root')
    monkeypatch.setenv(
        'LANGBOT_BOX_CONFIG',
        json.dumps({'local': {'host_root': runtime_workspace_root, 'default_workspace': 'default'}}),
    )
    config = {'backend': backend_name, 'file_transfer_mode': 'network', 'limits': {'max_sessions': 1}}
    if backend_name in {'docker', 'nsjail'}:
        output_root = '/tmp/core-network-files-' + uuid.uuid4().hex
        if backend_name == 'docker':
            await _require_existing_docker_image()
            backend = DockerBackend(logger)
        else:
            assert os.environ.get('LANGBOT_NSJAIL_CGROUP_V1_PARENT'), (
                'nsjail tests require delegated cgroup controllers'
            )
            tmp_path.chmod(0o755)
            backend = NsjailBackend(logger, base_dir=str(tmp_path / 'nsjail-sessions'))
            config['nsjail'] = {'cgroup_v1_parent': os.environ['LANGBOT_NSJAIL_CGROUP_V1_PARENT']}
    elif backend_name == 'e2b':
        from e2b import AsyncSandbox
        from langbot_plugin.box.models import E2BConnectionConfig

        required = ('E2B_API_KEY', 'E2B_API_URL', 'E2B_SANDBOX_URL')
        assert all(os.environ.get(name) for name in required), 'E2B tests require the complete connection configuration'
        e2b_connection = E2BConnectionConfig(
            api_url=os.environ['E2B_API_URL'],
            sandbox_url=os.environ['E2B_SANDBOX_URL'],
            api_key=os.environ['E2B_API_KEY'],
            template=os.environ.get('E2B_TEMPLATE') or 'base',
        )
        for name in (*required, 'E2B_DOMAIN', 'E2B_TEMPLATE'):
            monkeypatch.delenv(name, raising=False)
        original_create = AsyncSandbox.create

        async def create_one_bounded_sandbox(**kwargs):
            assert not created_e2b, 'Each Core scenario creates only one E2B sandbox'
            kwargs.update(timeout=180, request_timeout=15)
            kwargs['metadata'] = {**kwargs.get('metadata', {}), 'core-network-validation': instance_uuid}
            sandbox = await original_create(**kwargs)
            created_e2b.append(sandbox)
            (tmp_path / 'created-sandbox.json').write_text(json.dumps({'sandbox_id': sandbox.sandbox_id}))
            return sandbox

        monkeypatch.setattr(AsyncSandbox, 'create', create_one_bounded_sandbox)
        config['backend'] = 'docker'
        backend = DockerBackend(logger)
        output_root = '/tmp/core-network-files-' + uuid.uuid4().hex
    else:
        backend = HostProcessBackend(logger)
        output_root = str(tmp_path / 'outside-workspace')
        os.mkdir(output_root, mode=0o700)
    backends = [backend]
    if backend_name == 'e2b':
        backends.append(E2BSandboxBackend(logger))

    async def require_e2b_presence(expected):
        from e2b import AsyncSandbox
        from e2b.sandbox.sandbox_api import SandboxQuery, SandboxState

        pager = AsyncSandbox.list(
            query=SandboxQuery(
                metadata={'core-network-validation': instance_uuid}, state=[SandboxState.RUNNING, SandboxState.PAUSED]
            ),
            limit=10,
            request_timeout=5,
            **e2b_connection.model_dump(exclude={'template'}),
        )
        found = False
        for _ in range(3):
            items = await pager.next_items()
            found |= any(item.sandbox_id == created_e2b[0].sandbox_id for item in items)
            if not pager.has_next:
                break
        assert not pager.has_next, 'Exact sandbox query exceeded its validation budget'
        assert found == expected, 'Exact E2B sandbox presence differs from its expected state'

    runtime = BoxRuntime(
        logger,
        backends=backends,
        instance_id=instance_uuid,
        data_dir=tmp_path / 'runtime-identity',
        max_sessions=1,
    )
    runtime.init(config)
    await runtime.initialize()
    if backend_name == 'e2b':
        assert runtime._backend is backend and backend.name == 'docker'
    elif backend_name == 'nsjail':
        assert backend._cgroup_v1_available or backend._cgroup_v2_available
    server = TestServer(create_app(runtime, control_token=_TOKEN, trusted_instance_uuid=instance_uuid))
    await server.start_server()
    url = str(server.make_url('/rpc/ws')).replace('http://', 'ws://', 1)
    try:
        async with websockets.connect(
            url,
            additional_headers={BOX_CONTROL_TOKEN_HEADER: _TOKEN, BOX_INSTANCE_HEADER: instance_uuid},
            proxy=None,
        ) as websocket:
            handler = Handler(
                WebSocketConnection(websocket),
                file_storage_dir=tmp_path / 'core-transfers',
                max_file_bytes=20 * 1024 * 1024,
            )
            handler_task = asyncio.create_task(handler.run())
            client = ActionRPCBoxClient(logger)
            client.set_handler(handler)
            await client.init({'file_transfer_mode': 'network'})
            ap = make_app(
                logger,
                allowed_mount_roots=[],
                host_root='',
            )
            ap.workspace_service.instance_uuid = instance_uuid
            ap.workspace_service.get_execution_binding.return_value = SimpleNamespace(
                instance_uuid=instance_uuid,
                workspace_uuid=context.workspace_uuid,
                placement_generation=context.placement_generation,
            )
            ap.instance_config.data['box']['backend'] = config['backend']
            ap.instance_config.data['box']['file_transfer_mode'] = 'network'
            ap.instance_config.data['box']['runtime']['endpoint'] = url
            service = BoxService(ap, client=client)
            service._available = True
            assert service.default_workspace is None
            assert runtime.network_workspace is True
            query = make_query()
            object.__setattr__(query, 'instance_uuid', instance_uuid)
            object.__setattr__(query, '_box_binding', None)
            object.__setattr__(query, '_sandbox_backend', backend_name)
            object.__setattr__(
                query,
                '_sandbox_e2b_config',
                {'revision': 'fixture', 'config': e2b_connection.model_dump()} if e2b_connection is not None else {},
            )
            limits = {'timeout_sec': 5, 'max_sessions': 1, 'idle_ttl_sec': 60}
            if backend_name in {'docker', 'nsjail'}:
                limits.update(cpus=0.25, memory_mb=128, pids_limit=32)
            object.__setattr__(query, '_sandbox_limits', {'revision': 'fixture', 'config': limits})
            image = 'python:3.12-alpine' if backend_name == 'docker' else 'rockchin/langbot-sandbox:latest'
            if e2b_connection is not None:
                image = e2b_connection.template
            acquire_request = {'reuse_key': 'network-file-fixture', 'options': {'image': image}}
            box = SimpleNamespace(
                service=service,
                client=client,
                query=query,
                runner=RunnerBoxService(service),
                action_context=action_context,
                context=context,
                acquire_request=acquire_request,
                output_root=output_root,
            )

            def reject_host_query_directory(*args, **kwargs):
                raise AssertionError('Network file operations must not inspect a Core host directory')

            monkeypatch.setattr(service, '_host_query_dir', reject_host_query_directory)
            acquired_session = None
            try:
                acquired = await box.runner.acquire(context, acquire_request, query)
                acquired_session = acquired['id']
                session = runtime._sessions[namespace_session_id(action_context, acquired_session)]
                if backend_name == 'nsjail':
                    Path(session.info.host_path).chmod(0o777)
                await box.runner.bind(context, query, 'run-' + uuid.uuid4().hex, acquired_session)
                assert query._box_binding.session_id == acquired_session
                assert len(runtime._sessions) == 1
                await _command(box, 'mkdir -p -- ' + shlex.quote(output_root))
                if backend_name == 'e2b':
                    session = runtime._sessions[namespace_session_id(action_context, query._box_binding.session_id)]
                    assert runtime._backend is backend and session.info.backend_name == 'e2b'
                    assert session.backend.connection_config == e2b_connection
                    assert service.default_workspace is None
                    assert session.info.host_path is None, 'Network mode must disable the writable E2B host mirror'
                    assert len(created_e2b) == 1
                    await require_e2b_presence(True)
                yield box
            finally:
                try:
                    if acquired_session is not None:
                        await client.delete_session(acquired_session, action_context=action_context)
                finally:
                    await handler.close()
                    await asyncio.gather(handler_task, return_exceptions=True)
    finally:
        try:
            await server.close()
        finally:
            try:
                await runtime.shutdown()
            finally:
                if backend_name == 'host':
                    shutil.rmtree(output_root)
                elif backend_name == 'e2b' and created_e2b:
                    await require_e2b_presence(False)
                    assert not any(path.is_file() for path in Path(runtime_workspace_root).rglob('*'))
                elif backend_name == 'nsjail':
                    assert not any((tmp_path / 'nsjail-sessions').glob('*')), (
                        'nsjail session directories survived cleanup'
                    )


@pytest.mark.asyncio
async def test_network_import_preserves_same_name_files_from_separate_refs(network_files):
    box = network_files
    query = box.query
    second = b'second attachment'
    object.__setattr__(
        query,
        '_input_components',
        {
            'att-a': File(name='same.bin', base64=base64.b64encode(_CONTENT).decode()),
            'att-b': File(name='same.bin', base64=base64.b64encode(second).decode()),
        },
    )
    first_import = await box.runner.import_attachments(query, ['att-a'])
    second_import = await box.runner.import_attachments(query, ['att-b'])
    first = first_import['items'][0]
    last = second_import['items'][0]
    assert first['path'] != last['path']
    assert first['size'] == len(_CONTENT)
    assert await box.client.download_file(query._box_binding.session_id, first['path'], box.action_context) == _CONTENT
    assert await box.client.download_file(query._box_binding.session_id, last['path'], box.action_context) == second
    assert await box.runner.import_attachments(query, ['att-a']) == first_import
    assert await box.client.download_file(query._box_binding.session_id, first['path'], box.action_context) == _CONTENT


@pytest.mark.asyncio
async def test_network_selected_export_preserves_large_private_output_and_unselected_files(network_files):
    box = network_files
    session = box.query._box_binding.session_id
    selected = box.output_root + '/private-output.bin'
    unselected = box.output_root + '/unselected.bin'
    await box.client.upload_file(session, '/workspace/input.bin', _CONTENT, box.action_context)
    await _command(
        box, f'cp /workspace/input.bin {shlex.quote(selected)} && printf retained > {shlex.quote(unselected)}'
    )
    result = await box.runner.export_files(box.query, [selected])
    assert result['warning'] is None
    assert len(result['items']) == 1
    item = result['items'][0]
    assert item['name'] == 'private-output.bin'
    assert item['size'] == len(_CONTENT)
    assert 'base64' not in item
    message = exported_message(box.query, [item['id']])
    assert _decode(message[0].base64) == _CONTENT
    assert await _command(box, f'test ! -e {shlex.quote(selected)} && cat {shlex.quote(unselected)}') == 'retained'
    assert await _command(box, "find /workspace/.langbot-snapshots -name '.langbot-export-*'") == ''
    assert await _command(box, 'printf unrelated-command') == 'unrelated-command'
    assert await _command(box, f'test ! -e {shlex.quote(selected)} && cat {shlex.quote(unselected)}') == 'retained'
    assert await _command(box, "find /workspace/.langbot-snapshots -name '.langbot-export-*'") == ''


@pytest.mark.asyncio
@pytest.mark.parametrize('failed_import', [False, True])
async def test_run_cleanup_removes_exact_import_scopes_and_keeps_other_runs(network_files, monkeypatch, failed_import):
    box = network_files
    binding = box.query._box_binding
    source = File(name='cleanup.bin', base64=base64.b64encode(b'current input').decode())
    reference = '../' + 'x' * 600
    object.__setattr__(box.query, '_input_components', {reference: source})
    await _command(
        box,
        'mkdir -p /workspace/draft /workspace/inbox/other-run && '
        'printf draft > /workspace/draft/keep && printf other > /workspace/inbox/other-run/keep',
    )
    if failed_import:

        async def incomplete_materialization(query):
            imported = '/workspace/inbox/' + query._box_binding.io_scope + '/cleanup.bin'
            await box.client.upload_file(binding.session_id, imported, b'partial', box.action_context)
            raise BoxError('incomplete input materialization')

        monkeypatch.setattr(box.service, 'materialize_inbound_attachments', incomplete_materialization)
        with pytest.raises(BoxError, match='incomplete input'):
            await box.runner.import_attachments(box.query, [reference])
        assert not binding.imported
    else:
        await box.runner.import_attachments(box.query, [reference])
    assert len(binding.import_scopes) == 1
    scope = next(iter(binding.import_scopes))
    assert '/' not in scope and len(scope) <= 512
    imported = '/workspace/inbox/' + scope + '/cleanup.bin'
    assert await _command(box, 'test -f ' + shlex.quote(imported)) == ''
    await box.service.cleanup_run_files(box.query)
    assert await _command(box, 'test ! -e /workspace/inbox/' + shlex.quote(scope)) == ''
    assert await _command(box, 'cat /workspace/draft/keep /workspace/inbox/other-run/keep') == 'draftother'


@pytest.mark.asyncio
async def test_network_failed_batch_download_accepts_nothing_and_keeps_sources(network_files, monkeypatch):
    box = network_files
    first_path = box.output_root + '/first.bin'
    second_path = box.output_root + '/second.bin'
    await _command(box, f'printf first > {shlex.quote(first_path)} && printf second > {shlex.quote(second_path)}')
    download_file = box.client.download_file
    calls = 0

    async def fail_second_download(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise BoxError('Injected download interruption')
        return await download_file(*args, **kwargs)

    monkeypatch.setattr(box.client, 'download_file', fail_second_download)
    with pytest.raises(BoxError):
        await box.runner.export_files(box.query, [first_path, second_path])
    assert not box.query._box_binding.exported
    assert not box.query._box_binding.exported_fingerprints
    assert await _command(box, f'cat {shlex.quote(first_path)} && cat {shlex.quote(second_path)}') == 'firstsecond'
    assert await _command(box, "find /workspace/.langbot-snapshots -name '.langbot-export-*'") == ''
    monkeypatch.setattr(box.client, 'download_file', download_file)
    result = await box.runner.export_files(box.query, [first_path, second_path])
    assert {item['name'] for item in result['items']} == {'first.bin', 'second.bin'}
    assert await _command(box, f'test ! -e {shlex.quote(first_path)} && test ! -e {shlex.quote(second_path)}') == ''


@pytest.mark.asyncio
async def test_network_cleanup_warning_keeps_accepted_handles_and_changed_source(network_files, monkeypatch):
    box = network_files
    path = box.output_root + '/raced.bin'
    await _command(box, f'printf original > {shlex.quote(path)}')
    clear_selected_files = box.service.clear_selected_files

    async def change_source_before_cleanup(query, items):
        await _command(box, f'printf changed > {shlex.quote(path)}')
        return await clear_selected_files(query, items)

    monkeypatch.setattr(box.service, 'clear_selected_files', change_source_before_cleanup)
    result = await box.runner.export_files(box.query, [path])
    assert result['warning']
    assert len(result['items']) == 1
    item = result['items'][0]
    assert item['id'] in box.query._box_binding.exported
    assert _decode(exported_message(box.query, [item['id']])[0].base64) == b'original'
    assert await _command(box, f'cat {shlex.quote(path)}') == 'changed'
    assert await _command(box, "find /workspace/.langbot-snapshots -name '.langbot-export-*'") == ''


@pytest.mark.asyncio
async def test_network_legacy_outbox_collection_supports_large_files(network_files):
    box = network_files
    path = f'/workspace/outbox/{box.query._box_binding.io_scope}/nested/large.bin'
    await box.client.upload_file(box.query._box_binding.session_id, path, _CONTENT, box.action_context)
    retained = await box.service.collect_outbound_attachments(box.query, clear=False)
    assert len(retained) == 1 and _decode(retained[0]['base64']) == _CONTENT
    assert await _command(box, f'test -f {shlex.quote(path)}') == ''
    collected = await box.service.collect_outbound_attachments(box.query)
    assert len(collected) == 1 and _decode(collected[0]['base64']) == _CONTENT
    assert await box.service.collect_outbound_attachments(box.query) == []
    assert await _command(box, "find /workspace/.langbot-snapshots -name '.langbot-export-*'") == ''


@pytest.mark.asyncio
async def test_network_import_cancelled_after_publication_removes_unconfirmed_file(network_files, monkeypatch):
    box = network_files
    content = b'input remains available after a cancelled publication'
    source = File(name='cancelled.bin', base64=base64.b64encode(content).decode())
    object.__setattr__(box.query, '_input_components', {'att-cancelled': source})
    upload_file = box.client.upload_file
    published_paths = []

    async def cancel_after_publication(session_id, path, data, **kwargs):
        await upload_file(session_id, path, data, **kwargs)
        published_paths.append(path)
        raise asyncio.CancelledError

    monkeypatch.setattr(box.client, 'upload_file', cancel_after_publication)
    with pytest.raises(asyncio.CancelledError):
        await box.runner.import_attachments(box.query, ['att-cancelled'])
    assert len(published_paths) == 1
    assert not box.query._box_binding.imported
    assert box.query._input_components['att-cancelled'] is source
    assert await _command(box, 'test ! -e ' + shlex.quote(published_paths[0])) == ''
    monkeypatch.setattr(box.client, 'upload_file', upload_file)
    result = await box.runner.import_attachments(box.query, ['att-cancelled'])
    assert len(result['items']) == 1
    assert result['items'][0]['path'] == published_paths[0]
    assert (
        await box.client.download_file(box.query._box_binding.session_id, published_paths[0], box.action_context)
        == content
    )


@pytest.mark.asyncio
async def test_network_export_repeated_cancel_waits_for_preparation_and_cleans_snapshot(network_files, monkeypatch):
    box = network_files
    path = box.output_root + '/cancelled-export.bin'
    await _command(box, f'printf preserved > {shlex.quote(path)}')
    file_metadata = box.service._file_metadata
    prepared = asyncio.Event()
    release_preparation = asyncio.Event()

    async def pause_after_real_preparation(query, script, paths=None):
        metadata = await file_metadata(query, script, paths)
        prepared.set()
        await release_preparation.wait()
        return metadata

    monkeypatch.setattr(box.service, '_file_metadata', pause_after_real_preparation)
    export = asyncio.create_task(box.runner.export_files(box.query, [path]))
    try:
        await asyncio.wait_for(prepared.wait(), timeout=5)
        assert await _command(box, "find /workspace/.langbot-snapshots -name '.langbot-export-*'")
        export.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not export.done()
        export.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not export.done()
    finally:
        release_preparation.set()
        if not prepared.is_set():
            export.cancel()
        with pytest.raises(asyncio.CancelledError):
            await export
    assert not box.query._box_binding.exported
    assert not box.query._box_binding.exported_fingerprints
    assert await _command(box, 'cat ' + shlex.quote(path)) == 'preserved'
    assert await _command(box, "find /workspace/.langbot-snapshots -name '.langbot-export-*'") == ''
