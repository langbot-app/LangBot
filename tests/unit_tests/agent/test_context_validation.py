"""Test that LangBot context builder output validates against SDK AgentRunContext."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import uuid

# SDK imports for validation
from langbot_plugin.api.entities.builtin.agent_runner.context import AgentRunContext
from langbot_plugin.api.entities.builtin.agent_runner.event import AgentEventContext
from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.agent_runner.context_access import ContextAccess
from langbot_plugin.api.entities.builtin.agent_runner.trigger import AgentTrigger
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
from langbot_plugin.api.entities.builtin.agent_runner.resources import AgentResources
from langbot_plugin.api.entities.builtin.agent_runner.runtime import AgentRuntimeContext
from langbot_plugin.api.entities.builtin.agent_runner.state import AgentRunState

# LangBot imports
from langbot.pkg.agent.runner.context_builder import (
    AgentRunContextBuilder,
    AgentTrigger as BuilderTrigger,
    ConversationContext as BuilderConversation,
    AgentInput as BuilderInput,
    AgentRunState as BuilderState,
    AgentResources as BuilderResources,
    AgentRuntimeContext as BuilderRuntime,
)
from langbot.pkg.agent.runner.host_models import AgentEventEnvelope, AgentBinding, BindingScope
from langbot.pkg.core import app


class TestContextValidation:
    """Test that context builder output validates against SDK AgentRunContext."""

    def _make_mock_app(self):
        """Create a mock application."""
        mock_app = MagicMock(spec=app.Application)
        mock_app.ver_mgr = MagicMock()
        mock_app.ver_mgr.get_current_version = MagicMock(return_value="1.0.0")
        mock_app.persistence_mgr = MagicMock()
        mock_app.persistence_mgr.get_db_engine = MagicMock()
        mock_app.logger = MagicMock()
        return mock_app

    def _make_event_envelope(self) -> AgentEventEnvelope:
        """Create a test event envelope."""
        from langbot_plugin.api.entities.builtin.agent_runner.event import ActorContext
        from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput as EventInput
        from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext

        return AgentEventEnvelope(
            event_id="evt_1",
            event_type="message.received",
            event_time=1700000000,
            source="platform",
            bot_id="bot_1",
            workspace_id=None,
            conversation_id="conv_1",
            thread_id=None,
            actor=ActorContext(
                actor_type="user",
                actor_id="user_1",
                actor_name="Test User",
            ),
            subject=None,
            input=EventInput(text="Hello world"),
            delivery=DeliveryContext(surface="test"),
        )

    def _make_binding(self) -> AgentBinding:
        """Create a test binding."""
        return AgentBinding(
            binding_id="binding_1",
            scope=BindingScope(scope_type="pipeline", scope_id="pipeline_1"),
            event_types=["message.received"],
            runner_id="plugin:test/plugin/runner",
            runner_config={"timeout": 300},
            pipeline_uuid="pipeline_1",
            enabled=True,
        )

    def _make_resources(self) -> BuilderResources:
        """Create test resources."""
        return {
            'models': [],
            'tools': [],
            'knowledge_bases': [],
            'files': [],
            'storage': {'plugin_storage': True, 'workspace_storage': True},
            'platform_capabilities': {},
        }

    def _make_descriptor(self):
        """Create a mock runner descriptor."""
        descriptor = MagicMock()
        descriptor.id = "plugin:test/plugin/runner"
        descriptor.protocol_version = "1"
        descriptor.permissions = {
            'history': ['page', 'search'],
            'events': ['get', 'page'],
        }
        return descriptor

    @pytest.mark.asyncio
    async def test_build_context_from_event_validates(self):
        """Test that build_context_from_event output validates against SDK AgentRunContext."""
        mock_app = self._make_mock_app()
        builder = AgentRunContextBuilder(mock_app)

        event = self._make_event_envelope()
        binding = self._make_binding()
        resources = self._make_resources()
        descriptor = self._make_descriptor()

        # Build context
        context_dict = await builder.build_context_from_event(
            event=event,
            binding=binding,
            descriptor=descriptor,
            resources=resources,
        )

        # Validate it can be parsed by SDK AgentRunContext
        # This will raise ValidationError if invalid
        validated = AgentRunContext.model_validate(context_dict)

        # Verify required fields
        assert validated.run_id is not None
        assert validated.event is not None
        assert isinstance(validated.event, AgentEventContext)
        assert validated.delivery is not None
        assert isinstance(validated.delivery, DeliveryContext)
        assert validated.context is not None
        assert isinstance(validated.context, ContextAccess)
        assert validated.input is not None
        assert isinstance(validated.input, AgentInput)
        assert validated.resources is not None
        assert isinstance(validated.resources, AgentResources)
        assert validated.runtime is not None
        assert isinstance(validated.runtime, AgentRuntimeContext)

        # Verify event context
        assert validated.event.event_id == "evt_1"
        assert validated.event.event_type == "message.received"
        assert validated.event.source == "platform"

        # Verify delivery context
        assert validated.delivery.surface == "test"

        # Verify input
        assert validated.input.text == "Hello world"

    @pytest.mark.asyncio
    async def test_build_context_from_event_has_no_legacy_top_level_fields(self):
        """Test that build_context_from_event does NOT have top-level messages/prompt/params."""
        mock_app = self._make_mock_app()
        builder = AgentRunContextBuilder(mock_app)

        event = self._make_event_envelope()
        binding = self._make_binding()
        resources = self._make_resources()
        descriptor = self._make_descriptor()

        context_dict = await builder.build_context_from_event(
            event=event,
            binding=binding,
            descriptor=descriptor,
            resources=resources,
        )

        # Protocol v1 does NOT have these as core fields
        assert 'messages' not in context_dict, "messages should not be top-level in Protocol v1"
        assert 'prompt' not in context_dict, "prompt should not be top-level in Protocol v1"
        assert 'params' not in context_dict, "params should not be top-level in Protocol v1"

        # Protocol v1 DOES have these
        assert 'delivery' in context_dict, "delivery is REQUIRED in Protocol v1"
        assert 'context' in context_dict, "context (ContextAccess) is REQUIRED in Protocol v1"
        assert 'bootstrap' in context_dict, "bootstrap should exist (can be None)"
        assert 'compatibility' in context_dict, "compatibility should exist"
        assert 'metadata' in context_dict, "metadata should exist"

    @pytest.mark.asyncio
    async def test_build_context_from_event_event_is_not_none(self):
        """Test that event field is NOT None in Protocol v1."""
        mock_app = self._make_mock_app()
        builder = AgentRunContextBuilder(mock_app)

        event = self._make_event_envelope()
        binding = self._make_binding()
        resources = self._make_resources()
        descriptor = self._make_descriptor()

        context_dict = await builder.build_context_from_event(
            event=event,
            binding=binding,
            descriptor=descriptor,
            resources=resources,
        )

        # event is REQUIRED in Protocol v1
        assert context_dict.get('event') is not None, "event is REQUIRED for Protocol v1"

        # Validate
        validated = AgentRunContext.model_validate(context_dict)
        assert validated.event is not None

    @pytest.mark.asyncio
    async def test_build_context_from_event_delivery_is_not_none(self):
        """Test that delivery field is NOT None in Protocol v1."""
        mock_app = self._make_mock_app()
        builder = AgentRunContextBuilder(mock_app)

        event = self._make_event_envelope()
        binding = self._make_binding()
        resources = self._make_resources()
        descriptor = self._make_descriptor()

        context_dict = await builder.build_context_from_event(
            event=event,
            binding=binding,
            descriptor=descriptor,
            resources=resources,
        )

        # delivery is REQUIRED in Protocol v1
        assert context_dict.get('delivery') is not None, "delivery is REQUIRED for Protocol v1"

        # Validate
        validated = AgentRunContext.model_validate(context_dict)
        assert validated.delivery is not None
