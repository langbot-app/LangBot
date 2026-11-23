"""Permission recovery must keep sandbox exports inside the bound run."""

import asyncio
import errno
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.box.models import BoxExecutionResult, BoxExecutionStatus
from langbot.pkg.box import secure_fs
from tests.unit_tests.box import test_box_service as fixtures


@pytest.mark.parametrize('denied_component', ['root', 'outbox', 'run', 'nested', 'answer.txt'])
def test_unreadable_host_file_is_not_silently_dropped(tmp_path, monkeypatch, denied_component):
    outbox = tmp_path / 'outbox' / 'run' / 'nested'
    outbox.mkdir(parents=True)
    (outbox / 'answer.txt').write_bytes(b'private output')
    original_open = os.open

    def denied_open(path, flags, *args, **kwargs):
        target = str(tmp_path) if denied_component == 'root' else denied_component
        if path == target:
            raise PermissionError(errno.EACCES, 'container-owned output', path)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(secure_fs.os, 'open', denied_open)
    with pytest.raises(PermissionError):
        secure_fs.read_regular_files(
            str(tmp_path), 'outbox', 'run', max_file_bytes=1024, max_files=20, max_total_bytes=4096
        )


def test_host_outbox_skips_fifo_without_waiting_for_a_writer(tmp_path):
    outbox = tmp_path / 'outbox' / 'run'
    outbox.mkdir(parents=True)
    os.mkfifo(outbox / 'pipe')
    script = (
        'from langbot.pkg.box import secure_fs; '
        f'assert secure_fs.read_regular_files({str(tmp_path)!r}, "outbox", "run", '
        'max_file_bytes=1024, max_files=20, max_total_bytes=4096) == []'
    )
    subprocess.run([sys.executable, '-c', script], check=True, timeout=3)


@pytest.mark.asyncio
async def test_unreadable_host_output_uses_the_bound_sandbox(tmp_path):
    service, workspace = fixtures.TestAttachmentHostPath()._service_with_workspace(tmp_path)
    query = fixtures.make_query()
    outbox = Path(workspace) / 'outbox'
    current = outbox / 'query-42'
    current.mkdir(parents=True)
    (current / 'answer.txt').write_bytes(b'private output')
    (current / ' answer.txt ').write_bytes(b'spaced output')
    other = outbox / 'other-run'
    other.mkdir()
    (other / 'secret.txt').write_bytes(b'other run secret')
    (current / 'leak.txt').symlink_to(other / 'secret.txt')
    service.OUTBOX_MOUNT_DIR = str(outbox)
    service._read_outbox_host = Mock(side_effect=PermissionError('container-owned output'))
    service._clear_outbox = AsyncMock()
    observed = []

    async def execute(spec, *, action_context):
        assert action_context == fixtures._ACTION_CONTEXT
        assert spec.session_id == 'person_test_user'
        assert spec.host_path == workspace
        process = await asyncio.create_subprocess_shell(
            spec.cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        observed.append(spec)
        return BoxExecutionResult(
            session_id=spec.session_id,
            backend_name='test',
            status=BoxExecutionStatus.COMPLETED,
            exit_code=process.returncode,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
            duration_ms=0,
        )

    service.client.execute = AsyncMock(side_effect=execute)
    attachments = await service.collect_outbound_attachments(query)
    assert {item['name']: item['base64'] for item in attachments} == {
        'answer.txt': 'cHJpdmF0ZSBvdXRwdXQ=',
        ' answer.txt ': 'c3BhY2VkIG91dHB1dA==',
    }
    assert len(observed) == 1
    assert (other / 'secret.txt').read_bytes() == b'other run secret'
    service._clear_outbox.assert_awaited_once_with(query, str(current))


def _script(root, operation='read', **limits):
    from langbot.pkg.box.sandbox_files import outbox_script

    return outbox_script(
        str(root / 'workspace' / 'outbox'),
        'run',
        operation=operation,
        max_file_bytes=limits.get('max_file_bytes', 1024),
        max_files=limits.get('max_files', 20),
        max_total_bytes=limits.get('max_total_bytes', 4096),
    )


def _run_script(script):
    return subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=3)


@pytest.mark.parametrize('operation', ['read', 'clear'])
@pytest.mark.parametrize('component', ['workspace', 'outbox', 'run'])
def test_sandbox_outbox_never_follows_ancestor_links(tmp_path, operation, component):
    workspace = tmp_path / 'workspace'
    current = workspace / 'outbox' / 'run'
    current.mkdir(parents=True)
    other = tmp_path / 'other'
    other.mkdir()
    target = {
        'workspace': other / 'outbox' / 'run',
        'outbox': other / 'run',
        'run': other,
    }[component]
    target.mkdir(parents=True, exist_ok=True)
    protected = target / 'secret.txt'
    protected.write_bytes(b'other run secret')
    import shutil

    link = {'workspace': workspace, 'outbox': current.parent, 'run': current}[component]
    shutil.rmtree(link)
    link.symlink_to(other, target_is_directory=True)
    result = _run_script(_script(tmp_path, operation))
    assert result.returncode != 0
    assert protected.read_bytes() == b'other run secret'


@pytest.mark.parametrize('replacement', ['symlink', 'fifo', 'directory'])
def test_sandbox_file_open_resists_type_changes(tmp_path, replacement):
    import json

    current = tmp_path / 'workspace' / 'outbox' / 'run'
    current.mkdir(parents=True)
    (current / 'answer.txt').write_bytes(b'expected')
    secret = tmp_path / 'secret.txt'
    secret.write_bytes(b'outside secret')
    # Change the real filesystem after classification, immediately before open.
    prelude = f"""
import os
original_open = os.open
replacement = {replacement!r}
def racing_open(path, flags, *args, **kwargs):
    fd = kwargs.get('dir_fd')
    if path == 'answer.txt' and fd is not None:
        os.unlink(path, dir_fd=fd)
        if replacement == 'symlink':
            os.symlink({str(secret)!r}, path, dir_fd=fd)
        elif replacement == 'fifo':
            os.mkfifo({str(current / 'answer.txt')!r})
        else:
            os.mkdir(path, dir_fd=fd)
            child = original_open(path, os.O_RDONLY | os.O_DIRECTORY, dir_fd=fd)
            try:
                output = original_open('secret.txt', os.O_WRONLY | os.O_CREAT, 0o600, dir_fd=child)
                os.write(output, b'unexpected directory')
                os.close(output)
            finally:
                os.close(child)
    return original_open(path, flags, *args, **kwargs)
os.open = racing_open
"""
    result = _run_script(prelude + _script(tmp_path))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []
    assert secret.read_bytes() == b'outside secret'


@pytest.mark.parametrize('limit', ['file_bytes', 'total_bytes', 'total_bytes_exact', 'entries', 'directories'])
def test_sandbox_output_limits_fail_without_removing_files(tmp_path, limit):
    current = tmp_path / 'workspace' / 'outbox' / 'run'
    current.mkdir(parents=True)
    options = {}
    if limit == 'file_bytes':
        (current / 'answer.txt').write_bytes(b'1234')
        options['max_file_bytes'] = 3
    elif limit in {'total_bytes', 'total_bytes_exact'}:
        (current / 'a.txt').write_bytes(b'12')
        (current / 'b.txt').write_bytes(b'34')
        options['max_total_bytes'] = 3
        if limit == 'total_bytes_exact':
            (current / 'c.txt').write_bytes(b'56')
            options['max_total_bytes'] = 4
    elif limit == 'entries':
        for index in range(513):
            (current / str(index)).symlink_to(tmp_path / 'missing')
    else:
        for index in range(65):
            (current / str(index)).mkdir()
    before = set(current.iterdir())
    result = _run_script(_script(tmp_path, **options))
    assert result.returncode != 0
    assert 'limit' in result.stderr
    assert set(current.iterdir()) == before


def test_sandbox_output_count_and_depth_limits_retain_all_files(tmp_path):
    current = tmp_path / 'workspace' / 'outbox' / 'run'
    current.mkdir(parents=True)
    (current / 'a.txt').write_bytes(b'a')
    (current / 'b.txt').write_bytes(b'b')
    result = _run_script(_script(tmp_path, max_files=1))
    assert result.returncode != 0
    assert 'file-count limit' in result.stderr
    assert (current / 'a.txt').read_bytes() == b'a'
    assert (current / 'b.txt').read_bytes() == b'b'
    (current / 'a.txt').unlink()
    (current / 'b.txt').unlink()
    deep = current.joinpath(*('nested' for _ in range(9)))
    deep.mkdir(parents=True)
    (deep / 'too-deep.txt').write_bytes(b'not exported')
    result = _run_script(_script(tmp_path))
    assert result.returncode != 0
    assert 'depth limit' in result.stderr
    assert (deep / 'too-deep.txt').read_bytes() == b'not exported'


@pytest.mark.parametrize('operation', ['read', 'clear'])
def test_sandbox_nested_links_do_not_touch_their_targets(tmp_path, operation):
    import json

    current = tmp_path / 'workspace' / 'outbox' / 'run'
    current.mkdir(parents=True)
    other = tmp_path / 'other'
    other.mkdir()
    protected = other / 'secret.txt'
    protected.write_bytes(b'protected')
    (current / 'linked-dir').symlink_to(other, target_is_directory=True)
    (current / 'linked-file').symlink_to(protected)
    result = _run_script(_script(tmp_path, operation))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []
    assert protected.read_bytes() == b'protected'
    if operation == 'clear':
        assert list(current.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['permission', 'truncated-json'])
async def test_permission_recovery_failure_does_not_clear_output(tmp_path, failure):
    from langbot_plugin.box.errors import BoxValidationError

    service, workspace = fixtures.TestAttachmentHostPath()._service_with_workspace(tmp_path)
    query = fixtures.make_query()
    current = Path(workspace) / 'outbox' / 'query-42'
    current.mkdir(parents=True)
    output = current / 'answer.txt'
    output.write_bytes(b'keep on failure')
    service._read_outbox_host = Mock(side_effect=PermissionError('container-owned output'))
    service._clear_outbox = AsyncMock()
    service.client.execute = AsyncMock(
        return_value=BoxExecutionResult(
            session_id='person_test_user',
            backend_name='test',
            status=BoxExecutionStatus.COMPLETED,
            exit_code=1 if failure == 'permission' else 0,
            stdout='' if failure == 'permission' else '[{"name": "answer.txt", "b64": "truncated',
            stderr='Permission denied' if failure == 'permission' else '',
            duration_ms=0,
        )
    )
    error = 'Failed to read sandbox outbox' if failure == 'permission' else 'invalid attachment data'
    with pytest.raises(BoxValidationError, match=error):
        await service.collect_outbound_attachments(query)
    service._clear_outbox.assert_not_awaited()
    assert output.read_bytes() == b'keep on failure'


@pytest.mark.asyncio
async def test_changed_outbox_ancestor_never_uses_cleanup_exec(tmp_path):
    service, workspace = fixtures.TestAttachmentHostPath()._service_with_workspace(tmp_path)
    query = fixtures.make_query()
    outbox = Path(workspace) / 'outbox'
    other = tmp_path / 'other'
    protected = other / 'query-42' / 'secret.txt'
    protected.parent.mkdir(parents=True)
    protected.write_bytes(b'keep other run')
    outbox.symlink_to(other, target_is_directory=True)
    service.execute_tool = AsyncMock(side_effect=AssertionError('unsafe host ancestor must not use exec'))
    await service._clear_outbox(query, str(outbox / 'query-42'))
    service.execute_tool.assert_not_awaited()
    assert protected.read_bytes() == b'keep other run'
    assert any('unsafe sandbox outbox' in str(call.args[0]) for call in service.ap.logger.warning.call_args_list)


def test_sandbox_cleanup_has_a_bounded_inode_budget(tmp_path):
    current = tmp_path / 'workspace' / 'outbox' / 'run'
    current.mkdir(parents=True)
    for index in range(4097):
        (current / str(index)).write_bytes(b'')
    result = _run_script(_script(tmp_path, 'clear'))
    assert result.returncode != 0
    assert 'inode limit' in result.stderr
    assert list(current.iterdir())


def test_host_reset_preserves_permission_error_for_private_run_directory(tmp_path, monkeypatch):
    current = tmp_path / 'outbox' / 'run'
    current.mkdir(parents=True)
    original_open = os.open

    def denied_open(path, flags, *args, **kwargs):
        if path == 'run' and kwargs.get('dir_fd') is not None:
            raise PermissionError(errno.EACCES, 'private container directory', path)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(secure_fs.os, 'open', denied_open)
    with pytest.raises(PermissionError):
        secure_fs.reset_directory(str(tmp_path), 'outbox', 'run')
