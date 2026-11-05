"""Opt-in validation against operator-provided Docker, E2B and nsjail."""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from . import test_workspaces
from tests.unit_tests.box.test_box_service import _make_queue_connection_pair
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.box.runner import RunnerBoxService
from langbot.pkg.box.service import BoxService
from langbot_plugin.box.backend import DockerBackend
from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.e2b_backend import E2BSandboxBackend
from langbot_plugin.box.nsjail_backend import NsjailBackend
from langbot_plugin.box.runtime import BoxRuntime
from langbot_plugin.box.server import BoxServerHandler
from langbot_plugin.runtime.io.handler import Handler

live_workspace_api = test_workspaces.workspace_api
_auth = test_workspaces._auth

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.skipif(os.getenv('LANGBOT_LIVE_WORKSPACE_BACKENDS') != '1', reason='requires three live backends'),
]


@pytest.mark.parametrize(
    'before,after', list(itertools.permutations(('docker', 'e2b', 'nsjail'), 2)) + [('e2b', 'e2b')]
)
async def test_live_workspace_switch_preserves_running_task(live_workspace_api, tmp_path, before, after):
    from e2b import AsyncSandbox

    ap, http, engine, token = live_workspace_api
    current = (await (await http.get('/api/v1/workspaces/current', headers=_auth(token))).get_json())['data']
    workspace_uuid = current['workspace']['uuid']
    headers = _auth(token, workspace_uuid)
    binding = await ap.workspace_service.get_execution_binding(workspace_uuid)
    context = ExecutionContext(
        instance_uuid=binding.instance_uuid,
        workspace_uuid=workspace_uuid,
        placement_generation=binding.placement_generation,
    )
    config = {
        'backend': 'docker',
        'local': {'host_root': str(tmp_path / 'boxes'), 'allowed_mount_roots': [str(tmp_path)]},
        'nsjail': {'cgroup_v1_parent': os.environ['LANGBOT_NSJAIL_CGROUP_V1_PARENT']},
    }
    ap.instance_config.data['box'] = config
    runtime = BoxRuntime(
        ap.logger,
        backends=[
            DockerBackend(ap.logger),
            E2BSandboxBackend(ap.logger),
            NsjailBackend(ap.logger, base_dir=str(tmp_path / 'jails')),
        ],
        session_ttl_sec=0,
    )
    runtime.init(config)
    await runtime.initialize()
    client_conn, server_conn = _make_queue_connection_pair()
    server = BoxServerHandler(
        server_conn, runtime, host_control_authenticated=True, trusted_instance_uuid=context.instance_uuid
    )
    handler = Handler(client_conn)
    server_task, client_task = asyncio.create_task(server.run()), asyncio.create_task(handler.run())
    client = ActionRPCBoxClient(logging.getLogger('live-switch'))
    client.set_handler(handler)
    box = BoxService(ap, client=client)
    ap.box_service = box
    await box.initialize()
    runner = RunnerBoxService(box)
    pending = None
    sandbox = None
    nonce = uuid.uuid4().hex
    started_name, release_name = f'started-{nonce}', f'release-{nonce}'
    host_workspace = Path(box.workspace_host_path(context))

    e2b_saves = 0

    async def select(name):
        nonlocal e2b_saves
        payload = {'backend': name}
        if name == 'e2b':
            payload['e2b'] = {
                'api_url': os.environ['E2B_API_URL'],
                'sandbox_url': os.environ['E2B_SANDBOX_URL'],
                'api_key': os.environ['E2B_API_KEY'],
                'template': '' if before == after and e2b_saves else 'base',
            }
            e2b_saves += 1
        response = await http.put('/api/v1/workspaces/current/sandbox', headers=headers, json=payload)
        assert response.status_code == 200, await response.get_json()
        assert (await response.get_json())['data']['effective_backend'] == name

    async def acquire(run_id):
        query = SimpleNamespace(
            query_id=run_id,
            query_uuid=run_id,
            variables={},
            _execution_context=context,
            _sandbox_backend=await box.resolve_workspace_backend(context),
        )
        image = 'base' if query._sandbox_backend == 'e2b' else 'python:3.12-alpine'
        acquired = await runner.acquire(context, {'reuse_key': 'shared', 'options': {'image': image}}, query)
        await runner.bind(context, query, run_id, acquired['id'])
        return query

    async def release():
        if sandbox is not None:
            await sandbox.files.write(f'/home/user/workspace/{release_name}', 'release')
        else:
            host_workspace.mkdir(parents=True, exist_ok=True)
            (host_workspace / release_name).write_text('release')

    try:
        response = await http.get('/api/v1/workspaces/current/sandbox?refresh=true', headers=headers)
        detected = (await response.get_json())['data']['backends']
        assert {item['name'] for item in detected if item['available']} == {'docker', 'e2b', 'nsjail'}, detected
        await select(before)
        old = await acquire(f'old-{nonce}')
        pending = asyncio.create_task(
            box.execute_tool(
                {
                    'command': (
                        f'printf old-{before} > /workspace/{started_name}; '
                        f'while [ ! -f /workspace/{release_name} ]; do sleep 0.1; done; '
                        f'cat /workspace/{started_name}'
                    )
                },
                old,
            )
        )
        if before == 'e2b':
            sessions = await client.get_sessions(action_context=box._action_context(context))
            info = next(item for item in sessions if item['session_id'] == old._box_binding.session_id)
            sandbox = await AsyncSandbox.connect(info['backend_session_id'])
            for _ in range(100):
                try:
                    marker = await sandbox.files.read(f'/home/user/workspace/{started_name}')
                except Exception:
                    await asyncio.sleep(0.1)
                    continue
                assert marker == 'old-e2b'
                break
            else:
                raise AssertionError('Old E2B task did not reach its wait loop')
        else:
            for _ in range(100):
                if (host_workspace / started_name).exists():
                    break
                if pending.done():
                    raise AssertionError(await pending)
                await asyncio.sleep(0.1)
            assert (host_workspace / started_name).read_text() == f'old-{before}'
        assert not pending.done()
        if before == 'nsjail':
            parent = os.environ['LANGBOT_NSJAIL_CGROUP_V1_PARENT']
            values = {}
            for controller, files in {
                'memory': ['memory.limit_in_bytes', 'memory.memsw.limit_in_bytes'],
                'pids': ['pids.max'],
                'cpu': ['cpu.cfs_period_us', 'cpu.cfs_quota_us'],
            }.items():
                children = [p for p in (Path('/sys/fs/cgroup') / controller / parent).iterdir() if p.is_dir()]
                assert len(children) == 1, children
                values.update({name: int((children[0] / name).read_text()) for name in files})
            assert values['memory.limit_in_bytes'] == values['memory.memsw.limit_in_bytes'] == 512 * 1024 * 1024
            assert values['pids.max'] == 128
            assert values['cpu.cfs_quota_us'] / values['cpu.cfs_period_us'] == 1
            print('NSJAIL_KERNEL_LIMITS', json.dumps(values), flush=True)
        old_completed = before == after
        if old_completed:
            # The trial E2B service permits one sandbox; free its slot for the new creation probe.
            assert not pending.done(), 'Old task ended before the template update'
            await release()
            result = await asyncio.wait_for(pending, 15)
            assert result['ok'] and result['backend'] == before and result['stdout'] == f'old-{before}', result
            again = await box.execute_tool({'command': f'cat /workspace/{started_name}'}, old)
            assert again['ok'] and again['backend'] == before and again['stdout'] == f'old-{before}', again
            await client.delete_session(old._box_binding.session_id, action_context=box._action_context(context))
        await select(after)
        new = await acquire(f'new-{nonce}')
        assert old._box_binding.session_id != new._box_binding.session_id
        result = await box.execute_tool({'command': f'printf new-{after}'}, new)
        assert result['ok'] and result['backend'] == after and result['stdout'] == f'new-{after}', result
        if not old_completed:
            assert not pending.done(), 'Workspace update interrupted the old task'
            await release()
            result = await asyncio.wait_for(pending, 15)
            assert result['ok'] and result['backend'] == before and result['stdout'] == f'old-{before}', result
            again = await box.execute_tool({'command': f'cat /workspace/{started_name}'}, old)
            assert again['ok'] and again['backend'] == before and again['stdout'] == f'old-{before}', again
        print(
            'LIVE_SWITCH_PASS',
            json.dumps(
                {'from': before, 'to': after, 'new_backend': after, 'old_backend': before, 'old_files_preserved': True}
            ),
            flush=True,
        )
    finally:
        if pending is not None and not pending.done():
            await release()
            await asyncio.gather(pending, return_exceptions=True)
        await box.shutdown()
        server_task.cancel()
        client_task.cancel()
        await asyncio.gather(server_task, client_task, return_exceptions=True)
