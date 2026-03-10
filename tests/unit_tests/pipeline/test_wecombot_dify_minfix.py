from __future__ import annotations

import sys
import types
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session

# Avoid importing the full application graph during isolated unit tests.
logger_stub = types.ModuleType('langbot.pkg.platform.logger')
logger_stub.EventLogger = object
sys.modules.setdefault('langbot.pkg.platform.logger', logger_stub)


def get_respback_stage():
    import_module('langbot.pkg.pipeline.pipelinemgr')
    return import_module('langbot.pkg.pipeline.respback.respback').SendResponseBackStage


def get_wecom_converter():
    return import_module('langbot.pkg.platform.sources.wecombot').WecomBotMessageConverter


def get_dify_runner():
    return import_module('langbot.pkg.provider.runners.difysvapi').DifyServiceAPIRunner


def get_stream_types():
    api_module = import_module('langbot.libs.wecom_ai_bot_api.api')
    return api_module.StreamChunk, api_module.StreamSessionManager


@pytest.mark.asyncio
async def test_respback_uses_latest_chunk_final_flag(mock_app, sample_query):
    SendResponseBackStage = get_respback_stage()
    stage = SendResponseBackStage(mock_app)
    sample_query.pipeline_config['output']['force-delay'] = {'min': 0, 'max': 0}
    sample_query.adapter.is_stream_output_supported = AsyncMock(return_value=True)
    sample_query.resp_messages = [
        provider_message.MessageChunk(role='assistant', content='he', is_final=False),
        provider_message.MessageChunk(role='assistant', content='hello', is_final=True),
    ]
    sample_query.resp_message_chain = [platform_message.MessageChain([platform_message.Plain(text='hello')])]

    result = await stage.process(sample_query, 'SendResponseBackStage')

    assert result.new_query is sample_query
    sample_query.adapter.reply_message_chunk.assert_awaited_once()
    assert sample_query.adapter.reply_message_chunk.await_args.kwargs['is_final'] is True


@pytest.mark.asyncio
async def test_wecombot_converter_keeps_quote_and_non_plain_components():
    WecomBotMessageConverter = get_wecom_converter()
    message_chain = platform_message.MessageChain(
        [
            platform_message.Quote(
                id='origin-1',
                origin=platform_message.MessageChain([platform_message.Plain(text='引用内容')]),
            ),
            platform_message.Image(url='https://example.com/a.png'),
            platform_message.Plain(text='直接回复'),
        ]
    )

    content = await WecomBotMessageConverter.yiri2target(message_chain)

    assert '引用内容' in content
    assert '[Image]' in content
    assert content.endswith('直接回复')


@pytest.mark.asyncio
async def test_dify_stream_emits_first_chunk_immediately():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    runner = DifyServiceAPIRunner(
        app,
        {
            'ai': {
                'dify-service-api': {
                    'app-type': 'chat',
                    'api-key': 'test-key',
                    'base-url': 'https://example.com/v1',
                    'base-prompt': '',
                }
            },
            'output': {'misc': {'remove-think': False}},
        },
    )

    async def fake_chat_messages(**kwargs):
        yield {'event': 'message', 'answer': '你', 'conversation_id': 'conv-2'}
        yield {'event': 'message_end', 'conversation_id': 'conv-2'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid='conv-1'),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-1',
        ),
        variables={},
        user_message=provider_message.Message(role='user', content='hello'),
    )

    chunks = [chunk async for chunk in runner._chat_messages_chunk(query)]

    assert chunks[0].content == '你'
    assert chunks[-1].is_final is True
    assert query.session.using_conversation.uuid == 'conv-2'


@pytest.mark.asyncio
async def test_stream_session_manager_keeps_latest_snapshot_only():
    StreamChunk, StreamSessionManager = get_stream_types()
    manager = StreamSessionManager(logger=Mock())
    session, _ = manager.create_or_get({'msgid': 'msg-1', 'from': {'userid': 'user-1'}})

    await manager.publish(session.stream_id, StreamChunk(content='a', is_final=False))
    await manager.publish(session.stream_id, StreamChunk(content='abc', is_final=True))

    chunk = await manager.consume(session.stream_id, timeout=0.01)

    assert chunk is not None
    assert chunk.content == 'abc'
    assert chunk.is_final is True
