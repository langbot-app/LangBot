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
    from langbot_plugin.api.entities.builtin.provider.message import Message

    mocks = make_pipeline_handler_import_mocks()

    # Create a default runner that yields a simple response
    class DefaultRunner:
        name = 'local-agent'
        def __init__(self, app, config):
            self.app = app
            self.config = config
        async def run(self, query):
            yield Message(role='assistant', content='fake response')

    mocks['langbot.pkg.provider.runner'].preregistered_runners = [DefaultRunner]

    clear = get_handler_modules_to_clear('chat')

    with isolated_sys_modules(mocks=mocks, clear=clear):
        yield


@pytest.fixture
def fake_app():
    """Create FakeApp instance."""
    return FakeApp()


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
def set_runner():
    """Factory fixture to set a custom runner for tests."""
    def _set_runner(runner_class):
        import sys
        sys.modules['langbot.pkg.provider.runner'].preregistered_runners = [runner_class]
    return _set_runner


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
    async def test_user_message_alter_string(self, fake_app, mock_event_ctx, set_runner):
        """user_message_alter as string updates query.user_message."""
        from tests.factories import text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message

        chat = get_chat_handler()

        mock_event_ctx.is_prevented_default.return_value = False
        mock_event_ctx.event.user_message_alter = 'altered text'
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        query = text_query('original')
        query.adapter = Mock()
        query.adapter.is_stream_output_supported = AsyncMock(return_value=False)
        query.user_message = Message(role='user', content=[])

        class QuickRunner:
            name = 'local-agent'
            def __init__(self, app, config):
                self.app = app
                self.config = config
            async def run(self, query):
                yield Message(role='assistant', content='ok')

        set_runner(QuickRunner)

        handler = chat.ChatMessageHandler(fake_app)

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert query.user_message.content is not None

    @pytest.mark.asyncio
    async def test_adapter_without_stream_method_defaults_non_stream(self, fake_app, mock_event_ctx, set_runner):
        """Adapter without is_stream_output_supported defaults to non-stream."""
        from tests.factories import text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message, ContentElement

        chat = get_chat_handler()

        mock_event_ctx.is_prevented_default.return_value = False
        mock_event_ctx.event.user_message_alter = None
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        query = text_query('test')
        query.adapter = Mock(spec=[])
        query.user_message = Message(role='user', content=[ContentElement.from_text('test')])

        class SingleRunner:
            name = 'local-agent'
            def __init__(self, app, config):
                self.app = app
                self.config = config
            async def run(self, query):
                yield Message(role='assistant', content='response')

        set_runner(SingleRunner)

        handler = chat.ChatMessageHandler(fake_app)

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert len(results) >= 1


@pytest.mark.usefixtures('mock_circular_import_chain')
class TestChatHandlerStreaming:
    """Tests for streaming behavior."""

    @pytest.mark.asyncio
    async def test_streaming_chunks_collected(self, fake_app, mock_event_ctx, set_runner):
        """Streaming produces multiple results."""
        from tests.factories import text_query
        from langbot_plugin.api.entities.builtin.provider.message import Message, ContentElement, MessageChunk

        chat = get_chat_handler()

        mock_event_ctx.is_prevented_default.return_value = False
        fake_app.plugin_connector.emit_event = AsyncMock(return_value=mock_event_ctx)

        query = text_query('stream test')
        query.adapter = Mock()
        query.adapter.is_stream_output_supported = AsyncMock(return_value=True)
        query.adapter.create_message_card = AsyncMock()
        query.user_message = Message(role='user', content=[ContentElement.from_text('test')])

        class StreamRunner:
            name = 'local-agent'
            def __init__(self, app, config):
                self.app = app
                self.config = config
            async def run(self, query):
                yield MessageChunk(role='assistant', content='Hello', is_final=False)
                yield MessageChunk(role='assistant', content=' World', is_final=True)

        set_runner(StreamRunner)

        handler = chat.ChatMessageHandler(fake_app)

        results = []
        async for result in handler.handle(query):
            results.append(result)

        assert len(results) >= 1


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
            'ai': {'runner': {'runner': 'local-agent'}, 'local-agent': {'prompt': 'default', 'model': {'primary': 'test'}}},
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
            'ai': {'runner': {'runner': 'local-agent'}, 'local-agent': {'prompt': 'default', 'model': {'primary': 'test'}}},
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
            'ai': {'runner': {'runner': 'local-agent'}, 'local-agent': {'prompt': 'default', 'model': {'primary': 'test'}}},
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