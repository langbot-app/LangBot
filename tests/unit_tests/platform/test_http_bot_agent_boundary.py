from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import quart
import yaml
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import events, message
from langbot_plugin.box.client import BoxRuntimeClient
from langbot_plugin.api.proxies.runner.box import RunnerBoxAPIMixin
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

from langbot.pkg.agent.runner.execution_context import build_execution_query
from langbot.pkg.agent.runner.platform_tools import (
    build_platform_tool_resources,
    execute_platform_tool,
    freeze_platform_context,
    resolve_agent_platform_tool_names,
    resolve_platform_api_call,
)
from langbot.pkg.box.runner import RunBoxBinding, RunnerBoxService, exported_message, prepare_input_files
from langbot.pkg.box.service import BoxService
from langbot.pkg.discover.engine import Component
from langbot.pkg.platform.botmgr import RuntimeBot
from langbot.pkg.platform.sources import http_bot_signing as signing
from langbot.pkg.platform.sources.http_bot import HttpBotAdapter


def discovered_adapter():
    relative = 'pkg/platform/sources/http_bot.yaml'
    manifest = yaml.safe_load((Path(__file__).parents[3] / 'src/langbot' / relative).read_text())
    adapter_class = Component('builtin', manifest, relative).get_python_component_class()
    assert adapter_class is HttpBotAdapter
    return adapter_class(
        config={'inbound_secret': 'test-only-secret', 'signature_required': True, 'callback_timeout': 1},
        logger=AsyncMock(spec=AbstractEventLogger),
    )


def envelope(bot, adapter, inbound):
    return bot._eba_event_to_agent_envelope(bot._legacy_message_to_eba_event(inbound, adapter), adapter)


@pytest.mark.asyncio
@pytest.mark.parametrize('session_type', ['person', 'group'])
@pytest.mark.parametrize('mixed', [False, True])
async def test_signed_http_file_reaches_box_and_authorized_agent_reply_reaches_sync(
    tmp_path, monkeypatch, session_type, mixed
):
    async def inline_thread(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(asyncio, 'to_thread', inline_thread)
    adapter = discovered_adapter()
    adapter._enqueue_callback = AsyncMock(side_effect=AssertionError('sync reply must not use callback'))
    bot = object.__new__(RuntimeBot)
    bot.bot_entity = SimpleNamespace(uuid='http-test-bot')
    app = SimpleNamespace(
        logger=Mock(),
        instance_config=SimpleNamespace(data={'box': {'enabled': True}}),
        platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=SimpleNamespace(adapter=adapter))),
    )
    box = BoxService(app, client=Mock(spec=BoxRuntimeClient))
    box._available = True

    async def write_files(query, subdir, target_dir, pending):
        for name, content in pending:
            destination = tmp_path / target_dir.lstrip('/') / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        return [f'{target_dir}/{name}' for name, content in pending]

    box._write_files_into_sandbox = AsyncMock(side_effect=write_files)
    runner_box = RunnerBoxService(box)
    received = []
    listener_errors = []
    proof = b'HTTP inbound proof survives event conversion'
    image = b'\x89PNG\r\n\x1a\n'

    async def listener(inbound, live_adapter):
        event = envelope(bot, live_adapter, inbound)
        received.append(event)
        query = build_execution_query(event, [])
        prepare_input_files(query, event.input)
        object.__setattr__(query, '_box_binding', RunBoxBinding('run-test', 'box-test', {}, 'run-test'))
        imported = await runner_box.import_attachments(query, None)
        assert len(imported['items']) == (2 if mixed else 1)
        imported_file = next(item for item in imported['items'] if item['name'] == 'proof.txt')
        assert (tmp_path / imported_file['path'].lstrip('/')).read_bytes() == proof
        assert imported_file['size'] == len(proof)
        if mixed:
            imported_image = next(item for item in imported['items'] if item['type'] == 'Image')
            assert (tmp_path / imported_image['path'].lstrip('/')).read_bytes() == image
        resources, capabilities = build_platform_tool_resources(
            event, resolve_agent_platform_tool_names({}, event.event_type), ['call']
        )
        assert any(tool['tool_name'] == 'event_reply' for tool in resources)
        assert capabilities['supported_apis'] == ['send_message', 'reply_message']
        session = {
            'authorization': {
                'bot_id': event.bot_id,
                'resources': {'tools': resources},
                'platform_context': freeze_platform_context(event),
            }
        }
        chain = message.MessageChain([message.Plain(text=proof.decode())])
        tool, params, rich = resolve_platform_api_call(
            session,
            event.bot_id,
            'send_message',
            {'target_type': session_type, 'target_id': 'proof-session', 'message': chain.model_dump()},
        )
        assert tool == 'event_reply'
        await execute_platform_tool(app, object(), session, tool, params, message_chain=rich)

    async def checked_listener(inbound, live_adapter):
        try:
            await listener(inbound, live_adapter)
        except Exception as error:
            listener_errors.append(error)
            live_adapter.sync_waiters['proof-session'].done.set()

    adapter.register_listener(events.FriendMessage, checked_listener)
    adapter.register_listener(events.GroupMessage, checked_listener)
    web = quart.Quart(__name__)

    @web.post('/bots/http-test-bot/sync')
    async def sync():
        return await adapter.handle_unified_webhook('http-test-bot', 'sync', quart.request)

    components = [
        {'type': 'Plain', 'text': 'Read proof.txt and reply with its contents.'},
        {'type': 'File', 'name': 'proof.txt', 'base64': base64.b64encode(proof).decode()},
    ]
    if mixed:
        components.append({'type': 'Image', 'base64': base64.b64encode(image).decode()})
    body = json.dumps({'session_id': 'proof-session', 'session_type': session_type, 'message': components}).encode()
    timestamp, signature = signing.sign('test-only-secret', body)
    client = web.test_client()
    rejected = await client.post('/bots/http-test-bot/sync', data=body)
    assert rejected.status_code == 401
    assert received == []
    response = await asyncio.wait_for(
        client.post(
            '/bots/http-test-bot/sync',
            data=body,
            headers={signing.HEADER_TIMESTAMP: timestamp, signing.HEADER_SIGNATURE: signature},
        ),
        timeout=5,
    )
    assert response.status_code == 200
    if listener_errors:
        raise listener_errors[0]
    data = (await response.get_json())['data']
    assert data['message'] == [{'type': 'Plain', 'text': proof.decode()}]
    assert data['reply_to'].startswith('in_')
    assert len(received) == 1
    adapter._enqueue_callback.assert_not_awaited()
    assert adapter.sync_waiters == {}
    await asyncio.gather(*adapter.inbound_tasks)


@pytest.mark.parametrize('denial', ['bot', 'target', 'grant', 'operation', 'capability'])
def test_live_http_reply_grants_fail_closed(denial):
    adapter = discovered_adapter()
    bot = object.__new__(RuntimeBot)
    bot.bot_entity = SimpleNamespace(uuid='http-test-bot')
    inbound, *_ = adapter._build_event({'session_id': 'proof-session', 'message': [{'type': 'Plain', 'text': 'hi'}]})
    event = envelope(bot, adapter, inbound)
    if denial == 'capability':
        event.delivery.platform_capabilities['supported_apis'] = []
    resources, _ = build_platform_tool_resources(
        event, ['event_reply'], ['detail' if denial == 'operation' else 'call']
    )
    session = {
        'authorization': {
            'bot_id': event.bot_id,
            'resources': {'tools': [] if denial == 'grant' else resources},
            'platform_context': freeze_platform_context(event),
        }
    }
    with pytest.raises(ValueError, match='not authorized'):
        resolve_platform_api_call(
            session,
            'foreign-bot' if denial == 'bot' else event.bot_id,
            'send_message',
            {
                'target_type': 'person',
                'target_id': 'foreign-session' if denial == 'target' else 'proof-session',
                'message': [{'type': 'Plain', 'text': 'reply'}],
            },
        )


@pytest.mark.asyncio
async def test_http_send_without_sync_waiter_preserves_callback_delivery():
    adapter = discovered_adapter()
    adapter._enqueue_callback = AsyncMock()
    chain = message.MessageChain([message.Plain(text='async reply')])
    payload = await adapter.send_message('person', 'async-session', chain)
    adapter._enqueue_callback.assert_awaited_once_with('async-session', payload)
    assert payload['message'] == chain.model_dump()
    assert payload['is_final'] is True


@pytest.mark.asyncio
@pytest.mark.parametrize('text_api', ['send', 'reply', 'chunk'])
async def test_sync_waits_for_authorized_exported_file_after_final_text(text_api):
    adapter = discovered_adapter()
    adapter._enqueue_callback = AsyncMock()
    bot = object.__new__(RuntimeBot)
    bot.bot_entity = SimpleNamespace(uuid='http-test-bot')
    inbound, session_id, _, message_id = adapter._build_event(
        {'session_id': 'generated-session', 'message': [{'type': 'Plain', 'text': 'generate a file'}]}
    )
    text_sent = asyncio.Event()
    export_allowed = asyncio.Event()
    content = b'generated file bytes'

    async def listener(event, live_adapter):
        text = message.MessageChain([message.Plain(text=content.decode())])
        if text_api == 'send':
            await live_adapter.send_message('person', session_id, text)
        elif text_api == 'reply':
            await live_adapter.reply_message(event, text)
        else:
            await live_adapter.reply_message_chunk(event, None, text, is_final=True)
        text_sent.set()
        await export_allowed.wait()
        agent_event = envelope(bot, live_adapter, event)
        resources, _ = build_platform_tool_resources(agent_event, ['event_reply'], ['call'])
        session = {
            'authorization': {
                'bot_id': agent_event.bot_id,
                'resources': {'tools': resources},
                'platform_context': freeze_platform_context(agent_event),
            }
        }
        query = SimpleNamespace(_box_binding=RunBoxBinding('generated-run', 'box', {}, 'generated-run'))
        box = SimpleNamespace(
            _ATTACHMENT_MAX_FILES=10,
            _ATTACHMENT_MAX_TOTAL_BYTES=1000000,
            collect_selected_files=AsyncMock(
                return_value=[
                    {
                        'type': 'File',
                        'name': 'generated-proof.txt',
                        'base64': base64.b64encode(content).decode(),
                    }
                ]
            ),
        )
        paths = ['/workspace/generated-proof.txt']
        exported = await RunnerBoxService(box).export_files(query, paths)
        box.collect_selected_files.assert_awaited_once_with(query, paths)
        file_ids = [item['id'] for item in exported['items']]
        app = SimpleNamespace(
            platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=SimpleNamespace(adapter=live_adapter)))
        )

        class FileReplyAPI(RunnerBoxAPIMixin):
            async def _box_call(self, rpc_action, **data):
                assert rpc_action == PluginToRuntimeAction.CALL_PLATFORM_API
                files = exported_message(query, data['file_ids'])
                tool, params, rich = resolve_platform_api_call(
                    session,
                    agent_event.bot_id,
                    data['action'],
                    {**data['params'], 'message': files.model_dump()},
                    data['context_tool'],
                )
                result = await execute_platform_tool(app, object(), session, tool, params, message_chain=rich)
                exported_message(query, data['file_ids'], consume=True)
                return {'result': result}

        await FileReplyAPI().reply_files(file_ids)

    web = quart.Quart(__name__)
    async with web.app_context():
        request_task = asyncio.create_task(adapter._run_sync(inbound, listener, session_id, message_id))
        try:
            await asyncio.wait_for(text_sent.wait(), timeout=1)
            done, _ = await asyncio.wait({request_task}, timeout=0.03)
            assert not done, 'A final text send must not close the active Agent collector'
            assert session_id in adapter.sync_waiters
        finally:
            export_allowed.set()
            response, status = await asyncio.wait_for(request_task, timeout=2)
        assert status == 200
        payload = (await response.get_json())['data']
    assert payload['reply_to'] == message_id
    assert len(payload['message']) == 2, adapter.logger.mock_calls
    assert payload['message'][0] == {'type': 'Plain', 'text': content.decode()}
    delivered = payload['message'][1]
    assert delivered['type'] == 'File'
    assert delivered['name'] == 'generated-proof.txt'
    assert base64.b64decode(delivered['base64'], validate=True) == content
    adapter._enqueue_callback.assert_not_awaited()
    assert adapter.sync_waiters == {}
    assert adapter.outbound_states == {}


@pytest.mark.asyncio
async def test_sync_still_waits_for_queued_legacy_pipeline_reply():
    adapter = discovered_adapter()
    listener_returned = asyncio.Event()
    inbound, session_id, _, message_id = adapter._build_event(
        {'session_id': 'legacy-session', 'message': [{'type': 'Plain', 'text': 'hi'}]}
    )

    async def listener(event, live_adapter):
        listener_returned.set()

    web = quart.Quart(__name__)
    async with web.app_context():
        request_task = asyncio.create_task(adapter._run_sync(inbound, listener, session_id, message_id))
        await asyncio.wait_for(listener_returned.wait(), timeout=1)
        done, _ = await asyncio.wait({request_task}, timeout=0.03)
        assert not done
        await adapter.reply_message(inbound, message.MessageChain([message.Plain(text='queued reply')]))
        response, status = await asyncio.wait_for(request_task, timeout=1)
        assert status == 200
        assert (await response.get_json())['data']['message'] == [{'type': 'Plain', 'text': 'queued reply'}]


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel_request', [False, True])
async def test_sync_timeout_or_disconnect_does_not_cancel_active_listener(cancel_request):
    adapter = discovered_adapter()
    adapter.config['callback_timeout'] = 0 if not cancel_request else 1
    adapter._enqueue_callback = AsyncMock()
    listener_started = asyncio.Event()
    finish = asyncio.Event()
    inbound, session_id, _, message_id = adapter._build_event(
        {'session_id': 'slow-session', 'message': [{'type': 'Plain', 'text': 'hi'}]}
    )

    async def listener(event, live_adapter):
        await live_adapter.send_message('person', session_id, message.MessageChain([message.Plain(text='text')]))
        listener_started.set()
        await finish.wait()
        await live_adapter.send_message('person', session_id, message.MessageChain([message.Plain(text='late')]))

    web = quart.Quart(__name__)
    async with web.app_context():
        request_task = asyncio.create_task(adapter._run_sync(inbound, listener, session_id, message_id))
        await asyncio.wait_for(listener_started.wait(), timeout=1)
        tasks = tuple(adapter.inbound_tasks)
        if cancel_request:
            await asyncio.sleep(0)
            request_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await request_task
        else:
            _, status = await asyncio.wait_for(request_task, timeout=1)
            assert status == 200
        assert adapter.sync_waiters == {}
        assert tasks and all(not task.done() for task in tasks)
        finish.set()
        await asyncio.gather(*tasks)
    adapter._enqueue_callback.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_listener_failure_after_reply_returns_partial_without_leaking_error():
    adapter = discovered_adapter()
    inbound, session_id, _, message_id = adapter._build_event(
        {'session_id': 'failed-session', 'message': [{'type': 'Plain', 'text': 'hi'}]}
    )

    async def listener(event, live_adapter):
        await live_adapter.send_message('person', session_id, message.MessageChain([message.Plain(text='text')]))
        raise RuntimeError('private failure detail')

    web = quart.Quart(__name__)
    async with web.app_context():
        response, status = await asyncio.wait_for(adapter._run_sync(inbound, listener, session_id, message_id), 1)
        assert status == 200
        assert 'private failure detail' not in (await response.get_data()).decode()
    assert adapter.sync_waiters == {}
    adapter.logger.warning.assert_awaited_once()
