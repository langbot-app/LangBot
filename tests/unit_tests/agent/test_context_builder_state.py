"""Tests for ContextAccess.state determination in AgentRunContextBuilder.

Tests focus on:
- Event-first mode: state=True when enable_state=True and state_scopes non-empty
- Event-first mode: state=False when enable_state=False
- Legacy Query mode: state=False (no persistent state API)
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from langbot.pkg.agent.runner.context_builder import AgentRunContextBuilder
from langbot.pkg.agent.runner.host_models import AgentEventEnvelope, AgentBinding, BindingScope, StatePolicy
from langbot_plugin.api.entities.builtin.agent_runner.event import ActorContext
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext


class MockApplication:
    """Mock Application for testing."""
    def __init__(self):
        self.logger = MagicMock()
        self.persistence_mgr = MagicMock()
        self.persistence_mgr.get_db_engine = MagicMock()


class TestContextAccessStateDetermination:
    """Tests for ContextAccess.state field determination - real calls to _build_context_access."""

    @pytest.fixture
    def mock_app(self):
        """Create mock application."""
        return MockApplication()

    @pytest.fixture
    def mock_event(self):
        """Create mock event envelope."""
        return AgentEventEnvelope(
            event_id='evt_001',
            event_type='message.received',
            event_time=1234567890,
            source='test',
            bot_id='bot_001',
            workspace_id='ws_001',
            conversation_id='conv_001',
            thread_id=None,
            actor=ActorContext(actor_type='user', actor_id='user_001'),
            subject=None,
            input=AgentInput(text='hello', contents=[], attachments=[]),
            delivery=DeliveryContext(surface='test', supports_streaming=True),
        )

    @pytest.fixture
    def mock_descriptor(self):
        """Create mock runner descriptor."""
        descriptor = MagicMock()
        descriptor.id = 'plugin:test/runner/default'
        descriptor.protocol_version = '1.0'
        descriptor.permissions = {}
        return descriptor

    @pytest.mark.asyncio
    async def test_enable_state_true_with_scopes_sets_state_true(self, mock_app, mock_event, mock_descriptor):
        """ContextAccess.state=True when enable_state=True and state_scopes non-empty."""
        # Create binding with state enabled and non-empty scopes
        binding = AgentBinding(
            binding_id='binding_001',
            runner_id='plugin:test/runner/default',
            scope=BindingScope(scope_type='agent', scope_id='conv_001'),
            state_policy=StatePolicy(
                enable_state=True,
                state_scopes=['conversation', 'actor'],
            ),
        )

        builder = AgentRunContextBuilder(mock_app)

        # Real call to _build_context_access
        context_access = await builder._build_context_access(mock_event, mock_descriptor, binding)

        # Verify state=True based on binding.state_policy
        assert context_access['available_apis']['state'] is True

    @pytest.mark.asyncio
    async def test_enable_state_false_sets_state_false(self, mock_app, mock_event, mock_descriptor):
        """ContextAccess.state=False when enable_state=False."""
        binding = AgentBinding(
            binding_id='binding_001',
            runner_id='plugin:test/runner/default',
            scope=BindingScope(scope_type='agent', scope_id='conv_001'),
            state_policy=StatePolicy(
                enable_state=False,
                state_scopes=[],
            ),
        )

        builder = AgentRunContextBuilder(mock_app)

        # Real call
        context_access = await builder._build_context_access(mock_event, mock_descriptor, binding)

        # Verify state=False
        assert context_access['available_apis']['state'] is False

    @pytest.mark.asyncio
    async def test_enable_state_true_empty_scopes_sets_state_false(self, mock_app, mock_event, mock_descriptor):
        """ContextAccess.state=False when enable_state=True but state_scopes empty."""
        binding = AgentBinding(
            binding_id='binding_001',
            runner_id='plugin:test/runner/default',
            scope=BindingScope(scope_type='agent', scope_id='conv_001'),
            state_policy=StatePolicy(
                enable_state=True,
                state_scopes=[],  # Empty scopes - state not available
            ),
        )

        builder = AgentRunContextBuilder(mock_app)

        # Real call
        context_access = await builder._build_context_access(mock_event, mock_descriptor, binding)

        # Verify state=False (empty scopes means state not available)
        assert context_access['available_apis']['state'] is False

    @pytest.mark.asyncio
    async def test_no_binding_sets_state_false(self, mock_app, mock_event, mock_descriptor):
        """ContextAccess.state=False when no binding is provided."""
        builder = AgentRunContextBuilder(mock_app)

        # Real call without binding
        context_access = await builder._build_context_access(mock_event, mock_descriptor, binding=None)

        # Verify state=False (no binding = no state policy = state disabled)
        assert context_access['available_apis']['state'] is False

    @pytest.mark.asyncio
    async def test_runner_scope_available_without_conversation(self, mock_app, mock_descriptor):
        """State API with runner scope is available even without conversation_id."""
        mock_event = AgentEventEnvelope(
            event_id='evt_002',
            event_type='message.received',
            event_time=1234567890,
            source='test',
            bot_id='bot_001',
            workspace_id='ws_001',
            conversation_id=None,  # No conversation
            thread_id=None,
            actor=ActorContext(actor_type='user', actor_id='user_001'),
            subject=None,
            input=AgentInput(text='hello', contents=[], attachments=[]),
            delivery=DeliveryContext(surface='test', supports_streaming=True),
        )

        binding = AgentBinding(
            binding_id='binding_002',
            runner_id='plugin:test/runner/default',
            scope=BindingScope(scope_type='workspace', scope_id='ws_001'),
            state_policy=StatePolicy(
                enable_state=True,
                state_scopes=['runner'],  # Runner scope doesn't need conversation_id
            ),
        )

        builder = AgentRunContextBuilder(mock_app)

        # Real call
        context_access = await builder._build_context_access(mock_event, mock_descriptor, binding)

        # State should be True because runner scope is enabled
        assert context_access['available_apis']['state'] is True

    @pytest.mark.asyncio
    async def test_multiple_scopes_all_available(self, mock_app, mock_event, mock_descriptor):
        """State API with multiple scopes enabled."""
        binding = AgentBinding(
            binding_id='binding_003',
            runner_id='plugin:test/runner/default',
            scope=BindingScope(scope_type='agent', scope_id='conv_001'),
            state_policy=StatePolicy(
                enable_state=True,
                state_scopes=['conversation', 'actor', 'subject', 'runner'],
            ),
        )

        builder = AgentRunContextBuilder(mock_app)

        # Real call
        context_access = await builder._build_context_access(mock_event, mock_descriptor, binding)

        # State should be True with all scopes enabled
        assert context_access['available_apis']['state'] is True


class TestStatePolicyFromBinding:
    """Tests for state_policy extraction from binding."""

    def test_state_policy_structure(self):
        """State policy has correct structure."""
        policy = StatePolicy(
            enable_state=True,
            state_scopes=['conversation', 'actor', 'subject', 'runner'],
        )

        assert policy.enable_state is True
        assert len(policy.state_scopes) == 4
        assert 'conversation' in policy.state_scopes

    def test_state_policy_disabled(self):
        """State policy can be disabled."""
        policy = StatePolicy(
            enable_state=False,
            state_scopes=[],
        )

        assert policy.enable_state is False
        assert len(policy.state_scopes) == 0


class TestBindingWithStatePolicy:
    """Tests for binding with state_policy."""

    def test_binding_contains_state_policy(self):
        """Binding contains state_policy field."""
        binding = AgentBinding(
            binding_id='binding_001',
            runner_id='plugin:test/runner/default',
            scope=BindingScope(scope_type='agent', scope_id='conv_001'),
            state_policy=StatePolicy(
                enable_state=True,
                state_scopes=['conversation'],
            ),
        )

        assert binding.state_policy is not None
        assert binding.state_policy.enable_state is True


class TestContextAccessOtherAPIs:
    """Tests for other available_apis fields based on permissions."""

    @pytest.fixture
    def mock_app(self):
        """Create mock application."""
        return MockApplication()

    @pytest.mark.asyncio
    async def test_history_apis_based_on_permissions(self, mock_app):
        """History APIs availability based on runner permissions."""
        mock_event = MagicMock()
        mock_event.conversation_id = 'conv_001'
        mock_event.thread_id = None

        mock_descriptor = MagicMock()
        mock_descriptor.permissions = {
            'history': ['page', 'search'],
        }

        binding = AgentBinding(
            binding_id='binding_001',
            runner_id='plugin:test/runner/default',
            scope=BindingScope(scope_type='agent', scope_id='conv_001'),
            state_policy=StatePolicy(enable_state=False, state_scopes=[]),
        )

        builder = AgentRunContextBuilder(mock_app)

        # Real call
        context_access = await builder._build_context_access(mock_event, mock_descriptor, binding)

        # History APIs enabled based on permissions
        assert context_access['available_apis']['history_page'] is True
        assert context_access['available_apis']['history_search'] is True

    @pytest.mark.asyncio
    async def test_event_apis_based_on_permissions(self, mock_app):
        """Event APIs availability based on runner permissions."""
        mock_event = MagicMock()
        mock_event.conversation_id = 'conv_001'
        mock_event.thread_id = None

        mock_descriptor = MagicMock()
        mock_descriptor.permissions = {
            'events': ['get', 'page'],
        }

        binding = AgentBinding(
            binding_id='binding_001',
            runner_id='plugin:test/runner/default',
            scope=BindingScope(scope_type='agent', scope_id='conv_001'),
            state_policy=StatePolicy(enable_state=False, state_scopes=[]),
        )

        builder = AgentRunContextBuilder(mock_app)

        # Real call
        context_access = await builder._build_context_access(mock_event, mock_descriptor, binding)

        # Event APIs enabled based on permissions
        assert context_access['available_apis']['event_get'] is True
        assert context_access['available_apis']['event_page'] is True

    @pytest.mark.asyncio
    async def test_artifact_apis_based_on_permissions(self, mock_app):
        """Artifact APIs availability based on runner permissions."""
        mock_event = MagicMock()
        mock_event.conversation_id = 'conv_001'
        mock_event.thread_id = None

        mock_descriptor = MagicMock()
        mock_descriptor.permissions = {
            'artifacts': ['metadata', 'read'],
        }

        binding = AgentBinding(
            binding_id='binding_001',
            runner_id='plugin:test/runner/default',
            scope=BindingScope(scope_type='agent', scope_id='conv_001'),
            state_policy=StatePolicy(enable_state=False, state_scopes=[]),
        )

        builder = AgentRunContextBuilder(mock_app)

        # Real call
        context_access = await builder._build_context_access(mock_event, mock_descriptor, binding)

        # Artifact APIs enabled based on permissions
        assert context_access['available_apis']['artifact_metadata'] is True
        assert context_access['available_apis']['artifact_read'] is True

    @pytest.mark.asyncio
    async def test_no_permissions_all_apis_disabled(self, mock_app):
        """All pull APIs disabled when permissions are empty."""
        mock_event = MagicMock()
        mock_event.conversation_id = 'conv_001'
        mock_event.thread_id = None

        mock_descriptor = MagicMock()
        mock_descriptor.permissions = {}  # No permissions

        binding = AgentBinding(
            binding_id='binding_001',
            runner_id='plugin:test/runner/default',
            scope=BindingScope(scope_type='agent', scope_id='conv_001'),
            state_policy=StatePolicy(enable_state=False, state_scopes=[]),
        )

        builder = AgentRunContextBuilder(mock_app)

        # Real call
        context_access = await builder._build_context_access(mock_event, mock_descriptor, binding)

        # All pull APIs should be disabled
        assert context_access['available_apis']['history_page'] is False
        assert context_access['available_apis']['history_search'] is False
        assert context_access['available_apis']['event_get'] is False
        assert context_access['available_apis']['event_page'] is False
        assert context_access['available_apis']['artifact_metadata'] is False
        assert context_access['available_apis']['artifact_read'] is False
        assert context_access['available_apis']['state'] is False
