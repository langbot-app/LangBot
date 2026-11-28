"""Opt-in validation against operator-provided Docker, E2B and nsjail."""

from __future__ import annotations

import asyncio
import itertools
import hashlib
import json
import logging
import os
from pathlib import Path
import shlex
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
        data_dir=tmp_path / 'identity',
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
        payload = {'backend': name, 'limits': {'timeout_sec': 120}}
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
                    'timeout_sec': 120,
                    'command': (
                        f'printf old-{before} > /workspace/{started_name}; '
                        f'while [ ! -f /workspace/{release_name} ]; do sleep 0.1; done; '
                        f'cat /workspace/{started_name}'
                    ),
                },
                old,
            )
        )
        if before == 'e2b':
            sessions = await client.get_sessions(action_context=box._action_context(context))
            info = next(item for item in sessions if item['session_id'] == old._box_binding.session_id)
            sandbox = await AsyncSandbox.connect(
                info['backend_session_id'],
                headers={'E2b-Sandbox-Id': info['backend_session_id'], 'E2b-Sandbox-Port': '49983'},
            )
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
        await select(after)
        assert not pending.done(), 'Saving the sandbox revision interrupted the old task'
        new = await acquire(f'new-{nonce}')
        assert old._box_binding.session_id != new._box_binding.session_id
        if before == after == 'e2b':
            sessions = await client.get_sessions(action_context=box._action_context(context))
            session_ids = {old._box_binding.session_id, new._box_binding.session_id}
            backend_ids = {item['backend_session_id'] for item in sessions if item['session_id'] in session_ids}
            assert len(backend_ids) == 2, sessions
            active = await AsyncSandbox.list().next_items()
            assert backend_ids <= {item.sandbox_id for item in active}
            print('LIVE_DUAL_E2B_ACTIVE', json.dumps(sorted(backend_ids)), flush=True)
        result = await box.execute_tool({'command': f'printf new-{after}'}, new)
        assert result['ok'] and result['backend'] == after and result['stdout'] == f'new-{after}', result
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


@pytest.fixture
async def sandbox_limits_live(live_workspace_api, tmp_path):
    ap, http, _, token = live_workspace_api
    current = (await (await http.get('/api/v1/workspaces/current', headers=_auth(token))).get_json())['data']
    ws = current['workspace']['uuid']
    binding = await ap.workspace_service.get_execution_binding(ws)
    context = ExecutionContext(
        instance_uuid=binding.instance_uuid, workspace_uuid=ws, placement_generation=binding.placement_generation
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
        data_dir=tmp_path / 'identity',
    )
    runtime.init(config)
    await runtime.initialize()
    left, right = _make_queue_connection_pair()
    server = BoxServerHandler(
        right, runtime, host_control_authenticated=True, trusted_instance_uuid=context.instance_uuid
    )
    handler = Handler(left)
    tasks = [asyncio.create_task(server.run()), asyncio.create_task(handler.run())]
    client = ActionRPCBoxClient(logging.getLogger('limits-live'))
    client.set_handler(handler)
    ap.box_service = box = BoxService(ap, client=client)
    await box.initialize()
    try:
        yield box, runtime, http, _auth(token, ws), context, client
    finally:
        await box.shutdown()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.parametrize('box_count', [2, 8, 16])
async def test_live_e2b_concurrent_boxes_create_execute_isolate_and_cleanup(sandbox_limits_live, box_count):
    from e2b import AsyncSandbox

    box, _, http, headers, context, client = sandbox_limits_live
    runner = RunnerBoxService(box)
    nonce = uuid.uuid4().hex
    response = await http.put(
        '/api/v1/workspaces/current/sandbox',
        headers=headers,
        json={
            'backend': 'e2b',
            'e2b': {
                'api_url': os.environ['E2B_API_URL'],
                'sandbox_url': os.environ['E2B_SANDBOX_URL'],
                'api_key': os.environ['E2B_API_KEY'],
                'template': 'base',
            },
            'limits': {'timeout_sec': 120, 'max_sessions': box_count, 'idle_ttl_sec': 60},
        },
    )
    assert response.status_code == 200, await response.get_json()
    selected = await box.resolve_workspace_selection(context)

    async def acquire(own):
        run_id = f'{own}-{nonce}'
        query = SimpleNamespace(
            query_id=run_id,
            query_uuid=run_id,
            variables={},
            _execution_context=context,
            _sandbox_backend=selected['backend'],
            _sandbox_e2b_config=selected['e2b'],
            _sandbox_limits=selected['limits'],
        )
        acquired = await runner.acquire(context, {'reuse_key': run_id, 'options': {'image': 'base'}}, query)
        await runner.bind(context, query, run_id, acquired['id'])
        return query

    queries = await asyncio.gather(*(acquire(str(index)) for index in range(box_count)))
    session_ids = {query._box_binding.session_id for query in queries}
    assert len(session_ids) == box_count
    sessions = await client.get_sessions(action_context=box._action_context(context))
    backend_by_session = {
        item['session_id']: item['backend_session_id'] for item in sessions if item['session_id'] in session_ids
    }
    backend_ids = set(backend_by_session.values())
    assert len(backend_ids) == box_count
    active = await AsyncSandbox.list().next_items()
    assert backend_ids <= {item.sandbox_id for item in active}
    print('LIVE_E2B_CONCURRENT_CREATED', json.dumps({'count': box_count, 'ids': sorted(backend_ids)}), flush=True)

    async def connect(query):
        sandbox_id = backend_by_session[query._box_binding.session_id]
        return await AsyncSandbox.connect(
            sandbox_id, headers={'E2b-Sandbox-Id': sandbox_id, 'E2b-Sandbox-Port': '49983'}
        )

    sandboxes = await asyncio.gather(*(connect(query) for query in queries))

    async def execute(query, own):
        # /workspace is intentionally shared by runs in one Workspace; /tmp is Box-local.
        script = f"""import json,time
from pathlib import Path
p=Path('/tmp/langbot-{nonce}')
p.mkdir()
(p/'same-name').write_text({own!r})
(p/'only-{own}').write_text({own!r})
start=time.time()
(p/'ready').write_text('ready')
while not (p/'release').exists():
    assert time.time()-start < 45, 'test barrier timed out'
    time.sleep(0.1)
assert (p/'same-name').read_text()=={own!r}
assert sorted(x.name for x in p.glob('only-*'))==['only-{own}']
print(json.dumps(dict(own={own!r},start=start,end=time.time())))
"""
        result = await box.execute_tool({'command': 'python3 -c ' + shlex.quote(script)}, query)
        assert result['ok'] and result['backend'] == 'e2b', result
        return json.loads(result['stdout'])

    tasks = [asyncio.create_task(execute(query, str(index))) for index, query in enumerate(queries)]

    async def wait_ready(sandbox, task):
        for _ in range(200):
            if task.done():
                raise AssertionError(await task)
            try:
                ready = await sandbox.files.read(f'/tmp/langbot-{nonce}/ready')
            except Exception:
                await asyncio.sleep(0.1)
                continue
            assert ready == 'ready'
            return
        raise AssertionError('E2B command did not reach its test barrier')

    try:
        await asyncio.gather(*(wait_ready(sandbox, task) for sandbox, task in zip(sandboxes, tasks)))
        assert all(not task.done() for task in tasks)
        await asyncio.gather(*(sandbox.files.write(f'/tmp/langbot-{nonce}/release', 'go') for sandbox in sandboxes))
        results = await asyncio.wait_for(asyncio.gather(*tasks), 30)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert min(item['end'] for item in results) > max(item['start'] for item in results), results
    await client.delete_session(queries[0]._box_binding.session_id, action_context=box._action_context(context))
    result = await box.execute_tool({'command': f'cat /tmp/langbot-{nonce}/same-name'}, queries[-1])
    assert result['ok'] and result['stdout'] == str(box_count - 1), result
    for query in queries[1:]:
        await client.delete_session(query._box_binding.session_id, action_context=box._action_context(context))
    sessions = await client.get_sessions(action_context=box._action_context(context))
    assert not session_ids & {item['session_id'] for item in sessions}
    active = await AsyncSandbox.list().next_items()
    assert not backend_ids & {item.sandbox_id for item in active}
    print('LIVE_E2B_CONCURRENT_PASS', json.dumps({'count': box_count, 'commands': results}), flush=True)


async def test_live_e2b_save_never_creates_and_explicit_test_cleans_up(sandbox_limits_live, monkeypatch):
    from e2b import AsyncSandbox
    from langbot.pkg.box.settings import get_settings

    box, _, http, headers, context, _ = sandbox_limits_live
    original = AsyncSandbox.create
    calls, created = [], []

    async def create(**kwargs):
        calls.append(kwargs.get('template'))
        sandbox = await original(**kwargs)
        created.append(sandbox.sandbox_id)
        return sandbox

    monkeypatch.setattr(AsyncSandbox, 'create', staticmethod(create))
    draft = {
        'api_url': os.environ['E2B_API_URL'],
        'sandbox_url': os.environ['E2B_SANDBOX_URL'],
        'api_key': os.environ['E2B_API_KEY'],
        'template': 'base',
    }
    for method, path, body in [
        ('post', '/api/v1/workspaces/current/sandbox/check', {'e2b': draft}),
        (
            'put',
            '/api/v1/workspaces/current/sandbox',
            {'backend': 'e2b', 'e2b': draft, 'limits': {'timeout_sec': 2, 'max_sessions': 1, 'idle_ttl_sec': 60}},
        ),
    ]:
        response = await getattr(http, method)(path, headers=headers, json=body)
        assert response.status_code == 200, await response.get_json()
        info = next(item for item in (await response.get_json())['data']['backends'] if item['name'] == 'e2b')
        assert info['template_validation'] == 'unsupported' and info['available']
        assert not info['limit_capabilities'].get('memory_mb')
    assert calls == []
    stored = hashlib.sha256(
        json.dumps(await get_settings(box.ap, context.workspace_uuid), sort_keys=True).encode()
    ).hexdigest()
    response = await http.post('/api/v1/workspaces/current/sandbox/test', headers=headers, json={'e2b': draft})
    assert response.status_code == 200
    info = next(item for item in (await response.get_json())['data']['backends'] if item['name'] == 'e2b')
    assert info['template_validated'] and info['available'], info
    assert calls == ['base']
    remaining = {item.sandbox_id for item in await AsyncSandbox.list(limit=20).next_items()}
    assert not remaining.intersection(created)
    assert (
        hashlib.sha256(
            json.dumps(await get_settings(box.ap, context.workspace_uuid), sort_keys=True).encode()
        ).hexdigest()
        == stored
    )
    bad = {**draft, 'template': 'langbot-missing-template-for-validation'}
    response = await http.post('/api/v1/workspaces/current/sandbox/test', headers=headers, json={'e2b': bad})
    info = next(item for item in (await response.get_json())['data']['backends'] if item['name'] == 'e2b')
    assert not info['available'] and info['reason'] == 'template_not_found', info
    assert (
        hashlib.sha256(
            json.dumps(await get_settings(box.ap, context.workspace_uuid), sort_keys=True).encode()
        ).hexdigest()
        == stored
    )
    print(
        'LIVE_LIGHTWEIGHT_SAVE_NO_CREATE; EXPLICIT_TEST_EXECUTED_AND_CLEANED; UNKNOWN_TEMPLATE_CLASSIFIED', flush=True
    )


@pytest.mark.parametrize('backend', ['docker', 'nsjail'])
async def test_live_workspace_limits_snapshot_capacity_timeout_and_kernel(sandbox_limits_live, backend):
    from langbot_plugin.box.errors import BoxError

    box, runtime, http, headers, context, client = sandbox_limits_live
    runner = RunnerBoxService(box)

    async def select(limits):
        response = await http.put(
            '/api/v1/workspaces/current/sandbox', headers=headers, json={'backend': backend, 'limits': limits}
        )
        assert response.status_code == 200, await response.get_json()

    async def acquire(name):
        selected = await box.resolve_workspace_selection(context)
        query = SimpleNamespace(
            query_id=name,
            query_uuid=name,
            variables={},
            _execution_context=context,
            _sandbox_backend=selected['backend'],
            _sandbox_e2b_config=selected['e2b'],
            _sandbox_limits=selected['limits'],
        )
        acquired = await runner.acquire(context, {'reuse_key': name, 'options': {'image': 'python:3.12-alpine'}}, query)
        await runner.bind(context, query, name, acquired['id'])
        return query

    await select(
        {'timeout_sec': 10, 'idle_ttl_sec': 60, 'max_sessions': 2, 'cpus': 0.5, 'memory_mb': 128, 'pids_limit': 32}
    )
    old = await acquire('old-limits')
    # Probe the limits from inside the actual kernel/container environment.
    parent = os.environ['LANGBOT_NSJAIL_CGROUP_V1_PARENT']
    nonce = uuid.uuid4().hex
    started = Path(box.workspace_host_path(context)) / f'limits-started-{nonce}'
    release = started.with_name(f'limits-release-{nonce}')
    pending = asyncio.create_task(
        box.execute_tool(
            {
                'command': f'printf ready > /workspace/{started.name}; while [ ! -f /workspace/{release.name} ]; do sleep .1; done; printf old'
            },
            old,
        )
    )
    try:
        for _ in range(100):
            if started.exists():
                break
            if pending.done():
                raise AssertionError(await pending)
            await asyncio.sleep(0.1)
        assert started.exists()
        if backend == 'nsjail':
            root = Path('/sys/fs/cgroup')
            values = {}
            for controller, filename in [
                ('memory', 'memory.limit_in_bytes'),
                ('memory', 'memory.memsw.limit_in_bytes'),
                ('pids', 'pids.max'),
                ('cpu', 'cpu.cfs_quota_us'),
                ('cpu', 'cpu.cfs_period_us'),
            ]:
                children = [p for p in (root / controller / parent).iterdir() if p.is_dir()]
                assert len(children) == 1
                values[filename] = int((children[0] / filename).read_text())
            assert values['memory.limit_in_bytes'] == values['memory.memsw.limit_in_bytes'] == 128 * 1024 * 1024
            assert values['pids.max'] == 32 and values['cpu.cfs_quota_us'] / values['cpu.cfs_period_us'] == 0.5
        else:
            info = next(
                item
                for item in await client.get_sessions(action_context=box._action_context(context))
                if item['session_id'] == old._box_binding.session_id
            )
            proc = await asyncio.create_subprocess_exec(
                'docker',
                'inspect',
                '--format',
                '{{json .HostConfig}}',
                info['backend_session_id'],
                stdout=asyncio.subprocess.PIPE,
            )
            output, _ = await proc.communicate()
            assert proc.returncode == 0
            values = json.loads(output)
            assert values['Memory'] == 128 * 1024 * 1024 and values['PidsLimit'] == 32
            assert values['NanoCpus'] == 500000000
        await select(
            {'timeout_sec': 1, 'idle_ttl_sec': 1, 'max_sessions': 1, 'cpus': 1.0, 'memory_mb': 64, 'pids_limit': 16}
        )
        with pytest.raises(BoxError):
            await acquire('capacity-blocked')
        assert not pending.done()
        release.write_text('release')
        result = await asyncio.wait_for(pending, 5)
        assert result['ok'] and result['stdout'] == 'old'
        # The old task remains reusable under its original limits until explicitly released.
        again = await box.execute_tool({'command': 'printf old-snapshot'}, old)
        assert again['ok'] and again['stdout'] == 'old-snapshot'
        await client.delete_session(old._box_binding.session_id, action_context=box._action_context(context))
        fresh = await acquire('new-limits')
        timed = await box.execute_tool({'command': 'sleep 8', 'timeout_sec': 10}, fresh)
        assert timed['status'] == 'timed_out' and timed['duration_ms'] < 6500, timed
        await acquire('idle-limits')
        for _ in range(60):
            if not runtime.get_sessions():
                break
            await asyncio.sleep(0.1)
        assert not runtime.get_sessions()
        print('LIVE_WORKSPACE_LIMITS_PASS', backend, 'kernel/capacity/timeout/idle/snapshot', flush=True)
    finally:
        release.write_text('release')
        await asyncio.gather(pending, return_exceptions=True)
