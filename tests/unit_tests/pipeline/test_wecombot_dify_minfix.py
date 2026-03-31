from __future__ import annotations

import sys
import time
import types
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import yaml

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
    # Keep import order aligned with runtime startup to avoid partial runner module initialization.
    import_module('langbot.pkg.pipeline.pipelinemgr')
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


def make_valid_event_logger():
    from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger

    class _Logger(AbstractEventLogger):
        async def info(self, *args, **kwargs):
            return None

        async def debug(self, *args, **kwargs):
            return None

        async def warning(self, *args, **kwargs):
            return None

        async def error(self, *args, **kwargs):
            return None

    return _Logger()


def make_dify_pipeline_config(
    chunk_batch_size: int = 8,
    flush_window_enabled: bool = False,
    flush_window_ms: int = 2000,
) -> dict:
    return {
        'ai': {
            'dify-service-api': {
                'app-type': 'chat',
                'api-key': 'test-key',
                'base-url': 'https://example.com/v1',
                'base-prompt': '',
            }
        },
        'output': {
            'misc': {'remove-think': False},
            'dify-stream': {
                'chunk-batch-size': chunk_batch_size,
                'flush-window-enabled': flush_window_enabled,
                'flush-window-ms': flush_window_ms,
            },
        },
    }


def make_runtime_binding(uuid: str, created_at: int, last_active_at: int, policy_version: int = 2) -> dict:
    return {
        'uuid': uuid,
        'created_at': created_at,
        'last_active_at': last_active_at,
        'policy_version': policy_version,
    }


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
        make_dify_pipeline_config(),
    )

    async def fake_chat_messages(**kwargs):
        yield {'event': 'message', 'answer': '你', 'conversation_id': 'conv-2'}
        yield {'event': 'message_end', 'conversation_id': 'conv-2'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid='conv-1'),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-1',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
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
        make_dify_pipeline_config(chunk_batch_size=3),
    )

    async def fake_chat_messages(**kwargs):
        yield {'event': 'message', 'answer': '你', 'conversation_id': 'conv-2'}
        yield {'event': 'message', 'answer': '好', 'conversation_id': 'conv-2'}
        yield {'event': 'message', 'answer': '呀', 'conversation_id': 'conv-2'}
        yield {'event': 'message_end', 'conversation_id': 'conv-2'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid='conv-1'),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-1',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    chunks = [chunk async for chunk in runner._chat_messages_chunk(query)]

    assert [chunk.content for chunk in chunks] == ['你', '你好呀']
    assert chunks[-1].is_final is True


@pytest.mark.asyncio
async def test_dify_stream_flushes_on_time_window_before_batch_threshold(monkeypatch):
    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    DifyServiceAPIRunner = dify_module.DifyServiceAPIRunner
    app = Mock()
    app.logger = Mock()
    runner = DifyServiceAPIRunner(
        app,
        make_dify_pipeline_config(chunk_batch_size=8, flush_window_enabled=True, flush_window_ms=2000),
    )

    async def fake_chat_messages(**kwargs):
        yield {'event': 'message', 'answer': '你', 'conversation_id': 'conv-3'}
        yield {'event': 'message', 'answer': '好', 'conversation_id': 'conv-3'}
        yield {'event': 'message', 'answer': '呀', 'conversation_id': 'conv-3'}
        yield {'event': 'message_end', 'conversation_id': 'conv-3'}

    monotonic_values = iter([0.0, 0.1, 0.2, 2.6, 2.7, 2.8])

    def fake_monotonic():
        try:
            return next(monotonic_values)
        except StopIteration:
            return 3.0

    monkeypatch.setattr(dify_module.time, 'monotonic', fake_monotonic)

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid='conv-1'),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-1',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    chunks = [chunk async for chunk in runner._chat_messages_chunk(query)]

    assert [chunk.content for chunk in chunks] == ['你', '你好呀', '你好呀']
    assert [chunk.is_final for chunk in chunks] == [False, False, True]


@pytest.mark.asyncio
async def test_dify_chatflow_stream_ignores_empty_message_and_still_emits_final():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    runner = DifyServiceAPIRunner(
        app,
        make_dify_pipeline_config(),
    )

    async def fake_chat_messages(**kwargs):
        for answer in ['你', '好', '！', '有', '什', '么', '我', '可', '以', '帮', '助', '您']:
            yield {'event': 'message', 'answer': answer, 'conversation_id': 'conv-4'}
        yield {'event': 'message', 'answer': '', 'conversation_id': 'conv-4'}
        yield {'event': 'workflow_finished', 'conversation_id': 'conv-4', 'data': {'error': None}}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid='conv-1'),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-1',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    chunks = [chunk async for chunk in runner._chat_messages_chunk(query)]

    assert [chunk.content for chunk in chunks] == ['你', '你好！有什么我可以', '你好！有什么我可以帮助您']
    assert [chunk.is_final for chunk in chunks] == [False, False, True]


@pytest.mark.asyncio
async def test_stream_session_manager_keeps_latest_snapshot_only():
    StreamChunk, StreamSessionManager = get_stream_types()
    manager = StreamSessionManager(logger=make_async_logger())
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
        pending_placeholder_delay=0,
    )

    _, StreamSessionManager = get_stream_types()
    session, _ = client.stream_sessions.create_or_get({'msgid': 'msg-2', 'from': {'userid': 'user-2'}})
    fallback_chunk = client._resolve_followup_chunk(session, None)

    assert fallback_chunk is not None
    assert fallback_chunk.content == '思考中...'
    assert fallback_chunk.is_final is False
    assert session.last_chunk is fallback_chunk


def test_wecom_followup_delays_placeholder_before_window_expires():
    WecomBotClient = get_wecom_client()
    client = WecomBotClient(
        Token='token',
        EnCodingAESKey='aes',
        Corpid='corp',
        logger=Mock(),
        pending_placeholder='思考中...',
        pending_placeholder_delay=2,
    )

    session, _ = client.stream_sessions.create_or_get({'msgid': 'msg-delay', 'from': {'userid': 'user-delay'}})
    fallback_chunk = client._resolve_followup_chunk(session, None)

    assert fallback_chunk is None


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


def test_wecom_client_defaults_match_master_polling_behavior():
    WecomBotClient = get_wecom_client()
    client = WecomBotClient(
        Token='token',
        EnCodingAESKey='aes',
        Corpid='corp',
        logger=Mock(),
    )

    assert client.stream_poll_timeout == 0.5
    assert client.pending_placeholder == ''
    assert client.pending_placeholder_delay == 0.0


def test_dify_stream_uses_output_defaults_when_config_missing():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())
    query = SimpleNamespace(pipeline_config={'output': {'misc': {'remove-think': False}}})

    assert runner._get_stream_chunk_batch_size(query) == 8
    assert runner._is_stream_flush_window_enabled(query) is False
    assert runner._get_stream_flush_window_ms(query) == 2000


@pytest.mark.parametrize(
    ('enabled_value', 'expected'),
    [
        ('false', False),
        ('0', False),
        ('no', False),
        ('off', False),
        ('true', True),
        ('1', True),
        ('yes', True),
        ('on', True),
    ],
)
def test_dify_stream_flush_window_enabled_parses_common_boolean_strings(enabled_value, expected):
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())
    query = SimpleNamespace(
        pipeline_config={
            'output': {
                'dify-stream': {
                    'flush-window-enabled': enabled_value,
                }
            }
        }
    )

    assert runner._is_stream_flush_window_enabled(query) is expected




@pytest.mark.asyncio
async def test_dify_chat_stream_does_not_crash_when_output_misc_is_missing():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    pipeline_config = make_dify_pipeline_config()
    pipeline_config['output'] = {}
    runner = DifyServiceAPIRunner(app, pipeline_config)

    async def fake_chat_messages(**kwargs):
        yield {'event': 'message', 'answer': '你好', 'conversation_id': 'conv-misc-missing'}
        yield {'event': 'message_end', 'conversation_id': 'conv-misc-missing'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid='conv-1'),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-1',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    chunks = [chunk async for chunk in runner._chat_messages_chunk(query)]

    assert chunks
    assert chunks[-1].is_final is True


@pytest.mark.asyncio
async def test_dify_process_thinking_content_does_not_crash_when_output_misc_is_not_dict():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    pipeline_config = make_dify_pipeline_config()
    pipeline_config['output'] = {'misc': ''}
    runner = DifyServiceAPIRunner(app, pipeline_config)

    content, thinking = runner._process_thinking_content('<think>abc</think>hello')

    assert '<think>' in content
    assert thinking == 'abc'

def test_dify_conversation_store_lock_ttl_is_not_shorter_than_request_window():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'lock_ttl_seconds': 10}})
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    cfg = runner._resolve_conversation_store_config()

    assert cfg['lock_ttl_seconds'] >= 130
    assert cfg['contention_wait_retry_count'] >= 15
    assert cfg['contention_wait_interval_ms'] >= 500


def test_dify_conversation_store_config_prefers_idle_timeout_seconds_over_ttl_seconds():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(
        data={'dify_conversation_store': {'idle_timeout_seconds': 321, 'ttl_seconds': 999}}
    )
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    cfg = runner._resolve_conversation_store_config()

    assert cfg['idle_timeout_seconds'] == 321
    assert cfg['ttl_seconds'] == 321


@pytest.mark.parametrize('store_value', ['', [], 123, 0.1, True])
def test_dify_conversation_store_config_falls_back_to_defaults_when_store_config_is_not_dict(store_value):
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': store_value})
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    cfg = runner._resolve_conversation_store_config()

    assert cfg['enabled'] is True
    assert cfg['idle_timeout_seconds'] == 43200
    assert cfg['ttl_seconds'] == 43200
    assert cfg['lock_ttl_seconds'] == 130
    assert cfg['contention_wait_retry_count'] == 15
    assert cfg['contention_wait_interval_ms'] == 500


def test_dify_conversation_store_pipeline_idle_timeout_overrides_instance_default():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'idle_timeout_seconds': 111}})
    pipeline_config = make_dify_pipeline_config()
    pipeline_config['ai']['dify_conversation_store'] = {'idle_timeout_seconds': 222}
    runner = DifyServiceAPIRunner(app, pipeline_config)

    cfg = runner._resolve_conversation_store_config()

    assert cfg['idle_timeout_seconds'] == 222
    assert cfg['ttl_seconds'] == 222


def test_dify_conversation_store_pipeline_lock_ttl_overrides_instance_and_still_applies_floor():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'lock_ttl_seconds': 200}})
    pipeline_config = make_dify_pipeline_config()
    pipeline_config['ai']['dify_conversation_store'] = {'lock_ttl_seconds': 1}
    runner = DifyServiceAPIRunner(app, pipeline_config)

    cfg = runner._resolve_conversation_store_config()

    assert cfg['lock_ttl_seconds'] == 130


def test_dify_conversation_store_pipeline_idle_timeout_overrides_instance_legacy_ttl_seconds():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'ttl_seconds': 333}})
    pipeline_config = make_dify_pipeline_config()
    pipeline_config['ai']['dify_conversation_store'] = {'idle_timeout_seconds': 444}
    runner = DifyServiceAPIRunner(app, pipeline_config)

    cfg = runner._resolve_conversation_store_config()

    assert cfg['idle_timeout_seconds'] == 444
    assert cfg['ttl_seconds'] == 444


@pytest.mark.parametrize(
    ('enabled_value', 'expected'),
    [
        ('false', False),
        ('0', False),
        ('no', False),
        ('off', False),
        ('true', True),
        ('1', True),
        ('yes', True),
        ('on', True),
    ],
)
def test_dify_conversation_store_enabled_parses_common_boolean_strings(enabled_value, expected):
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'enabled': enabled_value}})
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    cfg = runner._resolve_conversation_store_config()

    assert cfg['enabled'] is expected


def test_dify_conversation_store_can_initialize_after_redis_manager_becomes_available():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.redis_mgr = None
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    assert runner._get_conversation_store() is None

    app.redis_mgr = Mock()
    store = runner._get_conversation_store()

    assert store is not None
    assert store.redis_mgr is app.redis_mgr
    assert runner._get_conversation_store() is store


def test_template_default_dify_idle_timeout_seconds_is_12_hours():
    config_path = Path(__file__).resolve().parents[3] / 'src' / 'langbot' / 'templates' / 'config.yaml'

    with config_path.open('r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    assert config['dify_conversation_store']['idle_timeout_seconds'] == 43200


def get_wecom_adapter():
    return import_module('langbot.pkg.platform.sources.wecombot').WecomBotAdapter


def test_wecombot_adapter_supports_websocket_mode_from_master():
    WecomBotAdapter = get_wecom_adapter()
    ws_module = import_module('langbot.libs.wecom_ai_bot_api.ws_client')

    adapter = WecomBotAdapter(
        {
            'BotId': 'bot-id',
            'enable-webhook': False,
            'Secret': 'secret',
        },
        make_valid_event_logger(),
    )

    assert adapter._ws_mode is True
    assert isinstance(adapter.bot, ws_module.WecomBotWsClient)
    assert adapter.config['enable-webhook'] is False


def test_wecombot_adapter_webhook_mode_normalizes_pull_config():
    WecomBotAdapter = get_wecom_adapter()

    adapter = WecomBotAdapter(
        {
            'BotId': 'bot-id',
            'enable-webhook': True,
            'Token': 'token',
            'EncodingAESKey': 'encoding-aes-key',
            'Corpid': 'corp-id',
        },
        make_valid_event_logger(),
    )

    assert adapter._ws_mode is False
    assert adapter.config['enable-webhook'] is True
    assert adapter.config['PullPollTimeoutMs'] == 500
    assert adapter.config['PullStreamMaxLifetimeMs'] == 300000
    assert adapter.config['PullPendingPlaceholderEnabled'] is False


@pytest.mark.asyncio
async def test_dify_chat_reuses_runtime_binding_when_not_expired_without_store_read(monkeypatch):
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'idle_timeout_seconds': 300}})
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    monkeypatch.setattr(dify_module.time, 'time', lambda: 1000)

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-1'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_binding=AsyncMock(return_value=make_runtime_binding('conv-from-store', 900, 995)),
        set_conversation_binding=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)

    observed_request = {}

    async def fake_chat_messages(**kwargs):
        observed_request.update(kwargs)
        yield {'event': 'message', 'answer': 'hello', 'conversation_id': 'conv-final'}
        yield {'event': 'message_end', 'conversation_id': 'conv-final'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-1',
        pipeline_uuid='pipe-1',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(
                uuid='conv-memory',
                dify_conversation_binding=make_runtime_binding('conv-memory', 900, 990),
            ),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-1',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    _ = [msg async for msg in runner._chat_messages(query)]

    assert observed_request['conversation_id'] == 'conv-memory'
    store.get_conversation_binding.assert_not_awaited()
    store.acquire_lock.assert_not_awaited()
    store.release_lock.assert_not_awaited()
    store.set_conversation_binding.assert_awaited_once_with(
        'bot-1',
        'pipe-1',
        'person',
        'user-1',
        'conv-final',
        now_ts=1000,
        created_at=1000,
    )
    assert query.session.using_conversation.uuid == 'conv-final'
    assert query.session.using_conversation.dify_conversation_binding == make_runtime_binding('conv-final', 1000, 1000)


@pytest.mark.asyncio
async def test_dify_chat_runtime_binding_expired_clears_and_restores_from_store(monkeypatch):
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'idle_timeout_seconds': 60}})
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    monkeypatch.setattr(dify_module.time, 'time', lambda: 1000)

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-1'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_binding=AsyncMock(return_value=make_runtime_binding('conv-restored', 900, 980)),
        set_conversation_binding=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)

    observed_request = {}

    async def fake_chat_messages(**kwargs):
        observed_request.update(kwargs)
        yield {'event': 'message', 'answer': 'hello', 'conversation_id': 'conv-final-2'}
        yield {'event': 'message_end', 'conversation_id': 'conv-final-2'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-2',
        pipeline_uuid='pipe-2',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(
                uuid='conv-expired',
                dify_conversation_binding=make_runtime_binding('conv-expired', 500, 900),
            ),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-2',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    _ = [msg async for msg in runner._chat_messages(query)]

    assert observed_request['conversation_id'] == 'conv-restored'
    store.get_conversation_binding.assert_awaited_once_with('bot-2', 'pipe-2', 'person', 'user-2')
    store.acquire_lock.assert_not_awaited()
    store.release_lock.assert_not_awaited()
    store.set_conversation_binding.assert_awaited_once_with(
        'bot-2',
        'pipe-2',
        'person',
        'user-2',
        'conv-final-2',
        now_ts=1000,
        created_at=1000,
    )
    assert query.session.using_conversation.uuid == 'conv-final-2'
    assert query.session.using_conversation.dify_conversation_binding == make_runtime_binding(
        'conv-final-2',
        1000,
        1000,
    )


@pytest.mark.asyncio
async def test_dify_chat_runtime_uuid_without_metadata_keeps_runtime_when_store_binding_differs(monkeypatch):
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'idle_timeout_seconds': 60}})
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    monkeypatch.setattr(dify_module.time, 'time', lambda: 1000)

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-3'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_binding=AsyncMock(return_value=make_runtime_binding('conv-restored-3', 900, 980)),
        set_conversation_binding=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)

    observed_request = {}

    async def fake_chat_messages(**kwargs):
        observed_request.update(kwargs)
        yield {'event': 'message', 'answer': 'hello', 'conversation_id': 'conv-memory-without-meta'}
        yield {'event': 'message_end', 'conversation_id': 'conv-memory-without-meta'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-3',
        pipeline_uuid='pipe-3',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid='conv-memory-without-meta'),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-3',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    _ = [msg async for msg in runner._chat_messages(query)]

    assert observed_request['conversation_id'] == 'conv-memory-without-meta'
    store.get_conversation_binding.assert_awaited_once_with('bot-3', 'pipe-3', 'person', 'user-3')
    store.acquire_lock.assert_not_awaited()


@pytest.mark.asyncio
async def test_dify_restore_from_store_binding_writes_runtime_metadata(monkeypatch):
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'idle_timeout_seconds': 60}})
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    monkeypatch.setattr(dify_module.time, 'time', lambda: 1000)

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-restore'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_binding=AsyncMock(return_value=make_runtime_binding('conv-restored-meta', 700, 980)),
    )
    runner._get_conversation_store = Mock(return_value=store)

    query = SimpleNamespace(
        bot_uuid='bot-restore',
        pipeline_uuid='pipe-restore',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid=''),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-restore',
        ),
    )

    conversation_id, lock_owner = await runner._restore_conversation_id_if_needed(query)

    assert lock_owner is None
    assert conversation_id == 'conv-restored-meta'
    assert query.session.using_conversation.uuid == 'conv-restored-meta'
    assert query.session.using_conversation.dify_conversation_binding == make_runtime_binding(
        'conv-restored-meta',
        700,
        980,
    )


@pytest.mark.asyncio
async def test_dify_restore_from_store_binding_ignores_expired_payload(monkeypatch):
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'idle_timeout_seconds': 60}})
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    monkeypatch.setattr(dify_module.time, 'time', lambda: 1000)

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-expired'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_binding=AsyncMock(
            side_effect=[
                make_runtime_binding('conv-expired-store', 100, 700),
                make_runtime_binding('conv-expired-store', 100, 700),
            ]
        ),
    )
    runner._get_conversation_store = Mock(return_value=store)

    query = SimpleNamespace(
        bot_uuid='bot-expired',
        pipeline_uuid='pipe-expired',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid=''),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-expired',
        ),
    )

    conversation_id, lock_owner = await runner._restore_conversation_id_if_needed(query)

    assert conversation_id is None
    assert lock_owner == 'owner-expired'
    assert query.session.using_conversation.uuid == ''


@pytest.mark.asyncio
async def test_dify_restore_uses_valid_runtime_binding_when_store_unavailable(monkeypatch):
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'idle_timeout_seconds': 300}})
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    monkeypatch.setattr(dify_module.time, 'time', lambda: 1000)

    runner._get_conversation_store = Mock(return_value=None)

    query = SimpleNamespace(
        bot_uuid='bot-runtime-none-store',
        pipeline_uuid='pipe-runtime-none-store',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(
                uuid='conv-runtime-valid',
                dify_conversation_binding=make_runtime_binding('conv-runtime-valid', 900, 990),
            ),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-runtime-none-store',
        ),
    )

    conversation_id, lock_owner = await runner._restore_conversation_id_if_needed(query)

    assert conversation_id == 'conv-runtime-valid'
    assert lock_owner is None
    assert query.session.using_conversation.uuid == 'conv-runtime-valid'
    assert query.session.using_conversation.dify_conversation_binding == make_runtime_binding(
        'conv-runtime-valid',
        900,
        990,
    )


@pytest.mark.asyncio
async def test_dify_restore_store_unavailable_keeps_runtime_uuid_without_metadata(monkeypatch):
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'idle_timeout_seconds': 60}})
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    monkeypatch.setattr(dify_module.time, 'time', lambda: 1000)

    runner._get_conversation_store = Mock(return_value=None)

    query = SimpleNamespace(
        bot_uuid='bot-runtime-without-meta-none-store',
        pipeline_uuid='pipe-runtime-without-meta-none-store',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid='conv-runtime-without-meta'),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-runtime-without-meta-none-store',
        ),
    )

    conversation_id, lock_owner = await runner._restore_conversation_id_if_needed(query)

    assert conversation_id == 'conv-runtime-without-meta'
    assert lock_owner is None
    assert query.session.using_conversation.uuid == 'conv-runtime-without-meta'
    assert getattr(query.session.using_conversation, 'dify_conversation_binding', None) is None


@pytest.mark.asyncio
async def test_dify_restore_store_unavailable_fail_closed_for_expired_runtime_binding(monkeypatch):
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'idle_timeout_seconds': 60}})
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    monkeypatch.setattr(dify_module.time, 'time', lambda: 1000)

    runner._get_conversation_store = Mock(return_value=None)

    query = SimpleNamespace(
        bot_uuid='bot-runtime-expired-none-store',
        pipeline_uuid='pipe-runtime-expired-none-store',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(
                uuid='conv-runtime-expired',
                dify_conversation_binding=make_runtime_binding('conv-runtime-expired', 100, 700),
            ),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-runtime-expired-none-store',
        ),
    )

    conversation_id, lock_owner = await runner._restore_conversation_id_if_needed(query)

    assert conversation_id is None
    assert lock_owner is None
    assert query.session.using_conversation.uuid is None
    assert getattr(query.session.using_conversation, 'dify_conversation_binding', None) is None


@pytest.mark.asyncio
async def test_dify_restore_malformed_store_binding_keeps_runtime_uuid_without_metadata(monkeypatch):
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'idle_timeout_seconds': 60}})
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    monkeypatch.setattr(dify_module.time, 'time', lambda: 1000)

    malformed_payload = {
        'uuid': 'conv-malformed',
        'created_at': 'oops',
        'last_active_at': 900,
        'policy_version': 2,
    }
    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-malformed'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_binding=AsyncMock(side_effect=[malformed_payload, malformed_payload]),
    )
    runner._get_conversation_store = Mock(return_value=store)

    query = SimpleNamespace(
        bot_uuid='bot-malformed',
        pipeline_uuid='pipe-malformed',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid='conv-orphan-runtime'),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-malformed',
        ),
    )

    conversation_id, lock_owner = await runner._restore_conversation_id_if_needed(query)

    assert conversation_id == 'conv-orphan-runtime'
    assert lock_owner is None
    assert query.session.using_conversation.uuid == 'conv-orphan-runtime'
    assert getattr(query.session.using_conversation, 'dify_conversation_binding', None) is None
    assert store.get_conversation_binding.await_count == 1
    store.acquire_lock.assert_not_awaited()


@pytest.mark.asyncio
async def test_dify_restore_id_only_store_fallback_marks_binding_as_policy_v1(monkeypatch):
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(data={'dify_conversation_store': {'idle_timeout_seconds': 60}})
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    monkeypatch.setattr(dify_module.time, 'time', lambda: 1000)

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-legacy'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(return_value='conv-legacy-only-id'),
    )
    runner._get_conversation_store = Mock(return_value=store)

    query = SimpleNamespace(
        bot_uuid='bot-legacy',
        pipeline_uuid='pipe-legacy',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid=''),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-legacy',
        ),
    )

    conversation_id, lock_owner = await runner._restore_conversation_id_if_needed(query)

    assert conversation_id == 'conv-legacy-only-id'
    assert lock_owner is None
    assert query.session.using_conversation.uuid == 'conv-legacy-only-id'
    assert query.session.using_conversation.dify_conversation_binding == {
        'uuid': 'conv-legacy-only-id',
        'created_at': 1000,
        'last_active_at': 1000,
        'policy_version': 1,
    }


@pytest.mark.asyncio
async def test_dify_chat_restore_miss_triggers_lock_and_second_recheck():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-1'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(side_effect=[None, 'conv-rechecked']),
        set_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)

    observed_request = {}

    async def fake_chat_messages(**kwargs):
        observed_request.update(kwargs)
        observed_request.update(kwargs)
        yield {'event': 'message', 'answer': 'hello', 'conversation_id': 'conv-after-recheck'}
        yield {'event': 'message_end', 'conversation_id': 'conv-after-recheck'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-3a',
        pipeline_uuid='pipe-3a',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid=''),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-3a',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    _ = [msg async for msg in runner._chat_messages(query)]

    assert observed_request['conversation_id'] == 'conv-rechecked'
    assert store.get_conversation_id.await_count == 2
    store.acquire_lock.assert_awaited_once_with('bot-3a', 'pipe-3a', 'person', 'user-3a')
    store.release_lock.assert_awaited_once_with('bot-3a', 'pipe-3a', 'person', 'user-3a', 'owner-1')


@pytest.mark.asyncio
async def test_dify_chat_cold_miss_holds_same_lock_owner_until_writeback_and_release():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    events = []

    async def acquire_lock(*args):
        events.append('acquire')
        return 'owner-cold'

    async def set_conversation_id(*args):
        events.append('set')

    async def release_lock(*args):
        events.append(f'release:{args[-1]}')
        return True

    store = SimpleNamespace(
        acquire_lock=AsyncMock(side_effect=acquire_lock),
        release_lock=AsyncMock(side_effect=release_lock),
        get_conversation_id=AsyncMock(side_effect=[None, None]),
        set_conversation_id=AsyncMock(side_effect=set_conversation_id),
    )
    runner._get_conversation_store = Mock(return_value=store)

    observed_request = {}

    async def fake_chat_messages(**kwargs):
        observed_request.update(kwargs)
        events.append('request')
        yield {'event': 'message', 'answer': 'hello', 'conversation_id': 'conv-cold-final'}
        yield {'event': 'message_end', 'conversation_id': 'conv-cold-final'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-4a',
        pipeline_uuid='pipe-4a',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid=''),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-4a',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    _ = [msg async for msg in runner._chat_messages(query)]

    assert observed_request['conversation_id'] is None
    assert query.session.using_conversation.uuid == 'conv-cold-final'
    assert events == ['acquire', 'request', 'set', 'release:owner-cold']


@pytest.mark.asyncio
async def test_dify_chat_lock_failures_do_not_break_request_path():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    acquire_fail_store = SimpleNamespace(
        acquire_lock=AsyncMock(side_effect=RuntimeError('lock acquire failed')),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(return_value=None),
        set_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=acquire_fail_store)

    async def fake_chat_messages_case1(**kwargs):
        yield {'event': 'message', 'answer': 'ok', 'conversation_id': 'conv-acquire-failed'}
        yield {'event': 'message_end', 'conversation_id': 'conv-acquire-failed'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages_case1, base_url='https://example.com/v1')

    query_case1 = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-4b',
        pipeline_uuid='pipe-4b',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid=''),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-4b',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    msgs_case1 = [msg async for msg in runner._chat_messages(query_case1)]
    assert len(msgs_case1) == 1
    assert query_case1.session.using_conversation.uuid == 'conv-acquire-failed'

    release_fail_store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-release-fail'),
        release_lock=AsyncMock(side_effect=RuntimeError('lock release failed')),
        get_conversation_id=AsyncMock(side_effect=[None, None]),
        set_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=release_fail_store)

    async def fake_chat_messages_case2(**kwargs):
        yield {'event': 'message', 'answer': 'ok', 'conversation_id': 'conv-release-failed'}
        yield {'event': 'message_end', 'conversation_id': 'conv-release-failed'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages_case2, base_url='https://example.com/v1')

    query_case2 = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-4c',
        pipeline_uuid='pipe-4c',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid=''),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-4c',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    msgs_case2 = [msg async for msg in runner._chat_messages(query_case2)]
    assert len(msgs_case2) == 1
    assert query_case2.session.using_conversation.uuid == 'conv-release-failed'
    release_fail_store.release_lock.assert_awaited_once_with(
        'bot-4c',
        'pipe-4c',
        'person',
        'user-4c',
        'owner-release-fail',
    )


@pytest.mark.asyncio
async def test_dify_chat_store_write_failure_does_not_break_request():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-1'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(return_value='conv-restored-4'),
        set_conversation_id=AsyncMock(side_effect=RuntimeError('write failed')),
    )
    runner._get_conversation_store = Mock(return_value=store)

    async def fake_chat_messages(**kwargs):
        yield {'event': 'message', 'answer': 'hello', 'conversation_id': 'conv-after-write-fail'}
        yield {'event': 'message_end', 'conversation_id': 'conv-after-write-fail'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-4',
        pipeline_uuid='pipe-4',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid=''),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-4',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    messages = [msg async for msg in runner._chat_messages(query)]

    assert len(messages) == 1
    assert query.session.using_conversation.uuid == 'conv-after-write-fail'


@pytest.mark.asyncio
async def test_dify_chat_lock_contention_uses_bounded_wait_and_recheck(monkeypatch):
    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    DifyServiceAPIRunner = dify_module.DifyServiceAPIRunner
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(
        data={
            'dify_conversation_store': {
                'contention_wait_retry_count': 4,
                'contention_wait_interval_ms': 50,
            }
        }
    )
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(dify_module.asyncio, 'sleep', fake_sleep)

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value=None),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(side_effect=[None, None, None, 'conv-after-wait']),
        set_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)

    observed_request = {}

    async def fake_chat_messages(**kwargs):
        observed_request.update(kwargs)
        yield {'event': 'message', 'answer': 'ok', 'conversation_id': 'conv-final-contention'}
        yield {'event': 'message_end', 'conversation_id': 'conv-final-contention'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-contention',
        pipeline_uuid='pipe-contention',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid=''),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-contention',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    _ = [msg async for msg in runner._chat_messages(query)]

    assert observed_request['conversation_id'] == 'conv-after-wait'
    store.acquire_lock.assert_awaited_once_with('bot-contention', 'pipe-contention', 'person', 'user-contention')
    assert store.get_conversation_id.await_count == 4
    assert sleep_calls == [0.05, 0.05, 0.05]


@pytest.mark.asyncio
async def test_dify_chat_lock_contention_unresolved_gracefully_degrades_to_new_conversation(monkeypatch):
    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    DifyServiceAPIRunner = dify_module.DifyServiceAPIRunner
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(
        data={
            'dify_conversation_store': {
                'contention_wait_retry_count': 2,
                'contention_wait_interval_ms': 50,
            }
        }
    )
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(dify_module.asyncio, 'sleep', fake_sleep)

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value=None),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(side_effect=[None, None, None]),
        set_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)

    observed_request = {}

    async def fake_chat_messages(**kwargs):
        observed_request.update(kwargs)
        yield {'event': 'message', 'answer': 'ok', 'conversation_id': 'conv-after-contention-fallback'}
        yield {'event': 'message_end', 'conversation_id': 'conv-after-contention-fallback'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-contention-fail',
        pipeline_uuid='pipe-contention-fail',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid=''),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-contention-fail',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    msgs = [msg async for msg in runner._chat_messages(query)]

    assert len(msgs) == 1
    assert observed_request['conversation_id'] is None
    assert query.session.using_conversation.uuid == 'conv-after-contention-fallback'


@pytest.mark.asyncio
async def test_dify_agent_restore_and_persist_conversation_id():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    config = make_dify_pipeline_config()
    config['ai']['dify-service-api']['app-type'] = 'agent'
    runner = DifyServiceAPIRunner(app, config)

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-agent'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(return_value='conv-agent-restored'),
        set_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)

    observed_request = {}

    async def fake_agent_chat_messages(**kwargs):
        observed_request.update(kwargs)
        yield {'event': 'agent_message', 'answer': 'hi', 'conversation_id': 'conv-agent-final'}
        yield {'event': 'message_end', 'conversation_id': 'conv-agent-final'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_agent_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-agent',
        pipeline_uuid='pipe-agent',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid=''),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-agent',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    msgs = [msg async for msg in runner._agent_chat_messages(query)]

    assert len(msgs) == 1
    assert observed_request['conversation_id'] == 'conv-agent-restored'
    store.set_conversation_id.assert_awaited_once_with(
        'bot-agent',
        'pipe-agent',
        'person',
        'user-agent',
        'conv-agent-final',
    )


@pytest.mark.asyncio
async def test_dify_chat_stream_chunk_restore_and_persist_conversation_id():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-stream'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(return_value='conv-stream-restored'),
        set_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)

    observed_request = {}

    async def fake_chat_messages(**kwargs):
        observed_request.update(kwargs)
        yield {'event': 'message', 'answer': '你', 'conversation_id': 'conv-stream-final'}
        yield {'event': 'message_end', 'conversation_id': 'conv-stream-final'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-stream',
        pipeline_uuid='pipe-stream',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid=''),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-stream',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    chunks = [chunk async for chunk in runner._chat_messages_chunk(query)]

    assert chunks[-1].is_final is True
    assert observed_request['conversation_id'] == 'conv-stream-restored'
    store.set_conversation_id.assert_awaited_once_with(
        'bot-stream',
        'pipe-stream',
        'person',
        'user-stream',
        'conv-stream-final',
    )


@pytest.mark.asyncio
async def test_dify_chat_invalid_conversation_retries_once_with_restored_binding_from_contention_wait(monkeypatch):
    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    DifyServiceAPIRunner = dify_module.DifyServiceAPIRunner
    dify_errors = import_module('langbot.libs.dify_service_api.v1.errors')
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(
        data={
            'dify_conversation_store': {
                'contention_wait_retry_count': 3,
                'contention_wait_interval_ms': 50,
            }
        }
    )
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(dify_module.asyncio, 'sleep', fake_sleep)

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value=None),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(side_effect=[None, None, 'conv-recovered-after-invalid']),
        set_conversation_id=AsyncMock(),
        delete_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)
    now_ts = int(time.time())

    request_args = []

    async def fake_chat_messages(**kwargs):
        request_args.append(kwargs)
        if len(request_args) == 1:
            raise dify_errors.DifyAPIError('400 {"code":"conversation_not_found","message":"Conversation not found"}')
        yield {'event': 'message', 'answer': 'retry-ok', 'conversation_id': 'conv-after-retry'}
        yield {'event': 'message_end', 'conversation_id': 'conv-after-retry'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-invalid-retry',
        pipeline_uuid='pipe-invalid-retry',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(
                uuid='conv-stale',
                dify_conversation_binding=make_runtime_binding('conv-stale', now_ts - 10, now_ts - 5),
            ),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-invalid-retry',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    messages = [msg async for msg in runner._chat_messages(query)]

    assert len(messages) == 1
    assert messages[0].content == 'retry-ok'
    assert len(request_args) == 2
    assert request_args[0]['conversation_id'] == 'conv-stale'
    assert request_args[1]['conversation_id'] == 'conv-recovered-after-invalid'
    assert request_args[1]['inputs']['conversation_id'] == 'conv-recovered-after-invalid'
    store.acquire_lock.assert_awaited_once_with('bot-invalid-retry', 'pipe-invalid-retry', 'person', 'user-invalid-retry')
    store.delete_conversation_id.assert_awaited_once_with(
        'bot-invalid-retry',
        'pipe-invalid-retry',
        'person',
        'user-invalid-retry',
    )
    store.set_conversation_id.assert_awaited_once_with(
        'bot-invalid-retry',
        'pipe-invalid-retry',
        'person',
        'user-invalid-retry',
        'conv-after-retry',
    )


@pytest.mark.asyncio
async def test_dify_chat_invalid_conversation_retry_reacquires_lock_before_empty_retry():
    DifyServiceAPIRunner = get_dify_runner()
    dify_errors = import_module('langbot.libs.dify_service_api.v1.errors')
    app = Mock()
    app.logger = Mock()
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-invalid-retry-lock-holder'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(side_effect=[None, None]),
        set_conversation_id=AsyncMock(),
        delete_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)
    now_ts = int(time.time())

    request_args = []

    async def fake_chat_messages(**kwargs):
        request_args.append(kwargs)
        if len(request_args) == 1:
            raise dify_errors.DifyAPIError('400 {"code":"conversation_not_found","message":"Conversation not found"}')
        yield {'event': 'message', 'answer': 'retry-ok-lock-holder', 'conversation_id': 'conv-after-lock-holder-retry'}
        yield {'event': 'message_end', 'conversation_id': 'conv-after-lock-holder-retry'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-invalid-retry-lock-holder',
        pipeline_uuid='pipe-invalid-retry-lock-holder',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(
                uuid='conv-stale-lock-holder',
                dify_conversation_binding=make_runtime_binding('conv-stale-lock-holder', now_ts - 10, now_ts - 5),
            ),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-invalid-retry-lock-holder',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    messages = [msg async for msg in runner._chat_messages(query)]

    assert len(messages) == 1
    assert messages[0].content == 'retry-ok-lock-holder'
    assert len(request_args) == 2
    assert request_args[0]['conversation_id'] == 'conv-stale-lock-holder'
    assert request_args[1]['conversation_id'] == ''
    assert request_args[1]['inputs']['conversation_id'] == ''
    store.acquire_lock.assert_awaited_once_with(
        'bot-invalid-retry-lock-holder',
        'pipe-invalid-retry-lock-holder',
        'person',
        'user-invalid-retry-lock-holder',
    )
    store.release_lock.assert_awaited_once_with(
        'bot-invalid-retry-lock-holder',
        'pipe-invalid-retry-lock-holder',
        'person',
        'user-invalid-retry-lock-holder',
        'owner-invalid-retry-lock-holder',
    )


@pytest.mark.asyncio
async def test_dify_chat_invalid_conversation_second_failure_raises_after_single_retry():
    DifyServiceAPIRunner = get_dify_runner()
    dify_errors = import_module('langbot.libs.dify_service_api.v1.errors')
    app = Mock()
    app.logger = Mock()
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-invalid-double-fail'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(side_effect=[None, None]),
        set_conversation_id=AsyncMock(),
        delete_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)
    now_ts = int(time.time())

    request_args = []

    async def fake_chat_messages(**kwargs):
        request_args.append(kwargs)
        raise dify_errors.DifyAPIError('400 {"code":"conversation_not_found","message":"Conversation not found"}')
        yield  # pragma: no cover

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-invalid-double-fail',
        pipeline_uuid='pipe-invalid-double-fail',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(
                uuid='conv-stale-double-fail',
                dify_conversation_binding=make_runtime_binding(
                    'conv-stale-double-fail',
                    now_ts - 10,
                    now_ts - 5,
                ),
            ),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-invalid-double-fail',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    with pytest.raises(dify_errors.DifyAPIError):
        _ = [msg async for msg in runner._chat_messages(query)]

    assert len(request_args) == 2
    assert request_args[0]['conversation_id'] == 'conv-stale-double-fail'
    assert request_args[1]['conversation_id'] == ''
    assert request_args[1]['inputs']['conversation_id'] == ''
    store.acquire_lock.assert_awaited_once_with(
        'bot-invalid-double-fail',
        'pipe-invalid-double-fail',
        'person',
        'user-invalid-double-fail',
    )
    store.release_lock.assert_awaited_once_with(
        'bot-invalid-double-fail',
        'pipe-invalid-double-fail',
        'person',
        'user-invalid-double-fail',
        'owner-invalid-double-fail',
    )
    store.acquire_lock.assert_awaited_once_with(
        'bot-invalid-double-fail',
        'pipe-invalid-double-fail',
        'person',
        'user-invalid-double-fail',
    )
    store.delete_conversation_id.assert_awaited_once()
    store.set_conversation_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_dify_chat_non_invalid_conversation_error_does_not_retry():
    DifyServiceAPIRunner = get_dify_runner()
    dify_errors = import_module('langbot.libs.dify_service_api.v1.errors')
    app = Mock()
    app.logger = Mock()
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-non-invalid'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(return_value=None),
        set_conversation_id=AsyncMock(),
        delete_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)
    now_ts = int(time.time())

    request_args = []

    async def fake_chat_messages(**kwargs):
        request_args.append(kwargs)
        raise dify_errors.DifyAPIError('500 internal server error')
        yield  # pragma: no cover

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-non-invalid',
        pipeline_uuid='pipe-non-invalid',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(
                uuid='conv-non-invalid',
                dify_conversation_binding=make_runtime_binding('conv-non-invalid', now_ts - 10, now_ts - 5),
            ),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-non-invalid',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    with pytest.raises(dify_errors.DifyAPIError):
        _ = [msg async for msg in runner._chat_messages(query)]

    assert len(request_args) == 1
    assert request_args[0]['conversation_id'] == 'conv-non-invalid'
    store.delete_conversation_id.assert_not_awaited()
    assert query.session.using_conversation.uuid == 'conv-non-invalid'


@pytest.mark.asyncio
async def test_dify_chat_stream_invalid_conversation_retries_once_with_restored_binding_from_contention_wait(
    monkeypatch,
):
    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    DifyServiceAPIRunner = dify_module.DifyServiceAPIRunner
    dify_errors = import_module('langbot.libs.dify_service_api.v1.errors')
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(
        data={
            'dify_conversation_store': {
                'contention_wait_retry_count': 3,
                'contention_wait_interval_ms': 50,
            }
        }
    )
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(dify_module.asyncio, 'sleep', fake_sleep)

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value=None),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(side_effect=[None, None, 'conv-stream-recovered-after-invalid']),
        set_conversation_id=AsyncMock(),
        delete_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)
    now_ts = int(time.time())

    request_args = []

    async def fake_chat_messages(**kwargs):
        request_args.append(kwargs)
        if len(request_args) == 1:
            raise dify_errors.DifyAPIError('400 {"code":"invalid_conversation","message":"invalid conversation"}')
        yield {'event': 'message', 'answer': '你', 'conversation_id': 'conv-stream-after-retry'}
        yield {'event': 'message_end', 'conversation_id': 'conv-stream-after-retry'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-stream-invalid-retry',
        pipeline_uuid='pipe-stream-invalid-retry',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(
                uuid='conv-stream-stale',
                dify_conversation_binding=make_runtime_binding('conv-stream-stale', now_ts - 10, now_ts - 5),
            ),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-stream-invalid-retry',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    chunks = [chunk async for chunk in runner._chat_messages_chunk(query)]

    assert len(chunks) >= 1
    assert chunks[-1].is_final is True
    assert len(request_args) == 2
    assert request_args[0]['conversation_id'] == 'conv-stream-stale'
    assert request_args[1]['conversation_id'] == 'conv-stream-recovered-after-invalid'
    assert request_args[1]['inputs']['conversation_id'] == 'conv-stream-recovered-after-invalid'
    store.acquire_lock.assert_awaited_once_with(
        'bot-stream-invalid-retry',
        'pipe-stream-invalid-retry',
        'person',
        'user-stream-invalid-retry',
    )
    store.acquire_lock.assert_awaited_once_with(
        'bot-stream-invalid-retry',
        'pipe-stream-invalid-retry',
        'person',
        'user-stream-invalid-retry',
    )
    store.delete_conversation_id.assert_awaited_once()


@pytest.mark.asyncio
async def test_dify_chat_invalid_conversation_waits_for_recovered_binding_before_retry(monkeypatch):
    DifyServiceAPIRunner = get_dify_runner()
    dify_errors = import_module('langbot.libs.dify_service_api.v1.errors')
    dify_module = import_module('langbot.pkg.provider.runners.difysvapi')
    app = Mock()
    app.logger = Mock()
    app.instance_config = SimpleNamespace(
        data={'dify_conversation_store': {'contention_wait_retry_count': 2, 'contention_wait_interval_ms': 50}}
    )
    runner = DifyServiceAPIRunner(app, make_dify_pipeline_config())

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(dify_module.asyncio, 'sleep', fake_sleep)
    now_ts = int(time.time())

    recovered_binding = {
        'conversation_id': 'conv-recovered-after-invalid',
        'created_at': now_ts,
        'last_active_at': now_ts,
        'policy_version': 2,
    }
    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value=None),
        release_lock=AsyncMock(return_value=True),
        get_conversation_binding=AsyncMock(side_effect=[None, None, recovered_binding]),
        set_conversation_binding=AsyncMock(),
        delete_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)

    request_args = []

    async def fake_chat_messages(**kwargs):
        request_args.append(kwargs)
        if len(request_args) == 1:
            raise dify_errors.DifyAPIError('400 {"code":"conversation_not_found","message":"Conversation not found"}')
        yield {'event': 'message', 'answer': 'retry-with-restored-binding', 'conversation_id': 'conv-recovered-after-invalid'}
        yield {'event': 'message_end', 'conversation_id': 'conv-recovered-after-invalid'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-invalid-contention',
        pipeline_uuid='pipe-invalid-contention',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(
                uuid='conv-stale-contention',
                dify_conversation_binding=make_runtime_binding('conv-stale-contention', now_ts - 10, now_ts - 5),
            ),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-invalid-contention',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    messages = [msg async for msg in runner._chat_messages(query)]

    assert len(messages) == 1
    assert request_args[0]['conversation_id'] == 'conv-stale-contention'
    assert request_args[1]['conversation_id'] == 'conv-recovered-after-invalid'
    assert request_args[1]['inputs']['conversation_id'] == 'conv-recovered-after-invalid'
    store.delete_conversation_id.assert_awaited_once_with(
        'bot-invalid-contention',
        'pipe-invalid-contention',
        'person',
        'user-invalid-contention',
    )
    store.acquire_lock.assert_awaited_once_with(
        'bot-invalid-contention',
        'pipe-invalid-contention',
        'person',
        'user-invalid-contention',
    )
    assert store.get_conversation_binding.await_count == 3


@pytest.mark.asyncio
async def test_dify_agent_invalid_conversation_retries_once_with_empty_conversation_id():
    DifyServiceAPIRunner = get_dify_runner()
    dify_errors = import_module('langbot.libs.dify_service_api.v1.errors')
    app = Mock()
    app.logger = Mock()
    config = make_dify_pipeline_config()
    config['ai']['dify-service-api']['app-type'] = 'agent'
    runner = DifyServiceAPIRunner(app, config)

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-agent-invalid-retry'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(side_effect=[None, None]),
        set_conversation_id=AsyncMock(),
        delete_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)
    now_ts = int(time.time())

    request_args = []

    async def fake_agent_chat_messages(**kwargs):
        request_args.append(kwargs)
        if len(request_args) == 1:
            raise dify_errors.DifyAPIError('400 {"code":"invalid_conversation","message":"invalid conversation"}')
        yield {'event': 'agent_message', 'answer': 'agent-retry-ok', 'conversation_id': 'conv-agent-after-retry'}
        yield {'event': 'message_end', 'conversation_id': 'conv-agent-after-retry'}

    runner.dify_client = SimpleNamespace(chat_messages=fake_agent_chat_messages, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-agent-invalid-retry',
        pipeline_uuid='pipe-agent-invalid-retry',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(
                uuid='conv-agent-stale',
                dify_conversation_binding=make_runtime_binding('conv-agent-stale', now_ts - 10, now_ts - 5),
            ),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-agent-invalid-retry',
        ),
        variables={},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    messages = [msg async for msg in runner._agent_chat_messages(query)]

    assert len(messages) == 1
    assert messages[0].content == 'agent-retry-ok'
    assert len(request_args) == 2
    assert request_args[0]['conversation_id'] == 'conv-agent-stale'
    assert request_args[1]['conversation_id'] == ''
    assert request_args[1]['inputs']['conversation_id'] == ''
    store.acquire_lock.assert_awaited_once_with(
        'bot-agent-invalid-retry',
        'pipe-agent-invalid-retry',
        'person',
        'user-agent-invalid-retry',
    )
    store.release_lock.assert_awaited_once_with(
        'bot-agent-invalid-retry',
        'pipe-agent-invalid-retry',
        'person',
        'user-agent-invalid-retry',
        'owner-agent-invalid-retry',
    )
    store.delete_conversation_id.assert_awaited_once_with(
        'bot-agent-invalid-retry',
        'pipe-agent-invalid-retry',
        'person',
        'user-agent-invalid-retry',
    )
    store.acquire_lock.assert_awaited_once_with(
        'bot-agent-invalid-retry',
        'pipe-agent-invalid-retry',
        'person',
        'user-agent-invalid-retry',
    )
    store.set_conversation_id.assert_awaited_once_with(
        'bot-agent-invalid-retry',
        'pipe-agent-invalid-retry',
        'person',
        'user-agent-invalid-retry',
        'conv-agent-after-retry',
    )


@pytest.mark.asyncio
async def test_dify_workflow_uses_restored_conversation_and_persists_on_finish():
    DifyServiceAPIRunner = get_dify_runner()
    app = Mock()
    app.logger = Mock()
    config = make_dify_pipeline_config()
    config['ai']['dify-service-api']['app-type'] = 'workflow'
    runner = DifyServiceAPIRunner(app, config)

    store = SimpleNamespace(
        acquire_lock=AsyncMock(return_value='owner-1'),
        release_lock=AsyncMock(return_value=True),
        get_conversation_id=AsyncMock(return_value='conv-workflow-restored'),
        set_conversation_id=AsyncMock(),
    )
    runner._get_conversation_store = Mock(return_value=store)

    observed_request = {}

    async def fake_workflow_run(**kwargs):
        observed_request.update(kwargs)
        yield {'event': 'workflow_started'}
        yield {'event': 'workflow_finished', 'data': {'error': None, 'outputs': {'summary': 'done'}}}

    runner.dify_client = SimpleNamespace(workflow_run=fake_workflow_run, base_url='https://example.com/v1')

    query = SimpleNamespace(
        adapter=SimpleNamespace(config={}),
        bot_uuid='bot-5',
        pipeline_uuid='pipe-5',
        session=SimpleNamespace(
            using_conversation=SimpleNamespace(uuid=''),
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='user-5',
        ),
        variables={'session_id': 'sess-1', 'msg_create_time': 1},
        pipeline_config=runner.pipeline_config,
        user_message=provider_message.Message(role='user', content='hello'),
    )

    messages = [msg async for msg in runner._workflow_messages(query)]

    assert len(messages) == 1
    assert observed_request['inputs']['conversation_id'] == 'conv-workflow-restored'
    store.set_conversation_id.assert_awaited_with('bot-5', 'pipe-5', 'person', 'user-5', 'conv-workflow-restored')
