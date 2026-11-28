"""Run a local workflow through HTTP and a real OneBot reverse WebSocket."""

import asyncio
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

import httpx
from websockets.asyncio.client import connect

from tests.unit_tests.platform.onebot_mock import OneBotMock


async def smoke(base_url, api_key, screenshot=None):
    async with httpx.AsyncClient(base_url=base_url, headers={'X-API-Key': api_key}, timeout=30) as client:
        for attempt in range(120):
            try:
                response = await client.get('/api/v1/workflows')
                if response.status_code == 200:
                    break
            except httpx.TransportError:
                pass
            await asyncio.sleep(1)
        else:
            raise RuntimeError('Isolated LangBot did not become ready')

        async def request(method, path, payload=None):
            response = await client.request(method, path, json=payload)
            response.raise_for_status()
            body = response.json()
            assert body['code'] == 0, body
            return body['data']

        account = {'user': 'workflow-smoke@example.com', 'password': secrets.token_urlsafe(32)}
        await request('POST', '/api/v1/user/init', account)
        authentication = await request('POST', '/api/v1/user/auth', account)
        client.headers['Authorization'] = f'Bearer {authentication["token"]}'
        await request('POST', '/api/v1/system/wizard/completed', {'status': 'skipped'})

        graph = {
            'nodes': [
                {'id': 'start', 'type': 'start', 'name': 'Message', 'config': {}},
                {
                    'id': 'remember',
                    'type': 'remember',
                    'name': 'Count',
                    'config': {'scope': 'user', 'items': [{'key': 'messages', 'op': 'increment', 'value': '1'}]},
                },
                {
                    'id': 'reply',
                    'type': 'reply',
                    'name': 'Echo',
                    'config': {
                        'content': [{'type': 'text', 'text': 'Echo {{ start.text }} ({{ memory.user.messages }})'}]
                    },
                },
            ],
            'edges': [{'from': 'start', 'to': 'remember'}, {'from': 'remember', 'to': 'reply'}],
        }
        workflow = await request('POST', '/api/v1/workflows', {'name': 'Workflow EBA smoke', 'graph': graph})
        workflow_uuid = workflow['workflow']['uuid']
        assert workflow['issues'] == [], workflow
        run = await request(
            'POST',
            f'/api/v1/workflows/{workflow_uuid}/test',
            {'text': 'manual', 'graph': graph, 'session_type': 'person'},
        )
        assert run['status'] == 'completed' and run['replies'] == ['Echo manual (1)'], run
        joined_uuid = await create_event_workflow(request)
        bot = await request(
            'POST',
            '/api/v1/platform/bots',
            {
                'name': 'Workflow wire test',
                'adapter': 'onebot-v11',
                'enable': True,
                'adapter_config': {'connection_mode': 'reverse_ws', 'access-token': api_key, 'self_id': '42'},
                'event_bindings': [
                    {
                        'id': 'joined',
                        'event_pattern': 'group.member_joined',
                        'target_type': 'workflow',
                        'target_uuid': joined_uuid,
                    },
                    {
                        'id': 'workflow-route',
                        'event_pattern': 'message.received',
                        'target_type': 'workflow',
                        'target_uuid': workflow_uuid,
                        'enabled': True,
                        'priority': 0,
                        'policy': {
                            'trigger': {'group-respond-rules': {'enabled': False}},
                            'safety': {
                                'rate-limit': {
                                    'enabled': True,
                                    'limitation': 1,
                                    'window-length': 60,
                                    'strategy': 'drop',
                                }
                            },
                            'output': {'long-text-processing': {'threshold': 16, 'strategy': 'forward'}},
                        },
                    },
                ],
            },
        )
        peer = OneBotMock()
        headers = {'Authorization': f'Bearer {api_key}', 'X-Self-ID': '42', 'X-Client-Role': 'Universal'}
        async with connect(
            base_url.replace('http', 'ws', 1) + f'/bots/{bot["uuid"]}/onebot/v11/ws', additional_headers=headers
        ) as socket:
            peer_task = asyncio.create_task(peer.run(socket.send, socket.recv))
            try:
                await peer.emit(peer.message('private', 'friend'))
                for attempt in range(100):
                    replies = [item for item in peer.requests if item.get('action') in ('send_msg', 'send_private_msg')]
                    if replies:
                        break
                    await asyncio.sleep(0.1)
                else:
                    raise AssertionError('No reply received over OneBot WebSocket')
                assert 'Echo hello' in json.dumps(replies), replies
                for attempt in range(50):
                    result = await request('GET', f'/api/v1/workflows/{workflow_uuid}/executions')
                    completed = [item for item in result['executions'] if item['status'] == 'completed']
                    if len(completed) == 2:
                        break
                    await asyncio.sleep(0.1)
                assert len(completed) == 2, result
                detail = await request('GET', f'/api/v1/workflows/{workflow_uuid}/executions/{completed[0]["uuid"]}')
                assert len(detail['execution']['steps']) == 3, detail
                await peer.emit(peer.message('private', 'friend') | {'message_id': 10})
                group = peer.message(
                    'group', 'normal', [{'type': 'text', 'data': {'text': 'a longer message for the group'}}]
                )
                await peer.emit(group | {'message_id': 11})
                for attempt in range(100):
                    page = await request(
                        'GET', f'/api/v1/monitoring/executions?source=event&botId={bot["uuid"]}&summary=false'
                    )
                    delivered = [row for row in page['items'] if row.get('handled_by') == f'workflow:{workflow_uuid}']
                    dropped = [row for row in page['items'] if row.get('handling') == 'policy']
                    if len(delivered) >= 2 and dropped:
                        break
                    await asyncio.sleep(0.1)
                assert delivered and dropped, page
                traces = [
                    await request('GET', f'/api/v1/monitoring/executions/event/{row["id"]}')
                    for row in [*delivered, dropped[0]]
                ]
                assert 'long_text' in json.dumps(traces) and 'message_policy' in json.dumps(traces), traces
                assert any(
                    'a longer message for the group' in json.dumps(item.get('params', {}).get('message'))
                    for item in peer.requests
                    if item['action'] in ('send_msg', 'send_group_msg')
                )
                await event_smoke(request, peer, joined_uuid)
                await trigger_smoke(request, client, base_url, api_key)
                print(json.dumps({'execution_details': traces}, ensure_ascii=False))
                response = await client.delete(f'/api/v1/workflows/{workflow_uuid}')
                assert response.status_code == 400
                if screenshot:
                    browser = await asyncio.create_subprocess_exec(
                        'node',
                        'tests/manual/workflow-smoke.mjs',
                        cwd=Path(__file__).resolve().parents[2] / 'web',
                        env=os.environ
                        | {
                            'WORKFLOW_SMOKE_TOKEN': authentication['token'],
                            'WORKFLOW_SMOKE_UUID': workflow_uuid,
                            'WORKFLOW_SMOKE_SCREENSHOT': str(Path(screenshot).resolve()),
                            'VITE_API_PROXY_TARGET': base_url,
                        },
                    )
                    assert await browser.wait() == 0, 'Browser execution history verification failed'
                print(
                    json.dumps(
                        {
                            'manual_run': run['status'],
                            'wire_reply': 'Echo hello',
                            'completed_executions': len(completed),
                            'node_records': 3,
                            'referenced_workflow_delete': response.status_code,
                        },
                        indent=2,
                    )
                )
            finally:
                peer_task.cancel()
                await asyncio.gather(peer_task, return_exceptions=True)


async def create_event_workflow(request):
    from tests.unit_tests.workflow.test_tree import node, path

    trigger = {'type': 'event', 'events': ['group.member_joined']}
    graph = path(
        node('start'),
        node('random', mode='seeded_pick', items=['welcome'], seed='{{start.event.member.id}}'),
        node('reply', text='{{random.value}} {{start.event.member.id}}'),
    )
    created = await request(
        'POST', '/api/v1/workflows', {'name': 'Welcome members', 'triggers': [trigger], 'graph': graph}
    )
    assert not created['issues']
    return created['workflow']['uuid']


async def event_smoke(request, peer, workflow_uuid):
    resource = '/api/v1/workflows/' + workflow_uuid
    nodes = await request('GET', '/api/v1/workflows/_/node-types')
    assert all(isinstance(item['available'], bool) for item in nodes['node_types'])
    code = next(item for item in nodes['node_types'] if item['type'] == 'code')
    box_enabled = os.getenv('LANGBOT_TEST_WORKFLOW_BOX') == '1'
    assert code['available'] == box_enabled, code
    code_run = None
    if box_enabled:
        from tests.unit_tests.workflow.test_tree import node, path

        code_graph = path(
            node('start'),
            node(
                'code',
                language='python',
                code="return {'length': len(inputs['text'])}",
                inputs={'text': '{{start.text}}'},
                outputs=['length'],
            ),
            node('reply', text='{{code.length}}'),
        )
        code_run = await request('POST', resource + '/test', {'graph': code_graph, 'text': 'hello'})
        assert code_run['replies'] == ['5'], code_run
    else:
        assert code['reason'] == 'box_unavailable'
    await peer.emit(
        {
            'post_type': 'notice',
            'notice_type': 'group_increase',
            'sub_type': 'approve',
            'group_id': 20001,
            'user_id': 10001,
            'operator_id': 10002,
        }
    )
    async with asyncio.timeout(20):
        while not any(
            'welcome 10001' in json.dumps(row['params'])
            for row in peer.requests
            if row['action'] in ('send_group_msg', 'send_msg')
        ):
            await asyncio.sleep(0.1)
        while not (
            rows := [
                row
                for row in (await request('GET', resource + '/executions'))['executions']
                if row['status'] == 'completed' and row['trigger'] == 'event'
            ]
        ):
            await asyncio.sleep(0.1)
    detail = await request('GET', resource + '/executions/' + rows[0]['uuid'])
    assert detail['execution']['steps'][0]['outputs']['trigger'] == 'event'
    if target := os.getenv('LANGBOT_EVENT_EVIDENCE'):
        Path(target).write_text(
            json.dumps(
                {
                    'GET node-types': nodes,
                    'GET workflow': await request('GET', resource),
                    'GET execution': detail,
                    **({'POST draft test': code_run} if code_run else {}),
                },
                indent=2,
            )
        )


async def wait_for(peer, text, actions=('send_msg', 'send_private_msg', 'send_group_msg'), timeout=20):
    async with asyncio.timeout(timeout):
        while not any(
            text in json.dumps(row['params'], ensure_ascii=False) for row in peer.requests if row['action'] in actions
        ):
            await asyncio.sleep(0.1)


async def trigger_smoke(request, client, base_url, api_key):
    """Command, webhook and schedule triggers through a second, unthrottled bot."""
    bot = await request(
        'POST',
        '/api/v1/platform/bots',
        {
            'name': 'Workflow trigger test',
            'adapter': 'onebot-v11',
            'enable': True,
            'adapter_config': {'connection_mode': 'reverse_ws', 'access-token': api_key, 'self_id': '43'},
        },
    )
    bot_uuid = bot['uuid']
    peer = OneBotMock()
    headers = {'Authorization': f'Bearer {api_key}', 'X-Self-ID': '43', 'X-Client-Role': 'Universal'}
    async with connect(
        base_url.replace('http', 'ws', 1) + f'/bots/{bot_uuid}/onebot/v11/ws', additional_headers=headers
    ) as socket:
        task = asyncio.create_task(peer.run(socket.send, socket.recv))
        try:
            command = await request(
                'POST',
                '/api/v1/workflows',
                {
                    'name': 'Weather command',
                    'triggers': [
                        {
                            'type': 'command',
                            'name': 'weather',
                            'aliases': ['tq'],
                            'args': [{'name': 'city', 'required': True}],
                            'description': 'Look up the weather',
                            'bots': 'all',
                        }
                    ],
                    'graph': {
                        'nodes': [
                            {'id': 'start', 'type': 'start', 'name': 'Start', 'config': {}},
                            {
                                'id': 'remember',
                                'type': 'remember',
                                'name': 'Count',
                                'config': {
                                    'scope': 'user',
                                    'items': [{'key': 'visits', 'op': 'increment', 'value': '1'}],
                                },
                            },
                            {
                                'id': 'reply',
                                'type': 'reply',
                                'name': 'Reply',
                                'config': {'text': 'weather {{start.args.city}} #{{memory.user.visits}}'},
                            },
                        ],
                        'edges': [{'from': 'start', 'to': 'remember'}, {'from': 'remember', 'to': 'reply'}],
                    },
                },
            )
            assert command['issues'] == [], command

            def private(text, message_id):
                payload = peer.message('private', 'friend', [{'type': 'text', 'data': {'text': text}}])
                return payload | {'message_id': message_id, 'raw_message': text, 'self_id': 43}

            await peer.emit(private('/weather Beijing', 101))
            await wait_for(peer, 'weather Beijing #1')
            await peer.emit(private('/tq Shanghai', 102))
            await wait_for(peer, 'weather Shanghai #2')
            await peer.emit(private('/weather', 103))
            await wait_for(peer, 'Usage: /weather <city>')
            await peer.emit(private('/help', 104))
            await wait_for(peer, '/weather <city>')

            hook = await request(
                'POST',
                '/api/v1/workflows',
                {
                    'name': 'Webhook push',
                    'triggers': [{'type': 'webhook', 'bot_uuid': bot_uuid}],
                    'graph': {
                        'nodes': [
                            {'id': 'start', 'type': 'start', 'name': 'Start', 'config': {}},
                            {
                                'id': 'send',
                                'type': 'send',
                                'name': 'Push',
                                'config': {
                                    'target_type': 'group',
                                    'target_id': '20001',
                                    'text': 'hook {{start.payload.title}}',
                                },
                            },
                        ],
                        'edges': [{'from': 'start', 'to': 'send'}],
                    },
                },
            )
            secret = hook['workflow']['triggers'][0]['secret']
            path = f'/api/v1/workflows/hooks/{bot_uuid}/{hook["workflow"]["uuid"]}'
            assert (await client.post(f'{path}/wrong-secret-value', json={'title': 'x'})).status_code == 404
            response = await client.post(f'{path}/{secret}', json={'title': 'Release 1.0'})
            assert response.status_code == 200 and response.json()['data']['status'] == 'completed', response.text
            await wait_for(peer, 'hook Release 1.0', actions=('send_group_msg', 'send_msg'))

            await request(
                'POST',
                '/api/v1/workflows',
                {
                    'name': 'Every minute',
                    'triggers': [
                        {
                            'type': 'schedule',
                            'every': 1,
                            'bot_uuid': bot_uuid,
                            'targets': [{'type': 'group', 'id': '20001'}],
                        }
                    ],
                    'graph': {
                        'nodes': [
                            {'id': 'start', 'type': 'start', 'name': 'Start', 'config': {}},
                            {
                                'id': 'reply',
                                'type': 'reply',
                                'name': 'Tick',
                                'config': {'text': 'tick {{start.target.id}}'},
                            },
                        ],
                        'edges': [{'from': 'start', 'to': 'reply'}],
                    },
                },
            )
            await wait_for(peer, 'tick 20001', actions=('send_group_msg', 'send_msg'), timeout=80)
            print(json.dumps({'triggers': ['command', 'usage', 'help', 'memory', 'webhook', 'schedule']}))
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def main():
    root = Path(__file__).resolve().parents[2]
    api_key = secrets.token_urlsafe(32)
    import socket

    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    log_path = Path(sys.argv[1] if len(sys.argv) > 1 else 'workflow-smoke-startup.log').resolve()
    with (
        tempfile.TemporaryDirectory(
            prefix='langbot-workflow-', dir=None if os.getenv('LANGBOT_TEST_WORKFLOW_BOX') == '1' else '/dev/shm'
        ) as directory,
        log_path.open('w') as log,
    ):
        environment = os.environ | {
            'API__HOST': '127.0.0.1',
            'API__PORT': str(port),
            'API__GLOBAL_API_KEY': api_key,
            'API__WEBHOOK_PREFIX': f'http://127.0.0.1:{port}',
            'BOX__ENABLED': 'true' if os.getenv('LANGBOT_TEST_WORKFLOW_BOX') == '1' else 'false',
            'BOX__BACKEND': 'docker',
            'PLUGIN__ENABLE': 'false',
            'LANGBOT_DATA_ROOT': str(Path(directory) / 'data'),
            'PLUGIN__DISPLAY_PLUGIN_DEBUG_URL': 'ws://127.0.0.1:15445/plugin/debug/ws',
        }
        process = subprocess.Popen(
            [sys.executable, str(root / 'main.py')],
            cwd=directory,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            asyncio.run(smoke(f'http://127.0.0.1:{port}', api_key, sys.argv[2] if len(sys.argv) > 2 else None))
        finally:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()
