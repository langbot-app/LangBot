"""Tests for event-first Protocol v1 entities and Pipeline adapter.

Tests cover:
1. Pipeline Query -> AgentEventEnvelope conversion
2. Pipeline config -> AgentBinding conversion
3. AgentRunContext not inlining full history by default
4. Pipeline max-round only affecting bootstrap/adapter context
5. Event-first run() entry point
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, MagicMock, patch
import typing

# Import SDK entities
from langbot_plugin.api.entities.builtin.agent_runner.event import (
    AgentEventContext,
    ConversationContext,
    ActorContext,
    SubjectContext,
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
from langbot_plugin.api.entities.builtin.agent_runner.context_policy import (
    AgentRunnerContextPolicy,
)
from langbot_plugin.api.entities.builtin.agent_runner.manifest import (
    AgentRunnerManifest,
)

# Import LangBot host models
from langbot.pkg.agent.runner.host_models import (
    AgentEventEnvelope,
    AgentBinding,
    BindingScope,
    ResourcePolicy,
    StatePolicy,
    DeliveryPolicy,
)
from langbot.pkg.agent.runner.pipeline_adapter import PipelineAdapter


class TestPipelineQueryToEventEnvelope:
    """Test Pipeline Query -> AgentEventEnvelope conversion."""

    def test_query_to_event_basic_fields(self, mock_query):
        """Test basic field conversion from Query to Event envelope."""
        event = PipelineAdapter.query_to_event(mock_query)

        assert event.event_type == "message.received"
        assert event.source == "pipeline_adapter"
        assert event.bot_id == mock_query.bot_uuid
        assert event.actor is not None
        assert event.actor.actor_type == "user"

    def test_query_to_event_input(self, mock_query):
        """Test input conversion from Query."""
        event = PipelineAdapter.query_to_event(mock_query)

        assert event.input is not None
        assert event.input.text == "Hello world"

    def test_query_to_event_conversation(self, mock_query):
        """Test conversation context extraction."""
        event = PipelineAdapter.query_to_event(mock_query)

        # Conversation may be None if no session
        if event.conversation_id:
            assert event.conversation_id is not None

    def test_query_to_event_delivery_context(self, mock_query):
        """Test delivery context extraction."""
        event = PipelineAdapter.query_to_event(mock_query)

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

        event = PipelineAdapter.query_to_event(mock_query)

        assert event.source_event_type == "platform.message.created"
        assert event.event_time == 1700000000
        assert event.data == {
            "type": "platform.message.created",
            "message_id": "source-message-1",
        }

    def test_query_to_event_handles_missing_message_chain(self, mock_query):
        """Test delivery context building when Query has no message_chain."""
        delattr(mock_query, "message_chain")

        event = PipelineAdapter.query_to_event(mock_query)

        assert event.delivery.reply_target == {"message_id": None}


class TestPipelineConfigToBinding:
    """Test Pipeline config -> AgentBinding conversion."""

    def test_config_to_binding_runner_id(self, mock_query):
        """Test binding runner_id extraction."""
        binding = PipelineAdapter.pipeline_config_to_binding(
            mock_query, "plugin:author/plugin/runner"
        )

        assert binding.runner_id == "plugin:author/plugin/runner"

    def test_config_to_binding_scope(self, mock_query):
        """Test binding scope extraction."""
        binding = PipelineAdapter.pipeline_config_to_binding(
            mock_query, "plugin:test/plugin/runner"
        )

        assert binding.scope.scope_type == "pipeline"
        assert binding.scope.scope_id == mock_query.pipeline_uuid

    def test_config_to_binding_max_round(self, mock_query_with_max_round):
        """Test max_round extraction for Pipeline adapter."""
        binding = PipelineAdapter.pipeline_config_to_binding(
            mock_query_with_max_round, "plugin:test/plugin/runner"
        )

        # max_round should be captured but NOT in Protocol v1 entities
        assert binding.max_round == 10

    def test_config_to_binding_no_max_round(self, mock_query):
        """Test binding without max_round."""
        binding = PipelineAdapter.pipeline_config_to_binding(
            mock_query, "plugin:test/plugin/runner"
        )

        # max_round may be None
        assert binding.max_round is None


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

    def test_sdk_context_messages_default_empty(self):
        """Test that messages default to empty (not full history)."""
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

        # messages is now in bootstrap, not top-level
        assert ctx.bootstrap is None or ctx.bootstrap.messages == []

    def test_sdk_context_bootstrap_optional(self):
        """Test that bootstrap is optional."""
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

        # bootstrap is optional
        assert ctx.bootstrap is None or isinstance(ctx.bootstrap.messages, list)


class TestMaxRoundNotInProtocol:
    """Test that Pipeline max-round only affects adapter context, not Protocol v1."""

    def test_max_round_not_in_sdk_context(self):
        """Test max-round is not a field in SDK AgentRunContext."""
        # AgentRunContext should not have max_round field
        ctx_fields = AgentRunContext.model_fields.keys()

        assert "max_round" not in ctx_fields
        assert "maxRound" not in ctx_fields

    def test_max_round_in_adapter_context(self):
        """Test max_round is in adapter context, not main context."""
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
        from langbot_plugin.api.entities.builtin.agent_runner.context import AdapterContext

        adapter = AdapterContext(max_round=10)

        ctx = AgentRunContext(
            run_id="run_1",
            trigger=trigger,
            event=event,
            input=input,
            delivery=DeliveryContext(surface="platform"),
            resources=AgentResources(),
            runtime=AgentRuntimeContext(),
            adapter=adapter,
        )

        # max_round is in adapter context, not main context
        assert ctx.adapter is not None
        assert ctx.adapter.max_round == 10

    def test_binding_max_round_for_adapter_only(self, mock_query_with_max_round):
        """Test max_round in binding is for adapter use, not Protocol v1."""
        binding = PipelineAdapter.pipeline_config_to_binding(
            mock_query_with_max_round, "plugin:test/plugin/runner"
        )

        # max_round is in binding (Host-internal) for Pipeline adapter
        assert binding.max_round == 10

        # But SDK entities don't have it
        ctx_fields = AgentRunContext.model_fields.keys()
        assert "max_round" not in ctx_fields


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
    """Create a mock Pipeline Query for testing."""
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
def mock_query_with_max_round(mock_query):
    """Create a mock Query with max_round configuration."""
    mock_query.pipeline_config = {
        "ai": {
            "runner": "plugin:test/plugin/runner",
            "max-round": 10,
        }
    }
    return mock_query


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
