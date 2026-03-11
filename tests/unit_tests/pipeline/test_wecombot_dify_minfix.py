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


def get_wecom_client():
    return import_module('langbot.libs.wecom_ai_bot_api.api').WecomBotClient


def make_async_logger():
    return SimpleNamespace(
        debug=AsyncMock(),
        info=AsyncMock(),
        warning=AsyncMock(),
        error=AsyncMock(),
    )


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
async def test_dify_stream_respects_configured_pull_chunk_batch_size():
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
        yield {'event': 'message', 'answer': '好', 'conversation_id': 'conv-2'}
        yield {'event': 'message', 'answer': '呀', 'conversation_id': 'conv-2'}
        yield {'event': 'message_end', 'conversation_id': 'conv-2'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={'PullChunkBatchSize': 3}),
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid='conv-1'),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-1',
        ),
        variables={},
        user_message=provider_message.Message(role='user', content='hello'),
    )

    chunks = [chunk async for chunk in runner._chat_messages_chunk(query)]

    assert [chunk.content for chunk in chunks] == ['你', '你好呀', '你好呀']
    assert chunks[-1].is_final is True


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


def test_wecom_followup_uses_placeholder_before_first_chunk():
    WecomBotClient = get_wecom_client()
    client = WecomBotClient(
        Token='token',
        EnCodingAESKey='aes',
        Corpid='corp',
        logger=Mock(),
        pending_placeholder='思考中...',
    )

    _, StreamSessionManager = get_stream_types()
    session, _ = client.stream_sessions.create_or_get({'msgid': 'msg-2', 'from': {'userid': 'user-2'}})
    fallback_chunk = client._resolve_followup_chunk(session, None)

    assert fallback_chunk is not None
    assert fallback_chunk.content == '思考中...'
    assert fallback_chunk.is_final is False
    assert session.last_chunk is fallback_chunk


def test_wecom_followup_prefers_latest_snapshot_over_empty_response():
    WecomBotClient = get_wecom_client()
    StreamChunk, _ = get_stream_types()
    client = WecomBotClient(
        Token='token',
        EnCodingAESKey='aes',
        Corpid='corp',
        logger=Mock(),
    )

    session, _ = client.stream_sessions.create_or_get({'msgid': 'msg-3', 'from': {'userid': 'user-3'}})
    session.last_chunk = StreamChunk(content='最新快照', is_final=False)

    fallback_chunk = client._resolve_followup_chunk(session, None)

    assert fallback_chunk is session.last_chunk
    assert fallback_chunk.content == '最新快照'


@pytest.mark.asyncio
async def test_wecom_followup_forces_finish_after_stream_timeout():
    WecomBotClient = get_wecom_client()
    StreamChunk, _ = get_stream_types()
    client = WecomBotClient(
        Token='token',
        EnCodingAESKey='aes',
        Corpid='corp',
        logger=make_async_logger(),
        stream_max_lifetime=1,
    )

    session, _ = client.stream_sessions.create_or_get({'msgid': 'msg-4', 'from': {'userid': 'user-4'}})
    session.created_at -= 5
    session.last_chunk = StreamChunk(content='进行中的回答', is_final=False)

    client.stream_sessions.consume = AsyncMock(return_value=None)
    client._encrypt_and_reply = AsyncMock(side_effect=lambda payload, nonce: (payload, 200))

    await client._handle_post_followup_response({'stream': {'id': session.stream_id}}, 'nonce')

    payload = client._encrypt_and_reply.await_args.args[0]
    assert payload['stream']['content'] == '进行中的回答'
    assert payload['stream']['finish'] is True
    assert client.stream_sessions.get_session(session.stream_id).finished is True


@pytest.mark.asyncio
async def test_wecom_dispatch_exception_forces_finish():
    WecomBotClient = get_wecom_client()
    StreamChunk, _ = get_stream_types()
    client = WecomBotClient(
        Token='token',
        EnCodingAESKey='aes',
        Corpid='corp',
        logger=make_async_logger(),
    )

    session, _ = client.stream_sessions.create_or_get({'msgid': 'msg-5', 'from': {'userid': 'user-5'}})
    client._handle_message = AsyncMock(side_effect=RuntimeError('boom'))

    await client._dispatch_event({'msgid': 'msg-5', 'type': 'text', 'stream_id': session.stream_id})

    chunk = await client.stream_sessions.consume(session.stream_id, timeout=0.01)
    assert isinstance(chunk, StreamChunk)
    assert chunk.is_final is True
    assert chunk.content == client.stream_error_final_text
