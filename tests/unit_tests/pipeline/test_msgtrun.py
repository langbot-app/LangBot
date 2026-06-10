"""
Unit tests for ConversationMessageTruncator (msgtrun) pipeline stage.

Tests cover:
- Normal truncation behavior based on max-round
- Boundary length handling
- Empty message handling
- Multi-message chain truncation
"""

from __future__ import annotations

import pytest
from importlib import import_module

from tests.factories import (
    FakeApp,
    text_query,
)

import langbot_plugin.api.entities.builtin.provider.message as provider_message


def get_msgtrun_module():
    """Lazy import to avoid circular import issues."""
    # Import pipelinemgr first to trigger stage registration
    import_module('langbot.pkg.pipeline.pipelinemgr')
    return import_module('langbot.pkg.pipeline.msgtrun.msgtrun')


def get_truncator_module():
    """Lazy import for truncator base."""
    return import_module('langbot.pkg.pipeline.msgtrun.truncator')


def get_entities_module():
    """Lazy import for pipeline entities."""
    return import_module('langbot.pkg.pipeline.entities')


def get_round_truncator_module():
    """Lazy import for round truncator."""
    return import_module('langbot.pkg.pipeline.msgtrun.truncators.round')


def make_truncate_config(max_round: int = 5):
    """Create a pipeline config with max-round setting."""
    return {
        'ai': {
            'local-agent': {
                'max-round': max_round,
            }
        }
    }


class TestConversationMessageTruncatorInit:
    """Tests for ConversationMessageTruncator initialization."""

    @pytest.mark.asyncio
    async def test_initialize_round_truncator(self):
        """Initialize should select 'round' truncator by default."""
        msgtrun = get_msgtrun_module()
        truncator = get_truncator_module()

        app = FakeApp()
        stage = msgtrun.ConversationMessageTruncator(app)

        pipeline_config = make_truncate_config()

        await stage.initialize(pipeline_config)

        assert stage.trun is not None
        assert isinstance(stage.trun, truncator.Truncator)

    @pytest.mark.asyncio
    async def test_initialize_unknown_truncator_raises(self):
        """Initialize with unknown truncator method should raise ValueError."""
        msgtrun = get_msgtrun_module()
        truncator = get_truncator_module()

        # Save original preregistered_truncators
        original_truncators = truncator.preregistered_truncators.copy()

        try:
            # Clear registered truncators to simulate unknown method
            truncator.preregistered_truncators = []

            app = FakeApp()
            stage = msgtrun.ConversationMessageTruncator(app)

            pipeline_config = make_truncate_config()

            with pytest.raises(ValueError, match='Unknown truncator'):
                await stage.initialize(pipeline_config)
        finally:
            # Restore original truncators
            truncator.preregistered_truncators = original_truncators


class TestRoundTruncatorProcess:
    """Tests for RoundTruncator truncation behavior."""

    @pytest.mark.asyncio
    async def test_truncate_within_limit(self):
        """Messages within max-round limit should not be truncated."""
        msgtrun = get_msgtrun_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = msgtrun.ConversationMessageTruncator(app)

        pipeline_config = make_truncate_config(max_round=5)

        await stage.initialize(pipeline_config)

        # Create query with 3 messages (within limit)
        query = text_query("current message")
        query.pipeline_config = pipeline_config
        query.messages = [
            provider_message.Message(role='user', content='message 1'),
            provider_message.Message(role='assistant', content='response 1'),
            provider_message.Message(role='user', content='message 2'),
            provider_message.Message(role='assistant', content='response 2'),
            provider_message.Message(role='user', content='current message'),
        ]

        result = await stage.process(query, 'ConversationMessageTruncator')

        assert result.result_type == entities.ResultType.CONTINUE
        # All messages should be preserved
        assert len(result.new_query.messages) == 5

    @pytest.mark.asyncio
    async def test_truncate_exceeds_limit(self):
        """Messages exceeding max-round should be truncated precisely.

        Algorithm: traverse backwards, collect while current_round < max_round, count user messages as rounds.
        For max_round=2 with 7 messages (u1, a1, u2, a2, u3, a3, u_current):
        - Iterate: u_current(r=0<2, collect, r=1), a3(r=1<2, collect), u3(r=1<2, collect, r=2)
        - a2: r=2 not < 2 → break
        - Collected reverse: [u_current, a3, u3]
        - Reversed: [u3, a3, u_current] = 3 messages
        """
        msgtrun = get_msgtrun_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = msgtrun.ConversationMessageTruncator(app)

        pipeline_config = make_truncate_config(max_round=2)  # Only keep 2 rounds

        await stage.initialize(pipeline_config)

        # Create query with many messages exceeding limit
        # 7 messages = 3 full rounds + 1 current user
        query = text_query("current message")
        query.pipeline_config = pipeline_config
        query.messages = [
            provider_message.Message(role='user', content='message 1'),
            provider_message.Message(role='assistant', content='response 1'),
            provider_message.Message(role='user', content='message 2'),
            provider_message.Message(role='assistant', content='response 2'),
            provider_message.Message(role='user', content='message 3'),
            provider_message.Message(role='assistant', content='response 3'),
            provider_message.Message(role='user', content='current message'),
        ]

        result = await stage.process(query, 'ConversationMessageTruncator')

        assert result.result_type == entities.ResultType.CONTINUE
        # Should keep exactly 3 messages: message3, response3, current message
        messages = result.new_query.messages
        assert len(messages) == 3

        # Verify exact message content
        assert messages[0].role == 'user'
        assert messages[0].content == 'message 3'
        assert messages[1].role == 'assistant'
        assert messages[1].content == 'response 3'
        assert messages[2].role == 'user'
        assert messages[2].content == 'current message'

    @pytest.mark.asyncio
    async def test_truncate_empty_messages(self):
        """Empty messages list should return empty list."""
        msgtrun = get_msgtrun_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = msgtrun.ConversationMessageTruncator(app)

        pipeline_config = make_truncate_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        query.messages = []

        result = await stage.process(query, 'ConversationMessageTruncator')

        assert result.result_type == entities.ResultType.CONTINUE
        assert len(result.new_query.messages) == 0

    @pytest.mark.asyncio
    async def test_truncate_single_message(self):
        """Single message should be preserved."""
        msgtrun = get_msgtrun_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = msgtrun.ConversationMessageTruncator(app)

        pipeline_config = make_truncate_config()

        await stage.initialize(pipeline_config)

        query = text_query("hello")
        query.pipeline_config = pipeline_config
        query.messages = [
            provider_message.Message(role='user', content='hello'),
        ]

        result = await stage.process(query, 'ConversationMessageTruncator')

        assert result.result_type == entities.ResultType.CONTINUE
        assert len(result.new_query.messages) == 1

    @pytest.mark.asyncio
    async def test_truncate_preserves_order(self):
        """Truncation should preserve message order."""
        msgtrun = get_msgtrun_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = msgtrun.ConversationMessageTruncator(app)

        pipeline_config = make_truncate_config(max_round=2)

        await stage.initialize(pipeline_config)

        query = text_query("current")
        query.pipeline_config = pipeline_config
        query.messages = [
            provider_message.Message(role='user', content='user1'),
            provider_message.Message(role='assistant', content='asst1'),
            provider_message.Message(role='user', content='user2'),
            provider_message.Message(role='assistant', content='asst2'),
            provider_message.Message(role='user', content='user3'),
        ]

        result = await stage.process(query, 'ConversationMessageTruncator')

        assert result.result_type == entities.ResultType.CONTINUE

        messages = result.new_query.messages
        assert [(msg.role, msg.content) for msg in messages] == [
            ('user', 'user2'),
            ('assistant', 'asst2'),
            ('user', 'user3'),
        ]

    @pytest.mark.asyncio
    async def test_truncate_max_round_one(self):
        """max-round=1 should only keep last user message."""
        msgtrun = get_msgtrun_module()
        entities = get_entities_module()

        app = FakeApp()
        stage = msgtrun.ConversationMessageTruncator(app)

        pipeline_config = make_truncate_config(max_round=1)

        await stage.initialize(pipeline_config)

        query = text_query("current")
        query.pipeline_config = pipeline_config
        query.messages = [
            provider_message.Message(role='user', content='old1'),
            provider_message.Message(role='assistant', content='old1_resp'),
            provider_message.Message(role='user', content='current'),
        ]

        result = await stage.process(query, 'ConversationMessageTruncator')

        assert result.result_type == entities.ResultType.CONTINUE
        messages = result.new_query.messages
        assert [(msg.role, msg.content) for msg in messages] == [('user', 'current')]


class TestRoundTruncatorDirect:
    """Direct tests for RoundTruncator class."""

    @pytest.mark.asyncio
    async def test_round_truncator_direct_process(self):
        """Test RoundTruncator truncate method directly."""
        truncator_mod = get_truncator_module()

        app = FakeApp()

        # Get the RoundTruncator class from preregistered
        for trun_cls in truncator_mod.preregistered_truncators:
            if trun_cls.name == 'round':
                trun = trun_cls(app)
                break

        query = text_query("hello")
        query.pipeline_config = make_truncate_config(max_round=3)
        query.messages = [
            provider_message.Message(role='user', content='m1'),
            provider_message.Message(role='assistant', content='r1'),
            provider_message.Message(role='user', content='m2'),
            provider_message.Message(role='assistant', content='r2'),
            provider_message.Message(role='user', content='hello'),
        ]

        result = await trun.truncate(query)

        assert result is not None
        assert hasattr(result, 'messages')
