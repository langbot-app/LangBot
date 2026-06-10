"""
Unit tests for MessageAggregator (aggregator) module.

Tests cover:
- Message buffering and merging
- Timer-based flush behavior
- MAX_BUFFER_MESSAGES limit
- Aggregation enabled/disabled
- Config delay clamping
"""

from __future__ import annotations

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from importlib import import_module

from tests.factories import (
    FakeApp,
    text_chain,
    friend_message_event,
    mock_adapter,
)

import langbot_plugin.api.entities.builtin.provider.session as provider_session


def get_aggregator_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.pipeline.aggregator')


def make_aggregator_app():
    """Create a FakeApp with necessary mocks for aggregator tests."""
    app = FakeApp()
    # Ensure query_pool has add_query method
    app.query_pool.add_query = AsyncMock()
    # Add pipeline_mgr mock
    app.pipeline_mgr = AsyncMock()
    app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(return_value=None)
    return app


class TestPendingMessage:
    """Tests for PendingMessage dataclass."""

    def test_pending_message_creation(self):
        """PendingMessage should be created with correct fields."""
        aggregator = get_aggregator_module()

        chain = text_chain("hello")
        event = friend_message_event(chain)
        adapter = mock_adapter()

        pending = aggregator.PendingMessage(
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=event,
            message_chain=chain,
            adapter=adapter,
            pipeline_uuid='test-pipeline',
        )

        assert pending.bot_uuid == 'test-bot'
        assert pending.launcher_type == provider_session.LauncherTypes.PERSON
        assert pending.message_chain == chain
        assert pending.timestamp is not None


class TestSessionBuffer:
    """Tests for SessionBuffer dataclass."""

    def test_session_buffer_creation(self):
        """SessionBuffer should be created with correct fields."""
        aggregator = get_aggregator_module()

        buffer = aggregator.SessionBuffer(session_id='test-session')

        assert buffer.session_id == 'test-session'
        assert buffer.messages == []
        assert buffer.timer_task is None
        assert buffer.last_message_time is not None

    def test_session_buffer_with_messages(self):
        """SessionBuffer should accept initial messages."""
        aggregator = get_aggregator_module()

        chain = text_chain("hello")
        event = friend_message_event(chain)
        adapter = mock_adapter()

        pending = aggregator.PendingMessage(
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=event,
            message_chain=chain,
            adapter=adapter,
            pipeline_uuid=None,
        )

        buffer = aggregator.SessionBuffer(
            session_id='test-session',
            messages=[pending],
        )

        assert len(buffer.messages) == 1


class TestMessageAggregatorInit:
    """Tests for MessageAggregator initialization."""

    def test_aggregator_init(self):
        """MessageAggregator should initialize with correct fields."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        assert agg.ap == app
        assert agg.buffers == {}
        assert isinstance(agg.lock, asyncio.Lock)


class TestMessageAggregatorSessionId:
    """Tests for session ID generation."""

    def test_session_id_format(self):
        """Session ID should be correctly formatted."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        session_id = agg._get_session_id(
            bot_uuid='bot-123',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=45678,
        )

        assert session_id == 'bot-123:person:45678'

    def test_session_id_different_launchers(self):
        """Different launcher types should produce different IDs."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        person_id = agg._get_session_id(
            bot_uuid='bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=123,
        )

        group_id = agg._get_session_id(
            bot_uuid='bot',
            launcher_type=provider_session.LauncherTypes.GROUP,
            launcher_id=123,
        )

        assert person_id != group_id


class TestMessageAggregatorConfig:
    """Tests for aggregation config retrieval."""

    @pytest.mark.asyncio
    async def test_config_none_pipeline(self):
        """None pipeline_uuid should return default config."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        enabled, delay = await agg._get_aggregation_config(None)

        assert enabled == False
        assert delay == 1.5

    @pytest.mark.asyncio
    async def test_config_pipeline_not_found(self):
        """Non-existent pipeline should return default config."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(return_value=None)
        agg = aggregator.MessageAggregator(app)

        enabled, delay = await agg._get_aggregation_config('unknown-pipeline')

        assert enabled == False
        assert delay == 1.5

    @pytest.mark.asyncio
    async def test_config_enabled(self):
        """Pipeline with enabled aggregation should return True."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()

        mock_pipeline = Mock()
        mock_pipeline.pipeline_entity = Mock()
        mock_pipeline.pipeline_entity.config = {
            'trigger': {
                'message-aggregation': {
                    'enabled': True,
                    'delay': 2.0,
                }
            }
        }
        app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(return_value=mock_pipeline)

        agg = aggregator.MessageAggregator(app)

        enabled, delay = await agg._get_aggregation_config('test-pipeline')

        assert enabled == True
        assert delay == 2.0

    @pytest.mark.asyncio
    async def test_config_delay_clamped_low(self):
        """Delay below 1.0 should be clamped to 1.0."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()

        mock_pipeline = Mock()
        mock_pipeline.pipeline_entity = Mock()
        mock_pipeline.pipeline_entity.config = {
            'trigger': {
                'message-aggregation': {
                    'enabled': True,
                    'delay': 0.5,  # Below minimum
                }
            }
        }
        app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(return_value=mock_pipeline)

        agg = aggregator.MessageAggregator(app)

        enabled, delay = await agg._get_aggregation_config('test-pipeline')

        assert delay == 1.0  # Clamped to minimum

    @pytest.mark.asyncio
    async def test_config_delay_clamped_high(self):
        """Delay above 10.0 should be clamped to 10.0."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()

        mock_pipeline = Mock()
        mock_pipeline.pipeline_entity = Mock()
        mock_pipeline.pipeline_entity.config = {
            'trigger': {
                'message-aggregation': {
                    'enabled': True,
                    'delay': 15.0,  # Above maximum
                }
            }
        }
        app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(return_value=mock_pipeline)

        agg = aggregator.MessageAggregator(app)

        enabled, delay = await agg._get_aggregation_config('test-pipeline')

        assert delay == 10.0  # Clamped to maximum

    @pytest.mark.asyncio
    async def test_config_delay_invalid_type(self):
        """Invalid delay type should use default."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()

        mock_pipeline = Mock()
        mock_pipeline.pipeline_entity = Mock()
        mock_pipeline.pipeline_entity.config = {
            'trigger': {
                'message-aggregation': {
                    'enabled': True,
                    'delay': 'invalid',  # Not a number
                }
            }
        }
        app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(return_value=mock_pipeline)

        agg = aggregator.MessageAggregator(app)

        enabled, delay = await agg._get_aggregation_config('test-pipeline')

        assert delay == 1.5  # Default


class TestMessageAggregatorAddMessage:
    """Tests for add_message behavior."""

    @pytest.mark.asyncio
    async def test_disabled_adds_to_query_pool(self):
        """Disabled aggregation should directly add to query_pool."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        chain = text_chain("hello")
        event = friend_message_event(chain)
        adapter = mock_adapter()

        await agg.add_message(
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=event,
            message_chain=chain,
            adapter=adapter,
            pipeline_uuid=None,  # None -> disabled
        )

        # Should have called query_pool.add_query
        assert app.query_pool.add_query.called

    @pytest.mark.asyncio
    async def test_enabled_buffers_message(self):
        """Enabled aggregation should buffer message."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()

        mock_pipeline = Mock()
        mock_pipeline.pipeline_entity = Mock()
        mock_pipeline.pipeline_entity.config = {
            'trigger': {
                'message-aggregation': {
                    'enabled': True,
                    'delay': 2.0,
                }
            }
        }
        app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(return_value=mock_pipeline)

        agg = aggregator.MessageAggregator(app)

        chain = text_chain("hello")
        event = friend_message_event(chain)
        adapter = mock_adapter()

        await agg.add_message(
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=event,
            message_chain=chain,
            adapter=adapter,
            pipeline_uuid='test-pipeline',
        )

        # Should have buffered the message
        assert len(agg.buffers) == 1

    @pytest.mark.asyncio
    async def test_max_buffer_flushes_immediately(self):
        """Reaching MAX_BUFFER_MESSAGES should flush immediately."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()

        mock_pipeline = Mock()
        mock_pipeline.pipeline_entity = Mock()
        mock_pipeline.pipeline_entity.config = {
            'trigger': {
                'message-aggregation': {
                    'enabled': True,
                    'delay': 10.0,  # Long delay
                }
            }
        }
        app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(return_value=mock_pipeline)

        agg = aggregator.MessageAggregator(app)

        chain = text_chain("hello")
        event = friend_message_event(chain)
        adapter = mock_adapter()

        # Add messages up to MAX_BUFFER_MESSAGES
        for i in range(aggregator.MAX_BUFFER_MESSAGES):
            await agg.add_message(
                bot_uuid='test-bot',
                launcher_type=provider_session.LauncherTypes.PERSON,
                launcher_id=12345,
                sender_id=12345,
                message_event=event,
                message_chain=chain,
                adapter=adapter,
                pipeline_uuid='test-pipeline',
            )

        # Buffer should be flushed (empty or no buffer)
        session_id = agg._get_session_id('test-bot', provider_session.LauncherTypes.PERSON, 12345)
        assert session_id not in agg.buffers or len(agg.buffers[session_id].messages) == 0


class TestMessageAggregatorMerge:
    """Tests for message merging."""

    def test_merge_single_message(self):
        """Single message should return unchanged."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        chain = text_chain("hello")
        event = friend_message_event(chain)
        adapter = mock_adapter()

        pending = aggregator.PendingMessage(
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=event,
            message_chain=chain,
            adapter=adapter,
            pipeline_uuid=None,
        )

        merged = agg._merge_messages([pending])

        assert merged.message_chain == chain

    def test_merge_multiple_messages(self):
        """Multiple messages should be merged with newline separator."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        chain1 = text_chain("hello")
        chain2 = text_chain("world")
        event = friend_message_event(chain1)
        adapter = mock_adapter()

        pending1 = aggregator.PendingMessage(
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=event,
            message_chain=chain1,
            adapter=adapter,
            pipeline_uuid=None,
        )

        pending2 = aggregator.PendingMessage(
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=event,
            message_chain=chain2,
            adapter=adapter,
            pipeline_uuid=None,
        )

        merged = agg._merge_messages([pending1, pending2])

        # Should contain both messages with separator
        merged_str = str(merged.message_chain)
        assert "hello" in merged_str
        assert "world" in merged_str

    def test_merge_messages_preserves_routed_by_rule_if_any_input_matches(self):
        """Merged PendingMessage should keep routed_by_rule when any input was rule-routed."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        chain1 = text_chain("first")
        chain2 = text_chain("second")
        event = friend_message_event(chain1)
        adapter = mock_adapter()

        pending1 = aggregator.PendingMessage(
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=event,
            message_chain=chain1,
            adapter=adapter,
            pipeline_uuid='test-pipeline-uuid',
            routed_by_rule=False,
        )

        pending2 = aggregator.PendingMessage(
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=event,
            message_chain=chain2,
            adapter=adapter,
            pipeline_uuid='test-pipeline-uuid',
            routed_by_rule=True,
        )

        merged = agg._merge_messages([pending1, pending2])

        assert merged.routed_by_rule is True
        assert str(merged.message_chain) == 'first\nsecond'


class TestMessageAggregatorFlush:
    """Tests for buffer flush behavior."""

    @pytest.mark.asyncio
    async def test_flush_empty_buffer(self):
        """Flushing empty buffer should do nothing."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        await agg._flush_buffer('nonexistent-session')

        # Should not call query_pool
        assert not app.query_pool.add_query.called

    @pytest.mark.asyncio
    async def test_flush_single_message(self):
        """Flushing single message should add directly to query_pool."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        chain = text_chain("hello")
        event = friend_message_event(chain)
        adapter = mock_adapter()

        pending = aggregator.PendingMessage(
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=event,
            message_chain=chain,
            adapter=adapter,
            pipeline_uuid=None,
        )

        buffer = aggregator.SessionBuffer(
            session_id='test-session',
            messages=[pending],
        )

        agg.buffers['test-session'] = buffer

        await agg._flush_buffer('test-session')

        assert app.query_pool.add_query.called
        assert 'test-session' not in agg.buffers


class TestMessageAggregatorFlushAll:
    """Tests for flush_all behavior."""

    @pytest.mark.asyncio
    async def test_flush_all_empty(self):
        """flush_all with no buffers should do nothing."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        await agg.flush_all()

        # Should not call query_pool
        assert not app.query_pool.add_query.called

    @pytest.mark.asyncio
    async def test_flush_all_with_buffers(self):
        """flush_all should flush all pending buffers."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        chain = text_chain("hello")
        event = friend_message_event(chain)
        adapter = mock_adapter()

        # Create two buffers
        pending1 = aggregator.PendingMessage(
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=event,
            message_chain=chain,
            adapter=adapter,
            pipeline_uuid=None,
        )

        pending2 = aggregator.PendingMessage(
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=67890,
            sender_id=67890,
            message_event=event,
            message_chain=chain,
            adapter=adapter,
            pipeline_uuid=None,
        )

        buffer1 = aggregator.SessionBuffer(session_id='session-1', messages=[pending1])
        buffer2 = aggregator.SessionBuffer(session_id='session-2', messages=[pending2])

        agg.buffers['session-1'] = buffer1
        agg.buffers['session-2'] = buffer2

        await agg.flush_all()

        # Both buffers should be flushed
        assert len(agg.buffers) == 0
        assert app.query_pool.add_query.call_count == 2
