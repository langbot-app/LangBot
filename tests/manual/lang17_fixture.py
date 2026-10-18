"""Real dedicated-worker faults and bounded OneBot load with synthetic QA runners."""

import io
import os
import zipfile

import yaml

RUNNER = """import asyncio, os, time
from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import Message, ContentElement
from langbot_plugin.api.entities.builtin.runner import RunnerResult
class Probe(Runner):
    async def run(self, ctx):
        text = ctx.input.to_text()
        if 'RAISE' in text: raise RuntimeError('LANG17 handler fault')
        if 'EXIT' in text: os._exit(17)
        if 'BLOCK' in text:
            until = time.monotonic() + 3
            while time.monotonic() < until: pass
        if 'TIMEOUT' in text: await asyncio.wait_for(asyncio.sleep(3), 0.2)
        if 'SLOW' in text: await asyncio.sleep(0.1)
        if 'WAIT' in text: await asyncio.sleep(60)
        if 'BUSY' in text:
            await asyncio.sleep(6)
            pulled = await ctx.steering_pull()
            yield RunnerResult.message_completed(ctx.run_id, Message(role='assistant', content='STEERING:' + str(pulled.model_dump())))
            yield RunnerResult.run_completed(ctx.run_id)
            return
        content = [ContentElement.from_image_base64('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')] if 'IMAGE' in text else 'LANG17_HEALTHY'
        yield RunnerResult.message_completed(ctx.run_id, Message(role='assistant', content=content))
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
            'capabilities': {'streaming': True, 'tool_calling': False, 'steering': True},
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
