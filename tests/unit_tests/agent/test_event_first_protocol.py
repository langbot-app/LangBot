"""Tests for event-first Protocol v1 entities and Query entry adapter.

Tests cover:
1. Query -> AgentEventEnvelope conversion
2. Current config -> AgentConfig projection and single-binding resolution
3. AgentRunContext not inlining full history by default
4. LangBot Host not defining context-window controls
5. Event-first run() entry point
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock

# Import SDK entities
from langbot_plugin.api.entities.builtin.agent_runner.event import (
    AgentEventContext,
)
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
from langbot_plugin.api.entities.builtin.agent_runner.trigger import AgentTrigger
from langbot_plugin.api.entities.builtin.agent_runner.context import AgentRunContext
from langbot_plugin.api.entities.builtin.agent_runner.result import (
    AgentRunResult,
)

# Import LangBot host models
from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter
from langbot.pkg.agent.runner.binding_resolver import (
    AgentBindingResolver,
    AgentBindingResolutionError,
)


class TestQueryToEventEnvelope:
    """Test Query -> AgentEventEnvelope conversion."""

    def test_query_to_event_basic_fields(self, mock_query):
        """Test basic field conversion from Query to Event envelope."""
        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.event_type == 'message.received'
        assert event.source == 'host_adapter'
        assert event.bot_id == mock_query.bot_uuid
        assert event.actor is not None
        assert event.actor.actor_type == 'user'

    def test_query_to_event_input(self, mock_query):
        """Test input conversion from Query."""
        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.input is not None
        assert event.input.text == 'Hello world'
        assert 'message_chain' not in event.input.model_dump()

    def test_query_to_event_conversation(self, mock_query):
        """Test conversation context extraction."""
        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.conversation_id == 'conv-uuid-123'

    def test_query_to_event_prefers_variable_conversation_id_when_conversation_uuid_missing(self, mock_query):
        """Pipeline variables can provide the conversation identity for state scope."""
        mock_query.session.using_conversation.uuid = None
        mock_query.variables['conversation_id'] = 'conv-from-vars'

        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.conversation_id == 'conv-from-vars'

    def test_query_to_event_falls_back_to_launcher_session_for_state_scope(self, mock_query):
        """Debug Chat and legacy pipeline runs may not have a conversation UUID."""
        mock_query.session.using_conversation.uuid = None

        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.conversation_id == 'person_launcher-123'

    def test_query_to_event_delivery_context(self, mock_query):
        """Test delivery context extraction."""
        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.delivery is not None
        assert event.delivery.surface == 'platform'
        assert isinstance(event.delivery.supports_streaming, bool)
        assert event.delivery.reply_target == {
            'target_type': 'person',
            'target_id': 'launcher-123',
            'message_id': 789,
        }

    def test_query_to_event_preserves_source_event_data(self, mock_query):
        """Test source event metadata survives the adapter boundary."""
        source_event = Mock()
        source_event.type = 'platform.message.created'
        source_event.time = 1700000000
        source_event.sender = None
        source_event.model_dump = Mock(
            return_value={
                'type': 'platform.message.created',
                'message_id': 'source-message-1',
                'source_platform_object': {'large': 'payload'},
            }
        )
        mock_query.message_event = source_event

        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.source_event_type == 'platform.message.created'
        assert event.event_time == 1700000000
        assert event.data == {
            'type': 'platform.message.created',
            'message_id': 'source-message-1',
        }

    @pytest.mark.parametrize(
        ('source_time', 'expected'),
        [
            (1_700_000_000, 1_700_000_000),
            (1_700_000_000_123, 1_700_000_000),
            (1_700_000_000_123_456, 1_700_000_000),
        ],
    )
    def test_query_to_event_normalizes_legacy_timestamp_units(
        self,
        mock_query,
        source_time,
        expected,
    ):
        mock_query.message_event = Mock(
            type='platform.message.created',
            time=source_time,
            sender=None,
        )
        mock_query.message_event.model_dump = Mock(return_value={})

        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.event_time == expected

    def test_query_to_event_keeps_large_payloads_out_of_event_data(self, mock_query):
        """Large or nested platform payloads should not be duplicated into event.data."""
        source_event = Mock()
        source_event.type = 'platform.message.created'
        source_event.time = 1700000000
        source_event.sender = None
        source_event.model_dump = Mock(
            return_value={
                'type': 'platform.message.created',
                'message_id': 'source-message-1',
                'message_chain': [{'type': 'Image', 'base64': 'data:image/png;base64,' + ('a' * 1024)}],
                'raw_text': 'x' * 1024,
                'source_platform_object': {'large': 'payload'},
            }
        )
        mock_query.message_event = source_event

        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.data == {
            'type': 'platform.message.created',
            'message_id': 'source-message-1',
        }

    def test_query_to_event_handles_missing_message_chain(self, mock_query):
        """Test delivery context building when Query has no message_chain."""
        delattr(mock_query, 'message_chain')

        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.delivery.reply_target == {
            'target_type': 'person',
            'target_id': 'launcher-123',
            'message_id': None,
        }

    def test_query_to_event_scopes_pipeline_local_event_ids(self, mock_query):
        """Pipeline-local message IDs must not become global audit IDs."""
        first = QueryEntryAdapter.query_to_event(mock_query)

        mock_query.launcher_id = 'launcher-456'
        second = QueryEntryAdapter.query_to_event(mock_query)

        assert first.event_id.startswith('host:')
        assert first.event_id != '789'
        assert second.event_id != first.event_id


class TestQueryConfigToAgentConfig:
    """Test current config projection and single-Agent binding resolution."""

    def test_config_to_agent_config_runner_id(self, mock_query):
        """Test AgentConfig runner_id extraction."""
        agent_config = QueryEntryAdapter.config_to_agent_config(mock_query, 'plugin:author/plugin/runner')

        assert agent_config.runner_id == 'plugin:author/plugin/runner'
        assert agent_config.processor_type == 'pipeline'
        assert agent_config.processor_id == mock_query.pipeline_uuid
        assert agent_config.delivery_policy.enable_interactions is True

    def test_config_to_agent_config_uses_current_runner_config(self, mock_query):
        """Temporary query adapters use the current runner config container."""
        mock_query.pipeline_config = {
            'ai': {
                'runner': {'id': 'plugin:langbot-team/LocalAgent/default'},
                'runner_config': {
                    'plugin:langbot-team/LocalAgent/default': {
                        'model': {'primary': 'model-primary', 'fallbacks': []},
                        'knowledge-bases': ['kb-001'],
                    },
                },
            }
        }

        agent_config = QueryEntryAdapter.config_to_agent_config(
            mock_query,
            'plugin:langbot-team/LocalAgent/default',
        )

        assert agent_config.runner_config['model'] == {'primary': 'model-primary', 'fallbacks': []}
        assert agent_config.runner_config['knowledge-bases'] == ['kb-001']

    def test_resolver_projects_agent_scope(self, mock_query):
        """Test binding scope projection through the resolver."""
        event = QueryEntryAdapter.query_to_event(mock_query)
        agent_config = QueryEntryAdapter.config_to_agent_config(mock_query, 'plugin:test/plugin/runner')
        binding = AgentBindingResolver().resolve_one(event, [agent_config])

        assert binding.scope.scope_type == 'agent'
        assert binding.scope.scope_id == mock_query.pipeline_uuid
        assert binding.agent_id == mock_query.pipeline_uuid
        assert binding.processor_type == 'pipeline'
        assert binding.processor_id == mock_query.pipeline_uuid

    def test_interaction_submission_projects_control_event(self, mock_query):
        """Pipeline callbacks keep structured submission data and match the runner binding."""
        mock_query.variables = {
            '_interaction_submission': {
                'interaction_id': 'form-1',
                'action_id': 'approve',
                'values': {'name': 'Alice'},
            }
        }

        event = QueryEntryAdapter.query_to_event(mock_query)
        agent_config = QueryEntryAdapter.config_to_agent_config(mock_query, 'plugin:langbot-team/DifyAgent/default')
        binding = AgentBindingResolver().resolve_one(event, [agent_config])

        assert event.event_type == 'interaction.submitted'
        assert event.data['interaction']['values'] == {'name': 'Alice'}
        assert event.subject.subject_type == 'interaction'
        assert agent_config.event_types == ['interaction.submitted']
        assert binding.processor_type == 'pipeline'

    def test_resolver_rejects_multiple_matching_agents(self, mock_query):
        """Event dispatch is single-Agent in v1."""
        event = QueryEntryAdapter.query_to_event(mock_query)
        first = QueryEntryAdapter.config_to_agent_config(mock_query, 'plugin:test/plugin/runner')
        second = first.model_copy(update={'agent_id': 'agent_2'})

        with pytest.raises(AgentBindingResolutionError):
            AgentBindingResolver().resolve_one(event, [first, second])


class TestAgentRunContextProtocolV1:
    """Test AgentRunContext Protocol v1 behavior."""

    def test_sdk_context_event_required(self):
        """Test that event is required in Protocol v1 context."""
        trigger = AgentTrigger(type='message.received')
        event = AgentEventContext(
            event_id='evt_1',
            event_type='message.received',
            source='platform',
        )
        input = AgentInput(text='Hello')
        from langbot_plugin.api.entities.builtin.agent_runner.resources import AgentResources
        from langbot_plugin.api.entities.builtin.agent_runner.runtime import AgentRuntimeContext
        from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext

        ctx = AgentRunContext(
            run_id='run_1',
            trigger=trigger,
            event=event,
            input=input,
            delivery=DeliveryContext(surface='platform'),
            resources=AgentResources(),
            runtime=AgentRuntimeContext(),
        )

        assert ctx.event is not None
        assert ctx.event.event_type == 'message.received'

    def test_sdk_context_has_no_history_message_fields(self):
        """AgentRunContext should not expose inline history message fields."""
        trigger = AgentTrigger(type='message.received')
        event = AgentEventContext(
            event_id='evt_1',
            event_type='message.received',
            source='platform',
        )
        input = AgentInput(text='Hello')
        from langbot_plugin.api.entities.builtin.agent_runner.resources import AgentResources
        from langbot_plugin.api.entities.builtin.agent_runner.runtime import AgentRuntimeContext
        from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext

        ctx = AgentRunContext(
            run_id='run_1',
            trigger=trigger,
            event=event,
            input=input,
            delivery=DeliveryContext(surface='platform'),
            resources=AgentResources(),
            runtime=AgentRuntimeContext(),
        )

        assert 'messages' not in AgentRunContext.model_fields
        assert 'bootstrap' not in AgentRunContext.model_fields
        assert not hasattr(ctx, 'bootstrap')


class TestHostManagedHistoryNotInProtocol:
    """Test that Host-managed history payloads are not in Protocol v1."""

    def test_messages_not_in_sdk_context_top_level(self):
        """AgentRunContext should not expose top-level history messages."""
        ctx_fields = AgentRunContext.model_fields.keys()

        assert 'messages' not in ctx_fields


class TestSDKResultProtocolV1:
    """Test SDK AgentRunResult for Protocol v1."""

    def test_result_requires_run_id(self):
        """Test result requires run_id for Protocol v1."""
        from langbot_plugin.api.entities.builtin.provider.message import Message

        result = AgentRunResult.message_completed(
            run_id='run_1',
            message=Message(role='assistant', content='Hello'),
        )

        assert result.run_id == 'run_1'


# Fixtures
@pytest.fixture
def mock_query():
    """Create a mock query for testing."""
    query = Mock()
    query.query_id = 123
    query.bot_uuid = 'bot-uuid-123'
    query.pipeline_uuid = 'pipeline-uuid-456'
    query.launcher_type = Mock(value='person')
    query.launcher_id = 'launcher-123'
    query.sender_id = 'sender-123'
    query.pipeline_config = {
        'ai': {
            'runner': 'plugin:test/plugin/runner',
        }
    }
    query.variables = {}

    # Create a proper content element mock
    content_elem = Mock(spec=['type', 'text', 'model_dump'])
    content_elem.type = 'text'
    content_elem.text = 'Hello world'
    content_elem.model_dump = Mock(return_value={'type': 'text', 'text': 'Hello world'})

    query.user_message = Mock()
    query.user_message.content = [content_elem]

    # Create message_chain mock
    message_chain = Mock()
    message_chain.message_id = 789
    message_chain.model_dump = Mock(return_value={'message_id': 789, 'components': []})
    query.message_chain = message_chain

    query.message_event = None

    # Mock session with proper conversation
    query.session = Mock()
    query.session.launcher_type = Mock(value='person')
    query.session.launcher_id = 'launcher-123'
    query.session.using_conversation = Mock()
    query.session.using_conversation.uuid = 'conv-uuid-123'

    # Mock use_funcs (empty list by default)
    query.use_funcs = []
    query.use_llm_model_uuid = None

    return query


@pytest.fixture
def mock_query_no_session():
    """Create a mock Query without session."""
    query = Mock()
    query.query_id = 456
    query.bot_uuid = 'bot-uuid-456'
    query.pipeline_uuid = 'pipeline-uuid-789'
    query.launcher_type = Mock(value='person')
    query.launcher_id = 'launcher-456'
    query.sender_id = 'sender-456'
    query.pipeline_config = {
        'ai': {
            'runner': 'plugin:test/plugin/runner',
        }
    }
    query.variables = {}

    # Create a proper content element mock
    content_elem = Mock(spec=['type', 'text', 'model_dump'])
    content_elem.type = 'text'
    content_elem.text = 'Test message'
    content_elem.model_dump = Mock(return_value={'type': 'text', 'text': 'Test message'})

    query.user_message = Mock()
    query.user_message.content = [content_elem]

    message_chain = Mock()
    message_chain.message_id = -1
    message_chain.model_dump = Mock(return_value={'message_id': -1, 'components': []})
    query.message_chain = message_chain

    query.message_event = None
    query.session = None

    # Mock use_funcs
    query.use_funcs = []
    query.use_llm_model_uuid = None

    return query
