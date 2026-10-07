"""
Unit tests for ChatMessageHandler - REAL imports.

Tests the actual ChatMessageHandler class from production code.
Uses tests.utils.import_isolation to break circular import chain safely.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock

from tests.factories import FakeApp


# ============== FIXTURE USING IMPORT ISOLATION UTILITY ==============


@pytest.fixture(scope='module')
def mock_circular_import_chain():
    """
    Break circular import chain using isolated_sys_modules.

    Chain: handler → core.app → pipeline.controller → http_controller → groups/plugins → taskmgr

    Uses tests.utils.import_isolation for safe, reversible sys.modules manipulation.
    """
    from tests.utils.import_isolation import (
        isolated_sys_modules,
        make_pipeline_handler_import_mocks,
        get_handler_modules_to_clear,
    )

    mocks = make_pipeline_handler_import_mocks()

    clear = get_handler_modules_to_clear('chat')

    with isolated_sys_modules(mocks=mocks, clear=clear):
        yield


@pytest.fixture
def fake_app():
    """Create FakeApp instance."""
    from langbot_plugin.api.entities.builtin.provider.message import Message

    app = FakeApp()

    class FakeAgentRunOrchestrator:
        runner_class = None

        async def try_claim_steering_from_query(self, query):
            return False

        async def run_from_query(self, query):
            if self.runner_class is None:
                yield Message(role='assistant', content='fake response')
                return

            runner = self.runner_class(app, {})
            async for result in runner.run(query):
                yield result

        def resolve_runner_id_for_telemetry(self, query):
            return 'plugin:langbot-team/LocalAgent/default'

    app.agent_run_orchestrator = FakeAgentRunOrchestrator()
    return app


@pytest.fixture
def mock_event_ctx():
    """Create mock event context."""
    ctx = Mock()
    ctx.is_prevented_default = Mock(return_value=False)
    ctx.event = Mock()
    ctx.event.user_message_alter = None
    ctx.event.reply_message_chain = None
    return ctx


@pytest.fixture
def set_runner(fake_app):
    """Configure the orchestrator test double for one test."""

    def _set_runner(runner_class):
        fake_app.agent_run_orchestrator.runner_class = runner_class

    return _set_runner


@pytest.fixture
def handler_query():
    """A prepared SDK query with history available for a successful handler turn."""
    from tests.factories import text_query
    from langbot_plugin.api.entities.builtin.provider.message import Message
    from langbot_plugin.api.entities.builtin.provider.prompt import Prompt
    from langbot_plugin.api.entities.builtin.provider.session import Conversation, Session

    query = text_query('original')
    query.user_message = Message(role='user', content='original')
    query.session = Session(
        launcher_type=query.launcher_type,
        launcher_id=query.launcher_id,
        using_conversation=Conversation(
            prompt=Prompt(name='test', messages=[]),
            messages=[],
            pipeline_uuid=query.pipeline_uuid,
            bot_uuid=query.bot_uuid,
        ),
    )
    return query


# ============== CACHED LAZY IMPORTS ==============

_chat_handler_module = None
_entities_module = None


def get_chat_handler():
    """Import ChatMessageHandler after circular import chain is mocked."""
    global _chat_handler_module
    if _chat_handler_module is None:
        from importlib import import_module

        _chat_handler_module = import_module('langbot.pkg.pipeline.process.handlers.chat')
    return _chat_handler_module


def get_entities():
    """Import pipeline entities - uses real module."""
    global _entities_module
    if _entities_module is None:
        from importlib import import_module

        _entities_module = import_module('langbot.pkg.pipeline.entities')
    return _entities_module


# ============== REAL ChatMessageHandler Tests ==============


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestChatMessageHandlerReal:
    """Tests for real ChatMessageHandler class."""

    @pytest.mark.asyncio
    async def test_real_import_works(self):
        """Verify we can import the real handler class."""
        chat = get_chat_handler()
        assert hasattr(chat, 'ChatMessageHandler')
        handler_cls = chat.ChatMessageHandler
        assert handler_cls.__name__ == 'ChatMessageHandler'

    @pytest.mark.asyncio
    async def test_handler_creation(self, fake_app):
        """ChatMessageHandler can be instantiated."""
        chat = get_chat_handler()
        handler = chat.ChatMessageHandler(fake_app)
        assert handler.ap is fake_app

    @pytest.mark.asyncio
    async def test_prevent_default_without_reply_interrupts(self, fake_app, mock_event_ctx):
        """prevent_default without reply chain yields INTERRUPT."""
        from tests.factories import text_query

        chat = get_chat_handler()
        entities = get_entities()

        mock_event_ctx.is_prevented_default.return_value = True
        mock_event_ctx.event.reply_message_chain = None
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        handler = chat.ChatMessageHandler(fake_app)
        query = text_query('hello')

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.INTERRUPT

    @pytest.mark.asyncio
    async def test_prevent_default_with_reply_continues(self, fake_app, mock_event_ctx):
        """prevent_default with reply yields CONTINUE and updates resp_messages."""
        from tests.factories import text_query, text_chain

        chat = get_chat_handler()
        entities = get_entities()

        reply_chain = text_chain('plugin reply')
        mock_event_ctx.is_prevented_default.return_value = True
        mock_event_ctx.event.reply_message_chain = reply_chain
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        handler = chat.ChatMessageHandler(fake_app)
        query = text_query('hello')
        query.resp_messages = []

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.CONTINUE
        assert len(query.resp_messages) == 1
        assert query.resp_messages[0] == reply_chain

    @pytest.mark.asyncio
    @pytest.mark.parametrize('alteration_kind', ['string', 'element', 'list'])
    async def test_user_message_alter_reaches_orchestrator(
        self, fake_app, mock_event_ctx, handler_query, alteration_kind
    ):
        """The runner receives the exact plugin alteration before it starts."""
        from langbot_plugin.api.entities.builtin.provider.message import ContentElement, Message

        expected = [ContentElement.from_text('altered text')]
        if alteration_kind == 'string':
            alteration = 'altered text'
        elif alteration_kind == 'element':
            alteration = expected[0]
        else:
            expected.append(ContentElement.from_image_url('https://example.com/input.png'))
            alteration = expected
        mock_event_ctx.event.user_message_alter = alteration
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)
        received = []

        async def run_from_query(query):
            received.append(query.user_message.model_copy(deep=True))
            yield Message(role='assistant', content='ok')

        fake_app.agent_run_orchestrator.run_from_query = run_from_query
        handler = get_chat_handler().ChatMessageHandler(fake_app)

        results = [result async for result in handler.handle(handler_query)]

        assert received == [Message(role='user', content=expected)]
        assert handler_query.user_message.content == expected
        assert len(results) == 1
        assert results[0].result_type == get_entities().ResultType.CONTINUE
        assert results[0].new_query is handler_query
        assert [message.content for message in handler_query.resp_messages] == ['ok']

    @pytest.mark.asyncio
    async def test_adapter_without_stream_method_defaults_non_stream(self, fake_app, mock_event_ctx, handler_query):
        """Missing stream support still delivers the completed turn exactly once."""
        from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk

        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)
        handler_query.adapter = Mock(spec=[])
        partial = MessageChunk(role='assistant', content='working')
        completed = Message(role='assistant', content='response')

        async def run_from_query(query):
            yield partial
            yield completed

        fake_app.agent_run_orchestrator.run_from_query = run_from_query
        handler = get_chat_handler().ChatMessageHandler(fake_app)
        observed = []

        async for result in handler.handle(handler_query):
            assert result.result_type == get_entities().ResultType.CONTINUE
            assert result.new_query is handler_query
            observed.append([message.content for message in result.new_query.resp_messages])

        assert observed == [['working', 'response']]
        assert handler_query.resp_messages == [partial, completed]


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestChatHandlerStreaming:
    """Tests for streaming behavior."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize('final_kind', ['message', 'chunk'])
    async def test_streaming_delivers_accumulated_text_and_one_final(
        self, fake_app, mock_event_ctx, handler_query, final_kind
    ):
        """Each yield updates the same card, preserving the full text and final flag."""
        from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk

        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)
        handler_query.adapter.is_stream_output_supported = AsyncMock(return_value=True)
        handler_query.adapter.create_message_card = AsyncMock()
        completed = (
            Message(role='assistant', content='Hello!')
            if final_kind == 'message'
            else MessageChunk(role='assistant', content='!', all_content='Hello!', is_final=True)
        )

        async def run_from_query(query):
            yield MessageChunk(role='assistant', content='Hel', all_content='Hel')
            yield MessageChunk(role='assistant', content='lo', all_content='Hello')
            yield completed

        fake_app.agent_run_orchestrator.run_from_query = run_from_query
        handler = get_chat_handler().ChatMessageHandler(fake_app)
        observed = []
        response_ids = []

        async for result in handler.handle(handler_query):
            assert result.result_type == get_entities().ResultType.CONTINUE
            assert result.new_query is handler_query
            assert len(result.new_query.resp_messages) == 1
            current = result.new_query.resp_messages[0]
            assert isinstance(current, MessageChunk)
            # Snapshot each yield: StageProcessResult points at the mutable query.
            observed.append((current.content, current.is_final))
            response_ids.append(current.resp_message_id)

        assert observed == [('Hel', False), ('Hello', False), ('Hello!', True)]
        assert response_ids[0]
        assert response_ids == [response_ids[0]] * 3
        handler_query.adapter.create_message_card.assert_awaited_once_with(response_ids[0], handler_query.message_event)


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestChatHandlerExceptions:
    """Tests for exception handling."""

    @pytest.mark.asyncio
    async def test_runner_exception_yields_interrupt(self, fake_app, mock_event_ctx, set_runner):
        """Runner exception yields INTERRUPT with error notices."""
        from tests.factories import text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message

        chat = get_chat_handler()
        entities = get_entities()

        mock_event_ctx.is_prevented_default.return_value = False
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        query = text_query('fail test')
        query.adapter = Mock()
        query.adapter.is_stream_output_supported = AsyncMock(return_value=False)
        query.user_message = Message(role='user', content=[])

        query.pipeline_config = {
            'output': {'misc': {'exception-handling': 'show-hint', 'failure-hint': 'Request failed.'}},
            'ai': {
                'runner': {'id': 'plugin:langbot-team/LocalAgent/default'},
                'runner_config': {
                    'plugin:langbot-team/LocalAgent/default': {
                        'prompt': 'default',
                        'model': {'primary': 'test'},
                    },
                },
            },
        }

        class FailingRunner:
            name = 'local-agent'

            def __init__(self, app, config):
                self.app = app
                self.config = config

            async def run(self, query):
                raise ValueError('API error')
                yield

        set_runner(FailingRunner)

        handler = chat.ChatMessageHandler(fake_app)

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.INTERRUPT
        assert results[0].user_notice == 'Request failed.'
        assert results[0].error_notice is not None

    @pytest.mark.asyncio
    async def test_exception_show_error_mode(self, fake_app, mock_event_ctx, set_runner):
        """show-error mode shows actual exception."""
        from tests.factories import text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message

        chat = get_chat_handler()

        mock_event_ctx.is_prevented_default.return_value = False
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        query = text_query('error test')
        query.adapter = Mock()
        query.adapter.is_stream_output_supported = AsyncMock(return_value=False)
        query.user_message = Message(role='user', content=[])

        query.pipeline_config = {
            'output': {'misc': {'exception-handling': 'show-error'}},
            'ai': {
                'runner': {'id': 'plugin:langbot-team/LocalAgent/default'},
                'runner_config': {
                    'plugin:langbot-team/LocalAgent/default': {
                        'prompt': 'default',
                        'model': {'primary': 'test'},
                    },
                },
            },
        }

        class ErrorRunner:
            name = 'local-agent'

            def __init__(self, app, config):
                self.app = app
                self.config = config

            async def run(self, query):
                raise ValueError('Custom error')
                yield

        set_runner(ErrorRunner)

        handler = chat.ChatMessageHandler(fake_app)

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert results[0].user_notice == 'Custom error'

    @pytest.mark.asyncio
    async def test_exception_hide_mode(self, fake_app, mock_event_ctx, set_runner):
        """hide mode shows no user notice."""
        from tests.factories import text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message

        chat = get_chat_handler()

        mock_event_ctx.is_prevented_default.return_value = False
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        query = text_query('hide test')
        query.adapter = Mock()
        query.adapter.is_stream_output_supported = AsyncMock(return_value=False)
        query.user_message = Message(role='user', content=[])

        query.pipeline_config = {
            'output': {'misc': {'exception-handling': 'hide'}},
            'ai': {
                'runner': {'id': 'plugin:langbot-team/LocalAgent/default'},
                'runner_config': {
                    'plugin:langbot-team/LocalAgent/default': {
                        'prompt': 'default',
                        'model': {'primary': 'test'},
                    },
                },
            },
        }

        class HideErrorRunner:
            name = 'local-agent'

            def __init__(self, app, config):
                self.app = app
                self.config = config

            async def run(self, query):
                raise RuntimeError('hidden')
                yield

        set_runner(HideErrorRunner)

        handler = chat.ChatMessageHandler(fake_app)

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert results[0].user_notice is None


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestChatHandlerHelper:
    """Tests for helper methods."""

    def test_cut_str_short(self, fake_app):
        """cut_str returns short string unchanged."""
        chat = get_chat_handler()
        handler = chat.ChatMessageHandler(fake_app)
        result = handler.cut_str('short text')
        assert result == 'short text'

    def test_cut_str_long(self, fake_app):
        """cut_str truncates long string."""
        chat = get_chat_handler()
        handler = chat.ChatMessageHandler(fake_app)
        result = handler.cut_str('this is a very long string that exceeds twenty characters')
        assert '...' in result
        assert len(result) <= 23

    def test_cut_str_multiline(self, fake_app):
        """cut_str truncates multiline string."""
        chat = get_chat_handler()
        handler = chat.ChatMessageHandler(fake_app)
        result = handler.cut_str('first line\nsecond line')
        assert '...' in result

    def test_response_size_limit_uses_instance_config(self, fake_app):
        from langbot_plugin.api.entities.builtin.provider.message import Message

        fake_app.instance_config.data['system'] = {'response_limits': {'max_generated_chars': 4}}
        chat = get_chat_handler()
        handler = chat.ChatMessageHandler(fake_app)

        with pytest.raises(RuntimeError, match='configured limit'):
            handler._check_response_size(Message(role='assistant', content='12345'))
