"""Seed an actual 4.10.10 database, then validate its 4.11 upgrade through APIs."""

import asyncio
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time

import httpx
import websockets


async def main():
    result = {'mode': os.environ['LANG16_UPGRADE']}
    async with httpx.AsyncClient(base_url='http://127.0.0.1:15399', timeout=20, trust_env=False) as client:

        async def api(method, path, data=None):
            r = await client.request(method, '/api/v1' + path, json=data)
            b = r.json()
            if r.status_code >= 400 or b.get('code') != 0:
                raise RuntimeError(f'{path}: HTTP {r.status_code}: {b.get("msg")}')
            return b.get('data', {})

        if result['mode'] == 'old':
            account = {'user': 'qa-upgrade@example.invalid', 'password': secrets.token_urlsafe(24)}
            await api('POST', '/user/init', account)
            Path('upgrade-account.json').write_text(json.dumps(account))
            Path('upgrade-account.json').chmod(0o600)
        else:
            account = json.loads(Path(os.environ['LANG16_UPGRADE_ACCOUNT']).read_text())
        client.headers['Authorization'] = 'Bearer ' + (await api('POST', '/user/auth', account))['token']
        if result['mode'] == 'old':
            pipeline = (await api('POST', '/pipelines', {'name': 'Real 4.10.10 seed', 'description': 'QA upgrade'}))[
                'uuid'
            ]
            bot = await api(
                'POST',
                '/platform/bots',
                {
                    'name': 'Upgrade OneBot',
                    'description': 'QA',
                    'adapter': 'aiocqhttp',
                    'enable': False,
                    'adapter_config': {'host': '127.0.0.1', 'port': 12280, 'access-token': ''},
                    'use_pipeline_uuid': pipeline,
                },
            )
            result.update(pipeline=pipeline, bot=bot['uuid'])
        else:
            preview = await api('GET', '/pipelines/_/migration/preview')
            result['preview'] = [{k: v for k, v in x.items() if k != 'preview_token'} for x in preview['items']]
            task = await api(
                'POST', '/pipelines/_/migration/execute', {'confirmed': True, 'all': True, 'install_plugins': True}
            )
            for _ in range(60):
                state = (await api('GET', '/system/tasks/' + str(task['task_id'])))['runtime']
                if state['done']:
                    break
                await asyncio.sleep(1)
            result['task'] = {k: v for k, v in state.items() if k != 'exception_traceback'}
            bots = (await api('GET', '/platform/bots'))['bots']
            result['bindings'] = [b.get('event_bindings') for b in bots]
            await api('PUT', '/platform/bots/' + bots[0]['uuid'], {'enable': True})
            await asyncio.sleep(1)
            async with websockets.connect(
                'ws://127.0.0.1:12280/ws/', additional_headers={'X-Self-ID': '920001', 'X-Client-Role': 'Universal'}
            ) as ws:

                async def respond():
                    async for raw in ws:
                        r = json.loads(raw)
                        await ws.send(
                            json.dumps({'status': 'ok', 'retcode': 0, 'data': {'message_id': 1}, 'echo': r.get('echo')})
                        )

                responder = asyncio.create_task(respond())
                try:
                    for i, text in enumerate(['unrelated chat', '[CQ:at,qq=920001]hello']):
                        await ws.send(
                            json.dumps(
                                {
                                    'time': int(time.time()),
                                    'self_id': 920001,
                                    'post_type': 'message',
                                    'message_type': 'group',
                                    'sub_type': 'normal',
                                    'message_id': i + 1,
                                    'group_id': 920100,
                                    'user_id': 920002,
                                    'message': text,
                                    'raw_message': text,
                                    'sender': {'user_id': 920002, 'nickname': 'QA', 'role': 'member'},
                                }
                            )
                        )
                        await asyncio.sleep(3)
                finally:
                    responder.cancel()
                    await asyncio.gather(responder, return_exceptions=True)
        with sqlite3.connect('data/langbot.db') as db:
            result['alembic_revision'] = list(db.execute('select version_num from alembic_version'))
            result['messages'] = list(db.execute('select role,status,message_content from monitoring_messages'))
        result['health'] = (await client.get('/healthz')).json()
    Path('upgrade-result.json').write_text(json.dumps(result, indent=2))


asyncio.run(main())
