"""Tests for ChatMessageHandler behavior with AgentRunOrchestrator.

Tests focus on:
- Streaming response text, finalization, card identity, and cross-query isolation
- Non-streaming mode behavior (no pop)
- Orchestrator invocation
- Error handling for RunnerNotFoundError, RunnerExecutionError

Avoids circular imports by using proper import structure.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langbot.pkg.agent.runner.errors import (
    RunnerNotFoundError,
    RunnerExecutionError,
    RunnerNotAuthorizedError,
)
from langbot.pkg.agent.runner.config_resolver import RunnerConfigResolver


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
                    'id': 'plugin:langbot-team/LocalAgent/default',
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
        self.tool_calls = []
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

    async def try_claim_steering_from_query(self, query):
        return False

    def resolve_runner_id_for_telemetry(self, query):
        return 'plugin:langbot-team/LocalAgent/default'


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


def make_handler_query(text):
    """Build SDK input entities; only the adapter and orchestration are fakes."""
    from tests.factories import text_query
    from langbot_plugin.api.entities.builtin.provider.message import Message
    from langbot_plugin.api.entities.builtin.provider.prompt import Prompt
    from langbot_plugin.api.entities.builtin.provider.session import Conversation, Session

    query = text_query(text)
    query.user_message = Message(role='user', content=text)
    query.adapter.is_stream_output_supported = AsyncMock(return_value=True)
    query.adapter.create_message_card = AsyncMock()
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


class TestRunnerConfigResolverInChatHandler:
    """Tests for RunnerConfigResolver usage in chat handler context."""

    def test_resolve_runner_id_from_pipeline_config(self):
        """Chat handler should use RunnerConfigResolver to resolve runner ID."""
        pipeline_config = {
            'ai': {
                'runner': {
                    'id': 'plugin:langbot-team/LocalAgent/default',
                },
            },
        }

        runner_id = RunnerConfigResolver.resolve_runner_id(pipeline_config)
        assert runner_id == 'plugin:langbot-team/LocalAgent/default'

    def test_old_runner_field_is_not_resolved(self):
        """The 4.x path requires ai.runner.id."""
        pipeline_config = {
            'ai': {
                'runner': {
                    'runner': 'local-agent',
                },
            },
        }

        runner_id = RunnerConfigResolver.resolve_runner_id(pipeline_config)
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
            'plugin:langbot-team/LocalAgent/default',
            'Upstream timeout',
            retryable=True,
        )
        assert error.runner_id == 'plugin:langbot-team/LocalAgent/default'
        assert error.retryable is True
        assert 'timeout' in str(error)

    def test_runner_execution_error_not_retryable(self):
        """RunnerExecutionError can be non-retryable."""
        error = RunnerExecutionError(
            'plugin:langbot-team/LocalAgent/default',
            'Configuration error',
            retryable=False,
        )
        assert error.retryable is False

    def test_runner_not_authorized_error_properties(self):
        """RunnerNotAuthorizedError should have bound_plugins property."""
        error = RunnerNotAuthorizedError(
            'plugin:langbot-team/LocalAgent/default',
            ['langbot-team/DifyAgent'],
        )
        assert error.runner_id == 'plugin:langbot-team/LocalAgent/default'
        assert error.bound_plugins == ['langbot-team/DifyAgent']


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
    async def test_interleaved_streams_keep_response_ids_and_messages_isolated(self):
        """Two turns on one handler must never update each other's response card."""
        from langbot.pkg.pipeline.process.handlers.chat import ChatMessageHandler
        from langbot.pkg.pipeline import entities
        from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk

        class InterleavedOrchestrator(MockAgentRunOrchestrator):
            async def run_from_query(self, query):
                text = query.user_message.content
                yield MessageChunk(role='assistant', content=f'{text}: partial')
                yield Message(role='assistant', content=f'{text}: completed')

        handler = ChatMessageHandler(MockApplication(orchestrator=InterleavedOrchestrator()))
        queries = [make_handler_query('first'), make_handler_query('second')]
        streams = [handler.handle(query) for query in queries]
        observed = [[], []]
        saved_messages = [None, None]

        try:
            for index in [0, 1, 0, 1]:
                result = await anext(streams[index])
                assert result.result_type == entities.ResultType.CONTINUE
                assert result.new_query is queries[index]
                assert len(queries[index].resp_messages) == 1
                current = queries[index].resp_messages[0]
                assert isinstance(current, MessageChunk)
                observed[index].append((current.content, current.is_final, current.resp_message_id))
                saved_messages[index] = current.model_dump()

                other = 1 - index
                if saved_messages[other] is not None:
                    assert [message.model_dump() for message in queries[other].resp_messages] == [saved_messages[other]]

            for stream in streams:
                with pytest.raises(StopAsyncIteration):
                    await anext(stream)
        finally:
            for stream in streams:
                await stream.aclose()

        first_id, second_id = (messages[0][2] for messages in observed)
        assert first_id and second_id and first_id != second_id
        assert observed == [
            [('first: partial', False, first_id), ('first: completed', True, first_id)],
            [('second: partial', False, second_id), ('second: completed', True, second_id)],
        ]
        for query, response_id in zip(queries, [first_id, second_id]):
            query.adapter.create_message_card.assert_awaited_once_with(response_id, query.message_event)

    @pytest.mark.asyncio
    async def test_non_streaming_keeps_prior_and_runner_messages_and_yields_once(self):
        """Non-streaming delivery preserves earlier messages and exposes only the completed turn."""
        from langbot.pkg.pipeline.process.handlers.chat import ChatMessageHandler
        from langbot.pkg.pipeline import entities
        from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk

        prior = Message(role='assistant', content='earlier reply', resp_message_id='earlier-id')
        prior_snapshot = prior.model_dump()
        chunks = [
            MessageChunk(role='assistant', content='working'),
            Message(role='assistant', content='completed'),
        ]
        handler = ChatMessageHandler(MockApplication(orchestrator=MockAgentRunOrchestrator(chunks=chunks)))
        query = make_handler_query('question')
        query.adapter.is_stream_output_supported.return_value = False
        query.resp_messages = [prior]
        observed = []

        async for result in handler.handle(query):
            assert result.result_type == entities.ResultType.CONTINUE
            assert result.new_query is query
            observed.append([message.content for message in result.new_query.resp_messages])

        assert observed == [['earlier reply', 'working', 'completed']]
        assert query.resp_messages == [prior, *chunks]
        assert prior.model_dump() == prior_snapshot
        assert chunks[0].resp_message_id
        assert chunks[0].resp_message_id == chunks[1].resp_message_id
        assert chunks[0].resp_message_id != prior.resp_message_id
        query.adapter.create_message_card.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_agent_turn_recreates_conversation_if_tool_resets_it(self):
        """Agent turn bookkeeping should tolerate CREATE_NEW_CONVERSATION during runner execution."""
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

        with (
            patch('langbot.pkg.pipeline.process.handlers.chat.events') as mock_events_module,
            patch('langbot.pkg.pipeline.entities.StageProcessResult', side_effect=make_result),
        ):
            mock_events_module.PersonNormalMessageReceived = mock_event
            mock_events_module.GroupNormalMessageReceived = mock_event

            results = []
            async for result in handler.handle(query):
                results.append(result)

        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.CONTINUE
        mock_ap.sess_mgr.get_conversation.assert_awaited_once()
        assert query.session.using_conversation is new_conversation
        assert new_conversation.messages == []

    @pytest.mark.asyncio
    async def test_runner_not_found_error(self):
        """Handler should catch RunnerNotFoundError and return INTERRUPT."""
        from langbot.pkg.pipeline.process.handlers.chat import ChatMessageHandler
        from langbot.pkg.pipeline import entities

        orchestrator = MockAgentRunOrchestrator(error=RunnerNotFoundError('plugin:notexist/unknown/default'))
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

        with (
            patch('langbot.pkg.pipeline.process.handlers.chat.events') as mock_events_module,
            patch('langbot.pkg.pipeline.entities.StageProcessResult', side_effect=make_result),
        ):
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
            error=RunnerNotAuthorizedError('plugin:langbot-team/LocalAgent/default', ['other/plugin'])
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

        with (
            patch('langbot.pkg.pipeline.process.handlers.chat.events') as mock_events_module,
            patch('langbot.pkg.pipeline.entities.StageProcessResult', side_effect=make_result),
        ):
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
            error=RunnerExecutionError('plugin:langbot-team/LocalAgent/default', 'timeout', retryable=True)
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

        with (
            patch('langbot.pkg.pipeline.process.handlers.chat.events') as mock_events_module,
            patch('langbot.pkg.pipeline.entities.StageProcessResult', side_effect=make_result),
        ):
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

        with (
            patch('langbot.pkg.pipeline.process.handlers.chat.events') as mock_events_module,
            patch('langbot.pkg.pipeline.entities.StageProcessResult', side_effect=make_result),
        ):
            mock_events_module.PersonNormalMessageReceived = mock_event
            mock_events_module.GroupNormalMessageReceived = mock_event

            results = []
            async for result in handler.handle(query):
                results.append(result)

        # Should return CONTINUE with reply message
        assert len(results) == 1
        assert results[0].result_type == entities.ResultType.CONTINUE
        assert len(query.resp_messages) == 1
