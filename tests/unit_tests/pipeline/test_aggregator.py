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
import contextvars
from contextlib import asynccontextmanager
from unittest.mock import Mock, AsyncMock
from importlib import import_module
from types import SimpleNamespace

from tests.factories import (
    FakeApp,
    text_chain,
    friend_message_event,
    mock_adapter,
)

import langbot_plugin.api.entities.builtin.provider.session as provider_session

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.pipeline.pool import (
    ExecutionContextMismatchError,
    ExecutionContextRequiredError,
    bind_execution_context,
)
from langbot.pkg.workspace.errors import WorkspaceGenerationMismatchError


def execution_context(
    workspace_uuid='workspace-test',
    *,
    bot_uuid='test-bot',
    pipeline_uuid=None,
    placement_generation=1,
):
    return ExecutionContext(
        instance_uuid='instance-test',
        workspace_uuid=workspace_uuid,
        placement_generation=placement_generation,
        bot_uuid=bot_uuid,
        pipeline_uuid=pipeline_uuid,
    )


def aggregation_key(
    context,
    *,
    launcher_type=provider_session.LauncherTypes.PERSON,
    launcher_id=12345,
    bot_uuid='test-bot',
    pipeline_uuid=None,
):
    return (
        context.instance_uuid,
        context.workspace_uuid,
        context.placement_generation,
        bot_uuid,
        pipeline_uuid,
        launcher_type.value,
        launcher_id,
    )


def get_aggregator_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.pipeline.aggregator')


def make_aggregator_app():
    """Create a FakeApp with necessary mocks for aggregator tests."""
    app = FakeApp()
    # Ensure query_pool has add_query method
    app.query_pool.add_query = AsyncMock()

    async def resolve_context(
        context,
        *,
        bot_uuid,
        pipeline_uuid,
        query_uuid=None,
    ):
        if context is None:
            raise ExecutionContextRequiredError('ExecutionContext required in test')
        return bind_execution_context(
            context,
            bot_uuid=bot_uuid,
            pipeline_uuid=pipeline_uuid,
            query_uuid=query_uuid,
        )

    app.query_pool.resolve_execution_context = AsyncMock(side_effect=resolve_context)
    # Add pipeline_mgr mock
    app.pipeline_mgr = AsyncMock()
    app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(return_value=None)
    app.workspace_service = Mock()
    app.workspace_service.get_execution_binding = AsyncMock(
        return_value=Mock(
            instance_uuid='instance-test',
            workspace_uuid='workspace-test',
            placement_generation=1,
        )
    )
    return app


def enable_aggregation(app, *, delay=10.0):
    pipeline = Mock()
    pipeline.pipeline_entity.config = {
        'trigger': {
            'message-aggregation': {
                'enabled': True,
                'delay': delay,
            }
        }
    }
    app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(return_value=pipeline)


def scoped_message_kwargs(context, *, launcher_id=12345, text='hello'):
    chain = text_chain(text)
    return {
        'execution_context': context,
        'bot_uuid': context.bot_uuid,
        'launcher_type': provider_session.LauncherTypes.PERSON,
        'launcher_id': launcher_id,
        'sender_id': launcher_id,
        'message_event': friend_message_event(chain),
        'message_chain': chain,
        'adapter': mock_adapter(),
        'pipeline_uuid': context.pipeline_uuid,
    }


class TestPendingMessage:
    """Tests for PendingMessage dataclass."""

    def test_pending_message_creation(self):
        """PendingMessage should be created with correct fields."""
        aggregator = get_aggregator_module()

        chain = text_chain('hello')
        event = friend_message_event(chain)
        adapter = mock_adapter()

        pending = aggregator.PendingMessage(
            execution_context=execution_context(pipeline_uuid='test-pipeline'),
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

        context = execution_context()
        key = aggregation_key(context)
        buffer = aggregator.SessionBuffer(
            aggregation_key=key,
            execution_context=context,
        )

        assert buffer.aggregation_key == key
        assert buffer.messages == []
        assert buffer.timer_task is None
        assert buffer.last_message_time is not None

    def test_session_buffer_with_messages(self):
        """SessionBuffer should accept initial messages."""
        aggregator = get_aggregator_module()

        chain = text_chain('hello')
        event = friend_message_event(chain)
        adapter = mock_adapter()

        pending = aggregator.PendingMessage(
            execution_context=execution_context(),
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=event,
            message_chain=chain,
            adapter=adapter,
            pipeline_uuid=None,
        )

        context = execution_context()
        buffer = aggregator.SessionBuffer(
            aggregation_key=aggregation_key(context),
            execution_context=context,
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
    """Tests for scoped aggregation key generation."""

    def test_session_id_format(self):
        """Session ID should be correctly formatted."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        context = execution_context()
        session_id = agg._get_aggregation_key(
            context,
            bot_uuid='bot-123',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=45678,
            pipeline_uuid=None,
        )

        assert session_id == (
            'instance-test',
            'workspace-test',
            1,
            'bot-123',
            None,
            'person',
            45678,
        )

    def test_session_id_different_launchers(self):
        """Different launcher types should produce different IDs."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        context = execution_context()
        person_id = agg._get_aggregation_key(
            context,
            bot_uuid='bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=123,
            pipeline_uuid=None,
        )

        group_id = agg._get_aggregation_key(
            context,
            bot_uuid='bot',
            launcher_type=provider_session.LauncherTypes.GROUP,
            launcher_id=123,
            pipeline_uuid=None,
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

        enabled, delay = await agg._get_aggregation_config(execution_context(), None)

        assert enabled == False
        assert delay == 1.5

    @pytest.mark.asyncio
    async def test_config_pipeline_not_found(self):
        """Non-existent pipeline should return default config."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        app.pipeline_mgr.get_pipeline_by_uuid = AsyncMock(return_value=None)
        agg = aggregator.MessageAggregator(app)

        enabled, delay = await agg._get_aggregation_config(
            execution_context(pipeline_uuid='unknown-pipeline'),
            'unknown-pipeline',
        )

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

        enabled, delay = await agg._get_aggregation_config(
            execution_context(pipeline_uuid='test-pipeline'),
            'test-pipeline',
        )

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

        enabled, delay = await agg._get_aggregation_config(
            execution_context(pipeline_uuid='test-pipeline'),
            'test-pipeline',
        )

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

        enabled, delay = await agg._get_aggregation_config(
            execution_context(pipeline_uuid='test-pipeline'),
            'test-pipeline',
        )

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

        enabled, delay = await agg._get_aggregation_config(
            execution_context(pipeline_uuid='test-pipeline'),
            'test-pipeline',
        )

        assert delay == 1.5  # Default


class TestMessageAggregatorAddMessage:
    """Tests for add_message behavior."""

    @pytest.mark.asyncio
    async def test_disabled_adds_to_query_pool(self):
        """Disabled aggregation should directly add to query_pool."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        chain = text_chain('hello')
        event = friend_message_event(chain)
        adapter = mock_adapter()

        await agg.add_message(
            execution_context=execution_context(),
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

        chain = text_chain('hello')
        event = friend_message_event(chain)
        adapter = mock_adapter()

        await agg.add_message(
            execution_context=execution_context(pipeline_uuid='test-pipeline'),
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

        chain = text_chain('hello')
        event = friend_message_event(chain)
        adapter = mock_adapter()

        # Add messages up to MAX_BUFFER_MESSAGES
        for i in range(aggregator.MAX_BUFFER_MESSAGES):
            await agg.add_message(
                execution_context=execution_context(pipeline_uuid='test-pipeline'),
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
        context = execution_context(pipeline_uuid='test-pipeline')
        session_id = agg._get_aggregation_key(
            context,
            'test-bot',
            provider_session.LauncherTypes.PERSON,
            12345,
            'test-pipeline',
        )
        assert session_id not in agg.buffers or len(agg.buffers[session_id].messages) == 0


class TestMessageAggregatorMerge:
    """Tests for message merging."""

    def test_merge_single_message(self):
        """Single message should return unchanged."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        chain = text_chain('hello')
        event = friend_message_event(chain)
        adapter = mock_adapter()

        pending = aggregator.PendingMessage(
            execution_context=execution_context(),
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

        chain1 = text_chain('hello')
        chain2 = text_chain('world')
        event = friend_message_event(chain1)
        adapter = mock_adapter()

        pending1 = aggregator.PendingMessage(
            execution_context=execution_context(),
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
            execution_context=execution_context(),
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
        assert 'hello' in merged_str
        assert 'world' in merged_str

    def test_merge_messages_preserves_routed_by_rule_if_any_input_matches(self):
        """Merged PendingMessage should keep routed_by_rule when any input was rule-routed."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        chain1 = text_chain('first')
        chain2 = text_chain('second')
        event = friend_message_event(chain1)
        adapter = mock_adapter()

        pending1 = aggregator.PendingMessage(
            execution_context=execution_context(pipeline_uuid='test-pipeline-uuid'),
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
            execution_context=execution_context(pipeline_uuid='test-pipeline-uuid'),
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

        context = execution_context()
        await agg._flush_buffer(aggregation_key(context), context)

        # Should not call query_pool
        assert not app.query_pool.add_query.called

    @pytest.mark.asyncio
    async def test_flush_single_message(self):
        """Flushing single message should add directly to query_pool."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        agg = aggregator.MessageAggregator(app)

        chain = text_chain('hello')
        event = friend_message_event(chain)
        adapter = mock_adapter()

        pending = aggregator.PendingMessage(
            execution_context=execution_context(),
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=event,
            message_chain=chain,
            adapter=adapter,
            pipeline_uuid=None,
        )

        context = execution_context()
        key = aggregation_key(context)
        buffer = aggregator.SessionBuffer(
            aggregation_key=key,
            execution_context=context,
            messages=[pending],
        )

        agg.buffers[key] = buffer

        await agg._flush_buffer(key, context)

        assert app.query_pool.add_query.called
        assert key not in agg.buffers

    @pytest.mark.asyncio
    async def test_flush_drops_buffer_when_placement_generation_is_stale(self):
        """A debounce timer cannot enqueue work after its placement is fenced."""
        aggregator = get_aggregator_module()

        app = make_aggregator_app()
        app.workspace_service.get_execution_binding.side_effect = WorkspaceGenerationMismatchError('stale generation')
        agg = aggregator.MessageAggregator(app)
        context = execution_context(placement_generation=3)
        pending = aggregator.PendingMessage(
            execution_context=context,
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            message_event=friend_message_event(text_chain('stale')),
            message_chain=text_chain('stale'),
            adapter=mock_adapter(),
            pipeline_uuid=None,
        )
        key = aggregation_key(context)
        agg.buffers[key] = aggregator.SessionBuffer(
            aggregation_key=key,
            execution_context=context,
            messages=[pending],
        )

        with pytest.raises(WorkspaceGenerationMismatchError):
            await agg._flush_buffer(key, context)

        app.workspace_service.get_execution_binding.assert_awaited_once_with(
            'workspace-test',
            expected_generation=3,
        )
        app.query_pool.add_query.assert_not_awaited()
        assert key not in agg.buffers


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

        chain = text_chain('hello')
        event = friend_message_event(chain)
        adapter = mock_adapter()

        # Create two buffers
        pending1 = aggregator.PendingMessage(
            execution_context=execution_context(),
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
            execution_context=execution_context(),
            bot_uuid='test-bot',
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=67890,
            sender_id=67890,
            message_event=event,
            message_chain=chain,
            adapter=adapter,
            pipeline_uuid=None,
        )

        context = execution_context()
        key1 = aggregation_key(context, launcher_id=12345)
        key2 = aggregation_key(context, launcher_id=67890)
        buffer1 = aggregator.SessionBuffer(
            aggregation_key=key1,
            execution_context=context,
            messages=[pending1],
        )
        buffer2 = aggregator.SessionBuffer(
            aggregation_key=key2,
            execution_context=context,
            messages=[pending2],
        )

        agg.buffers[key1] = buffer1
        agg.buffers[key2] = buffer2

        await agg.flush_all()

        # Both buffers should be flushed
        assert len(agg.buffers) == 0
        assert app.query_pool.add_query.call_count == 2


class TestMessageAggregatorWorkspaceIsolation:
    """Regression coverage for fail-closed and cross-workspace behavior."""

    @pytest.mark.asyncio
    async def test_missing_execution_context_fails_closed(self):
        app = make_aggregator_app()
        agg = get_aggregator_module().MessageAggregator(app)
        kwargs = scoped_message_kwargs(execution_context())
        kwargs['execution_context'] = None

        with pytest.raises(ExecutionContextRequiredError):
            await agg.add_message(**kwargs)

        app.query_pool.add_query.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_same_launcher_in_two_workspaces_uses_separate_buffers(self):
        app = make_aggregator_app()
        enable_aggregation(app)
        agg = get_aggregator_module().MessageAggregator(app)

        await agg.add_message(**scoped_message_kwargs(execution_context('workspace-a', pipeline_uuid='test-pipeline')))
        await agg.add_message(**scoped_message_kwargs(execution_context('workspace-b', pipeline_uuid='test-pipeline')))

        assert len(agg.buffers) == 2
        assert {key[1] for key in agg.buffers} == {'workspace-a', 'workspace-b'}
        await agg.flush_all()

    @pytest.mark.asyncio
    async def test_same_launcher_in_two_bots_uses_separate_buffers(self):
        app = make_aggregator_app()
        enable_aggregation(app)
        agg = get_aggregator_module().MessageAggregator(app)

        await agg.add_message(
            **scoped_message_kwargs(execution_context(bot_uuid='bot-a', pipeline_uuid='test-pipeline'))
        )
        await agg.add_message(
            **scoped_message_kwargs(execution_context(bot_uuid='bot-b', pipeline_uuid='test-pipeline'))
        )

        assert len(agg.buffers) == 2
        assert {key[3] for key in agg.buffers} == {'bot-a', 'bot-b'}
        await agg.flush_all()

    @pytest.mark.asyncio
    async def test_timer_receives_exact_captured_execution_context(self, monkeypatch):
        app = make_aggregator_app()
        enable_aggregation(app)
        agg = get_aggregator_module().MessageAggregator(app)
        request_value = contextvars.ContextVar('aggregator_request_value', default=None)
        token = request_value.set('request-scope')
        observed = []

        async def delayed_flush(*args):
            observed.append((request_value.get(), args[2]))

        monkeypatch.setattr(agg, '_delayed_flush', delayed_flush)
        context = execution_context(pipeline_uuid='test-pipeline')

        try:
            await agg.add_message(**scoped_message_kwargs(context))
            await asyncio.sleep(0)
        finally:
            request_value.reset(token)

        assert observed == [(None, context)]
        await agg.flush_all()

    @pytest.mark.asyncio
    async def test_delayed_flush_opens_explicit_workspace_uow(self, monkeypatch):
        app = make_aggregator_app()
        app.persistence_mgr.mode = SimpleNamespace(value='cloud_runtime')
        scopes = []

        @asynccontextmanager
        async def tenant_uow(workspace_uuid):
            scopes.append(workspace_uuid)
            yield

        app.persistence_mgr.tenant_uow = tenant_uow
        agg = get_aggregator_module().MessageAggregator(app)
        flush = AsyncMock()
        monkeypatch.setattr(agg, '_flush_buffer', flush)
        context = execution_context('workspace-a', pipeline_uuid='test-pipeline')
        key = aggregation_key(context, pipeline_uuid='test-pipeline')

        await agg._delayed_flush(key, 0, context)

        assert scopes == ['workspace-a']
        flush.assert_awaited_once_with(key, context)

    @pytest.mark.asyncio
    async def test_flush_rejects_context_from_another_workspace(self):
        app = make_aggregator_app()
        enable_aggregation(app)
        agg = get_aggregator_module().MessageAggregator(app)
        context_a = execution_context('workspace-a', pipeline_uuid='test-pipeline')
        context_b = execution_context('workspace-b', pipeline_uuid='test-pipeline')
        await agg.add_message(**scoped_message_kwargs(context_a))
        key = next(iter(agg.buffers))

        with pytest.raises(ExecutionContextMismatchError):
            await agg._flush_buffer(key, context_b)

        assert key in agg.buffers
        await agg.flush_all()

    def test_merge_rejects_messages_from_different_workspaces(self):
        app = make_aggregator_app()
        agg = get_aggregator_module().MessageAggregator(app)
        aggregator = get_aggregator_module()

        with pytest.raises(ExecutionContextMismatchError):
            agg._merge_messages(
                [
                    aggregator.PendingMessage(**scoped_message_kwargs(execution_context('workspace-a'))),
                    aggregator.PendingMessage(**scoped_message_kwargs(execution_context('workspace-b'))),
                ]
            )

    @pytest.mark.asyncio
    async def test_flush_all_preserves_each_workspace_context(self):
        app = make_aggregator_app()
        enable_aggregation(app)
        agg = get_aggregator_module().MessageAggregator(app)
        await agg.add_message(**scoped_message_kwargs(execution_context('workspace-a', pipeline_uuid='test-pipeline')))
        await agg.add_message(**scoped_message_kwargs(execution_context('workspace-b', pipeline_uuid='test-pipeline')))

        await agg.flush_all()

        forwarded_workspaces = {
            call.kwargs['execution_context'].workspace_uuid for call in app.query_pool.add_query.await_args_list
        }
        assert forwarded_workspaces == {'workspace-a', 'workspace-b'}
