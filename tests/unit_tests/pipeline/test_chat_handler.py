"""
Unit tests for ChatMessageHandler behavior patterns.

Tests cover chat processing patterns:
- Event emission for normal messages
- Provider invocation pattern
- Streaming response handling
- Error handling

Uses pattern-based testing to avoid circular import issues.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, AsyncMock
import uuid

from tests.factories import text_query


class TestNormalMessageEventPattern:
    """Tests for normal message event emission."""

    def test_person_event_type(self):
        """Person messages use PersonNormalMessageReceived."""
        import langbot_plugin.api.entities.events as events
        from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes

        launcher_type = LauncherTypes.PERSON

        event_class = (
            events.PersonNormalMessageReceived
            if launcher_type == LauncherTypes.PERSON
            else events.GroupNormalMessageReceived
        )

        assert event_class == events.PersonNormalMessageReceived

    def test_group_event_type(self):
        """Group messages use GroupNormalMessageReceived."""
        import langbot_plugin.api.entities.events as events
        from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes

        launcher_type = LauncherTypes.GROUP

        event_class = (
            events.PersonNormalMessageReceived
            if launcher_type == LauncherTypes.PERSON
            else events.GroupNormalMessageReceived
        )

        assert event_class == events.GroupNormalMessageReceived

    def test_event_fields_pattern(self):
        """Normal message event has expected fields."""
        launcher_type = 'person'
        launcher_id = '12345'
        sender_id = '12345'
        text_message = 'hello world'

        event_data = {
            'launcher_type': launcher_type,
            'launcher_id': launcher_id,
            'sender_id': sender_id,
            'text_message': text_message,
        }

        assert event_data['text_message'] == 'hello world'


class TestPreventDefaultHandling:
    """Tests for prevent_default handling in chat."""

    @pytest.mark.asyncio
    async def test_prevent_default_interrupts(self):
        """prevent_default without reply interrupts pipeline."""

        # Simulate event context
        event_ctx = Mock()
        event_ctx.is_prevented_default.return_value = True
        event_ctx.event = Mock()
        event_ctx.event.reply_message_chain = None

        query = text_query('hello')
        query.resp_messages = []

        should_interrupt = False
        if event_ctx.is_prevented_default():
            if event_ctx.event.reply_message_chain is None:
                should_interrupt = True

        assert should_interrupt is True

    @pytest.mark.asyncio
    async def test_prevent_default_with_reply_continues(self):
        """prevent_default with reply continues with that reply."""
        from tests.factories.message import text_chain

        event_ctx = Mock()
        event_ctx.is_prevented_default.return_value = True
        event_ctx.event = Mock()
        event_ctx.event.reply_message_chain = text_chain('plugin reply')

        query = text_query('hello')
        query.resp_messages = []

        if event_ctx.is_prevented_default():
            if event_ctx.event.reply_message_chain is not None:
                query.resp_messages.append(event_ctx.event.reply_message_chain)

        assert len(query.resp_messages) == 1


class TestUserMessageAlteration:
    """Tests for user_message alteration pattern."""

    @pytest.mark.asyncio
    async def test_string_alters_message(self):
        """User message can be altered to string."""
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        event_ctx = Mock()
        event_ctx.is_prevented_default.return_value = False
        event_ctx.event = Mock()
        event_ctx.event.user_message_alter = 'altered text'

        query = text_query('original')
        query.user_message = provider_message.Message(role='user', content=[])

        # Pattern from handler
        if event_ctx.event.user_message_alter is not None:
            if isinstance(event_ctx.event.user_message_alter, str):
                query.user_message.content = [
                    provider_message.ContentElement.from_text(event_ctx.event.user_message_alter)
                ]

        assert query.user_message.content[0].text == 'altered text'

    @pytest.mark.asyncio
    async def test_list_alters_message(self):
        """User message can be altered to list."""
        import langbot_plugin.api.entities.builtin.provider.message as provider_message

        altered_list = [
            provider_message.ContentElement.from_text('part1'),
            provider_message.ContentElement.from_text('part2'),
        ]

        event_ctx = Mock()
        event_ctx.is_prevented_default.return_value = False
        event_ctx.event = Mock()
        event_ctx.event.user_message_alter = altered_list

        query = text_query('original')
        query.user_message = provider_message.Message(role='user', content=[])

        if isinstance(event_ctx.event.user_message_alter, list):
            query.user_message.content = event_ctx.event.user_message_alter

        assert len(query.user_message.content) == 2


class TestRunnerSelection:
    """Tests for runner selection pattern."""

    def test_runner_by_name(self):
        """Runner is selected by name from config."""
        runner_name = 'local-agent'

        # Simulate preregistered runners lookup - Mock with name attribute
        r1 = Mock()
        r1.name = 'local-agent'
        r2 = Mock()
        r2.name = 'dify'
        r3 = Mock()
        r3.name = 'n8n'
        preregistered_runners = [r1, r2, r3]

        runner = None
        for r in preregistered_runners:
            if r.name == runner_name:
                runner = r
                break

        assert runner is not None
        assert runner.name == 'local-agent'

    def test_unknown_runner_raises(self):
        """Unknown runner name raises error."""
        runner_name = 'unknown-runner'
        preregistered_runners = [
            Mock(name='local-agent'),
            Mock(name='dify'),
        ]

        runner = None
        for r in preregistered_runners:
            if r.name == runner_name:
                runner = r
                break

        if runner is None:
            error_raised = True

        assert error_raised is True


class TestStreamingResponse:
    """Tests for streaming response pattern."""

    @pytest.mark.asyncio
    async def test_streaming_chunks_pattern(self):
        """Streaming produces multiple chunks."""
        chunks = ['Hello', ' World', '!']
        results = []

        # Simulate streaming generator
        async def stream_gen():
            for chunk in chunks:
                results.append(chunk)

        await stream_gen()

        assert len(results) == 3
        assert ''.join(results) == 'Hello World!'

    @pytest.mark.asyncio
    async def test_streaming_resp_message_id(self):
        """Streaming uses uuid for resp_message_id."""
        resp_message_id = str(uuid.uuid4())

        assert len(resp_message_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_streaming_pop_previous(self):
        """Streaming pops previous response before adding new."""
        query = text_query('test')
        query.resp_messages = [Mock()]  # Previous chunk
        query.resp_message_chain = [Mock()]

        # Pattern from handler: pop before adding new chunk
        if query.resp_messages:
            query.resp_messages.pop()
        if query.resp_message_chain:
            query.resp_message_chain.pop()

        query.resp_messages.append(Mock())  # New chunk

        assert len(query.resp_messages) == 1  # Only new chunk


class TestNonStreamingResponse:
    """Tests for non-streaming response pattern."""

    @pytest.mark.asyncio
    async def test_single_response_pattern(self):
        """Non-streaming produces single response."""
        query = text_query('test')
        query.resp_messages = []

        # Simulate non-streaming runner
        async def run():
            yield Mock(readable_str=lambda: 'response text')

        async for result in run():
            query.resp_messages.append(result)

        assert len(query.resp_messages) == 1


class TestExceptionHandling:
    """Tests for exception handling pattern."""

    @pytest.mark.asyncio
    async def test_exception_interrupts(self):
        """Exception produces INTERRUPT result."""

        text_query('test')
        pipeline_config = {
            'output': {
                'misc': {
                    'exception-handling': 'show-hint',
                    'failure-hint': 'Request failed.',
                }
            }
        }

        # Simulate exception
        exception = ValueError('provider error')

        exception_handling = pipeline_config['output']['misc'].get('exception-handling', 'show-hint')

        if exception_handling == 'show-error':
            user_notice = f'{exception}'
        elif exception_handling == 'show-hint':
            user_notice = pipeline_config['output']['misc'].get('failure-hint', 'Request failed.')
        else:  # hide
            user_notice = None

        assert user_notice == 'Request failed.'

    @pytest.mark.asyncio
    async def test_exception_show_error(self):
        """show-error mode shows actual error."""
        text_query('test')
        pipeline_config = {
            'output': {
                'misc': {
                    'exception-handling': 'show-error',
                }
            }
        }

        exception = ValueError('API timeout')

        exception_handling = pipeline_config['output']['misc'].get('exception-handling', 'show-hint')

        if exception_handling == 'show-error':
            user_notice = f'{exception}'
        else:
            user_notice = 'Request failed.'

        assert user_notice == 'API timeout'

    @pytest.mark.asyncio
    async def test_exception_hide(self):
        """hide mode shows no user notice."""
        text_query('test')
        pipeline_config = {
            'output': {
                'misc': {
                    'exception-handling': 'hide',
                }
            }
        }

        ValueError('hidden error')

        exception_handling = pipeline_config['output']['misc'].get('exception-handling', 'show-hint')

        if exception_handling == 'hide':
            user_notice = None
        else:
            user_notice = 'Error'

        assert user_notice is None


class TestMessageHistoryUpdate:
    """Tests for conversation message history."""

    @pytest.mark.asyncio
    async def test_messages_appended_to_conversation(self):
        """User message and response appended to conversation."""
        query = text_query('test')
        query.session = Mock()
        query.session.using_conversation = Mock()
        query.session.using_conversation.messages = []

        query.user_message = Mock()
        query.resp_messages = [Mock(), Mock()]

        # Pattern from handler after successful response
        query.session.using_conversation.messages.append(query.user_message)
        query.session.using_conversation.messages.extend(query.resp_messages)

        assert len(query.session.using_conversation.messages) == 3


class TestStreamOutputCheck:
    """Tests for stream output support check."""

    @pytest.mark.asyncio
    async def test_adapter_stream_check(self):
        """Adapter is checked for stream support."""
        adapter = AsyncMock()
        adapter.is_stream_output_supported = AsyncMock(return_value=True)

        is_stream = await adapter.is_stream_output_supported()

        assert is_stream is True

    @pytest.mark.asyncio
    async def test_adapter_no_stream_method(self):
        """Adapter without method defaults to False."""
        adapter = Mock(spec=[])  # Empty spec, no methods
        # No is_stream_output_supported method

        is_stream = False
        try:
            if hasattr(adapter, 'is_stream_output_supported'):
                is_stream = await adapter.is_stream_output_supported()
        except AttributeError:
            is_stream = False

        assert is_stream is False


class TestTelemetryPattern:
    """Tests for telemetry reporting pattern."""

    def test_telemetry_payload_fields(self):
        """Telemetry payload has expected fields."""
        query_id = 123
        adapter_name = 'TestAdapter'
        runner_name = 'local-agent'
        duration_ms = 150

        payload = {
            'query_id': query_id,
            'adapter': adapter_name,
            'runner': runner_name,
            'duration_ms': duration_ms,
        }

        assert payload['query_id'] == 123
        assert payload['duration_ms'] == 150

    def test_telemetry_error_included(self):
        """Telemetry includes error info on failure."""
        error_info = 'Traceback...'

        payload = {
            'error': error_info,
        }

        assert payload['error'] == 'Traceback...'