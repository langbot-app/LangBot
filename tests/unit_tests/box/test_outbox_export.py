"""Outbox failures must retain files; fallback reads use the bound Workspace."""

import asyncio
import base64
import errno
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.box import secure_fs
from langbot.pkg.box.service import BoxService
from langbot_plugin.box.client import BoxRuntimeClient
from langbot_plugin.box.errors import BoxError, BoxValidationError
from langbot_plugin.box.models import BoxExecutionResult, BoxExecutionStatus
from tests.unit_tests.box.test_box_service import make_app, make_query, _CONTEXT


@pytest.fixture
def env(tmp_path):
    app = make_app(Mock(), allowed_mount_roots=[str(tmp_path)], host_root=str(tmp_path / 'box'))
    box = BoxService(app, client=Mock(spec=BoxRuntimeClient))
    box._available = True
    box.default_workspace = str(tmp_path / 'box' / 'default')
    workspace = Path(box._tenant_workspace(_CONTEXT))
    query = make_query()
    outbox = workspace / 'outbox' / query.query_uuid
    outbox.mkdir(parents=True)
    # The actual generated exec reader runs against this test Workspace.
    box.OUTBOX_MOUNT_DIR = str(workspace / 'outbox')
    return box, query, outbox


def result(stdout='[]', exit_code=0):
    return BoxExecutionResult(
        session_id='box-test',
        backend_name='test',
        status=BoxExecutionStatus.COMPLETED,
        exit_code=exit_code,
        stdout=stdout,
        duration_ms=1,
    )


async def execute_script(spec, *, action_context):
    assert action_context.workspace_uuid == _CONTEXT.workspace_uuid
    assert action_context.instance_uuid == _CONTEXT.instance_uuid
    assert action_context.placement_generation == _CONTEXT.placement_generation
    process = await asyncio.create_subprocess_exec(
        '/bin/sh',
        '-c',
        spec.cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
    return BoxExecutionResult(
        session_id=spec.session_id,
        backend_name='test',
        status=BoxExecutionStatus.COMPLETED,
        exit_code=process.returncode,
        stdout=stdout.decode(),
        stderr=stderr.decode(),
        duration_ms=1,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['file', 'directory', 'query_directory'])
async def test_unreadable_output_is_not_empty_and_is_retained_when_fallback_fails(env, kind):
    if os.geteuid() == 0:
        pytest.skip('requires non-root filesystem permission checks')
    box, query, outbox = env
    nested = outbox / 'nested'
    nested.mkdir()
    file = nested / 'answer.txt'
    file.write_bytes(b'expected')
    unreadable = {'file': file, 'directory': nested, 'query_directory': outbox}[kind]
    mode = unreadable.stat().st_mode & 0o777
    box.client.execute = AsyncMock(side_effect=execute_script)
    box._clear_outbox = AsyncMock()
    try:
        unreadable.chmod(0)
        with pytest.raises(BoxError):
            await box.collect_outbound_attachments(query)
        box.client.execute.assert_awaited_once()
        box._clear_outbox.assert_not_awaited()
    finally:
        unreadable.chmod(mode)
    assert file.read_bytes() == b'expected'


@pytest.mark.asyncio
async def test_permission_fallback_retries_all_files_once_in_the_bound_box(env, monkeypatch):
    box, query, outbox = env
    (outbox / 'a.txt').write_bytes(b'first')
    (outbox / 'b.txt').write_bytes(b'second')
    original_open = secure_fs.os.open

    def denied_open(path, flags, *args, **kwargs):
        if path == 'b.txt':
            raise PermissionError(errno.EACCES, 'denied', path)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(secure_fs.os, 'open', denied_open)
    box.client.execute = AsyncMock(side_effect=execute_script)
    attachments = await box.collect_outbound_attachments(query)
    assert {a['name']: base64.b64decode(a['base64']) for a in attachments} == {
        'a.txt': b'first',
        'b.txt': b'second',
    }
    assert list(outbox.iterdir()) == []
    box.client.execute.assert_awaited_once()
    spec = box.client.execute.await_args.args[0]
    assert spec.session_id == query._box_binding.session_id
    assert spec.host_path == str(outbox.parent.parent)


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['transport', 'exit', 'empty', 'json', 'shape', 'base64', 'path', 'payload_limit'])
async def test_exec_failure_or_malformed_response_never_cleans_outbox(env, failure, monkeypatch):
    box, query, outbox = env
    file = outbox / 'answer.txt'
    file.write_bytes(b'keep')
    monkeypatch.setattr(box, '_host_query_dir', lambda *args: None)
    box._clear_outbox = AsyncMock()
    replies = {
        'exit': result(exit_code=1),
        'empty': result(''),
        'json': result('not json'),
        'shape': result('{}'),
        'base64': result('[{"name":"a","b64":"!"}]'),
        'path': result('[{"name":"../a","b64":"YQ=="}]'),
        'payload_limit': result(json.dumps([{'name': 'a', 'b64': base64.b64encode(b'large').decode()}])),
    }
    if failure == 'payload_limit':
        monkeypatch.setattr(box, '_EXEC_FALLBACK_MAX_BYTES', 4)
    box.client.execute = AsyncMock(
        side_effect=RuntimeError('transport failure') if failure == 'transport' else None,
        return_value=replies.get(failure),
    )
    with pytest.raises(BoxError):
        await box.collect_outbound_attachments(query)
    box._clear_outbox.assert_not_awaited()
    assert file.read_bytes() == b'keep'


@pytest.mark.asyncio
@pytest.mark.parametrize('remote', [False, True])
@pytest.mark.parametrize('limit', ['file_bytes', 'total_bytes', 'file_count', 'depth', 'entries', 'directories'])
async def test_export_limit_failure_retains_every_file(env, monkeypatch, remote, limit):
    box, query, outbox = env
    if limit == 'file_bytes':
        monkeypatch.setattr(box, '_ATTACHMENT_MAX_BYTES', 3)
        monkeypatch.setattr(box, '_EXEC_FALLBACK_MAX_BYTES', 3)
    if limit == 'total_bytes':
        monkeypatch.setattr(box, '_ATTACHMENT_MAX_TOTAL_BYTES', 7)
    if limit == 'file_count':
        monkeypatch.setattr(box, '_ATTACHMENT_MAX_FILES', 1)
    (outbox / 'one').write_bytes(b'1234')
    (outbox / 'two').write_bytes(b'5678')
    if limit == 'depth':
        (outbox / Path(*(['nested'] * 9))).mkdir(parents=True)
    if limit == 'entries':
        for i in range(1001):
            (outbox / f'link-{i}').symlink_to('one')
    if limit == 'directories':
        for i in range(65):
            (outbox / f'directory-{i}').mkdir()
    before = sorted(str(p.relative_to(outbox)) for p in outbox.rglob('*'))
    box._clear_outbox = AsyncMock()
    box.client.execute = AsyncMock(side_effect=execute_script)
    if remote:
        monkeypatch.setattr(box, '_host_query_dir', lambda *args: None)
    with pytest.raises(BoxError):
        await box.collect_outbound_attachments(query)
    assert sorted(str(p.relative_to(outbox)) for p in outbox.rglob('*')) == before
    assert (outbox / 'one').read_bytes() == b'1234'
    assert (outbox / 'two').read_bytes() == b'5678'
    box._clear_outbox.assert_not_awaited()
    if not remote:
        box.client.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('remote', [False, True])
async def test_exact_limits_succeed_and_other_run_is_untouched(env, monkeypatch, remote):
    box, query, outbox = env
    monkeypatch.setattr(box, '_ATTACHMENT_MAX_FILES', 2)
    monkeypatch.setattr(box, '_ATTACHMENT_MAX_BYTES', 4)
    monkeypatch.setattr(box, '_EXEC_FALLBACK_MAX_BYTES', 4)
    monkeypatch.setattr(box, '_ATTACHMENT_MAX_TOTAL_BYTES', 8)
    (outbox / 'one').write_bytes(b'1234')
    (outbox / 'two').write_bytes(b'5678')
    other = outbox.parent / 'other-run'
    other.mkdir()
    (other / 'secret').write_bytes(b'other run')
    (outbox / 'link').symlink_to(other / 'secret')
    box.client.execute = AsyncMock(side_effect=execute_script)
    if remote:
        monkeypatch.setattr(box, '_host_query_dir', lambda *args: None)
        box.execute_tool = AsyncMock(
            side_effect=lambda *args: secure_fs.reset_directory(str(outbox.parent.parent), 'outbox', outbox.name)
        )
    attachments = await box.collect_outbound_attachments(query)
    assert {a['name']: base64.b64decode(a['base64']) for a in attachments} == {'one': b'1234', 'two': b'5678'}
    assert list(outbox.iterdir()) == []
    assert (other / 'secret').read_bytes() == b'other run'


@pytest.mark.asyncio
async def test_unsafe_host_path_never_uses_privileged_fallback(env):
    box, query, outbox = env
    outbox.rmdir()
    other = outbox.parent.parent / 'other-workspace'
    other.mkdir()
    (other / 'secret').write_bytes(b'private')
    outbox.symlink_to(other)
    box.client.execute = AsyncMock()
    with pytest.raises(BoxValidationError, match='symbolic link'):
        await box.collect_outbound_attachments(query)
    box.client.execute.assert_not_awaited()
    assert (other / 'secret').read_bytes() == b'private'


@pytest.mark.asyncio
async def test_host_io_error_is_not_retried_as_a_permission_failure(env, monkeypatch):
    box, query, outbox = env
    file = outbox / 'answer.txt'
    file.write_bytes(b'keep')
    original = secure_fs.os.open

    def fail_open(path, flags, *args, **kwargs):
        if path == 'answer.txt':
            raise OSError(errno.EIO, 'I/O failure')
        return original(path, flags, *args, **kwargs)

    monkeypatch.setattr(secure_fs.os, 'open', fail_open)
    box.client.execute = AsyncMock()
    box._clear_outbox = AsyncMock()
    with pytest.raises(BoxError, match='retained'):
        await box.collect_outbound_attachments(query)
    box.client.execute.assert_not_awaited()
    box._clear_outbox.assert_not_awaited()
    assert file.read_bytes() == b'keep'


@pytest.mark.asyncio
async def test_cancelled_export_does_not_clear_output(env, monkeypatch):
    box, query, outbox = env
    (outbox / 'answer.txt').write_bytes(b'keep')
    monkeypatch.setattr(box, '_host_query_dir', lambda *args: None)
    box.client.execute = AsyncMock(side_effect=asyncio.CancelledError())
    box._clear_outbox = AsyncMock()
    with pytest.raises(asyncio.CancelledError):
        await box.collect_outbound_attachments(query)
    box._clear_outbox.assert_not_awaited()
    assert (outbox / 'answer.txt').read_bytes() == b'keep'


@pytest.mark.asyncio
async def test_stale_workspace_result_does_not_clear_output(env, monkeypatch):
    box, query, outbox = env
    (outbox / 'answer.txt').write_bytes(b'keep')
    monkeypatch.setattr(box, '_host_query_dir', lambda *args: None)
    binding = box.ap.workspace_service.get_execution_binding.return_value
    box.ap.workspace_service.get_execution_binding.side_effect = [binding, BoxError('stale generation')]
    box.client.execute = AsyncMock(return_value=result('[{"name":"answer.txt","b64":"a2VlcA=="}]'))
    box._clear_outbox = AsyncMock()
    with pytest.raises(BoxError, match='stale generation'):
        await box.collect_outbound_attachments(query)
    box._clear_outbox.assert_not_awaited()
    assert (outbox / 'answer.txt').read_bytes() == b'keep'


@pytest.mark.asyncio
@pytest.mark.parametrize('limit', ['files', 'bytes'])
async def test_run_limit_failure_preserves_files_and_export_references_for_retry(env, monkeypatch, limit):
    from langbot.pkg.box.runner import RunnerBoxService, binding_for

    box, query, outbox = env
    api = RunnerBoxService(box)
    binding = binding_for(query)
    (outbox / 'one').write_bytes(b'ab')
    (outbox / 'two').write_bytes(b'cd')
    if limit == 'files':
        binding.exported.update({f'existing-{i}': {'size': 1} for i in range(99)})
    else:
        monkeypatch.setattr(box, '_ATTACHMENT_MAX_TOTAL_BYTES', 5)
        binding.exported['existing'] = {'size': 2}
    before = dict(binding.exported)
    with pytest.raises(BoxValidationError):
        await api.export_files(query)
    assert binding.exported == before
    assert (outbox / 'one').read_bytes() == b'ab'
    assert (outbox / 'two').read_bytes() == b'cd'

    # After the caller reduces its output, it can retry without duplicate IDs.
    (outbox / 'two').unlink()
    exported = await api.export_files(query)
    assert len(binding.exported) == len(before) + 1
    assert any(item['name'] == 'one' for item in exported['items'] if 'name' in item)
    assert list(outbox.iterdir()) == []


@pytest.mark.asyncio
async def test_unavailable_box_does_not_turn_runner_export_into_empty_cleanup(env):
    from langbot.pkg.box.runner import RunnerBoxService

    box, query, outbox = env
    box._available = False
    (outbox / 'answer.txt').write_bytes(b'keep')
    with pytest.raises(BoxError, match='not available'):
        await RunnerBoxService(box).export_files(query)
    assert (outbox / 'answer.txt').read_bytes() == b'keep'
