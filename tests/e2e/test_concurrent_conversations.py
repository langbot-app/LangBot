"""Simultaneous conversations through the real app, Plugin Runtime and Local Agent.

Only the model is fake: it answers ``ECHO[token]`` after a random delay, so every
reply can be traced to the exact message that caused it.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import uuid

import aiohttp
import pytest
from aiohttp import web

from tests.e2e.test_local_runner_fake_provider import (  # noqa: F401  (session fixtures)
    FAKE_MODEL_UUID,
    LOCAL_RUNNER_ID,
    _free_port,
    _inject_fake_llm_model,
    _run_local_agent_probe,
    local_agent_e2e_config_path,
    local_agent_e2e_port,
    local_agent_e2e_tmpdir,
    local_agent_runtime_ports,
    local_agent_runtime_process,
)

pytestmark = [pytest.mark.e2e, pytest.mark.local_agent]

TOKEN = re.compile(r'TOK<([^>]+)>')
ECHO = re.compile(r'ECHO\[([^\]]+)\]')


def install_echo_model(fake, prompted: set[str]) -> None:
    from langbot_plugin.api.entities.builtin.provider import message as provider_message

    def answer(messages):
        texts = [fake._content_to_text(item.content) for item in messages]
        prompted.update(token for text in texts for token in TOKEN.findall(text))
        newest = [text for item, text in zip(messages, texts) if item.role == 'user'][-1]
        return 'ECHO[' + '+'.join(dict.fromkeys(TOKEN.findall(newest))) + ']'

    async def invoke(query, model, messages, funcs=None, extra_args={}, remove_think=False):
        await asyncio.sleep(random.uniform(0.1, 0.6))
        return provider_message.Message(role='assistant', content=answer(messages))

    async def stream(query, model, messages, funcs=None, extra_args={}, remove_think=False):
        parts = [f'part{index} ' for index in range(8)] + [answer(messages)]
        for index, part in enumerate(parts):
            await asyncio.sleep(random.uniform(0.02, 0.08))
            yield provider_message.MessageChunk(role='assistant', content=part, is_final=index == len(parts) - 1)

    fake.invoke_llm, fake.invoke_llm_stream = invoke, stream


async def create_bot(ap, context, adapter, adapter_config):
    runner_config = {
        'model': {'primary': FAKE_MODEL_UUID, 'fallbacks': []},
        'timeout': 60,
        'prompt': [{'role': 'system', 'content': 'You are a concise test assistant.'}],
        'knowledge-bases': [],
    }
    config = await ap.pipeline_service.get_default_pipeline_config(context, LOCAL_RUNNER_ID)
    config['ai']['runner']['id'] = LOCAL_RUNNER_ID
    config['ai']['runner_config'][LOCAL_RUNNER_ID] = runner_config
    pipeline = await ap.pipeline_service.create_pipeline(context, {'name': adapter, 'config': config})
    binding = {'event_pattern': 'message.received', 'target_type': 'pipeline', 'target_uuid': pipeline, 'enabled': True}
    return await ap.bot_service.create_bot(
        context,
        {
            'name': adapter,
            'adapter': adapter,
            'adapter_config': adapter_config,
            'enable': True,
            'event_bindings': [binding],
        },
    )


def text_of(parts) -> str:
    return ''.join(part.get('text', '') for part in parts if part.get('type') == 'Plain')


def plain(token) -> list[dict]:
    return [{'type': 'Plain', 'text': f'TOK<{token}>'}]


async def settle(items, expected, timeout=40):
    """Wait until every expected token was answered, then for stray extra replies."""
    deadline = asyncio.get_running_loop().time() + timeout
    while not expected() and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.1)
    count = -1
    while count != len(items):
        count = len(items)
        await asyncio.sleep(2)


async def http_probe(ap, context, base, http, prompted):
    callbacks, sync_replies = [], {}

    async def callback(request):
        payload = await request.json()
        if payload['is_final']:
            callbacks.append((payload['session_id'], text_of(payload['message'])))
        return web.json_response({})

    receiver = web.Application()
    receiver.add_routes([web.post('/cb', callback)])
    runner = web.AppRunner(receiver)
    await runner.setup()
    port = _free_port()
    await web.TCPSite(runner, '127.0.0.1', port).start()
    config = {
        'callback_url': f'http://127.0.0.1:{port}/cb',
        'inbound_secret': 's',
        'signature_required': False,
        'default_session_type': 'person',
    }
    bot = await create_bot(ap, context, 'http_bot', config)

    async def conversation(index):
        for turn in range(3):
            body = {'session_id': f's{index}', 'message': plain(f's{index}-{turn}')}
            await http.post(f'{base}/bots/{bot}', json=body)
            await asyncio.sleep(random.uniform(0, 0.4))

    async def sync_request(index):
        await asyncio.sleep(random.uniform(0, 0.5))
        body = {'session_id': f's{index}', 'message': plain(f's{index}-sync')}
        async with http.post(f'{base}/bots/{bot}/sync', json=body) as response:
            sync_replies[index] = text_of((await response.json())['data']['message'])

    await asyncio.gather(*(conversation(i) for i in range(6)), *(sync_request(i) for i in range(3)))
    sent = {f's{index}-{turn}' for index in range(6) for turn in range(3)}
    # A quick follow-up may join the running turn, so reaching the model is what must never fail.
    await settle(callbacks, lambda: sent <= prompted)
    await runner.cleanup()
    return callbacks, sync_replies, sent - prompted


async def websocket_probe(ap, context, base, http):
    bot = await create_bot(ap, context, 'web_page_bot', {})
    results = {}

    async def visitor(index):
        url = f'{base.replace("http", "ws", 1)}/api/v1/embed/{bot}/ws/connect'
        params = {'session_type': 'person', 'session_id': str(uuid.uuid4())}
        bubbles = {}
        async with http.ws_connect(url, params=params, headers={'Origin': base}) as socket:
            await socket.send_json({'type': 'authenticate', 'token': 'x'})
            # Half of the visitors opted out of streaming.
            await socket.send_json({'type': 'message', 'stream': index % 2 == 0, 'message': plain(f'w{index}')})
            while True:
                try:
                    frame = json.loads((await socket.receive(timeout=20 if not bubbles else 3)).data)
                except asyncio.TimeoutError:
                    break
                if frame.get('type') == 'response':
                    bubbles[frame['data']['id']] = frame['data']['content']
        results[index] = list(bubbles.values())

    await asyncio.gather(*(visitor(index) for index in range(8)))
    return results


@pytest.mark.contract('concurrent_conversations')
def test_simultaneous_conversations_keep_single_replies_with_their_sender(
    local_agent_e2e_tmpdir,  # noqa: F811
    local_agent_e2e_config_path,  # noqa: F811
    local_agent_e2e_port,  # noqa: F811
    local_agent_runtime_process,  # noqa: F811
):
    del local_agent_e2e_config_path, local_agent_runtime_process
    random.seed(7)

    async def probe(ap):
        prompted: set[str] = set()
        install_echo_model(await _inject_fake_llm_model(ap), prompted)
        context = await ap.plugin_connector._current_execution_context()
        base = f'http://127.0.0.1:{local_agent_e2e_port}'
        async with aiohttp.ClientSession() as http:
            return (
                await http_probe(ap, context, base, http, prompted),
                await websocket_probe(ap, context, base, http),
            )

    (callbacks, sync_replies, lost), visitors = _run_local_agent_probe(local_agent_e2e_tmpdir, probe)

    assert lost == set()
    answered = [(session, token) for session, text in callbacks for t in ECHO.findall(text) for token in t.split('+')]
    assert [item for item in answered if not item[1].startswith(f'{item[0]}-')] == []
    assert len(answered) == len(set(answered))
    for index, reply in sync_replies.items():
        assert ECHO.findall(reply) == [f's{index}-sync']
    for index, bubbles in visitors.items():
        assert len(bubbles) == 1, bubbles
        assert ECHO.findall(bubbles[0]) == [f'w{index}']
