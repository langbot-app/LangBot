"""Core attachment operations over real Box WebSocket RPC without shared paths."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import base64
import logging
import os
import shutil
import shlex
from types import SimpleNamespace
import uuid

from aiohttp.test_utils import TestServer
import pytest
import websockets

from langbot_plugin.api.entities.builtin.platform.message import File
from langbot_plugin.box.backend import DockerBackend
from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.errors import BoxError
from langbot_plugin.box.runtime import BoxRuntime
from langbot_plugin.box.security import BOX_CONTROL_TOKEN_HEADER, BOX_INSTANCE_HEADER
from langbot_plugin.box.server import create_app
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.runtime.security import PLUGIN_FILE_STORAGE_DIR_ENV
from langbot.pkg.box.runner import RunnerBoxService, exported_message
from langbot.pkg.box.service import BoxService
from tests.unit_tests.box.test_box_service import _ACTION_CONTEXT, _CONTEXT, make_app, make_query


HostProcessBackend = pytest.importorskip('langbot_plugin.box.host_backend').HostProcessBackend


pytestmark = pytest.mark.skipif(
    not callable(getattr(ActionRPCBoxClient, 'upload_file', None)),
    reason='requires the in-tree or released Box network file-transfer SDK',
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
    if backend_name not in {'host', 'docker'}:
        pytest.fail('LANGBOT_CORE_NETWORK_BACKEND must select host or docker')
    monkeypatch.delenv('LANGBOT_BOX_CONFIG', raising=False)
    monkeypatch.delenv('LANGBOT_BOX_INSTANCE_ID', raising=False)
    monkeypatch.setenv(PLUGIN_FILE_STORAGE_DIR_ENV, str(tmp_path / 'runtime-transfers'))
    logger = logging.getLogger(__name__)
    instance_uuid = 'core-network-files-' + uuid.uuid4().hex
    context = replace(_CONTEXT, instance_uuid=instance_uuid)
    action_context = _ACTION_CONTEXT.model_copy(update={'instance_uuid': instance_uuid})
    if backend_name == 'docker':
        await _require_existing_docker_image()
        backend = DockerBackend(logger)
        runtime_workspace = tmp_path / 'runtime-workspace'
        runtime_workspace.mkdir()
        output_root = '/tmp/core-network-files-' + uuid.uuid4().hex
    else:
        backend = HostProcessBackend(logger)
        runtime_workspace = None
        output_root = str(tmp_path / 'outside-workspace')
        os.mkdir(output_root, mode=0o700)
    runtime = BoxRuntime(
        logger,
        backends=[backend],
        instance_id=instance_uuid,
        data_dir=tmp_path / 'runtime-identity',
        max_sessions=1,
    )
    runtime.init({'backend': backend_name, 'limits': {'max_sessions': 1}})
    await runtime.initialize()
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
            ap = make_app(logger, allowed_mount_roots=[str(runtime_workspace)] if runtime_workspace else [])
            ap.workspace_service.instance_uuid = instance_uuid
            ap.workspace_service.get_execution_binding.return_value = SimpleNamespace(
                instance_uuid=instance_uuid,
                workspace_uuid=context.workspace_uuid,
                placement_generation=context.placement_generation,
            )
            ap.instance_config.data['box']['file_transfer_mode'] = 'network'
            ap.instance_config.data['box']['runtime']['endpoint'] = url
            service = BoxService(ap, client=client)
            service._available = True
            query = make_query()
            object.__setattr__(query, 'instance_uuid', instance_uuid)
            if runtime_workspace:
                query._box_binding.spec.update(
                    host_path=str(runtime_workspace),
                    image='python:3.12-alpine',
                    network='off',
                    cpus=0.25,
                    memory_mb=128,
                    pids_limit=32,
                )
            box = SimpleNamespace(
                service=service,
                client=client,
                query=query,
                runner=RunnerBoxService(service),
                action_context=action_context,
                output_root=output_root,
            )

            def reject_host_query_directory(*args, **kwargs):
                raise AssertionError('Network file operations must not inspect a Core host directory')

            monkeypatch.setattr(service, '_host_query_dir', reject_host_query_directory)
            try:
                await _command(box, 'mkdir -p -- ' + shlex.quote(output_root))
                yield box
            finally:
                try:
                    await client.delete_session(query._box_binding.session_id, action_context=action_context)
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
    assert await _command(box, "find /workspace -maxdepth 1 -name '.langbot-export-*'") == ''


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
    assert await _command(box, "find /workspace -maxdepth 1 -name '.langbot-export-*'") == ''
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
    assert await _command(box, "find /workspace -maxdepth 1 -name '.langbot-export-*'") == ''


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
    assert await _command(box, "find /workspace -maxdepth 1 -name '.langbot-export-*'") == ''


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
        assert await _command(box, "find /workspace -maxdepth 1 -name '.langbot-export-*'")
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
    assert await _command(box, "find /workspace -maxdepth 1 -name '.langbot-export-*'") == ''
