"""Integration-style tests for AgentRunOrchestrator with a fake plugin runner."""

from __future__ import annotations

import asyncio
import datetime
import types
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.agent.runner.errors import RunnerExecutionError
from langbot.pkg.agent.runner.orchestrator import AgentRunOrchestrator
from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter
from langbot.pkg.agent.runner.binding_resolver import AgentBindingResolver
from langbot.pkg.agent.runner.session_registry import get_session_registry
from langbot.pkg.agent.runner.run_ledger_store import RunLedgerStore
from langbot.pkg.agent.runner.persistent_state_store import reset_persistent_state_store
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.provider import session as provider_session
from langbot_plugin.api.entities.builtin.resource import tool as resource_tool


RUNNER_ID = 'plugin:langbot-team/LocalAgent/default'


class FakeLogger:
    def __init__(self):
        self.warnings: list[str] = []

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg, *args, **kwargs):
        self.warnings.append(str(msg))

    def error(self, msg):
        pass


class FakeVersionManager:
    def get_current_version(self):
        return 'test-version'


class FakeModel:
    def __init__(self, model_type: str = 'chat'):
        self.model_entity = types.SimpleNamespace(model_type=model_type)
        self.provider_entity = types.SimpleNamespace(name='fake-provider')


class FakeKnowledgeBase:
    def __init__(self, kb_id: str):
        self.kb_id = kb_id
        self.knowledge_base_entity = types.SimpleNamespace(kb_type='fake')

    def get_name(self):
        return f'KB {self.kb_id}'


class FakePluginConnector:
    is_enable_plugin = True

    def __init__(self, results=None, error: Exception | None = None, delay: float = 0):
        self.results = results or []
        self.error = error
        self.delay = delay
        self.calls: list[dict] = []
        self.contexts: list[dict] = []
        self.sessions_during_run: list[dict | None] = []

    async def run_agent(self, plugin_author, plugin_name, runner_name, context):
        self.calls.append(
            {
                'plugin_author': plugin_author,
                'plugin_name': plugin_name,
                'runner_name': runner_name,
            }
        )
        self.contexts.append(context)
        self.sessions_during_run.append(await get_session_registry().get(context['run_id']))

        if self.error:
            raise self.error

        for result in self.results:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield result


class FakeRegistry:
    def __init__(self, descriptor: AgentRunnerDescriptor):
        self.descriptor = descriptor
        self.calls: list[dict] = []

    async def get(self, runner_id, bound_plugins=None):
        self.calls.append({'runner_id': runner_id, 'bound_plugins': bound_plugins})
        assert runner_id == self.descriptor.id
        return self.descriptor


class FakePersistenceManager:
    def __init__(self, db_engine: AsyncEngine):
        self._db_engine = db_engine

    def get_db_engine(self):
        return self._db_engine


class FakeApplication:
    def __init__(self, plugin_connector: FakePluginConnector, db_engine: AsyncEngine):
        self.logger = FakeLogger()
        self.ver_mgr = FakeVersionManager()
        self.plugin_connector = plugin_connector
        self.persistence_mgr = FakePersistenceManager(db_engine)

        self.model_mgr = types.SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=FakeModel()))
        self.rag_mgr = types.SimpleNamespace(
            get_knowledge_base_by_uuid=AsyncMock(return_value=FakeKnowledgeBase('kb_001'))
        )
        self.skill_mgr = types.SimpleNamespace(
            skills={
                'demo': {
                    'name': 'demo',
                    'display_name': 'Demo Skill',
                    'description': 'Helps with demo tasks.',
                },
                'hidden': {
                    'name': 'hidden',
                    'display_name': 'Hidden Skill',
                    'description': 'Not bound to this pipeline.',
                },
            }
        )


class FakeConversation:
    uuid = 'conv_existing'
    create_time = datetime.datetime(2026, 5, 15, 12, 0, 0)


def make_descriptor() -> AgentRunnerDescriptor:
    return AgentRunnerDescriptor(
        id=RUNNER_ID,
        source='plugin',
        label={'en_US': 'Local Agent'},
        plugin_author='langbot-team',
        plugin_name='LocalAgent',
        runner_name='default',
        capabilities={
            'streaming': True,
            'tool_calling': True,
            'knowledge_retrieval': True,
            'skill_authoring': True,
        },
        permissions={
            'models': ['invoke', 'stream'],
            'tools': ['detail', 'call'],
            'knowledge_bases': ['list', 'retrieve'],
            'history': ['page', 'search'],
            'events': ['get', 'page'],
            'storage': ['plugin'],
        },
        config_schema=[
            {'name': 'model', 'type': 'model-fallback-selector'},
            {'name': 'knowledge-bases', 'type': 'knowledge-base-multi-selector', 'default': []},
        ],
    )


def make_query():
    async def fake_func(**kwargs):
        return kwargs

    message_chain = platform_message.MessageChain(
        [
            platform_message.Source(
                id='msg_001',
                time=datetime.datetime(2026, 5, 15, 12, 0, 0),
            ),
            platform_message.Plain(text='hello'),
            platform_message.File(name='spec.txt', url='https://example.com/spec.txt'),
        ]
    )
    sender = platform_entities.Friend(id='user_001', nickname='Alice', remark=None)
    message_event = platform_events.FriendMessage(sender=sender, message_chain=message_chain, time=1_784_098_800.0)
    session = types.SimpleNamespace(
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id='user_001',
        sender_id='user_001',
        using_conversation=FakeConversation(),
    )

    return types.SimpleNamespace(
        query_id=1001,
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id='user_001',
        sender_id='user_001',
        message_event=message_event,
        message_chain=message_chain,
        bot_uuid='bot_001',
        pipeline_uuid='pipeline_001',
        pipeline_config={
            'ai': {
                'runner': {'id': RUNNER_ID},
                'runner_config': {
                    RUNNER_ID: {
                        'model': {'primary': 'model_primary', 'fallbacks': ['model_fallback']},
                        'knowledge-bases': ['kb_001'],
                        'timeout': 30,
                    },
                },
            },
        },
        session=session,
        messages=[],
        user_message=provider_message.Message(
            role='user',
            content=[
                provider_message.ContentElement.from_text('hello'),
                provider_message.ContentElement.from_file_url('https://example.com/spec.txt', 'spec.txt'),
            ],
        ),
        variables={
            '_pipeline_bound_plugins': ['langbot-team/LocalAgent'],
            '_fallback_model_uuids': ['model_fallback'],
            '_pipeline_bound_skills': ['demo'],
            '_host_tool_source_refs': {
                'langbot/test-tool/search': {
                    'source': 'plugin',
                    'source_id': 'langbot/test-tool',
                },
            },
            'public_param': 'visible',
        },
        use_llm_model_uuid='model_primary',
        use_funcs=[
            resource_tool.LLMTool(
                name='langbot/test-tool/search',
                human_desc='Search',
                description='Search test data',
                parameters={'type': 'object', 'properties': {'q': {'type': 'string'}}},
                func=fake_func,
            )
        ],
    )


def test_context_builder_includes_consumable_base64_attachments():
    query = make_query()
    query.user_message = provider_message.Message(
        role='user',
        content=[
            provider_message.ContentElement.from_text('see attached'),
            provider_message.ContentElement.from_image_base64('data:image/png;base64,aGVsbG8='),
            provider_message.ContentElement.from_file_base64('data:text/plain;base64,aGVsbG8=', 'hello.txt'),
        ],
    )
    query.message_chain = platform_message.MessageChain(
        [platform_message.Image(base64='data:image/jpeg;base64,aGVsbG8=')]
    )

    input_data = QueryEntryAdapter._build_input(query)

    assert input_data.contents[0].text == 'see attached'
    assert input_data.contents[1].image_base64 == 'data:image/png;base64,aGVsbG8='
    assert input_data.contents[2].file_base64 == 'data:text/plain;base64,aGVsbG8='

    attachment_types = [attachment.type for attachment in input_data.attachments]
    assert attachment_types == ['image', 'file', 'image']
    assert input_data.attachments[1].name == 'hello.txt'


def test_context_builder_deduplicates_message_chain_attachments():
    query = make_query()
    query.user_message = None
    query.message_chain = platform_message.MessageChain(
        [platform_message.Image(base64='data:image/jpeg;base64,aGVsbG8=')]
    )

    input_data = QueryEntryAdapter._build_input(query)

    assert [content.type for content in input_data.contents] == ['image_base64']
    assert len(input_data.attachments) == 1
    assert input_data.attachments[0].type == 'image'
    assert input_data.attachments[0].content == 'data:image/jpeg;base64,aGVsbG8='


def test_context_builder_preserves_same_source_duplicate_attachments():
    query = make_query()
    query.user_message = provider_message.Message(
        role='user',
        content=[
            provider_message.ContentElement.from_image_base64('data:image/png;base64,aGVsbG8='),
            provider_message.ContentElement.from_image_base64('data:image/png;base64,aGVsbG8='),
        ],
    )
    query.message_chain = platform_message.MessageChain([])

    input_data = QueryEntryAdapter._build_input(query)

    assert [attachment.type for attachment in input_data.attachments] == ['image', 'image']


@pytest.fixture(autouse=True)
async def clean_agent_state():
    """Reset all singleton stores and create a test database engine."""
    from langbot.pkg.entity.persistence.base import Base

    reset_persistent_state_store()
    registry = get_session_registry()
    for session in await registry.list_active_runs():
        await registry.unregister(session['run_id'])

    # Create in-memory SQLite engine for tests
    test_engine = create_async_engine('sqlite+aiosqlite:///:memory:')

    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    # Cleanup
    for session in await registry.list_active_runs():
        await registry.unregister(session['run_id'])
    reset_persistent_state_store()
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_orchestrator_runs_fake_plugin_with_authorized_context(clean_agent_state):
    """Test that orchestrator properly builds and passes authorized context to runner."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                'type': 'message.completed',
                'data': {'message': {'role': 'assistant', 'content': 'fake response'}},
            }
        ]
    )
    ap = FakeApplication(plugin_connector, db_engine)
    orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
    query = make_query()

    messages = [message async for message in orchestrator.run_from_query(query)]

    assert len(messages) == 1
    assert messages[0].content == 'fake response'
    assert plugin_connector.calls == [
        {
            'plugin_author': 'langbot-team',
            'plugin_name': 'LocalAgent',
            'runner_name': 'default',
        }
    ]

    context = plugin_connector.contexts[0]
    assert context['config']['timeout'] == 30
    assert context['runtime']['deadline_at'] is not None
    # Protocol v1: params is in adapter.extra
    assert context['adapter']['extra']['params'] == {'public_param': 'visible'}
    assert context['event']['event_type'] == 'message.received'
    # Note: source_event_type is in event.source_event_type, not event.data
    # (event.data contains the raw event payload, not metadata)
    assert context['actor']['actor_id'] == 'user_001'
    assert context['actor']['actor_name'] == 'Alice'
    assert context['subject']['subject_id'] == 'msg_001'
    assert context['input']['attachments']
    assert context['context']['available_apis']['run_get'] is True
    assert context['context']['available_apis']['run_list'] is True
    assert context['context']['available_apis']['run_events_page'] is True
    assert context['context']['available_apis']['run_cancel'] is True
    assert context['context']['available_apis']['run_append_result'] is False
    assert context['context']['available_apis']['run_finalize'] is False
    assert context['context']['available_apis']['run_claim'] is False
    assert context['context']['available_apis']['run_renew_claim'] is False
    assert context['context']['available_apis']['run_release_claim'] is False
    assert context['context']['available_apis']['runtime_register'] is False
    assert context['context']['available_apis']['runtime_heartbeat'] is False
    assert context['context']['available_apis']['runtime_list'] is False

    resources = context['resources']
    assert {m['model_id'] for m in resources['models']} == {'model_primary', 'model_fallback'}
    assert resources['tools'][0]['tool_name'] == 'langbot/test-tool/search'
    assert resources['knowledge_bases'][0]['kb_id'] == 'kb_001'
    assert resources['skills'] == [
        {
            'skill_name': 'demo',
            'display_name': 'Demo Skill',
            'description': 'Helps with demo tasks.',
        }
    ]
    assert resources['storage']['plugin_storage'] is True

    session_during_run = plugin_connector.sessions_during_run[0]
    assert session_during_run is not None
    assert session_during_run['plugin_identity'] == 'langbot-team/LocalAgent'
    assert session_during_run['authorization']['authorized_ids']['tool'] == {'langbot/test-tool/search'}
    assert session_during_run['authorization']['authorized_ids']['skill'] == {'demo'}
    assert await get_session_registry().get(context['run_id']) is None


@pytest.mark.asyncio
async def test_orchestrator_persists_run_ledger(clean_agent_state):
    """AgentRunOrchestrator records Host-owned run and result events."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                'type': 'message.completed',
                'data': {'message': {'role': 'assistant', 'content': 'fake response'}},
            },
            {
                'type': 'run.completed',
                'data': {'finish_reason': 'stop'},
                'usage': {'prompt_tokens': 2, 'completion_tokens': 3, 'total_tokens': 5},
            },
        ]
    )
    ap = FakeApplication(plugin_connector, db_engine)
    orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))

    messages = [message async for message in orchestrator.run_from_query(make_query())]

    assert len(messages) == 1
    run_id = plugin_connector.contexts[0]['run_id']
    store = RunLedgerStore(db_engine)

    run = await store.get_run(run_id)
    assert run is not None
    assert run['status'] == 'completed'
    assert run['event_id'] == plugin_connector.contexts[0]['event']['event_id']
    assert run['runner_id'] == RUNNER_ID
    assert run['usage'] == {
        'prompt_tokens': 2,
        'completion_tokens': 3,
        'total_tokens': 5,
    }

    events, next_cursor, prev_cursor, has_more = await store.page_run_events(
        run_id=run_id,
        limit=10,
    )
    assert [event['sequence'] for event in events] == [1, 2]
    assert [event['type'] for event in events] == ['message.completed', 'run.completed']
    assert next_cursor is None
    assert prev_cursor == 1
    assert has_more is False


@pytest.mark.asyncio
async def test_orchestrator_stops_after_cancel_request(clean_agent_state):
    """A persisted cancel request stops further synchronous runner consumption."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                'type': 'message.completed',
                'data': {'message': {'role': 'assistant', 'content': 'first'}},
            },
            {
                'type': 'message.completed',
                'data': {'message': {'role': 'assistant', 'content': 'second'}},
            },
        ]
    )
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector, db_engine), FakeRegistry(descriptor))
    original_append_run_result = orchestrator.journal.append_run_result
    cancel_requested = False

    async def append_and_cancel_once(*args, **kwargs):
        nonlocal cancel_requested
        event = await original_append_run_result(*args, **kwargs)
        if not cancel_requested:
            cancel_requested = True
            await RunLedgerStore(db_engine).request_cancel(
                run_id=kwargs['run_id'],
                status_reason='user stopped',
            )
        return event

    orchestrator.journal.append_run_result = append_and_cancel_once

    messages = [message async for message in orchestrator.run_from_query(make_query())]

    assert [message.content for message in messages] == ['first']
    run_id = plugin_connector.contexts[0]['run_id']
    run = await RunLedgerStore(db_engine).get_run(run_id)
    assert run is not None
    assert run['status'] == 'cancelled'
    assert run['status_reason'] == 'user stopped'


@pytest.mark.asyncio
async def test_orchestrator_does_not_package_query_messages_into_context(clean_agent_state):
    """Host should not build an agent working-context window from query.messages."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                'type': 'message.completed',
                'data': {'message': {'role': 'assistant', 'content': 'fake response'}},
            }
        ]
    )
    ap = FakeApplication(plugin_connector, db_engine)
    orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
    query = make_query()
    query.pipeline_config['ai']['runner_config'][RUNNER_ID]['custom-option'] = 2
    query.messages = [
        provider_message.Message(role='user', content='message 1'),
        provider_message.Message(role='assistant', content='response 1'),
        provider_message.Message(role='user', content='message 2'),
        provider_message.Message(role='assistant', content='response 2'),
        provider_message.Message(role='user', content='message 3'),
        provider_message.Message(role='assistant', content='response 3'),
    ]

    messages = [message async for message in orchestrator.run_from_query(query)]

    assert len(messages) == 1
    context = plugin_connector.contexts[0]
    assert context['config']['custom-option'] == 2
    assert 'bootstrap' not in context
    assert set(context['adapter']) == {'extra'}
    assert 'context_packaging' not in context['runtime']['metadata']
    assert [message.content for message in query.messages] == [
        'message 1',
        'response 1',
        'message 2',
        'response 2',
        'message 3',
        'response 3',
    ]


@pytest.mark.asyncio
async def test_orchestrator_streams_fake_plugin_deltas(clean_agent_state):
    """Test that orchestrator properly streams message chunks."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {'type': 'message.delta', 'data': {'chunk': {'role': 'assistant', 'content': 'hel'}}},
            {'type': 'message.delta', 'data': {'chunk': {'role': 'assistant', 'content': 'hello'}}},
            {'type': 'run.completed', 'data': {'finish_reason': 'stop'}},
        ]
    )
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector, db_engine), FakeRegistry(descriptor))

    chunks = [message async for message in orchestrator.run_from_query(make_query())]

    assert [chunk.content for chunk in chunks] == ['hel', 'hello']


@pytest.mark.asyncio
async def test_orchestrator_persists_run_completed_message_transcript(clean_agent_state):
    """run.completed(message=...) should be treated as the final assistant transcript."""
    from langbot.pkg.agent.runner.transcript_store import TranscriptStore

    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                'type': 'run.completed',
                'data': {
                    'finish_reason': 'stop',
                    'message': {'role': 'assistant', 'content': 'final response'},
                },
            },
        ]
    )
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector, db_engine), FakeRegistry(descriptor))
    query = make_query()

    messages = [message async for message in orchestrator.run_from_query(query)]

    assert [message.content for message in messages] == ['final response']
    transcript_store = TranscriptStore(db_engine)
    transcripts, _, _, _ = await transcript_store.page_transcript(query.session.using_conversation.uuid, limit=10)
    assistant_items = [item for item in transcripts if item['role'] == 'assistant']
    assert len(assistant_items) == 1
    assert assistant_items[0]['content'] == 'final response'


@pytest.mark.asyncio
async def test_orchestrator_drops_duplicate_result_sequence(clean_agent_state):
    """Duplicate runner result sequences are idempotently ignored."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                'type': 'message.delta',
                'sequence': 1,
                'data': {'chunk': {'role': 'assistant', 'content': 'first'}},
            },
            {
                'type': 'message.delta',
                'sequence': 1,
                'data': {'chunk': {'role': 'assistant', 'content': 'duplicate'}},
            },
            {
                'type': 'message.delta',
                'sequence': 3,
                'data': {'chunk': {'role': 'assistant', 'content': 'after-gap'}},
            },
            {'type': 'run.completed', 'sequence': 4, 'data': {'finish_reason': 'stop'}},
        ]
    )
    ap = FakeApplication(plugin_connector, db_engine)
    orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))

    chunks = [message async for message in orchestrator.run_from_query(make_query())]

    assert [chunk.content for chunk in chunks] == ['first', 'after-gap']
    assert any('duplicate result sequence 1' in warning for warning in ap.logger.warnings)
    assert any('result sequence gap or out-of-order' in warning for warning in ap.logger.warnings)


@pytest.mark.asyncio
async def test_orchestrator_applies_state_updates_and_suppresses_protocol_event(clean_agent_state):
    """Test that state.updated events are applied and not yielded to pipeline."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                'type': 'state.updated',
                'data': {
                    'scope': 'conversation',
                    'key': 'external.conversation_id',
                    'value': 'external_conv_123',
                },
            },
            {
                'type': 'message.completed',
                'data': {'message': {'role': 'assistant', 'content': 'state saved'}},
            },
        ]
    )
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector, db_engine), FakeRegistry(descriptor))
    query = make_query()

    messages = [message async for message in orchestrator.run_from_query(query)]

    assert [message.content for message in messages] == ['state saved']
    # State is persisted to the database via PersistentStateStore.


@pytest.mark.asyncio
async def test_orchestrator_unregisters_session_after_runner_failure(clean_agent_state):
    """Test that session is unregistered even when runner fails."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                'type': 'run.failed',
                'data': {'error': 'boom', 'code': 'fake.error', 'retryable': False},
            }
        ]
    )
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector, db_engine), FakeRegistry(descriptor))

    with pytest.raises(RunnerExecutionError):
        [message async for message in orchestrator.run_from_query(make_query())]

    context = plugin_connector.contexts[0]
    assert plugin_connector.sessions_during_run[0] is not None
    assert await get_session_registry().get(context['run_id']) is None


@pytest.mark.asyncio
async def test_orchestrator_unregisters_session_after_event_log_failure(clean_agent_state):
    """Journal failures before runner invocation must not leave steerable sessions."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                'type': 'message.completed',
                'data': {'message': {'role': 'assistant', 'content': 'unused'}},
            }
        ]
    )
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector, db_engine), FakeRegistry(descriptor))
    orchestrator.journal.write_event_log = AsyncMock(side_effect=RuntimeError('journal unavailable'))

    with pytest.raises(RuntimeError, match='journal unavailable'):
        [message async for message in orchestrator.run_from_query(make_query())]

    assert plugin_connector.contexts == []
    assert await get_session_registry().list_active_runs() == []


@pytest.mark.asyncio
async def test_unconsumed_steering_audit_does_not_persist_pinned_context(clean_agent_state):
    """Dropped steering audits retain routing metadata but never execution-only context."""
    from langbot.pkg.agent.runner.event_log_store import EventLogStore

    class BlockingPluginConnector(FakePluginConnector):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def run_agent(self, plugin_author, plugin_name, runner_name, context):
            self.calls.append(
                {
                    'plugin_author': plugin_author,
                    'plugin_name': plugin_name,
                    'runner_name': runner_name,
                }
            )
            self.contexts.append(context)
            self.sessions_during_run.append(await get_session_registry().get(context['run_id']))
            self.started.set()
            await self.release.wait()
            yield {
                'type': 'message.completed',
                'data': {'message': {'role': 'assistant', 'content': 'response'}},
            }

    db_engine = clean_agent_state
    descriptor = make_descriptor()
    descriptor.capabilities.steering = True
    plugin_connector = BlockingPluginConnector()
    ap = FakeApplication(plugin_connector, db_engine)
    pinned_context = 'PINNED_CONTEXT_MUST_NOT_BE_PERSISTED'

    async def build_resource_context(query):
        attachments = query.variables.get('_pipeline_mcp_resource_attachments', [])
        return pinned_context if attachments else ''

    mcp_loader = types.SimpleNamespace(build_resource_context_for_query=AsyncMock(side_effect=build_resource_context))
    ap.tool_mgr = types.SimpleNamespace(mcp_tool_loader=mcp_loader)
    orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))

    active_query = make_query()

    async def consume_active_run():
        return [message async for message in orchestrator.run_from_query(active_query)]

    active_task = asyncio.create_task(consume_active_run())
    await asyncio.wait_for(plugin_connector.started.wait(), timeout=1)

    steering_query = make_query()
    steering_query.query_id = 1002
    steering_query.message_chain[0].id = 'msg_002'
    steering_query.variables['_pipeline_mcp_resource_attachments'] = [
        {
            'server_uuid': 'srv-1',
            'server_name': 'docs',
            'uri': 'file:///README.md',
            'mode': 'pinned',
        }
    ]
    steering_query.variables['_pipeline_mcp_resource_agent_read_enabled'] = True

    try:
        claimed = await orchestrator.try_claim_steering_from_query(steering_query)
    finally:
        plugin_connector.release.set()

    messages = await asyncio.wait_for(active_task, timeout=1)
    assert claimed is True
    assert len(messages) == 1

    event_store = EventLogStore(db_engine)
    event_logs, _, _ = await event_store.page_events(
        conversation_id=steering_query.session.using_conversation.uuid,
        limit=10,
    )
    dropped = next(event for event in event_logs if event['event_type'] == 'steering.dropped')
    queued = next(
        event
        for event in event_logs
        if event['event_type'] == 'message.received'
        and event.get('metadata', {}).get('steering', {}).get('status') == 'queued'
    )

    assert dropped['input_summary'] == 'Unconsumed steering input dropped'
    assert dropped['input_json'] is None
    assert dropped['metadata']['steering']['original_event_id'] == queued['event_id']
    assert pinned_context not in str(event_logs)


@pytest.mark.asyncio
async def test_orchestrator_enforces_total_runner_deadline(clean_agent_state):
    """Test that orchestrator enforces total runner timeout."""
    db_engine = clean_agent_state
    descriptor = make_descriptor()
    plugin_connector = FakePluginConnector(
        results=[
            {
                'type': 'message.completed',
                'data': {'message': {'role': 'assistant', 'content': 'too late'}},
            }
        ],
        delay=0.05,
    )
    orchestrator = AgentRunOrchestrator(FakeApplication(plugin_connector, db_engine), FakeRegistry(descriptor))
    query = make_query()
    query.pipeline_config['ai']['runner_config'][RUNNER_ID]['timeout'] = 0.01

    with pytest.raises(RunnerExecutionError) as exc_info:
        [message async for message in orchestrator.run_from_query(query)]

    assert exc_info.value.retryable is True
    assert 'runner.timeout' in str(exc_info.value)
    assert await get_session_registry().list_active_runs() == []


class TestQueryEntrySessionQueryId:
    """Tests for internal query_id entering session registry."""

    @pytest.mark.asyncio
    async def test_query_box_scope_exists_before_attachment_materialization(self, clean_agent_state):
        """Inbound staging and later runner tools resolve to the same Box session."""
        from langbot.pkg.box.service import BoxService

        class CapturingBoxService:
            available = True

            def __init__(self):
                self.resolver = object.__new__(BoxService)
                self.materialize_session_id = None

            async def materialize_inbound_attachments(self, query):
                self.materialize_session_id = self.resolver.resolve_box_session_id(query)
                return []

        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    'type': 'message.completed',
                    'data': {'message': {'role': 'assistant', 'content': 'response'}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        box_service = CapturingBoxService()
        ap.box_service = box_service
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()

        messages = [message async for message in orchestrator.run_from_query(query)]

        assert len(messages) == 1
        session = plugin_connector.sessions_during_run[0]
        assert session is not None
        assert session['execution_query'] is query
        runner_session_id = box_service.resolver.resolve_box_session_id(session['execution_query'])
        assert box_service.materialize_session_id == runner_session_id
        assert query.variables['_host_box_scope']

    @pytest.mark.asyncio
    async def test_query_id_registered_in_session_for_query_entry_flow(self, clean_agent_state):
        """query_id from Query entry flow is registered internally in session."""
        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    'type': 'message.completed',
                    'data': {'message': {'role': 'assistant', 'content': 'response'}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()
        query.user_message = provider_message.Message(
            role='user',
            content=[
                provider_message.ContentElement.from_text('hello'),
                provider_message.ContentElement.from_image_base64('data:image/png;base64,aGVsbG8='),
                provider_message.ContentElement.from_file_base64('data:text/plain;base64,aGVsbG8=', 'hello.txt'),
            ],
        )

        messages = [message async for message in orchestrator.run_from_query(query)]

        assert len(messages) == 1
        # Verify session during run had query_id
        session_during_run = plugin_connector.sessions_during_run[0]
        assert session_during_run is not None
        assert session_during_run['query_id'] == query.query_id
        assert session_during_run['execution_query'] is query
        assert query.pipeline_uuid == 'pipeline_001'
        assert query.pipeline_config is not None

    @pytest.mark.asyncio
    async def test_no_query_id_for_pure_event_first_flow(self, clean_agent_state):
        """Pure event-first flow has query_id=None in session."""
        from langbot.pkg.agent.runner.host_models import (
            AgentEventEnvelope,
            AgentBinding,
            BindingScope,
            StatePolicy,
            DeliveryPolicy,
            ResourcePolicy,
        )
        from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
        from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext

        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    'type': 'message.completed',
                    'data': {'message': {'role': 'assistant', 'content': 'response'}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        mcp_loader = types.SimpleNamespace(
            build_resource_context_for_query=AsyncMock(return_value='Pinned documentation')
        )
        ap.tool_mgr = types.SimpleNamespace(mcp_tool_loader=mcp_loader)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))

        # Create event and binding directly (not from Query)
        event = AgentEventEnvelope(
            event_id='evt_001',
            event_type='message.received',
            event_time=1234567890,
            source='test',
            bot_id='bot_001',
            workspace_id=None,
            conversation_id='conv_001',
            thread_id=None,
            actor=None,
            subject=None,
            input=AgentInput(
                text='hello',
                contents=[provider_message.ContentElement.from_text('hello')],
                attachments=[],
            ),
            delivery=DeliveryContext(surface='test', supports_streaming=True),
        )
        binding = AgentBinding(
            binding_id='binding_001',
            scope=BindingScope(scope_type='agent', scope_id='pipeline_001'),
            event_types=['message.received'],
            runner_id=RUNNER_ID,
            runner_config={
                'mcp-resources': [
                    {
                        'server_uuid': 'srv-1',
                        'server_name': 'docs',
                        'uri': 'file:///README.md',
                        'mode': 'pinned',
                    }
                ],
                'mcp-resource-agent-read-enabled': True,
            },
            resource_policy=ResourcePolicy(),
            state_policy=StatePolicy(enable_state=False, state_scopes=[]),
            delivery_policy=DeliveryPolicy(enable_streaming=True, enable_reply=True),
            enabled=True,
        )

        messages = [message async for message in orchestrator.run(event, binding)]

        assert len(messages) == 1
        # Verify session during run has query_id=None
        session_during_run = plugin_connector.sessions_during_run[0]
        assert session_during_run is not None
        assert session_during_run['query_id'] is None
        execution_query = session_during_run['execution_query']
        assert execution_query is not None
        assert execution_query.pipeline_uuid is None
        assert execution_query.pipeline_config is None
        assert execution_query.bot_uuid == event.bot_id
        assert execution_query.launcher_id == event.conversation_id
        assert execution_query.sender_id == event.conversation_id
        assert execution_query.session.launcher_id == event.conversation_id
        assert execution_query.message_event.type == event.event_type
        assert execution_query.variables['_host_box_scope']
        assert execution_query.variables['_pipeline_bound_skills'] == ['demo', 'hidden']
        assert execution_query.variables['_pipeline_mcp_resource_attachments'][0]['server_uuid'] == 'srv-1'
        assert execution_query.variables['_pipeline_mcp_resource_agent_read_enabled'] is True
        assert 'MCP resource context selected by LangBot host:' in plugin_connector.contexts[0]['input']['text']
        assert 'Pinned documentation' in plugin_connector.contexts[0]['input']['text']
        assert 'Pinned documentation' in plugin_connector.contexts[0]['input']['contents'][0]['text']
        assert event.input.text == 'hello'
        assert event.input.contents[0].text == 'hello'
        assert 'Pinned documentation' not in str(execution_query.user_message.content)
        mcp_loader.build_resource_context_for_query.assert_awaited_once_with(execution_query)


class TestQueryEntryAdapterParams:
    """Tests for params handling in Query entry adapter."""

    @pytest.mark.asyncio
    async def test_prompt_not_pushed_into_adapter_extra(self, clean_agent_state):
        """Pipeline prompt is not pushed into adapter.extra; runners pull it through prompt_get."""
        from langbot_plugin.api.entities.builtin.provider import prompt as provider_prompt

        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    'type': 'message.completed',
                    'data': {'message': {'role': 'assistant', 'content': 'response'}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()

        # Add prompt to query
        query.prompt = provider_prompt.Prompt(
            name='test_prompt',
            messages=[
                provider_message.Message(role='system', content='You are a helpful assistant.'),
            ],
        )

        _messages = [message async for message in orchestrator.run_from_query(query)]

        context = plugin_connector.contexts[0]
        assert 'prompt' not in context
        assert 'prompt' not in context['adapter']['extra']
        assert context['context']['available_apis']['prompt_get'] is True

    @pytest.mark.asyncio
    async def test_params_filtering_keeps_public_param(self, clean_agent_state):
        """Public params are kept."""
        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    'type': 'message.completed',
                    'data': {'message': {'role': 'assistant', 'content': 'response'}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()
        query.variables = {
            'public_param': 'visible',
            'another_param': 123,
        }

        _messages = [message async for message in orchestrator.run_from_query(query)]

        context = plugin_connector.contexts[0]
        assert context['adapter']['extra']['params'] == {
            'public_param': 'visible',
            'another_param': 123,
        }

    @pytest.mark.asyncio
    async def test_params_filtering_removes_internal_vars(self, clean_agent_state):
        """Internal variables (starting with _) are filtered."""
        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    'type': 'message.completed',
                    'data': {'message': {'role': 'assistant', 'content': 'response'}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()
        query.variables = {
            'public_param': 'visible',
            '_internal_var': 'should_be_filtered',
            '_pipeline_bound_plugins': ['plugin1'],
        }

        _messages = [message async for message in orchestrator.run_from_query(query)]

        context = plugin_connector.contexts[0]
        params = context['adapter']['extra']['params']
        assert 'public_param' in params
        assert '_internal_var' not in params
        assert '_pipeline_bound_plugins' not in params

    @pytest.mark.asyncio
    async def test_params_filtering_removes_sensitive_patterns(self, clean_agent_state):
        """Sensitive naming patterns are filtered."""
        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    'type': 'message.completed',
                    'data': {'message': {'role': 'assistant', 'content': 'response'}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()
        query.variables = {
            'public_param': 'visible',
            'api_token': 'secret123',
            'secret_key': 'secret456',
            'password': 'secret789',
            'credential': 'secret000',
        }

        _messages = [message async for message in orchestrator.run_from_query(query)]

        context = plugin_connector.contexts[0]
        params = context['adapter']['extra']['params']
        assert 'public_param' in params
        assert 'api_token' not in params
        assert 'secret_key' not in params
        assert 'password' not in params
        assert 'credential' not in params

    @pytest.mark.asyncio
    async def test_params_filtering_removes_non_json_serializable(self, clean_agent_state):
        """Non-JSON-serializable values are filtered."""
        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    'type': 'message.completed',
                    'data': {'message': {'role': 'assistant', 'content': 'response'}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()
        query.variables = {
            'public_param': 'visible',
            'a_set': {1, 2, 3},  # set is not JSON-serializable
            'a_lambda': lambda x: x,  # function is not JSON-serializable
        }

        _messages = [message async for message in orchestrator.run_from_query(query)]

        context = plugin_connector.contexts[0]
        params = context['adapter']['extra']['params']
        assert 'public_param' in params
        assert 'a_set' not in params
        assert 'a_lambda' not in params


class TestQueryEntryAdapterHostCapabilities:
    """Tests for event-first host capabilities via Query entry adapter path."""

    @pytest.mark.asyncio
    async def test_state_updated_writes_to_persistent_store(self, clean_agent_state):
        """state.updated via Pipeline path writes to PersistentStateStore."""
        from langbot.pkg.agent.runner.persistent_state_store import get_persistent_state_store

        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    'type': 'state.updated',
                    'data': {
                        'scope': 'conversation',
                        'key': 'external.test_key',
                        'value': 'test_value',
                    },
                },
                {
                    'type': 'message.completed',
                    'data': {'message': {'role': 'assistant', 'content': 'state saved'}},
                },
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()
        query.user_message = provider_message.Message(
            role='user',
            content=[
                provider_message.ContentElement.from_text('hello'),
                provider_message.ContentElement.from_image_base64('data:image/png;base64,aGVsbG8='),
            ],
        )

        messages = [message async for message in orchestrator.run_from_query(query)]

        assert len(messages) == 1
        assert messages[0].content == 'state saved'

        # Verify state was written to PersistentStateStore
        persistent_store = get_persistent_state_store(db_engine)
        # Build snapshot to check if state was written
        # Note: We need to rebuild the event and binding to query the store
        from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter

        event = QueryEntryAdapter.query_to_event(query)
        agent_config = QueryEntryAdapter.config_to_agent_config(query, RUNNER_ID)
        binding = AgentBindingResolver().resolve_one(event, [agent_config])

        snapshot = await persistent_store.build_snapshot_from_event(event, binding, descriptor)
        assert snapshot['conversation']['external.test_key'] == 'test_value'

    @pytest.mark.asyncio
    async def test_run_from_query_restores_activated_skills_from_state(self, clean_agent_state):
        """Persisted activated skill names are restored into the next Query run."""
        from langbot.pkg.agent.runner.persistent_state_store import get_persistent_state_store
        from langbot.pkg.provider.tools.loaders.skill import (
            ACTIVATED_SKILL_NAMES_STATE_KEY,
            ACTIVATED_SKILLS_KEY,
        )

        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    'type': 'message.completed',
                    'data': {'message': {'role': 'assistant', 'content': 'restored'}},
                }
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()

        persistent_store = get_persistent_state_store(db_engine)
        event = QueryEntryAdapter.query_to_event(query)
        agent_config = QueryEntryAdapter.config_to_agent_config(query, RUNNER_ID)
        binding = AgentBindingResolver().resolve_one(event, [agent_config])
        success, error = await persistent_store.apply_update_from_event(
            event,
            binding,
            descriptor,
            'conversation',
            ACTIVATED_SKILL_NAMES_STATE_KEY,
            ['demo'],
            None,
        )
        assert success is True
        assert error is None

        messages = [message async for message in orchestrator.run_from_query(query)]

        assert len(messages) == 1
        assert query.variables[ACTIVATED_SKILLS_KEY]['demo']['name'] == 'demo'

    @pytest.mark.asyncio
    async def test_event_log_and_transcript_written(self, clean_agent_state):
        """EventLog and Transcript are written via Pipeline path."""
        from langbot.pkg.agent.runner.event_log_store import EventLogStore
        from langbot.pkg.agent.runner.transcript_store import TranscriptStore

        db_engine = clean_agent_state
        descriptor = make_descriptor()
        plugin_connector = FakePluginConnector(
            results=[
                {
                    'type': 'message.completed',
                    'data': {'message': {'role': 'assistant', 'content': 'assistant response'}},
                },
            ]
        )
        ap = FakeApplication(plugin_connector, db_engine)
        mcp_loader = types.SimpleNamespace(
            build_resource_context_for_query=AsyncMock(return_value='Pinned documentation')
        )
        ap.tool_mgr = types.SimpleNamespace(mcp_tool_loader=mcp_loader)
        orchestrator = AgentRunOrchestrator(ap, FakeRegistry(descriptor))
        query = make_query()
        query.variables['_pipeline_mcp_resource_attachments'] = [
            {
                'server_uuid': 'srv-1',
                'server_name': 'docs',
                'uri': 'file:///README.md',
                'mode': 'pinned',
            }
        ]
        query.variables['_pipeline_mcp_resource_agent_read_enabled'] = True
        query.user_message = provider_message.Message(
            role='user',
            content=[
                provider_message.ContentElement.from_text('hello'),
                provider_message.ContentElement.from_image_base64('data:image/png;base64,aGVsbG8='),
            ],
        )

        messages = [message async for message in orchestrator.run_from_query(query)]

        assert len(messages) == 1
        assert 'Pinned documentation' in plugin_connector.contexts[0]['input']['text']

        # Check EventLog has incoming event
        event_log_store = EventLogStore(db_engine)
        event_logs, _, _ = await event_log_store.page_events(
            conversation_id=query.session.using_conversation.uuid,
            limit=10,
        )
        assert len(event_logs) >= 1
        # First event should be the incoming message.received
        assert event_logs[0]['event_type'] == 'message.received'
        assert event_logs[0]['input_json']['contents'][1]['image_base64'] is None
        assert event_logs[0]['input_json']['contents'][1]['content_redacted'] is True
        assert 'aGVsbG8=' not in str(event_logs[0]['input_json'])
        assert 'Pinned documentation' not in str(event_logs[0]['input_json'])

        # Check Transcript has user and assistant messages
        transcript_store = TranscriptStore(db_engine)
        transcripts, _, _, _ = await transcript_store.page_transcript(
            conversation_id=query.session.using_conversation.uuid,
            limit=10,
            include_attachments=True,
        )
        assert len(transcripts) >= 2
        # Find user and assistant messages
        roles = [t['role'] for t in transcripts]
        assert 'user' in roles
        assert 'assistant' in roles
        user_item = next(t for t in transcripts if t['role'] == 'user')
        assert user_item['content_json']['content'][1]['image_base64'] is None
        assert user_item['attachment_refs'][0]['content'] is None
        assert 'aGVsbG8=' not in str(user_item)
        assert 'Pinned documentation' not in str(user_item)
