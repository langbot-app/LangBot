"""Concurrent conversation delivery through the real scheduling path.

Several conversations send messages at the same time. Inbound messages enter
through ``MessageAggregator`` exactly as ``RuntimeBot`` hands them over, then
run through the real ``QueryPool``, ``Controller``, ``SessionManager`` and the
default Pipeline stage chain. Only the Runner and the platform adapter are
doubles: the Runner echoes the text it was given after yielding to the event
loop, and the adapter records every outbound send with the event it answers.

Every inbound text is unique, so each reply can be traced to the message and
conversation it answers. The invariants are: every message is answered exactly
once, and every reply goes to the conversation whose message it answers.

The WebSocket case drives the real ``WebSocketAdapter`` instead of a recording
double: embed visitors stream while a dashboard debug chat has streaming off,
and each browser must show exactly one complete answer per message it sent.

Run: uv run pytest tests/integration/pipeline/test_concurrent_conversations.py -q
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
import uuid
from collections import Counter
from importlib import resources
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_event_logger
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session
from langbot_plugin.api.entities import context as event_context

pytestmark = pytest.mark.integration

INSTANCE_UUID = 'instance-1'
WORKSPACE_UUID = 'workspace-1'
BOT_UUID = 'bot-1'
PIPELINE_UUID = 'pipeline-1'
RUNNER_ID = 'plugin:langbot-team/LocalAgent/default'
REPLY_PREFIX = 'reply-to:'


class SilentEventLogger(abstract_event_logger.AbstractEventLogger):
    async def info(self, *args, **kwargs):
        pass

    async def debug(self, *args, **kwargs):
        pass

    async def warning(self, *args, **kwargs):
        pass

    async def error(self, *args, **kwargs):
        pass


class RecordingAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """Platform adapter double that records each send with its target event."""

    streaming: bool = False
    sent: list = []
    chunks: list = []

    def __init__(self, *, streaming: bool):
        super().__init__(
            bot_account_id='bot', config={}, logger=SilentEventLogger(), streaming=streaming, sent=[], chunks=[]
        )

    async def is_stream_output_supported(self) -> bool:
        return self.streaming

    async def send_message(self, target_type, target_id, message):
        raise AssertionError('replies must answer their source event')

    def register_listener(self, event_type, callback):
        pass

    def unregister_listener(self, event_type, callback):
        pass

    async def run_async(self):
        pass

    async def kill(self) -> bool:
        return True

    async def create_message_card(self, message_id, event) -> bool:
        return True

    async def reply_message(self, message_source, message, quote_origin=False):
        await asyncio.sleep(0)
        self.sent.append((message_source, str(message)))

    async def reply_message_chunk(self, message_source, bot_message, message, quote_origin=False, is_final=False):
        await asyncio.sleep(0)
        self.chunks.append((message_source, str(message), is_final))
        if is_final:
            self.sent.append((message_source, str(message)))


class EchoOrchestrator:
    """AgentRunOrchestrator double: answers with the text the Query carries."""

    def __init__(self, *, streaming: bool, rng: random.Random):
        self.streaming = streaming
        self.rng = rng

    async def try_claim_steering_from_query(self, query) -> bool:
        return False

    async def cancel_active_from_query(self, query, *, allow_other_actors=False):
        return None

    def resolve_runner_id_for_telemetry(self, query) -> str:
        return RUNNER_ID

    async def run_from_query(self, query):
        prompt = str(query.message_chain).strip()
        # Let other conversations run while this "model call" is in flight.
        for _ in range(self.rng.randint(1, 4)):
            await asyncio.sleep(self.rng.uniform(0, 0.01))
        answer = f'{REPLY_PREFIX}{prompt}'
        if self.streaming:
            yield provider_message.MessageChunk(role='assistant', content=answer[:5], is_final=False)
            await asyncio.sleep(self.rng.uniform(0, 0.005))
            yield provider_message.MessageChunk(role='assistant', content=answer, all_content=answer, is_final=True)
        else:
            yield provider_message.Message(role='assistant', content=answer)


def _pipeline_config(*, aggregation: bool) -> dict:
    template = resources.files('langbot.templates').joinpath('default-pipeline-config.json')
    config = json.loads(template.read_text(encoding='utf-8'))
    config['ai']['runner'] = {'id': RUNNER_ID, 'expire-time': 0}
    config['ai']['runner_config'] = {RUNNER_ID: {'model': {'primary': '', 'fallbacks': []}, 'prompt': 'default'}}
    config['trigger']['group-respond-rules'] = {'at': False, 'prefix': [], 'regexp': [], 'random': 1.0}
    config['trigger']['message-aggregation'] = {'enabled': aggregation, 'delay': 1.0}
    config['safety']['content-filter']['check-sensitive-words'] = False
    config['safety']['rate-limit'] = {'window-length': 60, 'limitation': 100000, 'strategy': 'drop'}
    config['output']['misc']['at-sender'] = False
    config['output']['misc']['quote-origin'] = False
    return config


async def _build_app(
    *,
    streaming: bool,
    aggregation: bool,
    seed: int,
    pipeline_concurrency: int,
    session_concurrency: int,
    db_latency: float,
):
    """Assemble the real scheduling path around Runner and adapter doubles."""

    from langbot.pkg.api.http.context import ExecutionContext
    from langbot.pkg.api.http.service.pipeline import default_stage_order
    from langbot.pkg.pipeline import aggregator, controller, pipelinemgr, pool, stage
    from langbot.pkg.provider.session import sessionmgr

    execution_context = ExecutionContext(
        instance_uuid=INSTANCE_UUID,
        workspace_uuid=WORKSPACE_UUID,
        placement_generation=1,
    )
    tasks: set[asyncio.Task] = set()

    def create_task(coro, **kwargs):
        task = asyncio.create_task(coro, name=kwargs.get('name'))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return task

    async def emit_event(event, bound_plugins=None):
        # Same result as PluginConnector.emit_event with no plugin bound.
        event_ctx = event_context.EventContext.from_event(event)
        event_ctx._emitted_plugins = []
        event_ctx._response_sources = []
        return event_ctx

    ap = SimpleNamespace()
    ap.logger = Mock()
    ap.instance_config = SimpleNamespace(
        data={
            'command': {'prefix': ['/', '!'], 'enable': True},
            'concurrency': {'pipeline': pipeline_concurrency, 'session': session_concurrency},
            'admins': [],
        }
    )
    # SessionManager reads the conversation reset generation from the database
    # on every lookup; model that read as an awaited round trip.
    ap.persistence_mgr = SimpleNamespace(get_db_engine=lambda: None)
    db_rng = random.Random(seed + 1)

    async def get_reset_generation(engine, workspace, bot, conversation):
        await asyncio.sleep(db_rng.uniform(0, db_latency))
        return None

    ap.task_mgr = SimpleNamespace(create_task=create_task)
    ap.workspace_service = AsyncMock()
    ap.workspace_service.get_execution_binding.return_value = SimpleNamespace(
        instance_uuid=INSTANCE_UUID,
        workspace_uuid=WORKSPACE_UUID,
        placement_generation=1,
    )
    ap.plugin_connector = SimpleNamespace(emit_event=emit_event)
    ap.agent_run_orchestrator = EchoOrchestrator(streaming=streaming, rng=random.Random(seed))
    ap.bot_service = AsyncMock()
    ap.bot_service.get_bot.return_value = {'name': 'Bot'}
    ap.monitoring_service = AsyncMock()
    ap.monitoring_service.record_message.return_value = 'monitoring-message'
    ap.model_mgr = AsyncMock()
    ap.model_mgr.get_model_by_uuid.side_effect = ValueError('no model')
    ap.tool_mgr = AsyncMock()
    ap.tool_mgr.get_all_tools.return_value = []
    ap.tool_mgr.get_resolved_tool_catalog.return_value = []
    ap.runner_registry = None
    ap.survey = None
    ap.telemetry = None

    ap.query_pool = pool.QueryPool(lambda: execution_context)
    ap.sess_mgr = sessionmgr.SessionManager(ap)
    ap.msg_aggregator = aggregator.MessageAggregator(ap)
    ap.controller = controller.Controller(ap)

    config = _pipeline_config(aggregation=aggregation)
    stage_containers = []
    for stage_name in default_stage_order:
        inst = stage.preregistered_stages[stage_name](ap)
        await inst.initialize(config)
        stage_containers.append(pipelinemgr.StageInstContainer(inst_name=stage_name, inst=inst))
    pipeline_entity = SimpleNamespace(
        uuid=PIPELINE_UUID,
        name='Pipeline',
        workspace_uuid=WORKSPACE_UUID,
        config=config,
        extensions_preferences={},
    )
    runtime_pipeline = pipelinemgr.RuntimePipeline(ap, pipeline_entity, stage_containers, execution_context)
    ap.pipeline_mgr = SimpleNamespace(get_pipeline_by_uuid=AsyncMock(return_value=runtime_pipeline))
    return ap, tasks, get_reset_generation


def _friend_event(user_id: str, text: str) -> platform_events.FriendMessage:
    return platform_events.FriendMessage(
        sender=platform_entities.Friend(id=user_id, nickname=user_id, remark=None),
        message_chain=platform_message.MessageChain([platform_message.Plain(text=text)]),
        time=0,
    )


def _group_event(group_id: str, user_id: str, text: str) -> platform_events.GroupMessage:
    group = platform_entities.Group(id=group_id, name=group_id, permission=platform_entities.Permission.Member)
    return platform_events.GroupMessage(
        sender=platform_entities.GroupMember(
            id=user_id,
            member_name=user_id,
            permission=platform_entities.Permission.Member,
            group=group,
        ),
        message_chain=platform_message.MessageChain([platform_message.Plain(text=text)]),
        time=0,
    )


def _conversation_of(event: platform_events.MessageEvent) -> str:
    if isinstance(event, platform_events.GroupMessage):
        return f'group_{event.group.id}'
    return f'person_{event.sender.id}'


async def _deliver(ap, adapter, event: platform_events.MessageEvent) -> None:
    """Hand an inbound event to the aggregator the way RuntimeBot does."""

    is_group = isinstance(event, platform_events.GroupMessage)
    await ap.msg_aggregator.add_message(
        bot_uuid=BOT_UUID,
        launcher_type=provider_session.LauncherTypes.GROUP if is_group else provider_session.LauncherTypes.PERSON,
        launcher_id=event.group.id if is_group else event.sender.id,
        sender_id=event.sender.id,
        message_event=event,
        message_chain=event.message_chain,
        adapter=adapter,
        pipeline_uuid=PIPELINE_UUID,
    )


async def _run_burst(
    *,
    streaming: bool,
    aggregation: bool,
    seed: int,
    persons: int = 6,
    groups: int = 3,
    messages_per_conversation: int = 4,
    pipeline_concurrency: int = 20,
    session_concurrency: int = 1,
    db_latency: float = 0.002,
):
    """Send concurrent bursts and return what was sent and what was answered."""

    from importlib import import_module

    import_module('langbot.pkg.pipeline.pipelinemgr')

    ap, tasks, get_reset_generation = await _build_app(
        streaming=streaming,
        aggregation=aggregation,
        seed=seed,
        pipeline_concurrency=pipeline_concurrency,
        session_concurrency=session_concurrency,
        db_latency=db_latency,
    )
    adapter = RecordingAdapter(streaming=streaming)
    rng = random.Random(seed)

    inbound: list[platform_events.MessageEvent] = []
    for p in range(persons):
        for m in range(messages_per_conversation):
            inbound.append(_friend_event(f'u{p}', f'person_u{p}#{m}'))
    for g in range(groups):
        for m in range(messages_per_conversation):
            inbound.append(_group_event(f'g{g}', f'm{m % 2}', f'group_g{g}#{m}'))

    snapshot = [(event, str(event.message_chain).strip(), _conversation_of(event)) for event in inbound]
    from langbot.pkg.agent.runner import context_reset

    patch = pytest.MonkeyPatch()
    patch.setattr(context_reset, 'get_reset_generation', get_reset_generation)
    consumer = asyncio.create_task(ap.controller.consumer())

    async def sender(conversation_events):
        for event in conversation_events:
            await asyncio.sleep(rng.uniform(0, 0.004))
            await _deliver(ap, adapter, event)

    by_conversation: dict[str, list] = {}
    for event in inbound:
        by_conversation.setdefault(_conversation_of(event), []).append(event)
    try:
        await asyncio.gather(*(sender(events) for events in by_conversation.values()))
        if aggregation:
            await asyncio.sleep(1.3)
        deadline = asyncio.get_running_loop().time() + 15
        while ap.query_pool.cached_queries or tasks:
            assert asyncio.get_running_loop().time() < deadline, 'queries did not drain'
            await asyncio.sleep(0.01)
    finally:
        consumer.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consumer
        patch.undo()
    return snapshot, adapter


def _reply_violations(inbound, adapter, *, aggregation: bool) -> list[str]:
    """Return every duplicate, missing, or misrouted reply.

    ``inbound`` holds ``(event, text, conversation)`` captured before delivery:
    Pipeline stages may rewrite an event's chain in place, so replies are
    matched to the original event object rather than its current text.
    """

    violations: list[str] = []
    text_to_conversation = {text: conversation for _, text, conversation in inbound}
    event_text = {id(event): text for event, text, _ in inbound}
    answered: Counter[str] = Counter()
    for target_event, reply_text in adapter.sent:
        target_conversation = _conversation_of(target_event)
        assert reply_text.startswith(REPLY_PREFIX), reply_text
        prompts = [line.strip() for line in reply_text[len(REPLY_PREFIX) :].split('\n') if line.strip()]
        for prompt in prompts:
            answered[prompt] += 1
            owner = text_to_conversation.get(prompt)
            if owner != target_conversation:
                violations.append(f'misrouted: answer to {prompt!r} ({owner}) sent to {target_conversation}')
        source_text = event_text.get(id(target_event))
        if source_text is None:
            violations.append(f'unknown source: answer to {prompts} sent to an event that was never received')
        elif prompts[0] != source_text or (not aggregation and len(prompts) != 1):
            violations.append(f'wrong source: answer to {prompts} sent as a reply to {source_text!r}')
    for prompt in text_to_conversation:
        if answered[prompt] == 0:
            violations.append(f'missing: {prompt!r} was never answered')
        elif answered[prompt] > 1:
            violations.append(f'duplicate: {prompt!r} answered {answered[prompt]} times')
    return violations


@pytest.mark.asyncio
@pytest.mark.parametrize('streaming', [False, True], ids=['non-streaming', 'streaming'])
@pytest.mark.parametrize('seed', range(5))
async def test_concurrent_conversations_get_exactly_their_own_replies(streaming, seed):
    inbound, adapter = await _run_burst(streaming=streaming, aggregation=False, seed=seed)

    assert _reply_violations(inbound, adapter, aggregation=False) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('seed', range(2))
async def test_concurrent_aggregated_conversations_get_exactly_their_own_replies(seed):
    inbound, adapter = await _run_burst(streaming=False, aggregation=True, seed=seed)

    assert _reply_violations(inbound, adapter, aggregation=True) == []


def _browser_session_id(seed: int, name: str) -> str:
    return str(uuid.UUID(int=random.Random(f'{seed}-{name}').getrandbits(128), version=4))


async def _run_websocket_browsers(
    *,
    seed: int,
    visitors: int = 5,
    messages_per_browser: int = 4,
    dashboard_session_ids: tuple[str | None, ...] = (None,),
):
    """Embed visitors and non-streaming dashboard dialogs message at the same time.

    A dashboard dialog without a session id uses the legacy conversation
    shared by every such dialog on the Pipeline.
    """

    from importlib import import_module

    import_module('langbot.pkg.pipeline.pipelinemgr')
    from langbot.pkg.agent.runner import context_reset
    from langbot.pkg.platform.sources import websocket_adapter as websocket_adapter_module
    from langbot.pkg.platform.sources.websocket_manager import WebSocketConnectionManager, WebSocketScope

    ap, tasks, get_reset_generation = await _build_app(
        streaming=True,
        aggregation=False,
        seed=seed,
        pipeline_concurrency=20,
        session_concurrency=1,
        db_latency=0.002,
    )
    execution_context = ap.query_pool._singleton_context_resolver()
    logger = SilentEventLogger()
    object.__setattr__(logger, 'execution_context', execution_context)
    adapter = websocket_adapter_module.WebSocketAdapter.model_construct(
        config={},
        logger=logger,
        ap=ap,
        listeners={},
        bot_account_id='websocketbot',
        websocket_person_session=websocket_adapter_module.WebSocketSession(id='websocketperson'),
        websocket_group_session=websocket_adapter_module.WebSocketSession(id='websocketgroup'),
        outbound_message_queue=asyncio.Queue(maxsize=100),
        inbound_listener_tasks=set(),
        stream_enabled=True,
    )

    async def listener(event, callback_adapter):
        # RuntimeBot._handle_legacy_message_event for a person message.
        await ap.msg_aggregator.add_message(
            bot_uuid=BOT_UUID,
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=event.sender.id,
            sender_id=event.sender.id,
            message_event=event,
            message_chain=event.message_chain,
            adapter=callback_adapter,
            pipeline_uuid=PIPELINE_UUID,
        )

    adapter.register_listener(platform_events.FriendMessage, listener)

    manager = WebSocketConnectionManager()
    scope = WebSocketScope.from_context(execution_context)
    browsers = []
    for visitor in range(visitors):
        connection = await manager.add_connection(
            websocket=Mock(),
            scope=scope,
            pipeline_uuid=PIPELINE_UUID,
            session_type='person',
            session_id=_browser_session_id(seed, f'visitor{visitor}'),
        )
        # The embed widget always asks for streaming.
        browsers.append((f'visitor{visitor}', connection, True))
    for index, session_id in enumerate(dashboard_session_ids):
        dashboard = await manager.add_connection(
            websocket=Mock(),
            scope=scope,
            pipeline_uuid=PIPELINE_UUID,
            session_type='person',
            session_id=session_id,
        )
        # The dashboard debug dialog can turn streaming off.
        browsers.append((f'dashboard{index}', dashboard, False))

    rng = random.Random(seed)
    patch = pytest.MonkeyPatch()
    patch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)
    patch.setattr(context_reset, 'get_reset_generation', get_reset_generation)
    consumer = asyncio.create_task(ap.controller.consumer())

    async def browser(name, connection, stream):
        for index in range(messages_per_browser):
            await asyncio.sleep(rng.uniform(0, 0.02))
            await adapter.handle_websocket_message(
                connection,
                {'message': [{'type': 'Plain', 'text': f'{name}#{index}'}], 'stream': stream},
            )

    try:
        await asyncio.gather(*(browser(*entry) for entry in browsers))
        deadline = asyncio.get_running_loop().time() + 15
        while ap.query_pool.cached_queries or tasks or adapter.inbound_listener_tasks:
            assert asyncio.get_running_loop().time() < deadline, 'queries did not drain'
            await asyncio.sleep(0.01)
    finally:
        consumer.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consumer
        patch.undo()

    shown_by_browser: dict[str, list[str]] = {}
    for name, connection, _ in browsers:
        # The browser renders one bubble per message id; later events update it.
        bubbles: dict[int, str] = {}
        while not connection.send_queue.empty():
            item = connection.send_queue.get_nowait()
            if item.get('type') == 'response':
                bubbles[item['data']['id']] = item['data']['content']
        shown_by_browser[name] = list(bubbles.values())
    return shown_by_browser, messages_per_browser


@pytest.mark.asyncio
@pytest.mark.parametrize('seed', range(8))
async def test_websocket_stream_choice_does_not_leak_between_browsers(seed):
    shown_by_browser, messages_per_browser = await _run_websocket_browsers(seed=seed)

    for name, shown in shown_by_browser.items():
        expected = sorted(f'{REPLY_PREFIX}{name}#{index}' for index in range(messages_per_browser))
        assert sorted(shown) == expected, name


async def _run_web_page_bot_visitors(*, seed: int, visitors: int = 5, messages_per_visitor: int = 4):
    """Embed visitors message one web page bot the way the embed route delivers them."""

    from importlib import import_module

    import_module('langbot.pkg.pipeline.pipelinemgr')
    from langbot.pkg.agent.runner import context_reset
    from langbot.pkg.platform import botmgr
    from langbot.pkg.platform.sources import websocket_adapter as websocket_adapter_module
    from langbot.pkg.platform.sources.web_page_bot_adapter import WebPageBotAdapter
    from langbot.pkg.platform.sources.websocket_manager import WebSocketConnectionManager, WebSocketScope

    ap, tasks, get_reset_generation = await _build_app(
        streaming=True,
        aggregation=False,
        seed=seed,
        pipeline_concurrency=20,
        session_concurrency=1,
        db_latency=0.002,
    )
    ap.monitoring_service.record_ingress_event = AsyncMock()
    questions_by_record: dict[str, str] = {}

    async def record_message(_context, **kwargs):
        record_id = f'monitoring-{len(questions_by_record)}'
        questions_by_record[record_id] = ''.join(
            component.get('text', '') for component in kwargs['message_content'] if component.get('type') == 'Plain'
        )
        return record_id

    ap.monitoring_service.record_message.side_effect = record_message
    execution_context = ap.query_pool._singleton_context_resolver()
    logger = SilentEventLogger()
    object.__setattr__(logger, 'execution_context', execution_context)
    proxy_adapter = websocket_adapter_module.WebSocketAdapter.model_construct(
        config={},
        logger=logger,
        ap=ap,
        listeners={},
        bot_account_id='websocketbot',
        websocket_person_session=websocket_adapter_module.WebSocketSession(id='websocketperson'),
        websocket_group_session=websocket_adapter_module.WebSocketSession(id='websocketgroup'),
        outbound_message_queue=asyncio.Queue(maxsize=100),
        inbound_listener_tasks=set(),
        stream_enabled=True,
    )
    bot = botmgr.RuntimeBot(
        ap=ap,
        bot_entity=SimpleNamespace(
            uuid=BOT_UUID,
            name='Web page bot',
            adapter='web_page_bot',
            enable=True,
            workspace_uuid=WORKSPACE_UUID,
            event_bindings=[
                {
                    'id': 'route-1',
                    'event_pattern': 'message.received',
                    'target_type': 'pipeline',
                    'target_uuid': PIPELINE_UUID,
                    'enabled': True,
                }
            ],
            plugin_processors=[],
        ),
        adapter=WebPageBotAdapter(config={}, logger=SilentEventLogger()),
        logger=SimpleNamespace(info=AsyncMock(), debug=AsyncMock(), warning=AsyncMock(), error=AsyncMock()),
        execution_context=execution_context,
    )
    await bot.initialize()

    manager = WebSocketConnectionManager()
    scope = WebSocketScope.from_context(execution_context)
    browsers = []
    for visitor in range(visitors):
        connection = await manager.add_connection(
            websocket=Mock(),
            scope=scope,
            pipeline_uuid=PIPELINE_UUID,
            session_type='person',
            session_id=_browser_session_id(seed, f'visitor{visitor}'),
        )
        browsers.append((f'visitor{visitor}', connection))

    rng = random.Random(seed)
    patch = pytest.MonkeyPatch()
    patch.setattr(websocket_adapter_module, 'ws_connection_manager', manager)
    patch.setattr(context_reset, 'get_reset_generation', get_reset_generation)
    consumer = asyncio.create_task(ap.controller.consumer())

    async def browser(name, connection):
        for index in range(messages_per_visitor):
            await asyncio.sleep(rng.uniform(0, 0.02))
            # Same call as EmbedRouterGroup._handle_receive.
            await proxy_adapter.handle_websocket_message(
                connection,
                {'message': [{'type': 'Plain', 'text': f'{name}#{index}'}], 'stream': True},
                owner_bot=bot,
            )

    try:
        await asyncio.gather(*(browser(*entry) for entry in browsers))
        deadline = asyncio.get_running_loop().time() + 15
        while ap.query_pool.cached_queries or tasks or proxy_adapter.inbound_listener_tasks:
            assert asyncio.get_running_loop().time() < deadline, 'queries did not drain'
            await asyncio.sleep(0.01)
    finally:
        consumer.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consumer
        patch.undo()

    shown_by_browser: dict[str, list[str]] = {}
    # For each reply bubble, the question of the monitoring record its feedback links to.
    rated_question_by_browser: dict[str, dict[str, str | None]] = {}
    for name, connection in browsers:
        bubbles: dict[int, str] = {}
        while not connection.send_queue.empty():
            item = connection.send_queue.get_nowait()
            if item.get('type') == 'response':
                assert 'monitoring_message_id' not in item['data']
                bubbles[item['data']['id']] = item['data']['content']
        shown_by_browser[name] = list(bubbles.values())
        rated_question_by_browser[name] = {
            content: questions_by_record.get(
                proxy_adapter.get_monitoring_message_id(PIPELINE_UUID, 'person', connection.session_id, str(bubble_id))
            )
            for bubble_id, content in bubbles.items()
        }
    return shown_by_browser, ap, rated_question_by_browser


@pytest.mark.asyncio
@pytest.mark.parametrize('seed', range(4))
async def test_web_page_bot_visitors_keep_their_own_replies_and_ingress_records(seed):
    visitors, messages_per_visitor = 5, 4
    shown_by_browser, ap, rated_question_by_browser = await _run_web_page_bot_visitors(
        seed=seed,
        visitors=visitors,
        messages_per_visitor=messages_per_visitor,
    )

    for name, shown in shown_by_browser.items():
        expected = sorted(f'{REPLY_PREFIX}{name}#{index}' for index in range(messages_per_visitor))
        assert sorted(shown) == expected, name

    # The event log is unique on event_id: a reused id folds one visitor's
    # message into another visitor's conversation record.
    conversations_by_event: dict[str, set[str]] = {}
    for call in ap.monitoring_service.record_ingress_event.await_args_list:
        conversations_by_event.setdefault(call.kwargs['event_id'], set()).add(call.kwargs['conversation_id'])
    assert len(conversations_by_event) == visitors * messages_per_visitor
    assert all(len(conversations) == 1 for conversations in conversations_by_event.values())

    # Feedback on each reply links to the monitoring record of the question it answers.
    for name, rated_questions in rated_question_by_browser.items():
        assert rated_questions == {
            f'{REPLY_PREFIX}{name}#{index}': f'{name}#{index}' for index in range(messages_per_visitor)
        }, name


@pytest.mark.asyncio
@pytest.mark.parametrize('seed', range(4))
async def test_dashboard_dialogs_on_one_pipeline_get_only_their_own_replies(seed):
    shown_by_browser, messages_per_browser = await _run_websocket_browsers(
        seed=seed,
        visitors=2,
        dashboard_session_ids=(_browser_session_id(seed, 'dialog-a'), _browser_session_id(seed, 'dialog-b')),
    )

    for name, shown in shown_by_browser.items():
        expected = sorted(f'{REPLY_PREFIX}{name}#{index}' for index in range(messages_per_browser))
        assert sorted(shown) == expected, name
