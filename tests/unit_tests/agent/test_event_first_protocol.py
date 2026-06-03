"""Tests for event-first Protocol v1 entities and Query entry adapter.

Tests cover:
1. Query -> AgentEventEnvelope conversion
2. Current config -> AgentBinding conversion
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
    AgentRunResultType,
)
from langbot_plugin.api.entities.builtin.agent_runner.capabilities import (
    AgentRunnerCapabilities,
)
from langbot_plugin.api.entities.builtin.agent_runner.permissions import (
    AgentRunnerPermissions,
)

# Import LangBot host models
from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter


class TestQueryToEventEnvelope:
    """Test Query -> AgentEventEnvelope conversion."""

    def test_query_to_event_basic_fields(self, mock_query):
        """Test basic field conversion from Query to Event envelope."""
        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.event_type == "message.received"
        assert event.source == "host_adapter"
        assert event.bot_id == mock_query.bot_uuid
        assert event.actor is not None
        assert event.actor.actor_type == "user"

    def test_query_to_event_input(self, mock_query):
        """Test input conversion from Query."""
        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.input is not None
        assert event.input.text == "Hello world"

    def test_query_to_event_conversation(self, mock_query):
        """Test conversation context extraction."""
        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.conversation_id == "conv-uuid-123"

    def test_query_to_event_prefers_variable_conversation_id_when_conversation_uuid_missing(self, mock_query):
        """Pipeline variables can provide the conversation identity for state scope."""
        mock_query.session.using_conversation.uuid = None
        mock_query.variables["conversation_id"] = "conv-from-vars"

        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.conversation_id == "conv-from-vars"

    def test_query_to_event_falls_back_to_launcher_session_for_state_scope(self, mock_query):
        """Debug Chat and legacy pipeline runs may not have a conversation UUID."""
        mock_query.session.using_conversation.uuid = None

        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.conversation_id == "person_launcher-123"

    def test_query_to_event_delivery_context(self, mock_query):
        """Test delivery context extraction."""
        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.delivery is not None
        assert event.delivery.surface == "platform"
        assert isinstance(event.delivery.supports_streaming, bool)

    def test_query_to_event_preserves_source_event_data(self, mock_query):
        """Test source event metadata survives the adapter boundary."""
        source_event = Mock()
        source_event.type = "platform.message.created"
        source_event.time = 1700000000
        source_event.sender = None
        source_event.model_dump = Mock(return_value={
            "type": "platform.message.created",
            "message_id": "source-message-1",
            "source_platform_object": {"large": "payload"},
        })
        mock_query.message_event = source_event

        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.source_event_type == "platform.message.created"
        assert event.event_time == 1700000000
        assert event.data == {
            "type": "platform.message.created",
            "message_id": "source-message-1",
        }

    def test_query_to_event_handles_missing_message_chain(self, mock_query):
        """Test delivery context building when Query has no message_chain."""
        delattr(mock_query, "message_chain")

        event = QueryEntryAdapter.query_to_event(mock_query)

        assert event.delivery.reply_target == {"message_id": None}

    def test_query_to_event_scopes_pipeline_local_event_ids(self, mock_query):
        """Pipeline-local message IDs must not become global audit IDs."""
        first = QueryEntryAdapter.query_to_event(mock_query)

        mock_query.launcher_id = "launcher-456"
        second = QueryEntryAdapter.query_to_event(mock_query)

        assert first.event_id.startswith("host:")
        assert first.event_id != "789"
        assert second.event_id != first.event_id


class TestQueryConfigToBinding:
    """Test current config -> AgentBinding conversion."""

    def test_config_to_binding_runner_id(self, mock_query):
        """Test binding runner_id extraction."""
        binding = QueryEntryAdapter.config_to_binding(
            mock_query, "plugin:author/plugin/runner"
        )

        assert binding.runner_id == "plugin:author/plugin/runner"

    def test_config_to_binding_scope(self, mock_query):
        """Test binding scope extraction."""
        binding = QueryEntryAdapter.config_to_binding(
            mock_query, "plugin:test/plugin/runner"
        )

        assert binding.scope.scope_type == "agent"
        assert binding.scope.scope_id == mock_query.pipeline_uuid
        assert binding.agent_id == mock_query.pipeline_uuid

class TestAgentRunContextProtocolV1:
    """Test AgentRunContext Protocol v1 behavior."""

    def test_sdk_context_event_required(self):
        """Test that event is required in Protocol v1 context."""
        trigger = AgentTrigger(type="message.received")
        event = AgentEventContext(
            event_id="evt_1",
            event_type="message.received",
            source="platform",
        )
        input = AgentInput(text="Hello")
        from langbot_plugin.api.entities.builtin.agent_runner.resources import AgentResources
        from langbot_plugin.api.entities.builtin.agent_runner.runtime import AgentRuntimeContext
        from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext

        ctx = AgentRunContext(
            run_id="run_1",
            trigger=trigger,
            event=event,
            input=input,
            delivery=DeliveryContext(surface="platform"),
            resources=AgentResources(),
            runtime=AgentRuntimeContext(),
        )

        assert ctx.event is not None
        assert ctx.event.event_type == "message.received"

    def test_sdk_context_has_no_history_message_fields(self):
        """AgentRunContext should not expose inline history message fields."""
        trigger = AgentTrigger(type="message.received")
        event = AgentEventContext(
            event_id="evt_1",
            event_type="message.received",
            source="platform",
        )
        input = AgentInput(text="Hello")
        from langbot_plugin.api.entities.builtin.agent_runner.resources import AgentResources
        from langbot_plugin.api.entities.builtin.agent_runner.runtime import AgentRuntimeContext
        from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext

        ctx = AgentRunContext(
            run_id="run_1",
            trigger=trigger,
            event=event,
            input=input,
            delivery=DeliveryContext(surface="platform"),
            resources=AgentResources(),
            runtime=AgentRuntimeContext(),
        )

        assert "messages" not in AgentRunContext.model_fields
        assert "bootstrap" not in AgentRunContext.model_fields
        assert not hasattr(ctx, "bootstrap")


class TestHostManagedHistoryNotInProtocol:
    """Test that Host-managed history payloads are not in Protocol v1."""

    def test_messages_not_in_sdk_context_top_level(self):
        """AgentRunContext should not expose top-level history messages."""
        ctx_fields = AgentRunContext.model_fields.keys()

        assert "messages" not in ctx_fields


class TestSDKCapabilitiesProtocolV1:
    """Test SDK capabilities for Protocol v1."""

    def test_self_managed_context_default_true(self):
        """Test self_managed_context defaults to True for Protocol v1."""
        caps = AgentRunnerCapabilities()

        assert caps.self_managed_context is True

    def test_event_context_default_true(self):
        """Test event_context defaults to True for Protocol v1."""
        caps = AgentRunnerCapabilities()

        assert caps.event_context is True


class TestSDKPermissionsProtocolV1:
    """Test SDK permissions for Protocol v1."""

    def test_permissions_new_fields(self):
        """Test new permission fields for Protocol v1."""
        perms = AgentRunnerPermissions(
            models=["invoke", "stream", "rerank"],
            tools=["detail", "call"],
            knowledge_bases=["list", "retrieve"],
            history=["page", "search"],
            events=["get", "page"],
            artifacts=["metadata", "read"],
            storage=["plugin", "workspace", "binding"],
        )

        assert perms.history == ["page", "search"]
        assert perms.events == ["get", "page"]
        assert perms.artifacts == ["metadata", "read"]
        assert perms.storage == ["plugin", "workspace", "binding"]


class TestSDKResultProtocolV1:
    """Test SDK AgentRunResult for Protocol v1."""

    def test_result_requires_run_id(self):
        """Test result requires run_id for Protocol v1."""
        from langbot_plugin.api.entities.builtin.provider.message import Message

        result = AgentRunResult.message_completed(
            run_id="run_1",
            message=Message(role="assistant", content="Hello"),
        )

        assert result.run_id == "run_1"

    def test_artifact_created_result_type(self):
        """Test artifact.created result type."""
        result = AgentRunResult.artifact_created(
            run_id="run_1",
            artifact_id="artifact_1",
            artifact_type="image",
        )

        assert result.type == AgentRunResultType.ARTIFACT_CREATED
        assert result.data["artifact_id"] == "artifact_1"


# Fixtures
@pytest.fixture
def mock_query():
    """Create a mock query for testing."""
    query = Mock()
    query.query_id = 123
    query.bot_uuid = "bot-uuid-123"
    query.pipeline_uuid = "pipeline-uuid-456"
    query.launcher_type = Mock(value="person")
    query.launcher_id = "launcher-123"
    query.sender_id = "sender-123"
    query.pipeline_config = {
        "ai": {
            "runner": "plugin:test/plugin/runner",
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
    query.session.launcher_type = Mock(value="person")
    query.session.launcher_id = "launcher-123"
    query.session.using_conversation = Mock()
    query.session.using_conversation.uuid = "conv-uuid-123"

    # Mock use_funcs (empty list by default)
    query.use_funcs = []
    query.use_llm_model_uuid = None

    return query


@pytest.fixture
def mock_query_no_session():
    """Create a mock Query without session."""
    query = Mock()
    query.query_id = 456
    query.bot_uuid = "bot-uuid-456"
    query.pipeline_uuid = "pipeline-uuid-789"
    query.launcher_type = Mock(value="person")
    query.launcher_id = "launcher-456"
    query.sender_id = "sender-456"
    query.pipeline_config = {
        "ai": {
            "runner": "plugin:test/plugin/runner",
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
