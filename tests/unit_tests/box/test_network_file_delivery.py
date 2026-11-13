"""Signed HTTP delivery through real Box IO; bridge only the plugin dispatcher."""

import asyncio
import base64
import copy
import hashlib
import json
import shlex
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest
import quart

from langbot_plugin.api.entities.builtin.platform import events
from langbot_plugin.api.proxies.runner.box import RunnerBoxAPIMixin
from langbot_plugin.box.errors import BoxValidationError
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot.pkg.agent.runner.execution_context import build_execution_query
from langbot.pkg.agent.runner.platform_tools import (
    build_platform_tool_resources,
    execute_platform_tool,
    freeze_platform_context,
    resolve_platform_api_call,
)
from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.box.runner import RunBoxBinding, exported_message, prepare_input_files
from langbot.pkg.platform.botmgr import RuntimeBot
from langbot.pkg.platform.sources import http_bot_signing as signing
from tests.unit_tests.box import test_network_file_transfer as network_tests
from tests.unit_tests.platform.test_http_bot_agent_boundary import discovered_adapter, envelope

network_files = network_tests.network_files
pytestmark = network_tests.pytestmark


@pytest.mark.asyncio
async def test_signed_http_network_file_roundtrip_and_handle_ownership(network_files):
    box = network_files
    content = bytes(range(256)) * 8192
    expected_digest = hashlib.sha256(content).hexdigest()
    adapter = discovered_adapter()
    adapter.config['callback_timeout'] = 60
    adapter._enqueue_callback = AsyncMock(side_effect=AssertionError('sync must not use callback'))
    bot = object.__new__(RuntimeBot)
    bot.bot_entity = SimpleNamespace(uuid='http-test-bot')
    context = ExecutionContext(
        instance_uuid=box.action_context.instance_uuid,
        workspace_uuid=box.action_context.workspace_uuid,
        placement_generation=box.action_context.placement_generation,
    )
    app = SimpleNamespace(
        platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=SimpleNamespace(adapter=adapter)))
    )
    listener_errors = []
    received = []
    downloads = []

    async def source_file(request):
        downloads.append(request.path)
        return web.Response(body=content, content_type='application/octet-stream')

    async def listener(inbound, live_adapter):
        try:
            event = envelope(bot, live_adapter, inbound)
            received.append(event)
            query = build_execution_query(event, [], context)
            prepare_input_files(query, event.input)
            for field in ('_sandbox_backend', '_sandbox_e2b_config', '_sandbox_limits'):
                object.__setattr__(query, field, getattr(box.query, field))
            acquired = await box.runner.acquire(context, box.acquire_request, query)
            assert acquired['id'] == box.query._box_binding.session_id
            await box.runner.bind(context, query, 'http-delivery-run', acquired['id'])
            binding = query._box_binding
            imported = await box.runner.import_attachments(query, None)
            assert len(imported['items']) == 1
            source = imported['items'][0]
            assert source['size'] == len(content)
            output = box.output_root + '/http-delivered.bin'
            result = await box.service.execute_tool(
                {'command': f'cp -- {shlex.quote(source["path"])} {shlex.quote(output)}', 'timeout_sec': 30}, query
            )
            assert result['ok'], result['stderr']
            exported = await box.runner.export_files(query, [output])
            assert exported['warning'] is None
            file_ids = [item['id'] for item in exported['items']]
            assert len(file_ids) == 1
            resources, _ = build_platform_tool_resources(event, ['event_reply'], ['call'])
            session = {
                'authorization': {
                    'bot_id': event.bot_id,
                    'resources': {'tools': resources},
                    'platform_context': freeze_platform_context(event),
                }
            }

            class FileReplyAPI(RunnerBoxAPIMixin):
                def __init__(self, execution_query):
                    self.query = execution_query

                async def _box_call(self, rpc_action, **data):
                    # Bridge dispatch only: use production handle and platform authorization.
                    assert rpc_action == PluginToRuntimeAction.CALL_PLATFORM_API
                    current = self.query._box_binding
                    async with current.lock:
                        files = exported_message(self.query, data['file_ids'])
                        tool, params, rich = resolve_platform_api_call(
                            session,
                            event.bot_id,
                            data['action'],
                            {**data['params'], 'message': files.model_dump(mode='json')},
                            data['context_tool'],
                        )
                        reply = await execute_platform_tool(app, context, session, tool, params, message_chain=rich)
                        exported_message(self.query, data['file_ids'], consume=True)
                        return {'result': reply}

            other_query = copy.copy(query)
            other_binding = RunBoxBinding('another-run', binding.session_id, binding.spec, 'another-run')
            object.__setattr__(other_query, '_box_binding', other_binding)
            with pytest.raises(BoxValidationError, match='does not belong'):
                await FileReplyAPI(other_query).reply_files(file_ids)
            assert not other_binding.submitted and not binding.submitted
            api = FileReplyAPI(query)
            await api.reply_files(file_ids)
            assert binding.submitted == set(file_ids)
            with pytest.raises(BoxValidationError, match='already been submitted'):
                await api.reply_files(file_ids)
            assert binding.submitted == set(file_ids)
        except Exception as error:
            listener_errors.append(error)
            live_adapter.sync_waiters['delivery-session'].done.set()

    adapter.register_listener(events.FriendMessage, listener)
    http = quart.Quart(__name__)

    @http.post('/bots/http-test-bot/sync')
    async def sync():
        return await adapter.handle_unified_webhook('http-test-bot', 'sync', quart.request)

    async def signed_post(client, component):
        body = json.dumps({'session_id': 'delivery-session', 'session_type': 'person', 'message': [component]}).encode()
        timestamp, signature = signing.sign('test-only-secret', body)
        return await client.post(
            '/bots/http-test-bot/sync',
            data=body,
            headers={
                signing.HEADER_TIMESTAMP: timestamp,
                signing.HEADER_SIGNATURE: signature,
            },
        )

    source_app = web.Application()
    source_app.router.add_get('/input.bin', source_file)
    async with TestServer(source_app) as source_server:
        client = http.test_client()
        # HTTPBot intentionally limits inline request bodies to 1 MiB; use its URL contract.
        rejected = await signed_post(
            client, {'type': 'File', 'name': 'input.bin', 'base64': base64.b64encode(content).decode()}
        )
        assert rejected.status_code == 413
        assert not received and not downloads
        response = await asyncio.wait_for(
            signed_post(
                client,
                {
                    'type': 'File',
                    'name': 'input.bin',
                    'url': str(source_server.make_url('/input.bin')),
                },
            ),
            timeout=250,
        )
        if listener_errors:
            raise listener_errors[0]
        assert response.status_code == 200
        payload = (await response.get_json())['data']
        assert len(payload['message']) == 1
        delivered = payload['message'][0]
        assert delivered['type'] == 'File' and delivered['name'] == 'http-delivered.bin'
        actual = base64.b64decode(delivered['base64'].split(';base64,')[-1], validate=True)
        assert len(actual) == len(content)
        assert hashlib.sha256(actual).hexdigest() == expected_digest
        assert payload['reply_to'].startswith('in_')
        assert len(received) == 1 and downloads == ['/input.bin']
        adapter._enqueue_callback.assert_not_awaited()
        assert not adapter.sync_waiters
        await asyncio.gather(*adapter.inbound_tasks)
