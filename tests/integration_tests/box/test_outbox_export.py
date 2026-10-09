"""Real Docker file export through Core and the SDK, with ownership evidence."""

import base64
import json
import logging
import os
import shlex
import sys
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.box.runner import RunnerBoxService, binding_for, exported_message
from langbot.pkg.box.service import BoxService
from langbot_plugin.api.entities.builtin.platform.message import File, MessageChain
from langbot_plugin.box.backend import DockerBackend
from langbot_plugin.box.runtime import BoxRuntime
from tests.unit_tests.box.test_box_service import _InProcessBoxRuntimeClient, make_app, make_query, _CONTEXT


class _TestDockerBackend(DockerBackend):
    async def cleanup_orphaned_containers(self, current_instance_id=''):
        # Never inspect or remove another developer's Box containers.
        pass


class _Client(_InProcessBoxRuntimeClient):
    async def create_session(self, spec, *, action_context=None):
        return await self._runtime.create_session(spec, action_context=action_context)

    async def execute(self, spec, *, action_context=None):
        return await self._runtime.execute(spec, action_context=action_context)

    async def get_sessions(self, *, action_context=None):
        return self._runtime.get_sessions_for_workspace(action_context)


@pytest.mark.asyncio
async def test_root_owned_output_exports_from_reused_box_without_cross_run_leaks(tmp_path, monkeypatch):
    logger = logging.getLogger('test.box.outbox')
    backend = _TestDockerBackend(logger)
    if not await backend.is_available():
        pytest.skip('Docker is required for file ownership/export integration')
    if sys.platform == 'linux' and os.geteuid() == 0:
        pytest.skip('the Linux ownership regression requires non-root Core')
    app = make_app(logger, allowed_mount_roots=[str(tmp_path)], host_root=str(tmp_path / 'box'))
    app.instance_config.data['box']['backend'] = 'docker'
    app.instance_config.data['box']['local']['image'] = 'python:3.12-alpine'
    runtime = BoxRuntime(logger=logger, backends=[backend], max_sessions=1)
    box = BoxService(app, client=_Client(logger, runtime))
    api = RunnerBoxService(box)
    await box.initialize()
    original_reader = box._read_outbox_via_exec
    box._read_outbox_via_exec = AsyncMock(wraps=original_reader)
    try:
        first_box = await api.acquire(_CONTEXT, {'reuse_key': 'export-regression'})
        previous_file_id = None
        for index in range(2):
            acquired = await api.acquire(_CONTEXT, {'reuse_key': 'export-regression'})
            assert acquired['id'] == first_box['id']
            query = make_query(index)
            object.__setattr__(query, '_box_binding', None)
            await api.bind(_CONTEXT, query, f'export-run-{index}', acquired['id'])
            payload = f'exact input for run {index}'.encode()
            query.message_chain = MessageChain([File(name='input.txt', base64=base64.b64encode(payload).decode())])
            imported = await api.import_attachments(query, None)
            source = imported['items'][0]['path']
            outbox = f'/workspace/outbox/{binding_for(query).io_scope}'
            target = outbox + '/answer.txt'
            copied = await box.execute_tool(
                {'command': f'mkdir -p {shlex.quote(outbox)} && cp {shlex.quote(source)} {shlex.quote(target)}'},
                query,
            )
            assert copied['ok'], copied
            stat_script = (
                'import json, os, stat; '
                f's = os.stat({target!r}); '
                'print(json.dumps(dict(uid=s.st_uid, gid=s.st_gid, mode=stat.S_IMODE(s.st_mode))))'
            )
            evidence = await box.execute_tool({'command': 'python3 -c ' + shlex.quote(stat_script)}, query)
            assert evidence['ok'], evidence
            metadata = json.loads(evidence['stdout'])
            print(f'Core uid={os.geteuid()}; Docker copy: {metadata}')
            assert metadata['mode'] == 0o600
            if sys.platform == 'linux':
                # Linux CI exercises the issue's exact root-owned 0600 case.
                assert metadata['uid'] == 0
                assert metadata['gid'] == 0
            with monkeypatch.context() as patch:
                if sys.platform != 'linux':
                    # Docker Desktop maps ownership/permissions across its VM.
                    # Exercise the real remote reader here; Linux CI must reach
                    # it via the actual host PermissionError, without patching.
                    patch.setattr(box, '_host_query_dir', lambda *args: None)
                exported = await api.export_files(query)
            assert len(exported['items']) == 1
            item = exported['items'][0]
            assert item['size'] == len(payload)
            assert item['name'] == 'answer.txt'
            message = exported_message(query, [item['id']])
            assert base64.b64decode(message.root[0].base64) == payload
            if previous_file_id:
                from langbot_plugin.box.errors import BoxValidationError

                with pytest.raises(BoxValidationError, match='does not belong'):
                    exported_message(query, [previous_file_id])
            previous_file_id = item['id']
            remaining = await box.execute_tool({'command': f'find {shlex.quote(outbox)} -type f'}, query)
            assert remaining['ok'], remaining
            assert remaining['stdout'].strip() == ''
            assert len(await api.sessions(_CONTEXT)) == 1
        assert box._read_outbox_via_exec.await_count == 2
    finally:
        await box.shutdown()
