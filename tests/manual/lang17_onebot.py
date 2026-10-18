"""Real isolated Core/OneBot ingress probe with a synthetic protocol peer, no QQ traffic."""

import asyncio
import os
import json
from pathlib import Path
import secrets
import sqlite3
import time
import sys
import subprocess
import datetime

import httpx
import websockets
from lang17_fixture import package


async def main():
    async with httpx.AsyncClient(base_url='http://127.0.0.1:16399', timeout=15, trust_env=False) as client:

        async def api(method, path, data=None):
            response = await client.request(method, '/api/v1' + path, json=data)
            body = response.json()
            if response.status_code >= 400 or body.get('code') != 0:
                raise RuntimeError(f'{method} {path}: {response.status_code} {body.get("msg")}')
            return body.get('data', {})

        account = {'user': 'lang17@example.invalid', 'password': secrets.token_urlsafe(24)}
        await api('POST', '/user/init', account)
        auth = await api('POST', '/user/auth', account)
        client.headers['Authorization'] = 'Bearer ' + auth['token']
        await api('POST', '/system/wizard/completed', {'status': 'skipped'})
        response = await client.post(
            '/api/v1/plugins/install/local', files={'file': ('HealthyProbe.lbpkg', package('HealthyProbe'))}
        )
        response.raise_for_status()
        task = response.json()['data']['task_id']
        for _ in range(60):
            state = (await api('GET', '/system/tasks/' + str(task)))['runtime']
            if state['done']:
                assert not state.get('exception'), state.get('exception')
                break
            await asyncio.sleep(1)
        else:
            raise RuntimeError('Plugin installation timed out')
        pipeline = (await api('POST', '/pipelines', {'name': 'LANG17 response gate', 'description': 'isolated probe'}))[
            'uuid'
        ]
        config = (await api('GET', '/pipelines/' + pipeline))['pipeline']['config']
        config['trigger']['group-respond-rules'] = {'at': True, 'prefix': ['!qa'], 'regexp': []}
        if '--fault' not in sys.argv:
            config['trigger']['group-respond-rules']['random'] = 0
        runner = 'plugin:lang17-qa/HealthyProbe/default'
        config['ai'] = {'runner': {'id': runner, 'expire-time': 0}, 'runner_config': {runner: {}}}
        await api('PUT', '/pipelines/' + pipeline, {'config': config})
        bot = await api(
            'POST',
            '/platform/bots',
            {
                'name': 'LANG17 OneBot',
                'description': 'synthetic protocol peer only',
                'adapter': 'aiocqhttp',
                'enable': True,
                'adapter_config': {'host': '127.0.0.1', 'port': 13280, 'access-token': ''},
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
            'ws://127.0.0.1:13280/ws/',
            additional_headers={
                'X-Self-ID': '900001',
                'X-Client-Role': 'Universal',
            },
        ) as ws:
            actions = []
            sent_payloads = []
            box_snapshots = (
                [{'case': 'before', 'sessions': await api('GET', '/box/sessions')}] if '--box' in sys.argv else []
            )

            async def respond():
                async for raw in ws:
                    request = json.loads(raw)
                    actions.append(request.get('action'))
                    if str(request.get('action')).startswith('send_'):
                        sent_payloads.append(request.get('params', {}))
                    data = {'message_id': 1}
                    if request.get('action') == 'get_login_info':
                        data = {'user_id': 900001, 'nickname': 'LANG17'}
                    await ws.send(json.dumps({'status': 'ok', 'retcode': 0, 'data': data, 'echo': request.get('echo')}))

            responder = asyncio.create_task(respond())
            cases = [('unrelated', 'ordinary chat'), ('keyword', '!qa hello'), ('mention', '[CQ:at,qq=900001]hello')]
            if '--box' in sys.argv:
                cases = [('unrelated', 'ordinary chat'), ('keyword', '!qa Reply exactly QA_OK without using tools.')]
                if os.environ.get('LANG17_LLM_KEY'):
                    cases.append(('tool', '!qa Use exec to run printf LANG17_TOOL_OK and report its output.'))
            if '--fault' not in sys.argv and '--box' not in sys.argv:
                cases += [
                    ('other_mention', '[CQ:at,qq=900003]hello'),
                    ('private', 'hello'),
                    ('failure', '!qa RAISE'),
                    ('timeout', '!qa TIMEOUT'),
                    ('image', '!qa IMAGE'),
                ]
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
                    await asyncio.sleep(20 if os.environ.get('LANG17_LLM_KEY') else (8 if '--box' in sys.argv else 2))
                    if '--box' in sys.argv:
                        box_snapshots.append({'case': name, 'sessions': await api('GET', '/box/sessions')})
                if '--fault' not in sys.argv and '--box' not in sys.argv:
                    for i, text in enumerate(['!qa BUSY', 'ordinary busy ignored', '!qa accepted followup']):
                        await ws.send(
                            json.dumps(
                                {
                                    'time': int(time.time()),
                                    'self_id': 900001,
                                    'post_type': 'message',
                                    'message_type': 'group',
                                    'sub_type': 'normal',
                                    'message_id': 180 + i,
                                    'group_id': 900180,
                                    'user_id': 900002,
                                    'message': text,
                                    'raw_message': text,
                                    'sender': {'user_id': 900002, 'nickname': 'QA', 'role': 'member'},
                                }
                            )
                        )
                        await asyncio.sleep(1)
                    await asyncio.sleep(6)
                    steering = [payload for payload in sent_payloads if 'STEERING:' in str(payload)]
                    assert len(steering) == 1, steering
                    assert 'accepted followup' in str(steering), steering
                    assert 'ordinary busy ignored' not in str(steering), steering
                    Path('busy-steering.json').write_text(json.dumps(steering, indent=2))
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
        executions = await api('GET', '/monitoring/executions?source=pipeline')
        details = []
        for row in executions['items'][:3]:
            detail = await api(
                'GET',
                '/monitoring/executions/pipeline/'
                + row['id']
                + ('' if os.environ.get('LANG17_BASE') else '?section=overview'),
            )
            details.append({'id': row['id'], 'pages': list(detail['pages'])})
        Path('monitoring-api.json').write_text(json.dumps({'executions': executions, 'details': details}, indent=2))
        with sqlite3.connect('data/langbot.db') as db:
            tables = [row[0] for row in db.execute("select name from sqlite_master where type='table'")]
            monitoring = {}
            for table in tables:
                if table in ('monitoring_messages', 'monitoring_sessions'):
                    db.row_factory = sqlite3.Row
                    monitoring[table] = [dict(row) for row in db.execute('select * from ' + table)]
        # Historical input is seeded only into this task-owned database.
        with sqlite3.connect('data/langbot.db') as db:
            db.row_factory = sqlite3.Row
            template = dict(db.execute("SELECT * FROM monitoring_messages WHERE role='user' LIMIT 1").fetchone())
            template.update(
                status='pending',
                role='user',
                execution_owner_id=None,
                execution_lease_expires_at=None,
                event_id=None,
                run_id=None,
                session_id='group_history',
                timestamp=(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1))
                .replace(tzinfo=None)
                .isoformat(' '),
                message_content=json.dumps([{'type': 'Image', 'base64': 'eA==' * 65536}]),
            )
            for i in range(64):
                template['id'] = 'history-' + str(i)
                db.execute(
                    'INSERT INTO monitoring_messages ('
                    + ','.join(template)
                    + ') VALUES ('
                    + ','.join('?' for _ in template)
                    + ')',
                    list(template.values()),
                )
        history = {'seeded_rows': 64, 'payload_characters_per_row': len(template['message_content']), 'samples': []}
        for _ in range(3):
            started = time.monotonic()
            sessions = await api('GET', '/monitoring/sessions?botId=' + bot['uuid'])
            session_seconds = time.monotonic() - started
            started = time.monotonic()
            async with client.stream('GET', '/api/v1/monitoring/in-flight/stream') as stream:
                stream.raise_for_status()
                async for line in stream.aiter_lines():
                    if line.startswith('data: '):
                        snapshot = json.loads(line[6:])
                        break
            history['samples'].append(
                {
                    'sessions_seconds': session_seconds,
                    'snapshot_seconds': time.monotonic() - started,
                    'snapshot': snapshot,
                    'session_count': sessions['total'],
                }
            )
        Path('history-api.json').write_text(json.dumps(history, indent=2))
        if not os.environ.get('LANG17_BASE'):
            auth_path = Path('browser-auth.json')
            auth_path.write_text(json.dumps({'token': auth['token']}))
            auth_path.chmod(0o600)
            try:
                subprocess.run(['node', str(Path(__file__).with_name('lang17_ui.mjs'))], check=True, timeout=35)
            finally:
                auth_path.unlink()
        Path('onebot-result.json').write_text(
            json.dumps(
                {
                    'cases': cases,
                    'box_snapshots': box_snapshots,
                    'live_model': os.environ.get('LANG17_LLM_MODEL'),
                    'synthetic_runner_real_runtime': True,
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
