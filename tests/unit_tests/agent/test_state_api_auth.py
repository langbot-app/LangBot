"""Tests for State API handler authorization in RuntimeConnectionHandler.

Tests focus on:
- STATE_GET authorization
- STATE_SET authorization
- STATE_DELETE authorization
- STATE_LIST authorization

These tests instantiate real RuntimeConnectionHandler action handlers and verify:
- Authorization errors for missing/mismatched caller_plugin_identity
- Authorization errors for disabled state or scope
- Full flow: set -> get -> list -> delete with real SQLite

Authorization rules:
- caller_plugin_identity is REQUIRED when session has plugin_identity
- caller_plugin_identity must match session's plugin_identity
- enable_state must be True
- scope must be in state_scopes
"""
from __future__ import annotations

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.agent.runner.session_registry import AgentRunSessionRegistry, get_session_registry
from langbot.pkg.agent.runner.persistent_state_store import PersistentStateStore, reset_persistent_state_store
from langbot.pkg.plugin.handler import RuntimeConnectionHandler
from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

# Import shared test fixtures
from .conftest import make_resources


class FakeConnection:
    """Fake connection for testing."""
    pass


class FakeApplication:
    """Fake Application for testing."""
    def __init__(self, db_engine=None):
        self.logger = MagicMock()
        self.logger.debug = MagicMock()
        self.logger.warning = MagicMock()
        self.logger.error = MagicMock()
        self.persistence_mgr = MagicMock()
        self.persistence_mgr.get_db_engine = MagicMock(return_value=db_engine)


@pytest.fixture
def session_registry():
    """Create a fresh session registry for each test."""
    return AgentRunSessionRegistry()


@pytest.fixture
async def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    yield engine
    await engine.dispose()


@pytest.fixture
async def persistent_store(db_engine):
    """Create a persistent state store with real SQLite."""
    reset_persistent_state_store()
    store = PersistentStateStore(db_engine)

    # Create the table
    from langbot.pkg.entity.persistence.agent_runner_state import AgentRunnerState
    from sqlalchemy import text
    async with db_engine.begin() as conn:
        await conn.run_sync(AgentRunnerState.__table__.create, checkfirst=True)

    yield store
    reset_persistent_state_store()


class TestStateAPIHandlerAuthorization:
    """Tests for State API handler authorization with real action calls."""

    @pytest.mark.asyncio
    async def test_state_get_missing_run_id_returns_error(self, session_registry, db_engine, persistent_store):
        """STATE_GET: missing run_id returns error."""
        fake_app = FakeApplication(db_engine)
        fake_app.persistence_mgr.get_db_engine = MagicMock(return_value=db_engine)

        async def fake_disconnect():
            return True

        with patch('langbot.pkg.plugin.handler.get_session_registry', return_value=session_registry):
            handler = RuntimeConnectionHandler(FakeConnection(), fake_disconnect, fake_app)

            # Get the STATE_GET action handler (actions dict is keyed by action value string)
            state_get_handler = handler.actions[PluginToRuntimeAction.STATE_GET.value]

            # Call without run_id
            result = await state_get_handler({'scope': 'conversation', 'key': 'test_key'})

            assert result.code != 0
            assert 'run_id is required' in result.message

    @pytest.mark.asyncio
    async def test_state_get_run_not_found_returns_error(self, session_registry, db_engine, persistent_store):
        """STATE_GET: run_id not in session registry returns error."""
        fake_app = FakeApplication(db_engine)
        fake_app.persistence_mgr.get_db_engine = MagicMock(return_value=db_engine)

        async def fake_disconnect():
            return True

        with patch('langbot.pkg.plugin.handler.get_session_registry', return_value=session_registry):
            handler = RuntimeConnectionHandler(FakeConnection(), fake_disconnect, fake_app)
            state_get_handler = handler.actions[PluginToRuntimeAction.STATE_GET.value]

            # Call with non-existent run_id
            result = await state_get_handler({
                'run_id': 'nonexistent_run',
                'scope': 'conversation',
                'key': 'test_key',
            })

            assert result.code != 0
            assert 'not found' in result.message.lower()

    @pytest.mark.asyncio
    async def test_state_get_missing_caller_plugin_identity_returns_error(self, session_registry, db_engine, persistent_store):
        """STATE_GET: missing caller_plugin_identity when session has plugin_identity returns error."""
        fake_app = FakeApplication(db_engine)
        fake_app.persistence_mgr.get_db_engine = MagicMock(return_value=db_engine)

        # Register session with plugin_identity
        await session_registry.register(
            run_id='run_test_missing_identity',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=make_resources(),
            state_policy={'enable_state': True, 'state_scopes': ['conversation']},
            state_context={'scope_keys': {'conversation': 'conv_key'}, 'binding_identity': 'binding_1'},
        )

        async def fake_disconnect():
            return True

        with patch('langbot.pkg.plugin.handler.get_session_registry', return_value=session_registry):
            handler = RuntimeConnectionHandler(FakeConnection(), fake_disconnect, fake_app)
            state_get_handler = handler.actions[PluginToRuntimeAction.STATE_GET.value]

            # Call without caller_plugin_identity
            result = await state_get_handler({
                'run_id': 'run_test_missing_identity',
                'scope': 'conversation',
                'key': 'test_key',
            })

            assert result.code != 0
            assert 'caller_plugin_identity is required' in result.message

        await session_registry.unregister('run_test_missing_identity')

    @pytest.mark.asyncio
    async def test_state_get_caller_identity_mismatch_returns_error(self, session_registry, db_engine, persistent_store):
        """STATE_GET: caller_plugin_identity mismatch returns error."""
        fake_app = FakeApplication(db_engine)
        fake_app.persistence_mgr.get_db_engine = MagicMock(return_value=db_engine)

        await session_registry.register(
            run_id='run_test_mismatch',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=make_resources(),
            state_policy={'enable_state': True, 'state_scopes': ['conversation']},
            state_context={'scope_keys': {'conversation': 'conv_key'}, 'binding_identity': 'binding_1'},
        )

        async def fake_disconnect():
            return True

        with patch('langbot.pkg.plugin.handler.get_session_registry', return_value=session_registry):
            handler = RuntimeConnectionHandler(FakeConnection(), fake_disconnect, fake_app)
            state_get_handler = handler.actions[PluginToRuntimeAction.STATE_GET.value]

            # Call with wrong caller_plugin_identity
            result = await state_get_handler({
                'run_id': 'run_test_mismatch',
                'scope': 'conversation',
                'key': 'test_key',
                'caller_plugin_identity': 'other/plugin',
            })

            assert result.code != 0
            assert 'mismatch' in result.message.lower()

        await session_registry.unregister('run_test_mismatch')

    @pytest.mark.asyncio
    async def test_state_get_enable_state_false_returns_error(self, session_registry, db_engine, persistent_store):
        """STATE_GET: enable_state=False returns error."""
        fake_app = FakeApplication(db_engine)
        fake_app.persistence_mgr.get_db_engine = MagicMock(return_value=db_engine)

        await session_registry.register(
            run_id='run_test_disabled',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=make_resources(),
            state_policy={'enable_state': False, 'state_scopes': []},
            state_context={'scope_keys': {}, 'binding_identity': 'binding_1'},
        )

        async def fake_disconnect():
            return True

        with patch('langbot.pkg.plugin.handler.get_session_registry', return_value=session_registry):
            handler = RuntimeConnectionHandler(FakeConnection(), fake_disconnect, fake_app)
            state_get_handler = handler.actions[PluginToRuntimeAction.STATE_GET.value]

            result = await state_get_handler({
                'run_id': 'run_test_disabled',
                'scope': 'conversation',
                'key': 'test_key',
                'caller_plugin_identity': 'test/runner',
            })

            assert result.code != 0
            assert 'disabled' in result.message.lower()

        await session_registry.unregister('run_test_disabled')

    @pytest.mark.asyncio
    async def test_state_get_scope_not_enabled_returns_error(self, session_registry, db_engine, persistent_store):
        """STATE_GET: scope not in state_scopes returns error."""
        fake_app = FakeApplication(db_engine)
        fake_app.persistence_mgr.get_db_engine = MagicMock(return_value=db_engine)

        await session_registry.register(
            run_id='run_test_scope_disabled',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=make_resources(),
            state_policy={'enable_state': True, 'state_scopes': ['conversation']},
            state_context={'scope_keys': {'conversation': 'conv_key', 'actor': 'actor_key'}, 'binding_identity': 'binding_1'},
        )

        async def fake_disconnect():
            return True

        with patch('langbot.pkg.plugin.handler.get_session_registry', return_value=session_registry):
            handler = RuntimeConnectionHandler(FakeConnection(), fake_disconnect, fake_app)
            state_get_handler = handler.actions[PluginToRuntimeAction.STATE_GET.value]

            # Request 'actor' scope which is not in state_scopes
            result = await state_get_handler({
                'run_id': 'run_test_scope_disabled',
                'scope': 'actor',
                'key': 'test_key',
                'caller_plugin_identity': 'test/runner',
            })

            assert result.code != 0
            assert 'not enabled' in result.message.lower() or 'scope' in result.message.lower()

        await session_registry.unregister('run_test_scope_disabled')

    @pytest.mark.asyncio
    async def test_state_get_missing_scope_key_returns_error(self, session_registry, db_engine, persistent_store):
        """STATE_GET: missing scope_key in state_context returns error."""
        fake_app = FakeApplication(db_engine)
        fake_app.persistence_mgr.get_db_engine = MagicMock(return_value=db_engine)

        await session_registry.register(
            run_id='run_test_no_scope_key',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=make_resources(),
            state_policy={'enable_state': True, 'state_scopes': ['conversation']},
            state_context={'scope_keys': {}, 'binding_identity': 'binding_1'},  # No scope_keys
        )

        async def fake_disconnect():
            return True

        with patch('langbot.pkg.plugin.handler.get_session_registry', return_value=session_registry):
            handler = RuntimeConnectionHandler(FakeConnection(), fake_disconnect, fake_app)
            state_get_handler = handler.actions[PluginToRuntimeAction.STATE_GET.value]

            result = await state_get_handler({
                'run_id': 'run_test_no_scope_key',
                'scope': 'conversation',
                'key': 'test_key',
                'caller_plugin_identity': 'test/runner',
            })

            assert result.code != 0
            assert 'not available' in result.message.lower()

        await session_registry.unregister('run_test_no_scope_key')


class TestStateAPIFullFlowWithRealDB:
    """Tests for complete State API flow with real SQLite database."""

    @pytest.mark.asyncio
    async def test_state_set_get_list_delete_flow(self, session_registry, db_engine, persistent_store):
        """Test complete state flow: set -> get -> list -> delete with real SQLite."""
        fake_app = FakeApplication(db_engine)
        fake_app.persistence_mgr.get_db_engine = MagicMock(return_value=db_engine)

        # Register session
        await session_registry.register(
            run_id='run_full_flow',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=make_resources(),
            state_policy={'enable_state': True, 'state_scopes': ['conversation', 'runner']},
            state_context={
                'scope_keys': {
                    'conversation': 'conv:test_runner:binding_1:conv_123',
                    'runner': 'runner:test_runner:binding_1',
                },
                'binding_identity': 'binding_1',
                'conversation_id': 'conv_123',
            },
        )

        async def fake_disconnect():
            return True

        with patch('langbot.pkg.plugin.handler.get_session_registry', return_value=session_registry):
            handler = RuntimeConnectionHandler(FakeConnection(), fake_disconnect, fake_app)

            # Verify session has correct state_context
            session = await session_registry.get('run_full_flow')
            assert session is not None
            state_ctx = session.get('state_context')
            assert state_ctx is not None, f"state_context is None. Session keys: {list(session.keys())}"
            assert 'scope_keys' in state_ctx, f"scope_keys not in state_context: {state_ctx}"
            assert 'conversation' in state_ctx['scope_keys'], f"conversation not in scope_keys: {state_ctx['scope_keys']}"

            # Get handlers (actions dict is keyed by action value string)
            state_set_handler = handler.actions[PluginToRuntimeAction.STATE_SET.value]
            state_get_handler = handler.actions[PluginToRuntimeAction.STATE_GET.value]
            state_list_handler = handler.actions[PluginToRuntimeAction.STATE_LIST.value]
            state_delete_handler = handler.actions[PluginToRuntimeAction.STATE_DELETE.value]

            # 1. STATE_SET
            set_result = await state_set_handler({
                'run_id': 'run_full_flow',
                'scope': 'conversation',
                'key': 'external.test_key',
                'value': {'data': 'test_value'},
                'caller_plugin_identity': 'test/runner',
            })

            assert set_result.code == 0
            assert set_result.data.get('success') is True

            # 2. STATE_GET
            get_result = await state_get_handler({
                'run_id': 'run_full_flow',
                'scope': 'conversation',
                'key': 'external.test_key',
                'caller_plugin_identity': 'test/runner',
            })

            assert get_result.code == 0
            assert get_result.data.get('value') == {'data': 'test_value'}

            # 3. STATE_LIST
            list_result = await state_list_handler({
                'run_id': 'run_full_flow',
                'scope': 'conversation',
                'prefix': 'external.',
                'caller_plugin_identity': 'test/runner',
            })

            assert list_result.code == 0
            keys = list_result.data.get('keys', [])
            assert 'external.test_key' in keys

            # 4. STATE_DELETE
            delete_result = await state_delete_handler({
                'run_id': 'run_full_flow',
                'scope': 'conversation',
                'key': 'external.test_key',
                'caller_plugin_identity': 'test/runner',
            })

            assert delete_result.code == 0

            # 5. Verify deleted
            get_after_delete = await state_get_handler({
                'run_id': 'run_full_flow',
                'scope': 'conversation',
                'key': 'external.test_key',
                'caller_plugin_identity': 'test/runner',
            })

            assert get_after_delete.code == 0
            assert get_after_delete.data.get('value') is None

        await session_registry.unregister('run_full_flow')


class TestStateHandlerReadsFromSessionTopLevel:
    """Tests verifying handlers read state_policy/state_context from session top-level, not resources."""

    @pytest.mark.asyncio
    async def test_state_handler_reads_state_policy_from_session_top_level(self, session_registry, db_engine, persistent_store):
        """Handler reads state_policy from session['state_policy'], not session['resources']['state_policy']."""
        fake_app = FakeApplication(db_engine)
        fake_app.persistence_mgr.get_db_engine = MagicMock(return_value=db_engine)

        # Register with explicit state_policy at top level
        await session_registry.register(
            run_id='run_policy_top_level',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=make_resources(),
            state_policy={'enable_state': False, 'state_scopes': []},  # Disabled at top level
            state_context={'scope_keys': {}, 'binding_identity': 'binding_1'},
        )

        # Verify resources does NOT contain state_policy
        session = await session_registry.get('run_policy_top_level')
        assert session is not None
        assert 'state_policy' not in session.get('resources', {}), \
            "resources should NOT contain state_policy"

        async def fake_disconnect():
            return True

        with patch('langbot.pkg.plugin.handler.get_session_registry', return_value=session_registry):
            handler = RuntimeConnectionHandler(FakeConnection(), fake_disconnect, fake_app)
            state_get_handler = handler.actions[PluginToRuntimeAction.STATE_GET.value]

            # Should fail because enable_state=False in session['state_policy']
            result = await state_get_handler({
                'run_id': 'run_policy_top_level',
                'scope': 'conversation',
                'key': 'test_key',
                'caller_plugin_identity': 'test/runner',
            })

            assert result.code != 0
            assert 'disabled' in result.message.lower()

        await session_registry.unregister('run_policy_top_level')

    @pytest.mark.asyncio
    async def test_state_handler_reads_state_context_from_session_top_level(self, session_registry, db_engine, persistent_store):
        """Handler reads state_context from session['state_context'], not session['resources']['state_context']."""
        fake_app = FakeApplication(db_engine)
        fake_app.persistence_mgr.get_db_engine = MagicMock(return_value=db_engine)

        # Register with explicit state_context at top level
        await session_registry.register(
            run_id='run_context_top_level',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=make_resources(),
            state_policy={'enable_state': True, 'state_scopes': ['conversation']},
            state_context={'scope_keys': {'conversation': 'conv_key_xyz'}, 'binding_identity': 'binding_xyz'},
        )

        # Verify resources does NOT contain state_context
        session = await session_registry.get('run_context_top_level')
        assert session is not None
        assert 'state_context' not in session.get('resources', {}), \
            "resources should NOT contain state_context"

        async def fake_disconnect():
            return True

        with patch('langbot.pkg.plugin.handler.get_session_registry', return_value=session_registry):
            handler = RuntimeConnectionHandler(FakeConnection(), fake_disconnect, fake_app)
            state_set_handler = handler.actions[PluginToRuntimeAction.STATE_SET.value]

            # Should use scope_key from session['state_context']['scope_keys']['conversation']
            result = await state_set_handler({
                'run_id': 'run_context_top_level',
                'scope': 'conversation',
                'key': 'test_key',
                'value': 'test_value',
                'caller_plugin_identity': 'test/runner',
            })

            # Should succeed - scope_key was found in state_context
            assert result.code == 0

        await session_registry.unregister('run_context_top_level')


class TestResourcesDoesNotContainStateMetadata:
    """Tests verifying resources is clean - no state metadata mixed in."""

    @pytest.mark.asyncio
    async def test_resources_clean_after_register(self, session_registry):
        """After register(), resources should not contain state_policy or state_context."""
        resources = make_resources()

        await session_registry.register(
            run_id='run_resources_clean',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
            state_policy={'enable_state': True, 'state_scopes': ['conversation']},
            state_context={'scope_keys': {'conversation': 'conv_key'}, 'binding_identity': 'binding_1'},
        )

        session = await session_registry.get('run_resources_clean')
        assert session is not None

        # Verify resources is clean
        session_resources = session.get('resources', {})
        assert 'state_policy' not in session_resources, \
            "session['resources'] should NOT contain state_policy"
        assert 'state_context' not in session_resources, \
            "session['resources'] should NOT contain state_context"

        # Verify state metadata is at top level
        assert 'state_policy' in session
        assert 'state_context' in session

        await session_registry.unregister('run_resources_clean')
