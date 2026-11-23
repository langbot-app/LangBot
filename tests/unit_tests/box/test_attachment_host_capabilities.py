from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.box.service import BoxService
from langbot_plugin.box.client import BoxRuntimeClient
from tests.unit_tests.box.test_box_service import make_app, make_query


@pytest.mark.asyncio
async def test_host_without_openat_uses_sandbox_attachment_channel(monkeypatch, tmp_path):
    monkeypatch.setattr('os.supports_dir_fd', set())
    service = BoxService(make_app(Mock()), client=Mock(spec=BoxRuntimeClient))
    service._available = True
    service._tenant_workspace = Mock(return_value=str(tmp_path))
    service._read_outbox_host = Mock(side_effect=AssertionError('POSIX host reader must not run'))
    service._read_outbox_via_exec = AsyncMock(return_value=[])
    service._clear_outbox = AsyncMock()
    query = make_query()
    assert service._host_query_dir(service.OUTBOX_SUBDIR, query) is None
    assert await service.collect_outbound_attachments(query) == []
    service._read_outbox_via_exec.assert_awaited_once_with(query)
    service._clear_outbox.assert_awaited_once_with(query, None)


@pytest.mark.asyncio
async def test_outbox_exec_preserves_workspace_and_full_attachment(monkeypatch, tmp_path):
    import base64
    import json
    from langbot_plugin.box.models import BoxExecutionResult, BoxExecutionStatus

    monkeypatch.setattr('os.supports_dir_fd', set())
    client = Mock(spec=BoxRuntimeClient)
    content = base64.b64encode(b'file content' * 1000).decode()
    client.execute = AsyncMock(
        return_value=BoxExecutionResult(
            session_id='person_test_user',
            backend_name='docker',
            status=BoxExecutionStatus.COMPLETED,
            exit_code=0,
            stdout=json.dumps([{'name': 'report.txt', 'b64': content}]),
            stderr='',
            duration_ms=1,
        )
    )
    service = BoxService(make_app(Mock(), [str(tmp_path)]), client=client, output_limit_chars=100)
    service._available = True
    service._tenant_workspace = Mock(return_value=str(tmp_path))
    service._clear_outbox = AsyncMock()
    query = make_query()
    attachments = await service.collect_outbound_attachments(query)
    assert attachments == [{'type': 'File', 'name': 'report.txt', 'base64': content}]
    call = client.execute.await_args
    assert call.kwargs['action_context'].workspace_uuid == query.workspace_uuid
    assert call.kwargs['action_context'].instance_uuid == query.instance_uuid
    assert call.args[0].host_path == str(tmp_path)
    assert call.args[0].session_id == 'person_test_user'
    service._clear_outbox.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['rpc', 'command', 'invalid_json'])
async def test_outbox_read_failure_keeps_files(monkeypatch, failure):
    from langbot_plugin.box.errors import BoxValidationError
    from langbot_plugin.box.models import BoxExecutionResult, BoxExecutionStatus

    monkeypatch.setattr('os.supports_dir_fd', set())
    client = Mock(spec=BoxRuntimeClient)
    client.execute = AsyncMock(
        return_value=BoxExecutionResult(
            session_id='person_test_user',
            backend_name='docker',
            status=BoxExecutionStatus.COMPLETED,
            exit_code=1 if failure == 'command' else 0,
            stdout='not json',
            stderr='',
            duration_ms=1,
        )
    )
    if failure == 'rpc':
        client.execute.side_effect = BoxValidationError('missing context')
    service = BoxService(make_app(Mock()), client=client)
    service._available = True
    service._clear_outbox = AsyncMock()
    with pytest.raises(BoxValidationError):
        await service.collect_outbound_attachments(make_query())
    service._clear_outbox.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('oversized', [False, True])
async def test_real_outbox_reader_handles_image_above_old_256k_limit(tmp_path, monkeypatch, oversized):
    import asyncio
    import base64
    import sys
    from langbot_plugin.box.errors import BoxValidationError
    from langbot_plugin.box.models import BoxExecutionResult, BoxExecutionStatus

    monkeypatch.setattr('os.supports_dir_fd', set())
    service = BoxService(make_app(Mock()), client=Mock(spec=BoxRuntimeClient))
    service._available = True
    service.OUTBOX_MOUNT_DIR = tmp_path.as_posix()
    if oversized:
        service._ATTACHMENT_MAX_BYTES = 300000
    folder = tmp_path / 'query-42'
    folder.mkdir()
    payload = b'\x89PNG\r\n\x1a\n' + b'x' * (343154 - 8)
    (folder / 'sunset.png').write_bytes(payload)

    async def execute_script(spec, query):
        script = spec['cmd'].split('\n', 1)[1].rsplit('\nLBPY', 1)[0]
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            '-c',
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return BoxExecutionResult(
            session_id='person_test_user',
            backend_name='test',
            status=BoxExecutionStatus.COMPLETED,
            exit_code=process.returncode,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
            duration_ms=1,
        )

    service._execute_spec_payload_result = execute_script
    service._clear_outbox = AsyncMock()
    if oversized:
        with pytest.raises(BoxValidationError):
            await service.collect_outbound_attachments(make_query())
        service._clear_outbox.assert_not_awaited()
        assert (folder / 'sunset.png').exists()
    else:
        attachments = await service.collect_outbound_attachments(make_query())
        assert len(attachments) == 1
        assert attachments[0]['type'] == 'Image'
        assert base64.b64decode(attachments[0]['base64'].split(',', 1)[1]) == payload
        service._clear_outbox.assert_awaited_once()
