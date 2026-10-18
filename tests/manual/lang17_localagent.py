"""Real LocalAgent worker with a loopback model protocol fixture and Box disabled."""

import asyncio
import json
import os
from pathlib import Path
import secrets
import time

from aiohttp import web
import httpx
import websockets


async def main():
    calls = []
    tool_mode = bool(os.environ.get('LANG17_TOOL'))
    tool_results = []
    box_snapshots = []

    async def completion(request):
        body = await request.json()
        calls.append({'message_count': len(body['messages']), 'stream': body.get('stream')})
        base = {'id': 'qa-completion', 'object': 'chat.completion', 'created': int(time.time()), 'model': 'qa-model'}
        tool_messages = [message for message in body['messages'] if message.get('role') == 'tool']
        tool_results.extend(message.get('content') for message in tool_messages)
        wants_tool = tool_mode and 'tool request' in str(body['messages']) and not tool_messages
        delta = {'role': 'assistant', 'content': 'LOCALAGENT_NO_BOX_OK'}
        finish = 'stop'
        if wants_tool:
            name = next(tool['function']['name'] for tool in body['tools'] if 'exec' in tool['function']['name'])
            delta = {
                'role': 'assistant',
                'tool_calls': [
                    {
                        'index': 0,
                        'id': 'qa-exec',
                        'type': 'function',
                        'function': {'name': name, 'arguments': json.dumps({'command': 'printf LANG17_TOOL_OK'})},
                    }
                ],
            }
            finish = 'tool_calls'
        if body.get('stream'):
            response = web.StreamResponse(headers={'Content-Type': 'text/event-stream'})
            await response.prepare(request)
            for delta, finish in [(delta, None), ({}, finish)]:
                chunk = {
                    **base,
                    'object': 'chat.completion.chunk',
                    'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}],
                }
                await response.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
            await response.write(b'data: [DONE]\n\n')
            return response
        return web.json_response(
            {
                **base,
                'choices': [
                    {
                        'index': 0,
                        'message': {'role': 'assistant', 'content': 'LOCALAGENT_NO_BOX_OK'},
                        'finish_reason': 'stop',
                    }
                ],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
            }
        )

    app = web.Application()
    app.router.add_post('/v1/chat/completions', completion)
    server = web.AppRunner(app)
    await server.setup()
    site = web.TCPSite(server, '127.0.0.1', 16420)
    await site.start()
    try:
        async with httpx.AsyncClient(base_url='http://127.0.0.1:16399', timeout=30, trust_env=False) as client:

            async def api(method, path, data=None):
                response = await client.request(method, '/api/v1' + path, json=data)
                response.raise_for_status()
                body = response.json()
                assert body['code'] == 0, (path, body.get('msg'))
                return body.get('data', {})

            account = {'user': 'qa-localagent@example.invalid', 'password': secrets.token_urlsafe(24)}
            await api('POST', '/user/init', account)
            client.headers['Authorization'] = 'Bearer ' + (await api('POST', '/user/auth', account))['token']
            package = Path(__file__).resolve().parents[3] / 'evidence/LocalAgent-integration.lbpkg'
            response = await client.post(
                '/api/v1/plugins/install/local', files={'file': (package.name, package.read_bytes())}
            )
            response.raise_for_status()
            task = response.json()['data']['task_id']
            for _ in range(60):
                state = (await api('GET', '/system/tasks/' + str(task)))['runtime']
                if state['done']:
                    assert not state.get('exception'), 'Plugin installation failed'
                    break
                await asyncio.sleep(1)
            else:
                raise AssertionError('Plugin install deadline')
            model = await api(
                'POST',
                '/provider/models/llm',
                {
                    'name': 'qa-model',
                    'abilities': ['func_call'],
                    'provider': {
                        'requester': 'openai-chat-completions',
                        'base_url': 'http://127.0.0.1:16420/v1',
                        'api_keys': ['synthetic-key'],
                    },
                },
            )
            pipeline = (
                await api('POST', '/pipelines', {'name': 'LocalAgent no Box', 'description': 'protocol fixture'})
            )['uuid']
            config = (await api('GET', '/pipelines/' + pipeline))['pipeline']['config']
            runner = 'plugin:langbot-team/LocalAgent/default'
            config['trigger']['group-respond-rules'] = {'at': True, 'prefix': ['!qa'], 'regexp': [], 'random': 0}
            config['ai'] = {
                'runner': {'id': runner, 'expire-time': 0},
                'runner_config': {
                    runner: {
                        'box-enabled': True,
                        'model': {'primary': model['uuid'], 'fallbacks': [], 'reasoning': {}},
                        'enable-all-tools': False,
                        'tools': ['exec'],
                        'max-tool-iterations': 2,
                    }
                },
            }
            await api('PUT', '/pipelines/' + pipeline, {'config': config})
            bot = await api(
                'POST',
                '/platform/bots',
                {
                    'name': 'LocalAgent QA',
                    'description': 'isolated',
                    'adapter': 'aiocqhttp',
                    'enable': True,
                    'adapter_config': {'host': '127.0.0.1', 'port': 13280, 'access-token': ''},
                    'event_bindings': [
                        {
                            'id': 'qa',
                            'event_pattern': 'message.received',
                            'target_type': 'pipeline',
                            'target_uuid': pipeline,
                            'filters': [],
                            'enabled': True,
                        }
                    ],
                    'plugin_processors': [],
                },
            )
            await api('PUT', '/platform/bots/' + bot['uuid'], {'enable': True})
            replies = []
            async with websockets.connect(
                'ws://127.0.0.1:13280/ws/', additional_headers={'X-Self-ID': '900001', 'X-Client-Role': 'Universal'}
            ) as ws:

                async def respond():
                    async for raw in ws:
                        request = json.loads(raw)
                        if request.get('action', '').startswith('send_'):
                            replies.append(request['params'])
                        data = (
                            {'user_id': 900001, 'nickname': 'QA'}
                            if request.get('action') == 'get_login_info'
                            else {'message_id': 1}
                        )
                        await ws.send(
                            json.dumps({'status': 'ok', 'retcode': 0, 'data': data, 'echo': request.get('echo')})
                        )

                responder = asyncio.create_task(respond())
                try:
                    for i, text in enumerate(
                        ['ordinary ignored', '!qa answer plainly'] + (['!qa tool request'] if tool_mode else [])
                    ):
                        await ws.send(
                            json.dumps(
                                {
                                    'time': int(time.time()),
                                    'self_id': 900001,
                                    'post_type': 'message',
                                    'message_type': 'group',
                                    'sub_type': 'normal',
                                    'message_id': 100 + i,
                                    'group_id': 900100,
                                    'user_id': 900002,
                                    'message': text,
                                    'raw_message': text,
                                    'sender': {'user_id': 900002, 'nickname': 'QA', 'role': 'member'},
                                }
                            )
                        )
                        await asyncio.sleep(3 if i == 0 else 12)
                        if i == 0:
                            assert not calls and not replies
                        if tool_mode:
                            sessions = await api('GET', '/box/sessions')
                            box_snapshots.append({'step': i, 'sessions': sessions})
                            assert len(sessions) == (1 if i == 2 else 0), box_snapshots
                finally:
                    responder.cancel()
                    await asyncio.gather(responder, return_exceptions=True)
            assert calls and 'LOCALAGENT_NO_BOX_OK' in str(replies), replies
            if tool_mode:
                assert 'LANG17_TOOL_OK' in str(tool_results), tool_results
            Path('localagent-result.json').write_text(
                json.dumps(
                    {
                        'model': 'synthetic loopback protocol fixture',
                        'calls': calls,
                        'replies': replies,
                        'box': 'isolated Docker daemon'
                        if tool_mode
                        else 'Core disabled; plugin enabled with exec allowed; answer succeeded without Box',
                        'box_health': (await client.get('http://127.0.0.1:16410/healthz')).json()
                        if tool_mode
                        else None,
                        'box_snapshots': box_snapshots,
                        'tool_results': tool_results,
                        'health': (await client.get('/healthz')).json(),
                    },
                    indent=2,
                )
            )
    finally:
        await server.cleanup()


asyncio.run(main())
