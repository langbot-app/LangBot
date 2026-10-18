"""Real dedicated-worker faults and bounded OneBot load with synthetic QA runners."""

import asyncio
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
import zipfile

import httpx
import websockets
import yaml

RUNNER = """import asyncio, os, time
from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.runner import RunnerResult
class Probe(Runner):
    async def run(self, ctx):
        text = ctx.input.to_text()
        if 'RAISE' in text.split(): raise RuntimeError('LANG17 handler fault')
        if 'EXIT' in text.split(): os._exit(17)
        if 'BLOCK' in text.split():
            until = time.monotonic() + 3
            while time.monotonic() < until: pass
        if 'TIMEOUT' in text.split(): await asyncio.wait_for(asyncio.sleep(3), 0.2)
        if 'SLOW' in text.split(): await asyncio.sleep(0.1)
        if 'WAIT' in text.split(): await asyncio.sleep(60)
        yield RunnerResult.message_completed(ctx.run_id, Message(role='assistant', content='LANG17_HEALTHY'))
        yield RunnerResult.run_completed(ctx.run_id)
"""


LISTENER = """import asyncio, os, time
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain
class ProbeListener(EventListener):
    async def initialize(self):
        @self.handler(events.GroupNormalMessageReceived)
        async def handle(ctx):
            text = ctx.event.text_message
            name = 'PLUGIN_NAME'
            if name == 'FaultProbe':
                if 'LRAISE' in text: raise RuntimeError('LANG17 listener fault')
                if 'LTIMEOUT' in text: await asyncio.wait_for(asyncio.sleep(3), 0.2)
                if 'LEXIT' in text: os._exit(19)
                if 'LBLOCK' in text:
                    until = time.monotonic() + 3
                    while time.monotonic() < until: pass
            if 'CONTRACT' in text:
                previous = str(ctx.event.reply_message_chain or '')
                ctx.event.reply_message_chain = MessageChain([Plain(text=previous + name + '>')])
                ctx.prevent_default()
                if 'STOP' in text: ctx.prevent_postorder()
"""


def package(name, init_failure=False, dependency_failure=False):
    manifest = {
        'apiVersion': 'v1',
        'kind': 'Plugin',
        'metadata': {
            'author': 'lang17-qa',
            'name': name,
            'version': '0.0.1',
            'label': {'en_US': name},
            'description': {'en_US': 'Isolated synthetic QA fixture'},
            'icon': 'assets/icon.svg',
        },
        'spec': {'config': [], 'components': {'Runner': {'fromDirs': [{'path': 'components/runner/'}]}}},
        'execution': {'python': {'path': 'main.py', 'attr': 'ProbePlugin'}},
    }
    component = {
        'apiVersion': 'langbot/v1',
        'kind': 'Runner',
        'metadata': {'name': 'default', 'label': {'en_US': 'Probe'}, 'description': {'en_US': 'No model calls'}},
        'spec': {
            'usages': ['agent'],
            'config': [],
            'capabilities': {'streaming': True, 'tool_calling': False},
            'permissions': {},
        },
        'execution': {'python': {'path': 'default.py', 'attr': 'Probe'}},
    }
    main = 'from langbot_plugin.api.definition.plugin import BasePlugin\nclass ProbePlugin(BasePlugin):\n    async def initialize(self):\n        '
    main += "raise RuntimeError('LANG17 initialization fault')\n" if init_failure else 'pass\n'
    listener_files = {}
    if os.environ.get('LANG17_LISTENERS') == '1':
        manifest['spec']['components']['EventListener'] = {'fromDirs': [{'path': 'components/event_listener/'}]}
        listener_manifest = {
            'apiVersion': 'v1',
            'kind': 'EventListener',
            'metadata': {'name': 'events', 'label': {'en_US': 'QA events'}},
            'spec': {},
            'execution': {'python': {'path': 'events.py', 'attr': 'ProbeListener'}},
        }
        listener_files = {
            'components/event_listener/events.yaml': yaml.safe_dump(listener_manifest),
            'components/event_listener/events.py': LISTENER.replace('PLUGIN_NAME', name),
        }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        for path, data in {
            **listener_files,
            'manifest.yaml': yaml.safe_dump(manifest),
            'main.py': main,
            'components/runner/default.yaml': yaml.safe_dump(component),
            'components/runner/default.py': RUNNER,
            'requirements.txt': 'not a valid requirement === !!!' if dependency_failure else '',
            'assets/icon.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>',
        }.items():
            z.writestr(path, data)
    return stream.getvalue()


async def main():
    results = {
        'synthetic_plugins': True,
        'stages': [],
        'sent': 0,
        'listeners': os.environ.get('LANG17_LISTENERS') == '1',
        'explicit_plugin_bindings': os.environ.get('LANG17_BOUND') == '1',
    }
    async with httpx.AsyncClient(base_url='http://127.0.0.1:16399', timeout=15, trust_env=False) as client:

        async def api(method, path, data=None):
            r = await client.request(method, '/api/v1' + path, json=data)
            b = r.json()
            if r.status_code >= 400 or b.get('code') != 0:
                raise RuntimeError(f'{path}: HTTP {r.status_code}: {b.get("msg")}')
            return b.get('data', {})

        async def snapshot(label):
            health = (await client.get('/healthz')).json()
            list_started = time.monotonic()
            try:
                plugin_list = await api('GET', '/plugins')
                listing = {'ok': True, 'count': len(plugin_list.get('plugins', []))}
            except Exception as exc:
                listing = {'ok': False, 'error_type': type(exc).__name__}
            listing['seconds'] = round(time.monotonic() - list_started, 3)
            with sqlite3.connect('data/langbot.db') as db:
                states = list(db.execute('select role,status,count(*) from monitoring_messages group by role,status'))
            active = await api('GET', '/monitoring/executions?status=running&source=pipeline')
            results['stages'].append(
                {
                    'label': label,
                    'monotonic': time.monotonic(),
                    'health': health,
                    'message_states': states,
                    'plugin_list': listing,
                    'api_running_queries': active['total'],
                }
            )
            Path('matrix-result.json').write_text(json.dumps(results, indent=2))

        async def install(name, **kwargs):
            response = await client.post(
                '/api/v1/plugins/install/local', files={'file': (name + '.lbpkg', package(name, **kwargs))}
            )
            task = response.json()['data']['task_id']
            for _ in range(45):
                state = (await api('GET', '/system/tasks/' + str(task)))['runtime']
                if state['done']:
                    return {'name': name, 'done': True, 'failed': bool(state.get('exception'))}
                await asyncio.sleep(1)
            return {'name': name, 'done': False}

        account = {'user': 'qa-matrix@example.invalid', 'password': secrets.token_urlsafe(24)}
        await api('POST', '/user/init', account)
        client.headers['Authorization'] = 'Bearer ' + (await api('POST', '/user/auth', account))['token']
        results['installations'] = [await install('HealthyProbe'), await install('FaultProbe')]

        async def bot(name, port):
            pipeline = (await api('POST', '/pipelines', {'name': name, 'description': 'QA fixture'}))['uuid']
            config = (await api('GET', '/pipelines/' + pipeline))['pipeline']['config']
            config['trigger']['group-respond-rules'] = {'at': True, 'prefix': ['qa:'], 'regexp': [], 'random': 0}
            runner = 'plugin:lang17-qa/' + name + '/default'
            config['ai'] = {'runner': {'id': runner, 'expire-time': 0}, 'runner_config': {runner: {}}}
            payload = {'config': config}
            if os.environ.get('LANG17_BOUND') == '1':
                payload['extensions_preferences'] = {
                    'enable_all_plugins': False,
                    'enable_all_mcp_servers': True,
                    'plugins': [{'author': 'lang17-qa', 'name': name}],
                    'mcp_servers': [],
                }
            await api('PUT', '/pipelines/' + pipeline, payload)
            b = await api(
                'POST',
                '/platform/bots',
                {
                    'name': name,
                    'description': 'QA',
                    'adapter': 'aiocqhttp',
                    'enable': True,
                    'adapter_config': {'host': '127.0.0.1', 'port': port, 'access-token': ''},
                    'event_bindings': [
                        {
                            'id': 'default',
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
            await api('PUT', '/platform/bots/' + b['uuid'], {'enable': True})

        await bot('HealthyProbe', 13280)
        await bot('FaultProbe', 13281)
        await asyncio.sleep(1)
        async with (
            websockets.connect(
                'ws://127.0.0.1:13280/ws/', additional_headers={'X-Self-ID': '910001', 'X-Client-Role': 'Universal'}
            ) as healthy,
            websockets.connect(
                'ws://127.0.0.1:13281/ws/', additional_headers={'X-Self-ID': '910001', 'X-Client-Role': 'Universal'}
            ) as fault,
        ):
            replies = []

            async def responder(ws, owner):
                async for raw in ws:
                    r = json.loads(raw)
                    if r.get('action') == 'send_msg':
                        replies.append(
                            {'owner': owner, 'time': time.monotonic(), 'message': r.get('params', {}).get('message')}
                        )
                    await ws.send(
                        json.dumps({'status': 'ok', 'retcode': 0, 'data': {'message_id': 1}, 'echo': r.get('echo')})
                    )

            responders = [
                asyncio.create_task(responder(healthy, 'healthy')),
                asyncio.create_task(responder(fault, 'fault')),
            ]

            async def send(ws, text, group=910100):
                results['sent'] += 1
                await ws.send(
                    json.dumps(
                        {
                            'time': int(time.time()),
                            'self_id': 910001,
                            'post_type': 'message',
                            'message_type': 'group',
                            'sub_type': 'normal',
                            'message_id': results['sent'],
                            'group_id': group,
                            'user_id': 910002,
                            'message': text,
                            'raw_message': text,
                            'sender': {'user_id': 910002, 'nickname': 'QA', 'role': 'member'},
                        }
                    )
                )

            try:
                await send(healthy, 'qa: HEALTHY')
                await asyncio.sleep(2)
                await snapshot('healthy_baseline')
                assert any('LANG17_HEALTHY' in str(r['message']) for r in replies), 'Healthy runner did not execute'
                if os.environ.get('LANG17_LISTENERS') == '1':
                    for text in ('CONTRACT', 'CONTRACT STOP'):
                        first = len(replies)
                        await send(healthy, 'qa: ' + text, 910600)
                        await asyncio.sleep(2)
                        results.setdefault('contracts', {})[text] = replies[first:]
                        expected = 'HealthyProbe>' if 'STOP' in text else 'HealthyProbe>FaultProbe>'
                        actual = [
                            element['data']['text']
                            for reply in replies[first:]
                            for element in reply['message']
                            if element['type'] == 'text'
                        ]
                        assert actual == [expected], (text, actual)

                    for kind in ('LRAISE', 'LTIMEOUT', 'LBLOCK', 'LEXIT'):
                        results.setdefault('fault_started', {})[kind] = time.monotonic()
                        await send(fault, 'qa: ' + kind, 910601)
                        await asyncio.sleep(0.3)
                        await send(healthy, 'qa: HEALTHY control', 910101)
                        await asyncio.sleep(5)
                        await snapshot(kind)
                    await asyncio.sleep(3)
                if os.environ.get('LANG17_CANCEL') == '1':
                    await send(healthy, 'qa: WAIT', 910500)
                    await asyncio.sleep(1)
                    await snapshot('before_cancel')
                    Path('cancel-ready').touch()
                    return
                for kind in ('RAISE', 'TIMEOUT', 'BLOCK'):
                    results.setdefault('fault_started', {})[kind] = time.monotonic()
                    await send(fault, 'qa: ' + kind)
                    await asyncio.sleep(0.3)
                    await send(healthy, 'qa: HEALTHY control', 910101)
                    await asyncio.sleep(5)
                    await snapshot(kind)
                await send(fault, 'qa: SLOW', 910400)
                await asyncio.sleep(0.05)
                await fault.close()
                await asyncio.sleep(6)
                await snapshot('onebot_disconnect')
                async with websockets.connect(
                    'ws://127.0.0.1:13281/ws/',
                    additional_headers={'X-Self-ID': '910001', 'X-Client-Role': 'Universal'},
                ) as reconnected:
                    responders.append(asyncio.create_task(responder(reconnected, 'fault_reconnected')))
                    await send(reconnected, 'qa: HEALTHY reconnect', 910401)
                    await asyncio.sleep(2)
                    await snapshot('onebot_reconnected')
                    results.setdefault('fault_started', {})['EXIT'] = time.monotonic()
                    await send(reconnected, 'qa: EXIT', 910402)
                    await asyncio.sleep(0.3)
                    await send(healthy, 'qa: HEALTHY control', 910101)
                    await asyncio.sleep(5)
                    await snapshot('EXIT')
                if os.environ.get('LANG17_BOUND') == '1' or os.environ.get('LANG17_SHORT') == '1':
                    results['complete'] = True
                    results['replies'] = replies
                    Path('matrix-result.json').write_text(json.dumps(results, indent=2))
                    return
                results['installations'] += [
                    await install('InitFailure', init_failure=True),
                    await install('DependencyFailure', dependency_failure=True),
                ]
                await send(healthy, 'qa: HEALTHY after installs')
                await asyncio.sleep(3)
                await snapshot('installation_faults')
                for _ in range(160):
                    await send(healthy, 'qa: SLOW', 910200)
                await asyncio.sleep(1)
                await snapshot('burst_peak')
                await asyncio.sleep(25)
                await snapshot('burst_drained')
                for i in range(int(os.environ.get('LANG17_SOAK_ROUNDS', '6'))):
                    for _ in range(50):
                        await send(healthy, 'ordinary unrelated chat', 910300)
                    await send(healthy, 'qa: HEALTHY soak', 910301)
                    await asyncio.sleep(10)
                    await snapshot('soak_' + str(i))
                await asyncio.sleep(20)
                await snapshot('idle_recovery')
                results['complete'] = True
                results['replies'] = replies
                Path('matrix-result.json').write_text(json.dumps(results, indent=2))
            finally:
                for task in responders:
                    task.cancel()
                await asyncio.gather(*responders, return_exceptions=True)
    Path('matrix-finished').touch()


try:
    asyncio.run(main())
finally:
    Path('matrix-finished').touch()
