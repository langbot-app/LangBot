"""Replies of simultaneous conversations must stay single and reach their own sender."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
import quart
import telegram
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import entities, events, message
from langbot_plugin.api.entities.builtin.provider import message as provider_message

from langbot.libs.qq_official_api.api import QQOfficialClient
from langbot.libs.wecom_api.api import WecomClient
from langbot.pkg.platform.botmgr import RuntimeBot
from langbot.pkg.platform.ingress_dedup import InboundDeliveries, delivery_key
from langbot.pkg.platform.sources.http_bot import HttpBotAdapter
from langbot.pkg.platform.sources.websocket_adapter import WebSocketAdapter, WebSocketReplyContext
from langbot.pkg.platform.sources.websocket_manager import WebSocketScope
from langbot.pkg.platform.stream_output import stream_output_supported

pytestmark = pytest.mark.asyncio


def received(message_id='10', chat_id='chat-1', sender='user-1', timestamp=1700000000.0, text='hello', **extra):
    return events.MessageReceivedEvent(
        message_id=message_id,
        message_chain=message.MessageChain([message.Plain(text=text)]),
        sender=entities.User(id=sender, nickname=sender),
        chat_type=entities.ChatType.PRIVATE,
        chat_id=chat_id,
        timestamp=timestamp,
        **extra,
    )


def make_bot(primary, plugin_processors=()):
    bot = object.__new__(RuntimeBot)
    bot._inbound_deliveries = InboundDeliveries()
    bot._ingress_dedup_lock = asyncio.Lock()
    bot.bot_entity = SimpleNamespace(
        uuid='bot-1', adapter='x', name='x', workspace_uuid='w', plugin_processors=list(plugin_processors)
    )
    bot.workspace_uuid, bot.placement_generation, bot.execution_context = 'w', 1, None
    bot.logger = SimpleNamespace(info=AsyncMock(), warning=AsyncMock(), error=AsyncMock(), debug=AsyncMock())
    bot.ap = SimpleNamespace(workspace_service=SimpleNamespace(get_execution_binding=AsyncMock()))
    bot.assert_execution_active = AsyncMock()
    bot._dispatch_eba_event_to_processor = primary
    return bot


async def test_redelivered_message_is_processed_once():
    primary = AsyncMock(return_value={'status': 'delivered'})
    bot = make_bot(primary)

    await bot._handle_platform_event(received(), Mock())
    await bot._handle_platform_event(received(), Mock())

    assert primary.await_count == 1


@pytest.mark.parametrize(
    'other',
    [
        dict(message_id='11'),  # the same text sent again
        dict(chat_id='chat-2'),  # message IDs restart in every chat
        dict(sender='user-2'),
        dict(timestamp=1700000001.0),  # the platform reused an ID later
        dict(message_id=''),
        dict(timestamp=0.0),
    ],
)
async def test_lookalike_messages_are_never_dropped(other):
    primary = AsyncMock(return_value={})
    bot = make_bot(primary)

    for event in (received(), received(**other), received(**{**other, 'message_id': '99'})):
        await bot._handle_platform_event(event, Mock())

    assert primary.await_count == 3


async def test_unidentifiable_messages_have_no_delivery_key():
    for message_id in ('', '0', '-1'):
        assert delivery_key(received(message_id=message_id)) is None
    assert delivery_key(received(timestamp=0.0)) is None
    assert delivery_key(events.MessageEditedEvent(message_id='10', timestamp=1.0)) is None


async def test_retry_after_failed_delivery_is_processed():
    primary = AsyncMock(side_effect=[RuntimeError('queue full'), {}])
    bot = make_bot(primary)

    await bot._handle_platform_event(received(), Mock())
    await bot._handle_platform_event(received(), Mock())
    await bot._handle_platform_event(received(), Mock())

    assert primary.await_count == 2


@pytest.mark.parametrize('outcome', ['failed', 'cancelled'])
async def test_pending_copy_takes_over_a_lost_delivery(outcome):
    calls, started, release = [], asyncio.Event(), asyncio.Event()

    async def primary(event, adapter, execution_id=None):
        calls.append(event)
        if len(calls) == 1:
            started.set()
            await release.wait()
            raise RuntimeError('lost')
        return {}

    bot = make_bot(primary)
    first = asyncio.create_task(bot._handle_platform_event(received(), Mock()))
    await started.wait()
    copies = [asyncio.create_task(bot._handle_platform_event(received(), Mock())) for _ in range(3)]
    await asyncio.sleep(0)
    assert len(calls) == 1
    if outcome == 'failed':
        release.set()
    else:
        first.cancel()
    await asyncio.gather(first, *copies, return_exceptions=True)

    assert len(calls) == 2


async def test_slow_subscriber_does_not_reopen_an_answered_message():
    primary, hang = AsyncMock(return_value={}), asyncio.Event()
    bot = make_bot(primary, [{'processor_uuid': 'slow'}])

    async def subscriber(*args):
        await hang.wait()

    bot._dispatch_plugin_subscription = subscriber
    first = asyncio.create_task(bot._handle_platform_event(received(), Mock()))
    while not primary.await_count:
        await asyncio.sleep(0)
    await asyncio.sleep(0)
    await bot._handle_platform_event(received(), Mock())
    first.cancel()
    await asyncio.gather(first, return_exceptions=True)
    await bot._handle_platform_event(received(), Mock())

    assert primary.await_count == 1


async def test_conversations_are_processed_in_parallel():
    running, peak, gate = 0, 0, asyncio.Event()

    async def primary(event, adapter, execution_id=None):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await gate.wait()

    bot = make_bot(primary)
    tasks = [asyncio.create_task(bot._handle_platform_event(received(chat_id=f'chat-{i}'), Mock())) for i in range(20)]
    while peak < 20:
        await asyncio.sleep(0)
    gate.set()
    await asyncio.gather(*tasks)


async def test_delivery_registry_is_bounded():
    registry = InboundDeliveries(limit=3)
    for index in range(10):
        async with registry.admit((str(index),)) as delivery:
            delivery.accept()
    assert len(registry._outcomes) == 3


async def test_event_identity_separates_chats_and_keeps_native_reference():
    bot = make_bot(AsyncMock())
    first, second = received(chat_id='600'), received(chat_id='605')

    assert bot._platform_event_execution_id(first) != bot._platform_event_execution_id(second)
    envelope = bot._eba_event_to_agent_envelope(first, Mock(), bot._platform_event_execution_id(first))
    assert envelope.event_id == bot._platform_event_execution_id(first)
    assert envelope.raw_ref.ref_id == '10'
    # The durable WeCom customer-service journal must keep matching recorded IDs.
    kf = received(adapter_name='wecomcs-omni', source_platform_object={'msgid': 'kf-1'})
    assert bot._platform_event_execution_id(kf) == 'platform:bot-1:kf-1'


async def test_websocket_stream_choice_belongs_to_each_message():
    logger = AsyncMock(spec=AbstractEventLogger)
    adapter = WebSocketAdapter.model_construct(config={}, logger=logger)
    scope = WebSocketScope('i', 'w', 1)

    def source(session_id, stream):
        event = events.FriendMessage(
            sender=entities.Friend(id=session_id, nickname='', remark=''), message_chain=message.MessageChain([])
        )
        context = WebSocketReplyContext(scope=scope, pipeline_uuid='p', session_id=session_id, stream=stream)
        object.__setattr__(event, '_websocket_reply_context', context)
        return events.MessageReceivedEvent(legacy_event=event, sender=entities.User(id=session_id)).to_legacy_event()

    streaming, plain = source('a', True), source('b', False)
    assert await stream_output_supported(adapter, streaming) is True
    assert await stream_output_supported(adapter, plain) is False
    # Another conversation's choice does not change a reply already in progress.
    assert await stream_output_supported(adapter, streaming) is True
    assert await stream_output_supported(adapter, None) is True


class PerMessageAdapter:
    """An adapter whose shared capability says one thing and the message another."""

    def __init__(self, stream):
        self.stream = stream
        self.reply_message = AsyncMock()
        self.reply_message_chunk = AsyncMock()
        self.create_message_card = AsyncMock()

    async def is_stream_output_supported(self):
        return not self.stream

    async def is_stream_output_supported_for(self, message_source):
        return self.stream


@pytest.mark.parametrize('stream', [True, False])
async def test_response_stage_follows_the_message_being_answered(stream):
    import langbot.pkg.pipeline.pipelinemgr  # noqa: F401
    from langbot.pkg.pipeline.respback.respback import SendResponseBackStage

    adapter = PerMessageAdapter(stream)
    query = SimpleNamespace(
        pipeline_config={
            'output': {'force-delay': {'min': 0, 'max': 0}, 'misc': {'at-sender': False, 'quote-origin': False}}
        },
        message_event=received().to_legacy_event(),
        adapter=adapter,
        variables={},
        resp_messages=[provider_message.MessageChunk(role='assistant', content='part')],
        resp_message_chain=[chain('part')],
    )
    with patch('langbot.pkg.pipeline.entities.StageProcessResult'):
        await SendResponseBackStage(Mock()).process(query, 'SendResponseBackStage')

    assert adapter.reply_message_chunk.await_count == int(stream)
    assert adapter.reply_message.await_count == int(not stream)


@pytest.mark.parametrize('stream', [True, False])
async def test_chat_handler_follows_the_message_being_answered(stream):
    import langbot.pkg.pipeline.pipelinemgr  # noqa: F401
    from langbot.pkg.pipeline.process.handlers.chat import ChatMessageHandler
    from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes

    async def run_from_query(query):
        yield provider_message.Message(role='assistant', content='answer')

    async def emit_event(event, bound_plugins):
        return SimpleNamespace(is_prevented_default=lambda: False, event=SimpleNamespace(user_message_alter=None))

    adapter = PerMessageAdapter(stream)
    orchestrator = SimpleNamespace(
        run_from_query=run_from_query,
        try_claim_steering_from_query=AsyncMock(return_value=False),
        resolve_runner_id_for_telemetry=lambda query: '',
    )
    ap = Mock(
        instance_config=SimpleNamespace(data={}),
        agent_run_orchestrator=orchestrator,
        plugin_connector=SimpleNamespace(emit_event=emit_event),
        survey=None,
    )
    query = SimpleNamespace(
        query_id=1,
        adapter=adapter,
        launcher_type=LauncherTypes.PERSON,
        launcher_id='u',
        sender_id='u',
        message_event=received().to_legacy_event(),
        message_chain=chain('hi'),
        pipeline_config={'output': {'misc': {}}},
        variables={},
        resp_messages=[],
        resp_message_chain=[],
        session=SimpleNamespace(using_conversation=object()),
    )
    with (
        patch('langbot.pkg.pipeline.process.handlers.chat.events'),
        patch('langbot.pkg.pipeline.entities.StageProcessResult'),
    ):
        _ = [result async for result in ChatMessageHandler(ap).handle(query)]

    assert adapter.create_message_card.await_count == int(stream)
    assert isinstance(query.resp_messages[-1], provider_message.MessageChunk) is stream


async def test_stream_support_falls_back_to_the_adapter_capability():
    adapter = SimpleNamespace(is_stream_output_supported=AsyncMock(return_value=True))
    assert await stream_output_supported(adapter, received()) is True


def http_bot():
    adapter = HttpBotAdapter(config={'callback_timeout': 1}, logger=AsyncMock(spec=AbstractEventLogger))
    adapter._enqueue_callback = AsyncMock()
    return adapter


def http_event(adapter, session_type='person'):
    body = {'session_id': 's', 'session_type': session_type, 'message': [{'type': 'Plain', 'text': 'hi'}]}
    return adapter._build_event(body)


def chain(text):
    return message.MessageChain([message.Plain(text=text)])


async def test_sync_request_only_collects_the_reply_to_its_own_message():
    adapter = http_bot()
    pushed, *_ = http_event(adapter)
    grouped, *_ = http_event(adapter, 'group')
    inbound, session_id, _, message_id = http_event(adapter)

    async def listener(event, live_adapter):
        await live_adapter.reply_message(pushed, chain('answer to async push'))
        await live_adapter.reply_message(grouped, chain('answer to group'))
        await live_adapter.send_message('group', 's', chain('group push'))
        # Plugins may replace the chain that carried the Source component.
        event.message_chain = chain('rewritten')
        await live_adapter.reply_message(event, chain('mine'))

    async with quart.Quart(__name__).app_context():
        response, _ = await adapter._run_sync(inbound, listener, session_id, message_id)
        data = (await response.get_json())['data']

    assert [part['text'] for part in data['message']] == ['mine']
    assert adapter._enqueue_callback.await_count == 3


async def test_sync_message_is_marked_as_its_own_turn():
    adapter = http_bot()
    inbound, session_id, _, message_id = http_event(adapter)
    bot = make_bot(AsyncMock())
    bot.ap.msg_aggregator = SimpleNamespace(add_message=AsyncMock())
    bot.ap.webhook_pusher = None

    async def listener(event, live_adapter):
        eba_event = bot._legacy_message_to_eba_event(event, live_adapter)
        await bot._dispatch_eba_message_to_pipeline(eba_event, live_adapter, pipeline_uuid='p')
        await live_adapter.reply_message(event, chain('mine'))

    async with quart.Quart(__name__).app_context():
        await adapter._run_sync(inbound, listener, session_id, message_id)
    variables = bot.ap.msg_aggregator.add_message.await_args.kwargs['variables']
    assert variables == {'_standalone_turn': True}

    from langbot.pkg.agent.runner.orchestrator import AgentRunOrchestrator

    orchestrator = object.__new__(AgentRunOrchestrator)
    orchestrator.query_bridge = SimpleNamespace(
        build_plan=Mock(side_effect=AssertionError('a standalone turn must not look for a run'))
    )
    assert await orchestrator.try_claim_steering_from_query(SimpleNamespace(variables=variables)) is False


def telegram_stream(edit):
    from langbot.pkg.platform.adapters.telegram.adapter import TelegramAdapter

    adapter = TelegramAdapter.model_construct(config={})
    object.__setattr__(adapter, 'bot', SimpleNamespace(edit_message_text=edit))
    return adapter


async def test_telegram_final_edit_waits_out_flood_control(monkeypatch):
    waits = AsyncMock()
    monkeypatch.setattr('langbot.pkg.platform.adapters.telegram.adapter.asyncio.sleep', waits)
    edit = AsyncMock(side_effect=[telegram.error.RetryAfter(2), telegram.error.RetryAfter(3), None])

    await telegram_stream(edit)._edit_stream_text({'text': 'final'}, is_final=True)

    assert edit.await_count == 3
    assert [call.args[0] for call in waits.await_args_list] == [2, 3]


async def test_telegram_stream_reply_survives_flood_control(monkeypatch):
    """The answer must land in the streamed message instead of being sent again."""
    from langbot.pkg.platform.adapters.telegram.adapter import Update

    monkeypatch.setattr('langbot.pkg.platform.adapters.telegram.adapter.asyncio.sleep', AsyncMock())
    edit = AsyncMock(side_effect=[telegram.error.RetryAfter(1), None])
    adapter = telegram_stream(edit)
    adapter.msg_stream_id = {'reply': ('message', 5, True)}
    update = Update.de_json(
        {'update_id': 1, 'message': {'message_id': 1, 'date': 1, 'chat': {'id': 7, 'type': 'private'}, 'text': 'q'}}
    )
    bot_message = SimpleNamespace(resp_message_id='reply', msg_sequence=2, tool_calls=None)

    await adapter.reply_message_chunk(
        received(source_platform_object=update), bot_message, chain('final answer'), is_final=True
    )

    assert edit.await_count == 2
    assert adapter.msg_stream_id == {}


async def test_telegram_intermediate_edit_never_blocks_the_stream(monkeypatch):
    waits = AsyncMock()
    monkeypatch.setattr('langbot.pkg.platform.adapters.telegram.adapter.asyncio.sleep', waits)
    edit = AsyncMock(side_effect=telegram.error.RetryAfter(2))

    await telegram_stream(edit)._edit_stream_text({'text': 'partial'}, is_final=False)

    assert edit.await_count == 1
    waits.assert_not_awaited()


@pytest.mark.parametrize('delay,attempts', [(1, 4), (3600, 1)])
async def test_telegram_flood_wait_is_bounded(monkeypatch, delay, attempts):
    monkeypatch.setattr('langbot.pkg.platform.adapters.telegram.adapter.asyncio.sleep', AsyncMock())
    edit = AsyncMock(side_effect=telegram.error.RetryAfter(delay))

    with pytest.raises(telegram.error.RetryAfter):
        await telegram_stream(edit)._edit_stream_text({'text': 'final'}, is_final=True)
    assert edit.await_count == attempts


async def assert_acknowledged_while_processing(call, client, handlers):
    started, finish, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def slow(event):
        started.set()
        await finish.wait()
        finished.set()

    handlers(slow)
    await asyncio.wait_for(call(), 1)
    await asyncio.wait_for(started.wait(), 1)
    assert not finished.is_set()
    finish.set()
    await asyncio.wait_for(finished.wait(), 1)
    await asyncio.sleep(0)
    assert not client._processing_tasks


async def test_wecom_callback_is_acknowledged_before_the_answer(monkeypatch):
    client = WecomClient('corp', 's', 't', 'a' * 43, 'c', AsyncMock(), unified_mode=True)
    crypt = SimpleNamespace(DecryptMsg=lambda *args: (0, '<xml/>'))
    monkeypatch.setattr('langbot.libs.wecom_api.api.WXBizMsgCrypt', lambda *args: crypt)
    client.get_message = AsyncMock(return_value={'MsgType': 'text', 'Content': 'hi', 'MsgId': 1})

    async def body():
        return b'x'

    await assert_acknowledged_while_processing(
        lambda: client.handle_unified_webhook(SimpleNamespace(method='POST', args={}, data=body())),
        client,
        lambda handler: client.on_message('text')(handler),
    )


async def test_qq_official_callback_is_acknowledged_before_the_answer():
    client = QQOfficialClient('s', 't', '1', AsyncMock(), unified_mode=True)
    payload = b'{"op":0,"id":"e","t":"C2C_MESSAGE_CREATE","d":{"id":"m","content":"hi","author":{"user_openid":"u"}}}'

    await assert_acknowledged_while_processing(
        lambda: client.handle_unified_webhook(SimpleNamespace(get_data=AsyncMock(return_value=payload))),
        client,
        lambda handler: client.on_message('C2C_MESSAGE_CREATE')(handler),
    )


async def test_steering_only_targets_runs_started_by_the_same_actor():
    from langbot.pkg.agent.runner.orchestrator import AgentRunOrchestrator

    event = SimpleNamespace(
        event_type='message.received',
        conversation_id='group_1',
        bot_id='b',
        workspace_id='w',
        thread_id=None,
        actor=SimpleNamespace(actor_id='bob'),
    )
    plan = SimpleNamespace(event=event, binding=SimpleNamespace(runner_id='r'), bound_plugins=None)
    orchestrator = object.__new__(AgentRunOrchestrator)
    orchestrator.query_bridge = SimpleNamespace(build_plan=lambda query: plan)
    orchestrator.registry = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(id='r', supports_steering=lambda: True))
    )
    orchestrator._session_registry = SimpleNamespace(find_steering_target=AsyncMock(return_value=None))
    with patch('langbot.pkg.agent.runner.orchestrator.get_query_execution_context'):
        assert await orchestrator.try_claim_steering_from_query(SimpleNamespace(variables={})) is False

    assert orchestrator._session_registry.find_steering_target.await_args.kwargs['actor_id'] == 'bob'
