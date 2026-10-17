"""Real isolated Core/OneBot ingress probe with a synthetic protocol peer, no QQ traffic."""

import asyncio
import os
import json
from pathlib import Path
import secrets
import sqlite3
import time
import sys

import httpx
import websockets


async def main():
    async with httpx.AsyncClient(base_url='http://127.0.0.1:15399', timeout=15, trust_env=False) as client:

        async def api(method, path, data=None):
            response = await client.request(method, '/api/v1' + path, json=data)
            body = response.json()
            if response.status_code >= 400 or body.get('code') != 0:
                raise RuntimeError(f'{method} {path}: {response.status_code} {body.get("msg")}')
            return body.get('data', {})

        account = {'user': 'lang16@example.invalid', 'password': secrets.token_urlsafe(24)}
        await api('POST', '/user/init', account)
        auth = await api('POST', '/user/auth', account)
        client.headers['Authorization'] = 'Bearer ' + auth['token']
        if '--installed' in sys.argv:
            if os.environ.get('LANG16_PLUGIN_PACKAGE'):
                package = Path(os.environ['LANG16_PLUGIN_PACKAGE'])
                response = await client.post(
                    '/api/v1/plugins/install/local', files={'file': (package.name, package.read_bytes())}
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get('code') != 0:
                    raise RuntimeError('Local plugin upload failed')
                task = payload['data']
            else:
                task = await api(
                    'POST',
                    '/plugins/install/marketplace',
                    {'plugin_author': 'langbot-team', 'plugin_name': 'LocalAgent', 'plugin_version': '0.2.1'},
                )
            for _ in range(60):
                state = (await api('GET', '/system/tasks/' + str(task['task_id'])))['runtime']
                if state.get('done'):
                    if state.get('exception'):
                        raise RuntimeError('LocalAgent installation failed')
                    break
                await asyncio.sleep(1)
            else:
                raise RuntimeError('LocalAgent installation deadline')
        pipeline = (await api('POST', '/pipelines', {'name': 'LANG16 response gate', 'description': 'isolated probe'}))[
            'uuid'
        ]
        config = (await api('GET', '/pipelines/' + pipeline))['pipeline']['config']
        config['trigger']['group-respond-rules'] = {'at': True, 'prefix': ['!qa'], 'regexp': []}
        if '--fault' not in sys.argv:
            config['trigger']['group-respond-rules']['random'] = 0
        if '--installed' in sys.argv:
            config['ai']['runner']['id'] = 'plugin:langbot-team/LocalAgent/default'
            # Exercise real Runner failure/cleanup without models or sandboxes.
            config['ai']['runner_config'] = {
                'plugin:langbot-team/LocalAgent/default': {'box-enabled': '--box' in sys.argv}
            }
        if os.environ.get('LANG16_LLM_KEY'):
            model = await api(
                'POST',
                '/provider/models/llm',
                {
                    'name': os.environ['LANG16_LLM_MODEL'],
                    'abilities': ['func_call'],
                    'extra_args': {'max_tokens': 128},
                    'provider': {
                        'requester': 'openai-chat-completions',
                        'base_url': os.environ['LANG16_LLM_BASE_URL'],
                        'api_keys': [os.environ['LANG16_LLM_KEY']],
                    },
                },
            )
            runner = config['ai']['runner_config']['plugin:langbot-team/LocalAgent/default']
            runner.update(
                {
                    'model': {'primary': model['uuid'], 'fallbacks': [], 'reasoning': {}},
                    'enable-all-tools': False,
                    'tools': ['exec'],
                    'max-tool-iterations': 2,
                }
            )
        await api('PUT', '/pipelines/' + pipeline, {'config': config})
        bot = await api(
            'POST',
            '/platform/bots',
            {
                'name': 'LANG16 OneBot',
                'description': 'synthetic protocol peer only',
                'adapter': 'aiocqhttp',
                'enable': True,
                'adapter_config': {'host': '127.0.0.1', 'port': 12280, 'access-token': ''},
                'event_bindings': [
                    {
                        'id': 'default-migrated',
                        'event_pattern': 'message.received',
                        'target_type': 'pipeline',
                        'target_uuid': pipeline,
                        'filters': [],
                        'enabled': True,
                        'description': 'Migrated from default pipeline binding',
                    }
                ],
                'plugin_processors': [],
            },
        )
        # The release create API loads but does not run the adapter; applying
        # enable through the update API starts it without restarting Core.
        await api('PUT', '/platform/bots/' + bot['uuid'], {'enable': True})
        await asyncio.sleep(1)
        async with websockets.connect(
            'ws://127.0.0.1:12280/ws/',
            additional_headers={
                'X-Self-ID': '900001',
                'X-Client-Role': 'Universal',
            },
        ) as ws:
            actions = []
            box_snapshots = (
                [{'case': 'before', 'sessions': await api('GET', '/box/sessions')}] if '--box' in sys.argv else []
            )

            async def respond():
                async for raw in ws:
                    request = json.loads(raw)
                    actions.append(request.get('action'))
                    data = {'message_id': 1}
                    if request.get('action') == 'get_login_info':
                        data = {'user_id': 900001, 'nickname': 'LANG16'}
                    await ws.send(json.dumps({'status': 'ok', 'retcode': 0, 'data': data, 'echo': request.get('echo')}))

            responder = asyncio.create_task(respond())
            cases = [('unrelated', 'ordinary chat'), ('keyword', '!qa hello'), ('mention', '[CQ:at,qq=900001]hello')]
            if '--box' in sys.argv:
                cases = [('unrelated', 'ordinary chat'), ('keyword', '!qa Reply exactly QA_OK without using tools.')]
                if os.environ.get('LANG16_LLM_KEY'):
                    cases.append(('tool', '!qa Use exec to run printf LANG16_TOOL_OK and report its output.'))
            if '--fault' not in sys.argv and '--box' not in sys.argv:
                cases += [('other_mention', '[CQ:at,qq=900003]hello'), ('private', 'hello')]
            try:
                for i, (name, content) in enumerate(cases):
                    await ws.send(
                        json.dumps(
                            {
                                'time': int(time.time()),
                                'self_id': 900001,
                                'post_type': 'message',
                                'message_type': 'private' if name == 'private' else 'group',
                                'sub_type': 'friend' if name == 'private' else 'normal',
                                'message_id': 100 + i,
                                'group_id': 900100 if '--box' in sys.argv else 900100 + i,
                                'user_id': 900002,
                                'message': content,
                                'raw_message': content,
                                'sender': {'user_id': 900002, 'nickname': 'QA', 'card': '', 'role': 'member'},
                            }
                        )
                    )
                    await asyncio.sleep(20 if os.environ.get('LANG16_LLM_KEY') else (8 if '--box' in sys.argv else 2))
                    if '--box' in sys.argv:
                        box_snapshots.append({'case': name, 'sessions': await api('GET', '/box/sessions')})
                if '--fault' not in sys.argv and '--box' not in sys.argv:
                    for i in range(30):
                        await ws.send(
                            json.dumps(
                                {
                                    'time': int(time.time()),
                                    'self_id': 900001,
                                    'post_type': 'message',
                                    'message_type': 'group',
                                    'sub_type': 'normal',
                                    'message_id': 200 + i,
                                    'group_id': 900200,
                                    'user_id': 900002,
                                    'message': 'unrelated burst',
                                    'raw_message': 'unrelated burst',
                                    'sender': {'user_id': 900002, 'nickname': 'QA', 'role': 'member'},
                                }
                            )
                        )
                    await asyncio.sleep(4)
            finally:
                responder.cancel()
                try:
                    await responder
                except asyncio.CancelledError:
                    pass
        health = (await client.get('/healthz')).json()
        with sqlite3.connect('data/langbot.db') as db:
            tables = [row[0] for row in db.execute("select name from sqlite_master where type='table'")]
            monitoring = {}
            for table in tables:
                if table in ('monitoring_messages', 'monitoring_sessions'):
                    db.row_factory = sqlite3.Row
                    monitoring[table] = [dict(row) for row in db.execute('select * from ' + table)]
        Path('onebot-result.json').write_text(
            json.dumps(
                {
                    'cases': cases,
                    'box_snapshots': box_snapshots,
                    'live_model': os.environ.get('LANG16_LLM_MODEL'),
                    'installed_runner_no_model': '--installed' in sys.argv,
                    'actions': actions,
                    'health': health,
                    'monitoring': monitoring,
                    'pipeline': pipeline,
                    'bot': bot,
                },
                indent=2,
            )
        )


asyncio.run(main())
