"""Tests for agent runner result normalizer."""
from __future__ import annotations

import pytest

from langbot.pkg.agent.runner.result_normalizer import AgentResultNormalizer
from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.agent.runner.errors import RunnerExecutionError, RunnerProtocolError

from langbot_plugin.api.entities.builtin.provider import message as provider_message


class FakeApplication:
    """Fake Application for testing."""
    def __init__(self):
        class FakeLogger:
            def __init__(self):
                self.warnings = []

            def info(self, msg):
                pass
            def debug(self, msg):
                pass
            def warning(self, msg):
                self.warnings.append(msg)
            def error(self, msg):
                pass

        self.logger = FakeLogger()


def make_descriptor():
    """Create a test descriptor."""
    return AgentRunnerDescriptor(
        id='plugin:langbot/local-agent/default',
        source='plugin',
        label={'en_US': 'Local Agent', 'zh_Hans': '内置 Agent'},
        plugin_author='langbot',
        plugin_name='local-agent',
        runner_name='default',
        capabilities={'streaming': True},
    )


class TestNormalizeMessageDelta:
    """Tests for normalizing message.delta results."""

    @pytest.mark.asyncio
    async def test_normalize_message_delta_text(self):
        """Normalize message.delta with text chunk."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        result_dict = {
            'type': 'message.delta',
            'data': {
                'chunk': {
                    'role': 'assistant',
                    'content': 'Hello',
                },
            },
        }

        result = await normalizer.normalize(result_dict, descriptor)

        assert result is not None
        assert isinstance(result, provider_message.MessageChunk)
        assert result.role == 'assistant'
        assert result.content == 'Hello'

    @pytest.mark.asyncio
    async def test_normalize_message_delta_missing_chunk(self):
        """Invalid message.delta payload is dropped."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        result_dict = {
            'type': 'message.delta',
            'data': {},
        }

        result = await normalizer.normalize(result_dict, descriptor)

        assert result is None


class TestNormalizeMessageCompleted:
    """Tests for normalizing message.completed results."""

    @pytest.mark.asyncio
    async def test_normalize_message_completed(self):
        """Normalize message.completed with full message."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        result_dict = {
            'type': 'message.completed',
            'data': {
                'message': {
                    'role': 'assistant',
                    'content': 'Complete response',
                },
            },
        }

        result = await normalizer.normalize(result_dict, descriptor)

        assert result is not None
        assert isinstance(result, provider_message.Message)
        assert result.role == 'assistant'
        assert result.content == 'Complete response'

    @pytest.mark.asyncio
    async def test_normalize_message_completed_missing_message(self):
        """Invalid message.completed payload is dropped."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        result_dict = {
            'type': 'message.completed',
            'data': {},
        }

        result = await normalizer.normalize(result_dict, descriptor)

        assert result is None


class TestNormalizeRunCompleted:
    """Tests for normalizing run.completed results."""

    @pytest.mark.asyncio
    async def test_normalize_run_completed_with_message(self):
        """Normalize run.completed with final message."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        result_dict = {
            'type': 'run.completed',
            'data': {
                'message': {
                    'role': 'assistant',
                    'content': 'Final response',
                },
                'finish_reason': 'stop',
            },
        }

        result = await normalizer.normalize(result_dict, descriptor)

        assert result is not None
        assert isinstance(result, provider_message.Message)

    @pytest.mark.asyncio
    async def test_normalize_run_completed_without_message(self):
        """Normalize run.completed without message."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        result_dict = {
            'type': 'run.completed',
            'data': {
                'finish_reason': 'stop',
            },
        }

        result = await normalizer.normalize(result_dict, descriptor)

        assert result is None


class TestNormalizeRunFailed:
    """Tests for normalizing run.failed results."""

    @pytest.mark.asyncio
    async def test_normalize_run_failed(self):
        """Normalize run.failed raises RunnerExecutionError."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        result_dict = {
            'type': 'run.failed',
            'data': {
                'error': 'Upstream timeout',
                'code': 'upstream.timeout',
                'retryable': True,
            },
        }

        with pytest.raises(RunnerExecutionError) as exc_info:
            await normalizer.normalize(result_dict, descriptor)

        assert exc_info.value.runner_id == 'plugin:langbot/local-agent/default'
        assert exc_info.value.retryable is True
        assert 'timeout' in str(exc_info.value)


class TestNormalizeNonMessageResults:
    """Tests for normalizing non-message results."""

    @pytest.mark.asyncio
    async def test_normalize_tool_call_started(self):
        """Normalize tool.call.started returns None."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        result_dict = {
            'type': 'tool.call.started',
            'data': {
                'tool_call_id': 'call_1',
                'tool_name': 'weather',
            },
        }

        result = await normalizer.normalize(result_dict, descriptor)
        assert result is None

    @pytest.mark.asyncio
    async def test_normalize_tool_call_completed(self):
        """Normalize tool.call.completed returns None."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        result_dict = {
            'type': 'tool.call.completed',
            'data': {
                'tool_call_id': 'call_1',
                'tool_name': 'weather',
                'result': {'temp': 20},
            },
        }

        result = await normalizer.normalize(result_dict, descriptor)
        assert result is None

    @pytest.mark.asyncio
    async def test_normalize_state_updated(self):
        """Normalize state.updated returns None."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        result_dict = {
            'type': 'state.updated',
            'data': {
                'scope': 'conversation',
                'key': 'external_conversation_id',
                'value': 'abc123',
            },
        }

        result = await normalizer.normalize(result_dict, descriptor)
        assert result is None

    @pytest.mark.asyncio
    async def test_normalize_action_requested(self):
        """Normalize action.requested returns None (EBA reserved)."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        result_dict = {
            'type': 'action.requested',
            'data': {
                'action': 'platform.message.edit',
                'payload': {},
            },
        }

        result = await normalizer.normalize(result_dict, descriptor)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_state_updated_payload_is_dropped(self):
        """Invalid state.updated payload returns None with a warning."""
        app = FakeApplication()
        normalizer = AgentResultNormalizer(app)
        descriptor = make_descriptor()

        result = await normalizer.normalize(
            {
                'type': 'state.updated',
                'data': {
                    'scope': 'invalid',
                    'key': 'k',
                    'value': 'v',
                },
            },
            descriptor,
        )

        assert result is None
        assert app.logger.warnings

    @pytest.mark.asyncio
    async def test_invalid_artifact_created_payload_is_dropped(self):
        """Invalid artifact.created payload returns None with a warning."""
        app = FakeApplication()
        normalizer = AgentResultNormalizer(app)
        descriptor = make_descriptor()

        result = await normalizer.normalize(
            {
                'type': 'artifact.created',
                'data': {
                    'artifact_id': 'artifact-1',
                    'artifact_type': 'file',
                    'content_base64': 'not base64',
                },
            },
            descriptor,
        )

        assert result is None
        assert app.logger.warnings


class TestNormalizeInvalidResults:
    """Tests for handling invalid results."""

    @pytest.mark.asyncio
    async def test_normalize_missing_type(self):
        """Normalize result without type."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        result_dict = {
            'data': {},
        }

        with pytest.raises(RunnerProtocolError) as exc_info:
            await normalizer.normalize(result_dict, descriptor)

        assert 'Missing result type' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_normalize_unknown_type(self):
        """Normalize unknown type returns None."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        result_dict = {
            'type': 'unknown_type',
            'data': {},
        }

        result = await normalizer.normalize(result_dict, descriptor)
        assert result is None

    @pytest.mark.asyncio
    async def test_normalize_legacy_type_returns_none(self):
        """Legacy types (chunk, text, finish) are now treated as unknown."""
        normalizer = AgentResultNormalizer(FakeApplication())
        descriptor = make_descriptor()

        # chunk is now unknown
        result_dict = {
            'type': 'chunk',
            'data': {
                'message_chunk': {
                    'role': 'assistant',
                    'content': 'Legacy chunk',
                },
            },
        }
        result = await normalizer.normalize(result_dict, descriptor)
        assert result is None

        # text is now unknown
        result_dict = {
            'type': 'text',
            'data': {
                'content': 'Legacy text',
            },
        }
        result = await normalizer.normalize(result_dict, descriptor)
        assert result is None

        # finish is now unknown
        result_dict = {
            'type': 'finish',
            'data': {
                'message': {
                    'role': 'assistant',
                    'content': 'Legacy finish',
                },
            },
        }
        result = await normalizer.normalize(result_dict, descriptor)
        assert result is None
