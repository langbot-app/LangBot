"""Tests for ChatMessageHandler behavior with AgentRunOrchestrator.

Tests focus on:
- Streaming mode behavior (single resp_message_id, pop/append pattern)
- Non-streaming mode behavior (no pop)
- Orchestrator invocation
- Error handling for RunnerNotFoundError, RunnerExecutionError

Avoids circular imports by using proper import structure.
"""
from __future__ import annotations

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langbot.pkg.agent.runner.errors import (
    RunnerNotFoundError,
    RunnerExecutionError,
    RunnerNotAuthorizedError,
)
from langbot.pkg.agent.runner.config_migration import ConfigMigration


# Define mock classes in dependency order (no forward references needed)

class MockLauncherType:
    value = 'person'


class MockConversation:
    def __init__(self):
        self.uuid = 'conv-uuid'
        self.messages = []


class MockMessage:
    role = 'user'
    content = 'Hello'


class MockAdapter:
    is_stream = False

    async def is_stream_output_supported(self):
        return self.is_stream

    async def create_message_card(self, resp_message_id, message_event):
        pass


class MockSession:
    launcher_type = MockLauncherType()
    launcher_id = 'user123'

    def __init__(self):
        self.using_conversation = MockConversation()


class MockQuery:
    """Mock Query for testing."""
    def __init__(self):
        self.query_id = 1
        self.launcher_type = MockLauncherType()
        self.launcher_id = 'user123'
        self.sender_id = 'user123'
        self.bot_uuid = 'bot-uuid'
        self.pipeline_uuid = 'pipeline-uuid'
        self.pipeline_config = {
            'ai': {
                'runner': {
                    'id': 'plugin:langbot/local-agent/default',
                },
                'runner_config': {},
            },
            'output': {
                'misc': {
                    'exception-handling': 'show-hint',
                    'failure-hint': 'Request failed.',
                },
            },
        }
        self.variables = {}
        self.session = MockSession()
        self.user_message = MockMessage()
        self.messages = []
        self.resp_messages = []
        self.resp_message_chain = None
        self.adapter = MockAdapter()
        self.message_event = MagicMock()
        self.message_chain = MagicMock()


class MockMessageChunk:
    """Mock MessageChunk for testing."""
    def __init__(self, content, resp_message_id=None):
        self.role = 'assistant'
        self.content = content
        self.resp_message_id = resp_message_id
        self.is_final = False

    def readable_str(self):
        return self.content


class MockEventContext:
    """Mock event context for testing."""
    def __init__(self, prevented=False, reply_message_chain=None, user_message_alter=None):
        self._prevented = prevented
        self.event = MagicMock()
        self.event.reply_message_chain = reply_message_chain
        self.event.user_message_alter = user_message_alter

    def is_prevented_default(self):
        return self._prevented


class MockAgentRunOrchestrator:
    """Mock AgentRunOrchestrator for testing."""
    def __init__(self, chunks=None, error=None):
        self._chunks = chunks or []
        self._error = error

    async def run_from_query(self, query):
        """Async generator that yields chunks or raises error."""
        if self._error:
            raise self._error
        for chunk in self._chunks:
            yield chunk

    def resolve_runner_id_for_telemetry(self, query):
        return 'plugin:langbot/local-agent/default'


class MockApplication:
    """Mock Application for testing."""
    def __init__(self, orchestrator=None):
        self.agent_run_orchestrator = orchestrator or MockAgentRunOrchestrator()
        self.logger = MagicMock()
        self.logger.info = MagicMock()
        self.logger.debug = MagicMock()
        self.logger.warning = MagicMock()
        self.logger.error = MagicMock()

        # Mock plugin_connector
        self.plugin_connector = MagicMock()
        self.plugin_connector.emit_event = AsyncMock(return_value=MockEventContext())

        # Mock telemetry
        self.telemetry = MagicMock()
        self.telemetry.start_send_task = AsyncMock()

        # Mock survey
        self.survey = MagicMock()
        self.survey.trigger_event = AsyncMock()

        # Mock model_mgr
        self.model_mgr = MagicMock()
        self.model_mgr.get_model_by_uuid = AsyncMock(return_value=None)

        # Mock sess_mgr
        self.sess_mgr = MagicMock()
        self.sess_mgr.get_conversation = AsyncMock()


class TestStreamingBehavior:
    """Tests for streaming mode behavior."""

    def test_single_resp_message_id_for_streaming(self):
        """Streaming mode should use single resp_message_id for entire response."""
        # Simulate the streaming logic: resp_message_id created outside loop
        resp_message_id = uuid.uuid4()

        chunks = ['Hello', ' World', '!']
        resp_messages = []

        for chunk in chunks:
            result = MockMessageChunk(chunk)
            result.resp_message_id = str(resp_message_id)

            # Pop old chunk (streaming behavior)
            if resp_messages:
                resp_messages.pop()
            resp_messages.append(result)

        # All chunks should have same resp_message_id
        assert len(resp_messages) == 1  # Only last chunk remains after pop/append
        assert resp_messages[0].resp_message_id == str(resp_message_id)

    def test_pop_before_append_in_streaming(self):
        """Streaming mode should pop old chunk before appending new."""
        resp_message_id = uuid.uuid4()
        resp_messages = []

        # First chunk - no pop
        chunk1 = MockMessageChunk('Hello')
        chunk1.resp_message_id = str(resp_message_id)
        resp_messages.append(chunk1)
        assert len(resp_messages) == 1

        # Second chunk - pop first, then append
        if resp_messages:
            resp_messages.pop()
        chunk2 = MockMessageChunk('Hello World')
        chunk2.resp_message_id = str(resp_message_id)
        resp_messages.append(chunk2)
        assert len(resp_messages) == 1
        assert resp_messages[0].content == 'Hello World'

    def test_non_streaming_no_pop(self):
        """Non-streaming mode should NOT pop previous responses."""
        resp_messages = []

        # First message
        msg1 = MockMessageChunk('Response 1')
        resp_messages.append(msg1)
        assert len(resp_messages) == 1

        # Second message - should NOT pop in non-streaming
        msg2 = MockMessageChunk('Response 2')
        resp_messages.append(msg2)
        assert len(resp_messages) == 2


class TestConfigMigrationInChatHandler:
    """Tests for ConfigMigration usage in chat handler context."""

    def test_resolve_runner_id_from_pipeline_config(self):
        """Chat handler should use ConfigMigration to resolve runner ID."""
        pipeline_config = {
            'ai': {
                'runner': {
                    'id': 'plugin:langbot/local-agent/default',
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        assert runner_id == 'plugin:langbot/local-agent/default'

    def test_resolve_runner_id_from_old_format(self):
        """ConfigMigration should not resolve removed runner aliases."""
        pipeline_config = {
            'ai': {
                'runner': {
                    'runner': 'local-agent',
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        assert runner_id is None


class TestErrorHandling:
    """Tests for orchestrator error handling."""

    def test_runner_not_found_error_properties(self):
        """RunnerNotFoundError should have runner_id property."""
        error = RunnerNotFoundError('plugin:notexist/unknown/default')
        assert error.runner_id == 'plugin:notexist/unknown/default'
        assert 'not found' in str(error)

    def test_runner_execution_error_retryable(self):
        """RunnerExecutionError should have retryable property."""
        error = RunnerExecutionError(
            'plugin:langbot/local-agent/default',
            'Upstream timeout',
            retryable=True,
        )
        assert error.runner_id == 'plugin:langbot/local-agent/default'
        assert error.retryable is True
        assert 'timeout' in str(error)

    def test_runner_execution_error_not_retryable(self):
        """RunnerExecutionError can be non-retryable."""
        error = RunnerExecutionError(
            'plugin:langbot/local-agent/default',
            'Configuration error',
            retryable=False,
        )
        assert error.retryable is False

    def test_runner_not_authorized_error_properties(self):
        """RunnerNotAuthorizedError should have bound_plugins property."""
        error = RunnerNotAuthorizedError(
            'plugin:langbot/local-agent/default',
            ['langbot/dify-agent'],
        )
        assert error.runner_id == 'plugin:langbot/local-agent/default'
        assert error.bound_plugins == ['langbot/dify-agent']


class TestChatHandlerImports:
    """Test that chat handler can be imported without circular import."""

    def test_import_chat_handler_module(self):
        """Import chat handler module should work."""
        # This test verifies the import works without circular dependency
        from langbot.pkg.pipeline.process.handlers import chat
        assert chat.ChatMessageHandler is not None

    def test_chat_handler_class_exists(self):
        """ChatMessageHandler class should be defined."""
        from langbot.pkg.pipeline.process.handlers.chat import ChatMessageHandler
        assert ChatMessageHandler.__name__ == 'ChatMessageHandler'

    def test_chat_handler_has_handle_method(self):
        """ChatMessageHandler should have async generator handle method."""
        from langbot.pkg.pipeline.process.handlers.chat import ChatMessageHandler
        assert hasattr(ChatMessageHandler, 'handle')
        # handle returns AsyncGenerator, so check for async generator function
        import inspect
        assert inspect.isasyncgenfunction(ChatMessageHandler.handle)


class TestChatHandlerAsyncBehavior:
    """Real async tests for ChatMessageHandler.handle() with mocked orchestrator."""

    @pytest.mark.asyncio
    async def test_streaming_single_resp_message_id(self):
        """Streaming mode: all chunks should have same resp_message_id."""
        from langbot.pkg.pipeline.process.handlers.chat import ChatMessageHandler
        from langbot.pkg.pipeline import entities

        # Create chunks for streaming
        chunks = [
            MockMessageChunk('Hello'),
            MockMessageChunk('Hello World'),
            MockMessageChunk('Hello World!'),
        ]

        orchestrator = MockAgentRunOrchestrator(chunks=chunks)
        mock_ap = MockApplication(orchestrator=orchestrator)

        # Mock event context to not prevent default
        event_ctx = MockEventContext(prevented=False)
        mock_ap.plugin_connector.emit_event = AsyncMock(return_value=event_ctx)

        query = MockQuery()
        query.adapter.is_stream = True  # Enable streaming mode

        handler = ChatMessageHandler(mock_ap)

        # Mock event creation and StageProcessResult to bypass pydantic validation
        mock_event = MagicMock()
        mock_event.return_value = MagicMock()

        def make_result(*args, **kwargs):
            return MagicMock(result_type=kwargs.get('result_type', entities.ResultType.CONTINUE))

        with patch('langbot.pkg.pipeline.process.handlers.chat.events') as mock_events_module, \
             patch('langbot.pkg.pipeline.entities.StageProcessResult', side_effect=make_result):
            mock_events_module.PersonNormalMessageReceived = mock_event
            mock_events_module.GroupNormalMessageReceived = mock_event

            results = []
            async for result in handler.handle(query):
                results.append(result)

        # Verify single resp_message_id
        resp_ids = [msg.resp_message_id for msg in query.resp_messages if hasattr(msg, 'resp_message_id')]
        assert len(set(resp_ids)) == 1  # All same ID

        # Verify pop/append pattern: only last chunk remains
        assert len(query.resp_messages) == 1
        assert query.resp_messages[0].content == 'Hello World!'

    @pytest.mark.asyncio
    async def test_non_streaming_no_pop(self):
        """Non-streaming mode: all chunks should remain."""
        from langbot.pkg.pipeline.process.handlers.chat import ChatMessageHandler
        from langbot.pkg.pipeline import entities

        chunks = [
            MockMessageChunk('Response 1'),
            MockMessageChunk('Response 2'),
        ]

        orchestrator = MockAgentRunOrchestrator(chunks=chunks)
        mock_ap = MockApplication(orchestrator=orchestrator)
        mock_ap.plugin_connector.emit_event = AsyncMock(return_value=MockEventContext(prevented=False))

        query = MockQuery()
        query.adapter.is_stream = False  # Disable streaming mode

        handler = ChatMessageHandler(mock_ap)

        mock_event = MagicMock()
        mock_event.return_value = MagicMock()

        def make_result(*args, **kwargs):
            return MagicMock(result_type=kwargs.get('result_type', entities.ResultType.CONTINUE))

        with patch('langbot.pkg.pipeline.process.handlers.chat.events') as mock_events_module, \
             patch('langbot.pkg.pipeline.entities.StageProcessResult', side_effect=make_result):
            mock_events_module.PersonNormalMessageReceived = mock_event
            mock_events_module.GroupNormalMessageReceived = mock_event

            results = []
            async for result in handler.handle(query):
                results.append(result)

        # No pop: all chunks should remain
        assert len(query.resp_messages) == 2
        assert query.resp_messages[0].content == 'Response 1'
        assert query.resp_messages[1].content == 'Response 2'

    @pytest.mark.asyncio
    async def test_history_update_recreates_conversation_if_tool_resets_it(self):
        """History update should tolerate CREATE_NEW_CONVERSATION during runner execution."""
        from langbot.pkg.pipeline.process.handlers.chat import ChatMessageHandler
        from langbot.pkg.pipeline import entities

        response = MockMessageChunk('Tool response')
        new_conversation = MockConversation()

        class ResetConversationOrchestrator(MockAgentRunOrchestrator):
            async def run_from_query(self, query):
                query.session.using_conversation = None
                yield response

        mock_ap = MockApplication(orchestrator=ResetConversationOrchestrator())
        mock_ap.plugin_connector.emit_event = AsyncMock(return_value=MockEventContext(prevented=False))
        mock_ap.sess_mgr.get_conversation = AsyncMock(return_value=new_conversation)

        query = MockQuery()
        query.adapter.is_stream = False

        handler = ChatMessageHandler(mock_ap)

        mock_event = MagicMock()
        mock_event.return_value = MagicMock()

        def make_result(*args, **kwargs):
            return MagicMock(result_type=kwargs.get('result_type', entities.ResultType.CONTINUE))

        with patch('langbot.pkg.pipeline.process.handlers.chat.events') as mock_events_module, \
             patch('langbot.pkg.pipeline.entities.StageProcessResult', side_effect=make_result):
            mock_events_module.PersonNormalMessageReceived = mock_event
            mock_events_module.GroupNormalMessageReceived = mock_event

            results = []
            async for result in handler.handle(query):
                results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.CONTINUE
        mock_ap.sess_mgr.get_conversation.assert_awaited_once()
        assert query.session.using_conversation is new_conversation
        assert new_conversation.messages == [query.user_message, response]

    @pytest.mark.asyncio
    async def test_runner_not_found_error(self):
        """Handler should catch RunnerNotFoundError and return INTERRUPT."""
        from langbot.pkg.pipeline.process.handlers.chat import ChatMessageHandler
        from langbot.pkg.pipeline import entities

        orchestrator = MockAgentRunOrchestrator(
            error=RunnerNotFoundError('plugin:notexist/unknown/default')
        )
        mock_ap = MockApplication(orchestrator=orchestrator)
        mock_ap.plugin_connector.emit_event = AsyncMock(return_value=MockEventContext(prevented=False))

        query = MockQuery()

        handler = ChatMessageHandler(mock_ap)

        mock_event = MagicMock()
        mock_event.return_value = MagicMock()

        def make_result(*args, **kwargs):
            return MagicMock(
                result_type=kwargs.get('result_type'),
                user_notice=kwargs.get('user_notice'),
            )

        with patch('langbot.pkg.pipeline.process.handlers.chat.events') as mock_events_module, \
             patch('langbot.pkg.pipeline.entities.StageProcessResult', side_effect=make_result):
            mock_events_module.PersonNormalMessageReceived = mock_event
            mock_events_module.GroupNormalMessageReceived = mock_event

            results = []
            async for result in handler.handle(query):
                results.append(result)

        # Should return INTERRUPT with user_notice
        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.INTERRUPT
        assert 'not found' in results[0].user_notice

    @pytest.mark.asyncio
    async def test_runner_not_authorized_error(self):
        """Handler should catch RunnerNotAuthorizedError and return INTERRUPT."""
        from langbot.pkg.pipeline.process.handlers.chat import ChatMessageHandler
        from langbot.pkg.pipeline import entities

        orchestrator = MockAgentRunOrchestrator(
            error=RunnerNotAuthorizedError('plugin:langbot/local-agent/default', ['other/plugin'])
        )
        mock_ap = MockApplication(orchestrator=orchestrator)
        mock_ap.plugin_connector.emit_event = AsyncMock(return_value=MockEventContext(prevented=False))

        query = MockQuery()

        handler = ChatMessageHandler(mock_ap)

        mock_event = MagicMock()
        mock_event.return_value = MagicMock()

        def make_result(*args, **kwargs):
            return MagicMock(
                result_type=kwargs.get('result_type'),
                user_notice=kwargs.get('user_notice'),
            )

        with patch('langbot.pkg.pipeline.process.handlers.chat.events') as mock_events_module, \
             patch('langbot.pkg.pipeline.entities.StageProcessResult', side_effect=make_result):
            mock_events_module.PersonNormalMessageReceived = mock_event
            mock_events_module.GroupNormalMessageReceived = mock_event

            results = []
            async for result in handler.handle(query):
                results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.INTERRUPT
        assert 'not authorized' in results[0].user_notice

    @pytest.mark.asyncio
    async def test_runner_execution_error_retryable(self):
        """Handler should catch retryable RunnerExecutionError."""
        from langbot.pkg.pipeline.process.handlers.chat import ChatMessageHandler
        from langbot.pkg.pipeline import entities

        orchestrator = MockAgentRunOrchestrator(
            error=RunnerExecutionError('plugin:langbot/local-agent/default', 'timeout', retryable=True)
        )
        mock_ap = MockApplication(orchestrator=orchestrator)
        mock_ap.plugin_connector.emit_event = AsyncMock(return_value=MockEventContext(prevented=False))

        query = MockQuery()

        handler = ChatMessageHandler(mock_ap)

        mock_event = MagicMock()
        mock_event.return_value = MagicMock()

        def make_result(*args, **kwargs):
            return MagicMock(
                result_type=kwargs.get('result_type'),
                user_notice=kwargs.get('user_notice'),
            )

        with patch('langbot.pkg.pipeline.process.handlers.chat.events') as mock_events_module, \
             patch('langbot.pkg.pipeline.entities.StageProcessResult', side_effect=make_result):
            mock_events_module.PersonNormalMessageReceived = mock_event
            mock_events_module.GroupNormalMessageReceived = mock_event

            results = []
            async for result in handler.handle(query):
                results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.INTERRUPT
        assert 'temporarily unavailable' in results[0].user_notice

    @pytest.mark.asyncio
    async def test_prevented_default_with_reply(self):
        """When event prevented default with reply, use reply message."""
        from langbot.pkg.pipeline.process.handlers.chat import ChatMessageHandler
        from langbot.pkg.pipeline import entities

        # Mock reply message chain
        reply_chain = MockMessageChunk('Reply from plugin')

        mock_ap = MockApplication()
        mock_ap.plugin_connector.emit_event = AsyncMock(
            return_value=MockEventContext(prevented=True, reply_message_chain=reply_chain)
        )

        query = MockQuery()

        handler = ChatMessageHandler(mock_ap)

        mock_event = MagicMock()
        mock_event.return_value = MagicMock()

        def make_result(*args, **kwargs):
            return MagicMock(result_type=kwargs.get('result_type', entities.ResultType.CONTINUE))

        with patch('langbot.pkg.pipeline.process.handlers.chat.events') as mock_events_module, \
             patch('langbot.pkg.pipeline.entities.StageProcessResult', side_effect=make_result):
            mock_events_module.PersonNormalMessageReceived = mock_event
            mock_events_module.GroupNormalMessageReceived = mock_event

            results = []
            async for result in handler.handle(query):
                results.append(result)

        # Should return CONTINUE with reply message
        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.CONTINUE
        assert len(query.resp_messages) == 1
