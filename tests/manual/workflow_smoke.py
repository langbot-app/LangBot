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

        if screenshot:
            account = {'user': 'workflow-smoke@example.com', 'password': secrets.token_urlsafe(32)}
            await request('POST', '/api/v1/user/init', account)
            authentication = await request('POST', '/api/v1/user/auth', account)
            client.headers['Authorization'] = f'Bearer {authentication["token"]}'
            await request('POST', '/api/v1/system/wizard/completed', {'status': 'skipped'})

        workflow = await request(
            'POST',
            '/api/v1/workflows',
            {
                'name': 'Workflow EBA smoke',
                'nodes': [
                    {'id': 'trigger', 'type': 'trigger.message_trigger', 'position': {'x': 0, 'y': 0}},
                    {
                        'id': 'condition',
                        'type': 'control.condition',
                        'position': {'x': 250, 'y': 0},
                        'config': {'condition_type': 'expression', 'expression': 'True'},
                    },
                    {
                        'id': 'reply',
                        'type': 'action.reply_message',
                        'position': {'x': 500, 'y': 0},
                        'config': {'message_template': 'Echo {{input}}'},
                    },
                ],
                'edges': [
                    {
                        'id': 'first',
                        'source': 'trigger',
                        'source_port': 'message',
                        'target': 'condition',
                        'target_port': 'input',
                    },
                    {
                        'id': 'second',
                        'source': 'condition',
                        'source_port': 'true',
                        'target': 'reply',
                        'target_port': 'input',
                    },
                ],
            },
        )
        workflow_uuid = workflow['uuid']
        run = await request(
            'POST', f'/api/v1/workflows/{workflow_uuid}/run', {'message': 'manual', 'session_type': 'person'}
        )
        assert run['status'] == 'completed' and run['replies'] == ['Echo manual'], run
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
                        'id': 'workflow-route',
                        'event_pattern': 'message.received',
                        'target_type': 'workflow',
                        'target_uuid': workflow_uuid,
                        'enabled': True,
                        'priority': 0,
                    }
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
                assert len(detail['execution']['node_executions']) == 3, detail
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


def main():
    root = Path(__file__).resolve().parents[2]
    api_key = secrets.token_urlsafe(32)
    port = 15344
    log_path = Path(sys.argv[1] if len(sys.argv) > 1 else 'workflow-smoke-startup.log').resolve()
    with (
        tempfile.TemporaryDirectory(prefix='langbot-workflow-', dir='/dev/shm') as directory,
        log_path.open('w') as log,
    ):
        environment = os.environ | {
            'API__HOST': '127.0.0.1',
            'API__PORT': str(port),
            'API__GLOBAL_API_KEY': api_key,
            'API__WEBHOOK_PREFIX': f'http://127.0.0.1:{port}',
            'BOX__ENABLED': 'false',
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
