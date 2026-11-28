import asyncio
import json
import os
from contextlib import AsyncExitStack
from pathlib import Path

import httpx
import pytest
from aiohttp import web
from websockets.asyncio.client import connect

from tests.e2e.test_local_runner_fake_provider import (  # noqa: F401
    FAKE_MODEL_UUID,
    LOCAL_RUNNER_ID,
    _inject_llm_model,
    _run_local_agent_probe,
    local_agent_e2e_config_path,
    local_agent_e2e_port,
    local_agent_e2e_tmpdir,
    local_agent_runtime_ports,
    local_agent_runtime_process,
)
from tests.unit_tests.platform.onebot_mock import OneBotMock

pytestmark = [pytest.mark.e2e, pytest.mark.local_agent]


def test_workflow_classification_wire(request):
    public_ip = os.getenv('LANGBOT_TEST_PUBLIC_IP')
    if not public_ip:
        pytest.skip('requires a local globally routable address for the HTTP workflow node')
    request.getfixturevalue('local_agent_runtime_process')
    port = request.getfixturevalue('local_agent_e2e_port')

    async def probe(ap):
        from langbot_plugin.api.entities.builtin.provider.message import MessageChunk

        fake = await _inject_llm_model(ap)

        async def stream(*args, **kwargs):
            answer = await fake.invoke_llm(*args, **kwargs)
            yield MessageChunk(role='assistant', content=answer.content, is_final=True)

        fake.invoke_llm_stream = stream
        fake.queue_llm_responses('c1', 'order accepted', 'else', 'chat accepted', 'agent accepted')
        peer = OneBotMock()
        app = web.Application()

        async def order(_):
            return web.json_response({'order': 'fixed'})

        app.router.add_get('/order', order)
        async with (
            AsyncExitStack() as stack,
            httpx.AsyncClient(
                base_url=f'http://127.0.0.1:{port}', headers={'X-API-Key': 'e2e-local-agent-key'}
            ) as client,
        ):
            runner = web.AppRunner(app)
            await runner.setup()
            stack.push_async_callback(runner.cleanup)
            await web.TCPSite(runner, '0.0.0.0', 0).start()

            async def api(method, path, body=None):
                response = await client.request(method, '/api/v1/' + path, json=body)
                response.raise_for_status()
                data = response.json()
                assert data['code'] == 0, data
                return data['data']

            from tests.unit_tests.workflow.test_tree import node

            account = {'user': 'workflow@example.com', 'password': 'isolated-test-password'}
            await api('POST', 'user/init', account)
            token = (await api('POST', 'user/auth', account))['token']
            client.headers['Authorization'] = f'Bearer {token}'
            await api('POST', 'system/wizard/completed', {'status': 'skipped'})

            chat = (await api('POST', 'pipelines', {'name': 'Workflow chat'}))['uuid']
            config = (await api('GET', f'pipelines/{chat}'))['pipeline']['config']
            config['ai'].update(
                runner={'id': LOCAL_RUNNER_ID}, runner_config={LOCAL_RUNNER_ID: {'model': {'primary': FAKE_MODEL_UUID}}}
            )
            await api('PUT', f'pipelines/{chat}', {'config': config})
            graph = {
                'nodes': [
                    node('start'),
                    node('classify', model_uuid=FAKE_MODEL_UUID, categories=[{'id': 'c1', 'label': 'order'}]),
                    node('http', url=f'http://{public_ip}:{runner.addresses[0][1]}/order'),
                    node('llm', model_uuid=FAKE_MODEL_UUID, prompt='Order {{http.json.order}}'),
                    node('reply', text='{{llm.text}}'),
                    node('handoff', target_type='chat', target_uuid=chat, text='chat question'),
                ],
                'edges': [
                    {'from': 'start', 'to': 'classify'},
                    {'from': 'classify', 'branch': 'c1', 'to': 'http'},
                    {'from': 'http', 'to': 'llm'},
                    {'from': 'llm', 'to': 'reply'},
                    {'from': 'classify', 'branch': 'else', 'to': 'handoff'},
                ],
            }
            created = await api('POST', 'workflows', {'name': 'Order classifier', 'graph': graph})
            assert not created['issues'], created['issues']
            workflow = created['workflow']['uuid']
            from tests.unit_tests.workflow.test_tree import path

            agent = (
                await api(
                    'POST',
                    'agents',
                    {
                        'kind': 'agent',
                        'name': 'Workflow agent',
                        'config': {
                            'runner': {'id': LOCAL_RUNNER_ID},
                            'runner_config': {LOCAL_RUNNER_ID: {'model': {'primary': FAKE_MODEL_UUID}}},
                        },
                    },
                )
            )['uuid']
            child = (
                await api(
                    'POST',
                    'workflows',
                    {'name': 'Child', 'graph': path(node('start'), node('reply', text='nested accepted'))},
                )
            )['workflow']['uuid']
            evidence = {'GET workflow': await api('GET', f'workflows/{workflow}')}
            draft = await api(
                'POST',
                f'workflows/{workflow}/test',
                {'text': 'draft', 'graph': path(node('start'), node('reply', text='draft {{start.text}}'))},
            )
            assert draft['replies'] == ['draft draft']
            evidence['POST draft test'] = draft
            rejected = await api(
                'POST',
                f'workflows/{workflow}/test',
                {
                    'text': 'loopback',
                    'graph': path(node('start'), node('http', url=f'http://127.0.0.1:{runner.addresses[0][1]}/order')),
                },
            )
            assert rejected['status'] == 'failed' and 'private address' in rejected['error']
            bot = (
                await api(
                    'POST',
                    'platform/bots',
                    {
                        'name': 'OneBot classifier',
                        'adapter': 'onebot-v11',
                        'enable': True,
                        'adapter_config': {
                            'connection_mode': 'reverse_ws',
                            'access-token': 'test-peer',
                            'self_id': '42',
                        },
                        'event_bindings': [
                            {
                                'id': 'classifier',
                                'event_pattern': 'message.received',
                                'target_type': 'workflow',
                                'target_uuid': workflow,
                                'policy': {
                                    'safety': {
                                        'rate-limit': {
                                            'enabled': True,
                                            'limitation': 1,
                                            'window-length': 1,
                                            'strategy': 'drop',
                                        }
                                    }
                                },
                            }
                        ],
                    },
                )
            )['uuid']
            async with connect(
                f'ws://127.0.0.1:{port}/bots/{bot}/onebot/v11/ws',
                additional_headers={
                    'Authorization': 'Bearer test-peer',
                    'X-Self-ID': '42',
                    'X-Client-Role': 'Universal',
                },
            ) as socket:
                peer_task = asyncio.create_task(peer.run(socket.send, socket.recv))
                try:
                    for index, expected in enumerate(
                        (
                            'order accepted',
                            'chat accepted',
                            'agent accepted',
                            'nested accepted',
                            'counter 1',
                            'counter 2',
                        )
                    ):
                        if index in (2, 3):
                            kind, target = ('agent', agent) if index == 2 else ('workflow', child)
                            updated = await api(
                                'PUT',
                                f'workflows/{workflow}',
                                {
                                    'graph': path(
                                        node('start'),
                                        node(
                                            'handoff', target_type=kind, target_uuid=target, text='forwarded question'
                                        ),
                                    )
                                },
                            )
                            assert not updated['issues']
                        if index == 4:
                            updated = await api(
                                'PUT',
                                f'workflows/{workflow}',
                                {
                                    'graph': path(
                                        node('start'),
                                        node(
                                            'remember',
                                            scope='user',
                                            items=[{'key': 'count', 'op': 'increment', 'value': '1'}],
                                        ),
                                        node('reply', text='counter {{memory.user.count}}'),
                                    )
                                },
                            )
                            assert not updated['issues']
                        event = peer.message(
                            'private', 'friend', [{'type': 'text', 'data': {'text': f'question {index}'}}]
                        )
                        event.update(message_id=100 + index, raw_message=f'question {index}')
                        await peer.emit(event)
                        for _ in range(200):
                            if any(
                                expected in json.dumps(row['params']['message'])
                                for row in peer.requests
                                if row['action'] in ('send_msg', 'send_private_msg')
                            ):
                                break
                            await asyncio.sleep(0.1)
                        else:
                            raise AssertionError(f'Missing OneBot reply: {expected}')
                        await asyncio.sleep(1.1)
                        if index < 2:
                            async with asyncio.timeout(30):
                                while True:
                                    runs = (await api('GET', f'workflows/{workflow}/executions'))['executions']
                                    run = next((row for row in runs if row['input_text'] == f'question {index}'), None)
                                    if run and run['status'] in ('completed', 'failed'):
                                        break
                                    await asyncio.sleep(0.1)
                            assert run['status'] == 'completed', run['error']
                            detail = await api('GET', f'workflows/{workflow}/executions/{run["uuid"]}')
                            steps = detail['execution']['steps']
                            assert [step['node_type'] for step in steps] == (
                                ['start', 'classify', 'http', 'llm', 'reply']
                                if index == 0
                                else ['start', 'classify', 'handoff']
                            )
                            assert steps[1]['branch'] == ('c1' if index == 0 else 'else')
                            evidence['GET execution ' + steps[1]['branch']] = detail
                    if evidence_file := os.environ.get('LANGBOT_TEST_WORKFLOW_EVIDENCE'):
                        Path(evidence_file).write_text(json.dumps(evidence, indent=2), encoding='utf-8')
                finally:
                    peer_task.cancel()
                    await asyncio.gather(peer_task, return_exceptions=True)

    _run_local_agent_probe(request.getfixturevalue('local_agent_e2e_tmpdir'), probe)
