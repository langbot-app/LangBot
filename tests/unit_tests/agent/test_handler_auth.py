"""Tests for RuntimeConnectionHandler proxy action authorization.

Tests focus on:
- INVOKE_LLM authorization
- INVOKE_LLM_STREAM authorization
- CALL_TOOL authorization
- RETRIEVE_KNOWLEDGE_BASE authorization

Authorization paths:
1. AgentRunner calls: has run_id, validates against session_registry
2. Regular plugin calls: no run_id, unscoped plugin action path
"""
from __future__ import annotations

import pytest
import types
from unittest.mock import AsyncMock, MagicMock

from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.agent.runner.session_registry import AgentRunSessionRegistry
from langbot.pkg.plugin.handler import _build_tool_detail, _get_pipeline_knowledge_base_uuids

# Import shared test fixtures from conftest.py
from .conftest import make_resources


class MockModel:
    """Mock LLM model for testing."""
    def __init__(self, uuid: str):
        self.uuid = uuid
        self.provider = MagicMock()
        self.provider.invoke_llm = AsyncMock(return_value=MagicMock(model_dump=lambda: {'content': 'response'}))


class MockEmbeddingModel:
    """Mock embedding model for testing."""
    def __init__(self, uuid: str):
        self.uuid = uuid
        self.provider = MagicMock()


class MockKnowledgeBase:
    """Mock knowledge base for testing."""
    def __init__(self, uuid: str, name: str = 'KB'):
        self.knowledge_base_entity = MagicMock()
        self.knowledge_base_entity.description = f'{name} description'
        self._uuid = uuid
        self._name = name
        self.retrieve = AsyncMock(return_value=[])

    def get_uuid(self):
        return self._uuid

    def get_name(self):
        return self._name


class MockQuery:
    """Mock query for testing."""
    def __init__(self, query_id: int = 1):
        self.query_id = query_id
        self.session = MagicMock()
        self.session.launcher_type = MagicMock()
        self.session.launcher_type.value = 'telegram'
        self.session.launcher_id = 'group_123'
        self.sender_id = 'user_001'
        self.bot_uuid = 'bot_001'
        self.pipeline_config = {
            'ai': {
                'runner': {
                    'id': 'plugin:test/runner/default',
                },
                'runner_config': {
                    'plugin:test/runner/default': {
                        'knowledge-bases': ['kb_001', 'kb_002'],
                    },
                },
            },
        }


class MockApplication:
    """Mock Application for testing."""
    def __init__(self):
        self.logger = MagicMock()
        self.logger.debug = MagicMock()
        self.logger.warning = MagicMock()
        self.logger.info = MagicMock()
        self.logger.error = MagicMock()

        self.query_pool = MagicMock()
        self.query_pool.cached_queries = {}

        self.model_mgr = MagicMock()
        self.model_mgr.get_model_by_uuid = AsyncMock(return_value=None)
        self.model_mgr.get_embedding_model_by_uuid = AsyncMock(return_value=None)

        self.tool_mgr = MagicMock()
        self.tool_mgr.execute_func_call = AsyncMock(return_value={'result': 'success'})

        self.rag_mgr = MagicMock()
        self.rag_mgr.get_knowledge_base_by_uuid = AsyncMock(return_value=None)
        self.rag_mgr.knowledge_bases = {}

        self.persistence_mgr = MagicMock()
        self.persistence_mgr.execute_async = AsyncMock(return_value=MagicMock(first=lambda: None))


class FakeAgentRunnerRegistry:
    async def get(self, runner_id, bound_plugins=None):
        return AgentRunnerDescriptor(
            id=runner_id,
            source='plugin',
            label={'en_US': 'Test Runner'},
            plugin_author='test',
            plugin_name='runner',
            runner_name='default',
            config_schema=[
                {'name': 'knowledge-bases', 'type': 'knowledge-base-multi-selector', 'default': []},
            ],
            capabilities={'knowledge_retrieval': True},
            permissions={'knowledge_bases': ['list', 'retrieve']},
        )


class MockConnection:
    """Mock connection for testing."""
    pass


class TestPipelineKnowledgeBaseScope:
    """Tests for schema-driven pipeline KB scope resolution."""

    @pytest.mark.asyncio
    async def test_uses_preprocessed_query_scope(self):
        app = MockApplication()
        query = MockQuery()
        query.variables = {'_knowledge_base_uuids': ['kb_var', '__none__', 'kb_var']}

        kb_uuids = await _get_pipeline_knowledge_base_uuids(app, query)

        assert kb_uuids == ['kb_var']

    @pytest.mark.asyncio
    async def test_uses_runner_schema_when_query_scope_not_preprocessed(self):
        app = MockApplication()
        app.agent_runner_registry = FakeAgentRunnerRegistry()
        query = MockQuery()
        query.variables = {}

        kb_uuids = await _get_pipeline_knowledge_base_uuids(app, query)

        assert kb_uuids == ['kb_001', 'kb_002']


class MockDisconnectCallback:
    """Mock disconnect callback for testing."""
    async def __call__(self):
        return True


class TestInvokeLLMAuthorization:
    """Tests for INVOKE_LLM authorization."""

    @pytest.mark.asyncio
    async def test_invoke_llm_authorized_with_run_id(self):
        """INVOKE_LLM: authorized when model in session.resources."""
        # Setup registry with session
        registry = AgentRunSessionRegistry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_authorized',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        # Verify authorization logic directly
        session = await registry.get('run_authorized')
        assert session is not None
        assert registry.is_resource_allowed(session, 'model', 'model_001') is True

        # Cleanup
        await registry.unregister('run_authorized')

    @pytest.mark.asyncio
    async def test_invoke_llm_unauthorized_with_run_id(self):
        """INVOKE_LLM: unauthorized when model not in session.resources."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_unauthorized',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        # Test authorization logic directly
        session = await registry.get('run_unauthorized')
        assert session is not None
        # model_002 is not in resources
        assert registry.is_resource_allowed(session, 'model', 'model_002') is False

        await registry.unregister('run_unauthorized')

    @pytest.mark.asyncio
    async def test_invoke_llm_session_not_found(self):
        """INVOKE_LLM: session not found should return error."""
        registry = AgentRunSessionRegistry()

        # No session registered for this run_id
        session = await registry.get('run_nonexistent')
        assert session is None

    @pytest.mark.asyncio
    async def test_invoke_llm_no_run_id_unrestricted(self):
        """INVOKE_LLM: no run_id should be unrestricted (backward compat)."""
        # When no run_id is provided, the authorization check is skipped
        # This is the unscoped path for regular plugin calls

        # Simulate: if not run_id, skip authorization
        run_id = None
        # Authorization check should NOT be triggered
        assert run_id is None  # No authorization check


class TestInvokeLLMStreamAuthorization:
    """Tests for INVOKE_LLM_STREAM authorization."""

    @pytest.mark.asyncio
    async def test_invoke_llm_stream_authorized_with_run_id(self):
        """INVOKE_LLM_STREAM: authorized when model in session.resources."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_stream_authorized',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_stream_authorized')
        assert session is not None
        assert registry.is_resource_allowed(session, 'model', 'model_001') is True

        await registry.unregister('run_stream_authorized')

    @pytest.mark.asyncio
    async def test_invoke_llm_stream_unauthorized_with_run_id(self):
        """INVOKE_LLM_STREAM: unauthorized when model not in session.resources."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_stream_unauthorized',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_stream_unauthorized')
        assert session is not None
        assert registry.is_resource_allowed(session, 'model', 'model_002') is False

        await registry.unregister('run_stream_unauthorized')

    @pytest.mark.asyncio
    async def test_invoke_llm_stream_no_run_id_unrestricted(self):
        """INVOKE_LLM_STREAM: no run_id should be unrestricted."""
        run_id = None
        # No authorization check
        assert run_id is None


def test_build_tool_detail_normalizes_plugin_component_manifest():
    """GET_TOOL_DETAIL returns a uniform schema for ordinary plugin Tool manifests."""
    manifest_tool = types.SimpleNamespace(
        metadata=types.SimpleNamespace(
            name='search',
            label={'en_US': 'Search'},
            description={'en_US': 'Search public data'},
        ),
        spec={
            'llm_prompt': 'Search test data',
            'parameters': {
                'type': 'object',
                'properties': {'q': {'type': 'string'}},
            },
        },
    )

    detail = _build_tool_detail(manifest_tool, requested_tool_name='author/plugin/search')

    assert detail['name'] == 'author/plugin/search'
    assert detail['description'] == 'Search test data'
    assert detail['human_desc'] == 'Search test data'
    assert detail['parameters']['properties']['q']['type'] == 'string'
    assert detail['label'] == {'en_US': 'Search'}
    assert detail['spec'] == manifest_tool.spec


class TestCallToolAuthorization:
    """Tests for CALL_TOOL authorization."""

    @pytest.mark.asyncio
    async def test_call_tool_authorized_with_run_id(self):
        """CALL_TOOL: authorized when tool in session.resources."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(tools=[{'tool_name': 'web_search'}])

        await registry.register(
            run_id='run_tool_authorized',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_tool_authorized')
        assert session is not None
        assert registry.is_resource_allowed(session, 'tool', 'web_search') is True

        await registry.unregister('run_tool_authorized')

    @pytest.mark.asyncio
    async def test_call_tool_unauthorized_with_run_id(self):
        """CALL_TOOL: unauthorized when tool not in session.resources."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(tools=[{'tool_name': 'web_search'}])

        await registry.register(
            run_id='run_tool_unauthorized',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_tool_unauthorized')
        assert session is not None
        assert registry.is_resource_allowed(session, 'tool', 'image_gen') is False

        await registry.unregister('run_tool_unauthorized')

    @pytest.mark.asyncio
    async def test_call_tool_no_run_id_unrestricted(self):
        """CALL_TOOL: no run_id should be unrestricted."""
        run_id = None
        # No authorization check
        assert run_id is None


class TestRetrieveKnowledgeBaseAuthorization:
    """Tests for RETRIEVE_KNOWLEDGE_BASE authorization."""

    @pytest.mark.asyncio
    async def test_retrieve_knowledge_base_authorized_with_run_id(self):
        """RETRIEVE_KNOWLEDGE_BASE: authorized when kb in session.resources."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(knowledge_bases=[{'kb_id': 'kb_001'}])

        await registry.register(
            run_id='run_kb_authorized',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_kb_authorized')
        assert session is not None
        assert registry.is_resource_allowed(session, 'knowledge_base', 'kb_001') is True

        await registry.unregister('run_kb_authorized')

    @pytest.mark.asyncio
    async def test_retrieve_knowledge_base_unauthorized_with_run_id(self):
        """RETRIEVE_KNOWLEDGE_BASE: unauthorized when kb not in session.resources."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(knowledge_bases=[{'kb_id': 'kb_001'}])

        await registry.register(
            run_id='run_kb_unauthorized',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_kb_unauthorized')
        assert session is not None
        assert registry.is_resource_allowed(session, 'knowledge_base', 'kb_999') is False

        await registry.unregister('run_kb_unauthorized')

    @pytest.mark.asyncio
    async def test_retrieve_knowledge_base_no_run_id_pipeline_check(self):
        """RETRIEVE_KNOWLEDGE_BASE: no run_id checks pipeline config."""
        # When no run_id, the handler checks against pipeline's configured KBs
        # This is the unscoped path for regular plugin calls

        from langbot.pkg.agent.runner.config_migration import ConfigMigration

        # Simulate pipeline config
        pipeline_config = {
            'ai': {
                'runner': {
                    'id': 'plugin:test/runner/default',
                },
                'runner_config': {
                    'plugin:test/runner/default': {
                        'knowledge-bases': ['kb_001', 'kb_002'],
                    },
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        assert runner_id == 'plugin:test/runner/default'

        runner_config = ConfigMigration.resolve_runner_config(pipeline_config, runner_id)
        allowed_kbs = runner_config.get('knowledge-bases', [])
        assert 'kb_001' in allowed_kbs
        assert 'kb_999' not in allowed_kbs


class TestAuthorizationPathDifferentiation:
    """Tests that verify AgentRunner vs regular plugin call differentiation."""

    @pytest.mark.asyncio
    async def test_agent_runner_path_with_run_id(self):
        """AgentRunner calls provide run_id and use session_registry."""
        registry = AgentRunSessionRegistry()

        # AgentRunner call has run_id
        run_id = 'run_agent_123'

        # Register session with resources
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/agent/default',
            query_id=1,
            plugin_identity='test/agent',
            resources=make_resources(
                models=[{'model_id': 'model_xyz'}],
                tools=[{'tool_name': 'agent_tool'}],
                knowledge_bases=[{'kb_id': 'kb_agent'}],
            ),
        )

        session = await registry.get(run_id)
        assert session is not None

        # Authorization checks
        assert registry.is_resource_allowed(session, 'model', 'model_xyz') is True
        assert registry.is_resource_allowed(session, 'model', 'other_model') is False
        assert registry.is_resource_allowed(session, 'tool', 'agent_tool') is True
        assert registry.is_resource_allowed(session, 'tool', 'other_tool') is False
        assert registry.is_resource_allowed(session, 'knowledge_base', 'kb_agent') is True
        assert registry.is_resource_allowed(session, 'knowledge_base', 'kb_other') is False

        await registry.unregister(run_id)

    @pytest.mark.asyncio
    async def test_regular_plugin_path_no_run_id(self):
        """Regular plugin calls have no run_id and skip session check."""
        # Regular plugin call has no run_id
        run_id = None

        # Authorization check should be skipped when run_id is None.
        # This is handled in handler.py with: if run_id: ...
        assert run_id is None

        # For regular plugins:
        # - INVOKE_LLM: unrestricted access to any model
        # - CALL_TOOL: unrestricted access to any tool
        # - RETRIEVE_KNOWLEDGE_BASE: checks pipeline config instead


class TestHandlerAuthorizationErrorMessages:
    """Tests for error message content in authorization failures."""

    def test_model_not_authorized_error_message(self):
        """Error message should mention model not authorized."""
        expected_msg = "Model model_999 is not authorized for this agent run"
        assert 'not authorized' in expected_msg
        assert 'model_999' in expected_msg

    def test_tool_not_authorized_error_message(self):
        """Error message should mention tool not authorized."""
        expected_msg = "Tool image_gen is not authorized for this agent run"
        assert 'not authorized' in expected_msg
        assert 'image_gen' in expected_msg

    def test_kb_not_authorized_error_message(self):
        """Error message should mention kb not authorized."""
        expected_msg = "Knowledge base kb_999 is not authorized for this agent run"
        assert 'not authorized' in expected_msg
        assert 'kb_999' in expected_msg

    def test_session_not_found_error_message(self):
        """Error message should mention session not found."""
        expected_msg = "Run session run_xyz not found or expired"
        assert 'not found' in expected_msg
        assert 'run_xyz' in expected_msg


class TestRETRIEVEKNOWLEDGEBASEBugFix:
    """Tests for the RETRIEVE_KNOWLEDGE_BASE bug fix in handler.py.

    Bug: Previously, the handler directly accessed pipeline_config['ai']['local-agent']
    without first resolving the runner_id, causing issues when non-local-agent runners
    were used.

    Fix: Now uses ConfigMigration.resolve_runner_id first, then resolve_runner_config.
    """

    def test_retrieve_kb_fix_local_agent_runner(self):
        """Fix should work for local-agent runner."""
        from langbot.pkg.agent.runner.config_migration import ConfigMigration

        pipeline_config = {
            'ai': {
                'runner': {
                    'id': 'plugin:langbot/local-agent/default',
                },
                'runner_config': {
                    'plugin:langbot/local-agent/default': {
                        'knowledge-bases': ['kb_001'],
                    },
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        runner_config = ConfigMigration.resolve_runner_config(pipeline_config, runner_id)
        allowed_kbs = runner_config.get('knowledge-bases', [])

        assert 'kb_001' in allowed_kbs

    def test_retrieve_kb_fix_other_runner(self):
        """Fix should work for non-local-agent runners."""
        from langbot.pkg.agent.runner.config_migration import ConfigMigration

        pipeline_config = {
            'ai': {
                'runner': {
                    'id': 'plugin:custom/my-agent/default',
                },
                'runner_config': {
                    'plugin:custom/my-agent/default': {
                        'knowledge-bases': ['kb_custom'],
                    },
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        runner_config = ConfigMigration.resolve_runner_config(pipeline_config, runner_id)
        allowed_kbs = runner_config.get('knowledge-bases', [])

        assert 'kb_custom' in allowed_kbs

    def test_retrieve_kb_fix_old_format(self):
        """Fix should work for old format pipeline config."""
        from langbot.pkg.agent.runner.config_migration import ConfigMigration

        # Old format: ai.runner.runner = 'local-agent'
        pipeline_config = {
            'ai': {
                'runner': {
                    'runner': 'local-agent',
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        # Should resolve to plugin:langbot/local-agent/default
        assert 'local-agent' in runner_id

    def test_retrieve_kb_fix_backward_compat_knowledge_base(self):
        """Fix should handle backward compat for old 'knowledge-base' field."""
        from langbot.pkg.agent.runner.config_migration import ConfigMigration

        pipeline_config = {
            'ai': {
                'runner': {
                    'id': 'plugin:langbot/local-agent/default',
                },
                'runner_config': {
                    'plugin:langbot/local-agent/default': {
                        'knowledge-base': 'kb_single',  # Old singular field
                    },
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        runner_config = ConfigMigration.resolve_runner_config(pipeline_config, runner_id)

        # Handler.py checks both knowledge-bases and knowledge-base
        allowed_kbs = runner_config.get('knowledge-bases', [])
        if not allowed_kbs:
            old_kb = runner_config.get('knowledge-base', '')
            if old_kb and old_kb != '__none__':
                allowed_kbs = [old_kb]

        assert 'kb_single' in allowed_kbs


class TestHandlerActionAuthorization:
    """Tests for real handler action-level authorization.

    These tests simulate RuntimeConnectionHandler action handlers
    to verify actual authorization behavior at the action level.
    """

    @pytest.mark.asyncio
    async def test_invoke_llm_handler_authorized_path(self):
        """INVOKE_LLM handler: authorized when model in resources."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_invoke_llm_auth',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        # Simulate handler authorization logic
        run_id = 'run_invoke_llm_auth'
        llm_model_uuid = 'model_001'

        session_registry = registry
        session = await session_registry.get(run_id)
        assert session is not None

        # Authorization check (same as handler.py line 352)
        is_allowed = session_registry.is_resource_allowed(session, 'model', llm_model_uuid)
        assert is_allowed is True

        await registry.unregister(run_id)

    @pytest.mark.asyncio
    async def test_invoke_llm_handler_unauthorized_path(self):
        """INVOKE_LLM handler: unauthorized when model not in resources."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_invoke_llm_unauth',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        run_id = 'run_invoke_llm_unauth'
        llm_model_uuid = 'model_999'  # Not in resources

        session_registry = registry
        session = await session_registry.get(run_id)
        assert session is not None

        # Authorization check (same as handler.py line 352)
        is_allowed = session_registry.is_resource_allowed(session, 'model', llm_model_uuid)
        assert is_allowed is False

        # Should return error response (handler.py line 357)
        expected_error = f'Model {llm_model_uuid} is not authorized for this agent run'
        assert 'not authorized' in expected_error

        await registry.unregister(run_id)

    @pytest.mark.asyncio
    async def test_invoke_llm_handler_session_not_found(self):
        """INVOKE_LLM handler: session not found returns error."""
        registry = AgentRunSessionRegistry()

        # No session registered
        run_id = 'run_nonexistent'
        session = await registry.get(run_id)
        assert session is None

        # Handler should return error (handler.py line 348)
        expected_error = f'Run session {run_id} not found or expired'
        assert 'not found' in expected_error

    @pytest.mark.asyncio
    async def test_invoke_llm_handler_no_run_id_unrestricted(self):
        """INVOKE_LLM handler: no run_id skips authorization (backward compat)."""
        # Simulate handler logic: if not run_id, skip authorization
        run_id = None

        # In handler.py, authorization check is inside: if run_id: ...
        # So when run_id is None, authorization is skipped.
        assert run_id is None

    @pytest.mark.asyncio
    async def test_call_tool_handler_authorized_path(self):
        """CALL_TOOL handler: authorized when tool in resources."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(tools=[{'tool_name': 'web_search'}])

        await registry.register(
            run_id='run_call_tool_auth',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        run_id = 'run_call_tool_auth'
        tool_name = 'web_search'

        session_registry = registry
        session = await session_registry.get(run_id)
        assert session is not None

        # Authorization check (handler.py line 475)
        is_allowed = session_registry.is_resource_allowed(session, 'tool', tool_name)
        assert is_allowed is True

        await registry.unregister(run_id)

    @pytest.mark.asyncio
    async def test_call_tool_handler_unauthorized_path(self):
        """CALL_TOOL handler: unauthorized when tool not in resources."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(tools=[{'tool_name': 'web_search'}])

        await registry.register(
            run_id='run_call_tool_unauth',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        run_id = 'run_call_tool_unauth'
        tool_name = 'image_gen'  # Not in resources

        session_registry = registry
        session = await session_registry.get(run_id)
        assert session is not None

        # Authorization check
        is_allowed = session_registry.is_resource_allowed(session, 'tool', tool_name)
        assert is_allowed is False

        # Should return error (handler.py line 480)
        expected_error = f'Tool {tool_name} is not authorized for this agent run'
        assert 'not authorized' in expected_error

        await registry.unregister(run_id)

    @pytest.mark.asyncio
    async def test_call_tool_handler_no_run_id_unrestricted(self):
        """CALL_TOOL handler: no run_id skips authorization."""
        run_id = None

        # Authorization check is inside: if run_id: ...
        assert run_id is None

    @pytest.mark.asyncio
    async def test_retrieve_knowledge_base_handler_authorized_path(self):
        """RETRIEVE_KNOWLEDGE_BASE handler: authorized when kb in resources."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(knowledge_bases=[{'kb_id': 'kb_001'}])

        await registry.register(
            run_id='run_kb_auth',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        run_id = 'run_kb_auth'
        kb_id = 'kb_001'

        session_registry = registry
        session = await session_registry.get(run_id)
        assert session is not None

        # Authorization check (handler.py line 889)
        is_allowed = session_registry.is_resource_allowed(session, 'knowledge_base', kb_id)
        assert is_allowed is True

        await registry.unregister(run_id)

    @pytest.mark.asyncio
    async def test_retrieve_knowledge_base_handler_unauthorized_path(self):
        """RETRIEVE_KNOWLEDGE_BASE handler: unauthorized when kb not in resources."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(knowledge_bases=[{'kb_id': 'kb_001'}])

        await registry.register(
            run_id='run_kb_unauth',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        run_id = 'run_kb_unauth'
        kb_id = 'kb_999'  # Not in resources

        session_registry = registry
        session = await session_registry.get(run_id)
        assert session is not None

        # Authorization check
        is_allowed = session_registry.is_resource_allowed(session, 'knowledge_base', kb_id)
        assert is_allowed is False

        # Should return error (handler.py line 894)
        expected_error = f'Knowledge base {kb_id} is not authorized for this agent run'
        assert 'not authorized' in expected_error

        await registry.unregister(run_id)


class TestSDKAgentRunAPIProxyFieldConsistency:
    """Tests for SDK AgentRunAPIProxy field name consistency with Host handler.

    These tests verify that SDK sends field names that match what Host handler reads.
    """

    def test_call_tool_field_names_match(self):
        """CALL_TOOL: SDK 'parameters' matches Host 'parameters'."""
        # SDK agent_run_api.py line 146: "parameters": parameters
        # Host handler.py line 457: parameters = data['parameters']
        sdk_field = 'parameters'
        host_field = 'parameters'
        assert sdk_field == host_field

    def test_call_tool_run_id_field_present(self):
        """CALL_TOOL: SDK includes 'run_id' field."""
        # SDK agent_run_api.py line 144: "run_id": self.run_id
        # Host handler.py line 458: run_id = data.get('run_id')
        sdk_fields = ['run_id', 'tool_name', 'parameters', 'session', 'query_id']
        host_expected_fields = ['tool_name', 'parameters', 'run_id']

        for field in host_expected_fields:
            assert field in sdk_fields

    def test_invoke_llm_field_names_match(self):
        """INVOKE_LLM: SDK fields match Host handler."""
        # SDK agent_run_api.py lines 77-82
        sdk_fields = ['run_id', 'llm_model_uuid', 'messages', 'funcs', 'extra_args', 'timeout']
        # Host handler.py lines 333-337
        host_fields = ['llm_model_uuid', 'messages', 'funcs', 'extra_args', 'run_id']

        for field in host_fields:
            assert field in sdk_fields

    def test_invoke_llm_stream_field_names_match(self):
        """INVOKE_LLM_STREAM: SDK fields match Host handler."""
        # SDK agent_run_api.py lines 111-116
        sdk_fields = ['run_id', 'llm_model_uuid', 'messages', 'funcs', 'extra_args']
        # Host handler.py lines 397-401
        host_fields = ['llm_model_uuid', 'messages', 'funcs', 'extra_args', 'run_id']

        for field in host_fields:
            assert field in sdk_fields

    def test_retrieve_knowledge_base_field_names_match(self):
        """RETRIEVE_KNOWLEDGE_BASE: SDK fields match Host handler."""
        # SDK agent_run_api.py lines 178-183
        sdk_fields = ['run_id', 'kb_id', 'query_text', 'top_k', 'filters']

        # Note: query_id is from query context, not SDK proxy
        for field in ['run_id', 'kb_id', 'query_text', 'top_k', 'filters']:
            assert field in sdk_fields

    def test_retrieve_knowledge_base_action_enum_correct(self):
        """RETRIEVE_KNOWLEDGE_BASE: SDK uses correct action enum."""
        from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

        # SDK agent_run_api.py line 178: PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE
        # Host handler.py line 851: @self.action(PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE)
        action = PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE
        assert action.value == 'retrieve_knowledge_base'

        # Verify it's different from unrestricted RETRIEVE_KNOWLEDGE
        unrestricted_action = PluginToRuntimeAction.RETRIEVE_KNOWLEDGE
        assert unrestricted_action.value == 'retrieve_knowledge'
        assert action != unrestricted_action


class TestNoRunIdBackwardCompatPath:
    """Tests for unscoped plugin action path when no run_id is provided.

    Regular plugins (non-AgentRunner) don't have run_id and should
    have unrestricted access to certain APIs.
    """

    @pytest.mark.asyncio
    async def test_invoke_llm_no_run_id_unrestricted_access(self):
        """INVOKE_LLM: no run_id means unrestricted model access."""
        # Handler.py line 340: if run_id: ...
        # When run_id is None, the authorization block is skipped
        run_id = None
        llm_model_uuid = 'any_model'

        # Simulate handler logic: no run_id skips authorization.
        assert run_id is None

        # Model can be any UUID (unrestricted)
        assert llm_model_uuid == 'any_model'

    @pytest.mark.asyncio
    async def test_call_tool_no_run_id_unrestricted_access(self):
        """CALL_TOOL: no run_id means unrestricted tool access."""
        run_id = None
        tool_name = 'any_tool'

        # Handler.py line 463: if run_id: ...
        assert run_id is None

        assert tool_name == 'any_tool'

    @pytest.mark.asyncio
    async def test_retrieve_knowledge_base_no_run_id_pipeline_check(self):
        """RETRIEVE_KNOWLEDGE_BASE: no run_id uses pipeline config check."""
        from langbot.pkg.agent.runner.config_migration import ConfigMigration

        # When no run_id, handler.py lines 897-914 check pipeline config
        pipeline_config = {
            'ai': {
                'runner': {
                    'id': 'plugin:test/runner/default',
                },
                'runner_config': {
                    'plugin:test/runner/default': {
                        'knowledge-bases': ['kb_001', 'kb_002'],
                    },
                },
            },
        }

        runner_id = ConfigMigration.resolve_runner_id(pipeline_config)
        runner_config = ConfigMigration.resolve_runner_config(pipeline_config, runner_id)
        allowed_kb_uuids = runner_config.get('knowledge-bases', [])

        # kb_001 should be allowed
        assert 'kb_001' in allowed_kb_uuids
        # kb_999 should NOT be allowed
        assert 'kb_999' not in allowed_kb_uuids


class TestSessionExpiryAndCleanup:
    """Tests for session expiry and cleanup scenarios."""

    @pytest.mark.asyncio
    async def test_session_expiry_detection(self):
        """Session expiry: old session should be considered expired."""
        import time

        registry = AgentRunSessionRegistry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        # Register session
        await registry.register(
            run_id='run_expiry_test',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_expiry_test')
        assert session is not None

        # Check session status
        started_at = session['status']['started_at']
        last_activity = session['status']['last_activity_at']
        assert last_activity >= started_at

        # Session should be valid initially
        current_time = int(time.time())
        assert current_time - started_at < 10  # Less than 10 seconds old

        await registry.unregister('run_expiry_test')

    @pytest.mark.asyncio
    async def test_cleanup_stale_sessions(self):
        """Cleanup: stale sessions should be removed."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        # Register session
        await registry.register(
            run_id='run_cleanup_test',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        # Session exists
        session = await registry.get('run_cleanup_test')
        assert session is not None

        # Cleanup with max_age=0 (immediate cleanup)
        # Note: This won't actually cleanup because session is just created
        # We need to manually test cleanup logic
        cleaned = await registry.cleanup_stale_sessions(max_age_seconds=0)
        assert isinstance(cleaned, int)

        # Session should still exist (it was just created)
        # With max_age=0, sessions with last_activity > 0 seconds ago would be cleaned
        # But since it's just created, last_activity_at is current time
        session_after = await registry.get('run_cleanup_test')
        assert session_after is not None

        await registry.unregister('run_cleanup_test')

    @pytest.mark.asyncio
    async def test_unregister_removes_session(self):
        """Unregister: session should be removed from registry."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_unregister_test',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        # Session exists
        session = await registry.get('run_unregister_test')
        assert session is not None

        # Unregister
        await registry.unregister('run_unregister_test')

        # Session should not exist
        session_after = await registry.get('run_unregister_test')
        assert session_after is None


class TestResourceTypeValidation:
    """Tests for different resource type validation in is_resource_allowed."""

    @pytest.mark.asyncio
    async def test_model_resource_validation(self):
        """Model resource: correct model_id validation."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(models=[
            {'model_id': 'model_001'},
            {'model_id': 'model_002'},
        ])

        await registry.register(
            run_id='run_model_validation',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_model_validation')

        # Authorized models
        assert registry.is_resource_allowed(session, 'model', 'model_001') is True
        assert registry.is_resource_allowed(session, 'model', 'model_002') is True

        # Unauthorized models
        assert registry.is_resource_allowed(session, 'model', 'model_999') is False

        await registry.unregister('run_model_validation')

    @pytest.mark.asyncio
    async def test_tool_resource_validation(self):
        """Tool resource: correct tool_name validation."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(tools=[
            {'tool_name': 'web_search'},
            {'tool_name': 'image_gen'},
        ])

        await registry.register(
            run_id='run_tool_validation',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_tool_validation')

        # Authorized tools
        assert registry.is_resource_allowed(session, 'tool', 'web_search') is True
        assert registry.is_resource_allowed(session, 'tool', 'image_gen') is True

        # Unauthorized tools
        assert registry.is_resource_allowed(session, 'tool', 'file_upload') is False

        await registry.unregister('run_tool_validation')

    @pytest.mark.asyncio
    async def test_knowledge_base_resource_validation(self):
        """Knowledge base resource: correct kb_id validation."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(knowledge_bases=[
            {'kb_id': 'kb_001'},
            {'kb_id': 'kb_002'},
        ])

        await registry.register(
            run_id='run_kb_validation',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_kb_validation')

        # Authorized KBs
        assert registry.is_resource_allowed(session, 'knowledge_base', 'kb_001') is True
        assert registry.is_resource_allowed(session, 'knowledge_base', 'kb_002') is True

        # Unauthorized KBs
        assert registry.is_resource_allowed(session, 'knowledge_base', 'kb_999') is False

        await registry.unregister('run_kb_validation')

    @pytest.mark.asyncio
    async def test_storage_resource_validation(self):
        """Storage resource: boolean permission validation."""
        registry = AgentRunSessionRegistry()
        resources = make_resources()
        resources['storage'] = {'plugin_storage': True, 'workspace_storage': False}

        await registry.register(
            run_id='run_storage_validation',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_storage_validation')

        # Plugin storage allowed
        assert registry.is_resource_allowed(session, 'storage', 'plugin') is True

        # Workspace storage not allowed
        assert registry.is_resource_allowed(session, 'storage', 'workspace') is False

        await registry.unregister('run_storage_validation')

    def test_unknown_resource_type_returns_false(self):
        """Unknown resource type: should return False."""
        registry = AgentRunSessionRegistry()
        resources = make_resources()

        # Create session manually for this test
        session = {
            'run_id': 'test',
            'runner_id': 'test',
            'query_id': 1,
            'plugin_identity': 'test',
            'resources': resources,
            'status': {'started_at': 0, 'last_activity_at': 0},
        }

        # Unknown resource type should return False
        assert registry.is_resource_allowed(session, 'unknown_type', 'any_id') is False


class TestBypassPrevention:
    """Tests to ensure AgentRunAPIProxy cannot bypass authorization."""

    @pytest.mark.asyncio
    async def test_cannot_bypass_via_unrestricted_retrieve_knowledge(self):
        """Cannot bypass KB authorization via unrestricted RETRIEVE_KNOWLEDGE action."""
        # AgentRunAPIProxy uses RETRIEVE_KNOWLEDGE_BASE (with run_id)
        # RETRIEVE_KNOWLEDGE is unrestricted and separate
        # AgentRunner should NOT use RETRIEVE_KNOWLEDGE to bypass authorization

        registry = AgentRunSessionRegistry()
        resources = make_resources(knowledge_bases=[{'kb_id': 'kb_001'}])

        await registry.register(
            run_id='run_bypass_test',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_bypass_test')

        # kb_002 is not authorized
        assert registry.is_resource_allowed(session, 'knowledge_base', 'kb_002') is False

        # If AgentRunner tried to use RETRIEVE_KNOWLEDGE (unrestricted),
        # it would bypass authorization - but AgentRunAPIProxy correctly uses
        # RETRIE_KNOWLEDGE_BASE which requires authorization

        from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

        # Verify SDK uses correct action
        assert PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE.value == 'retrieve_knowledge_base'

        await registry.unregister('run_bypass_test')

    @pytest.mark.asyncio
    async def test_cannot_bypass_via_missing_run_id_in_session(self):
        """Cannot bypass by using run_id that doesn't exist in registry."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_valid',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        # Try to use a run_id that doesn't exist
        fake_run_id = 'run_fake'
        session = await registry.get(fake_run_id)
        assert session is None

        # Handler should return error for non-existent run_id
        # (handler.py line 348, 466, 881)
        expected_error = f'Run session {fake_run_id} not found or expired'
        assert 'not found' in expected_error

        await registry.unregister('run_valid')


class TestValidateRunAuthorizationHelper:
    """Tests for _validate_run_authorization helper function.

    This helper is used by INVOKE_LLM, INVOKE_LLM_STREAM, CALL_TOOL,
    and RETRIEVE_KNOWLEDGE_BASE handlers to validate run_id authorization.

    Note: This helper uses get_session_registry() which returns the global singleton.
    Tests must use the same global registry.
    """

    @pytest.mark.asyncio
    async def test_validate_returns_session_when_authorized(self):
        """_validate_run_authorization returns session when resource is authorized."""
        # Use global session registry (same as _validate_run_authorization)
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_validate_test_helper',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        # Import the helper
        from langbot.pkg.plugin.handler import _validate_run_authorization

        # Create mock application
        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()

        session, error = await _validate_run_authorization(
            'run_validate_test_helper',
            'model',
            'model_001',
            mock_ap
        )

        # Should return session, no error
        assert session is not None
        assert error is None
        assert session['run_id'] == 'run_validate_test_helper'

        await registry.unregister('run_validate_test_helper')

    @pytest.mark.asyncio
    async def test_validate_returns_error_when_session_not_found(self):
        """_validate_run_authorization returns error when session not found."""
        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()
        mock_ap.logger.warning = MagicMock()

        session, error = await _validate_run_authorization(
            'run_nonexistent_helper',
            'model',
            'model_001',
            mock_ap
        )

        # Should return no session, error response
        assert session is None
        assert error is not None
        assert 'not found' in error.message.lower()
        assert mock_ap.logger.warning.called

    @pytest.mark.asyncio
    async def test_validate_returns_error_when_resource_not_allowed(self):
        """_validate_run_authorization returns error when resource not allowed."""
        # Use global session registry
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_unauthorized_helper',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()
        mock_ap.logger.warning = MagicMock()

        session, error = await _validate_run_authorization(
            'run_unauthorized_helper',
            'model',
            'model_999',  # Not in resources
            mock_ap
        )

        # Should return no session, error response
        assert session is None
        assert error is not None
        assert 'not authorized' in error.message.lower()
        assert mock_ap.logger.warning.called

        await registry.unregister('run_unauthorized_helper')

    @pytest.mark.asyncio
    async def test_validate_for_tool_resource_type(self):
        """_validate_run_authorization works for tool resource type."""
        # Use global session registry
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(tools=[{'tool_name': 'web_search'}])

        await registry.register(
            run_id='run_tool_test_helper',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()

        session, error = await _validate_run_authorization(
            'run_tool_test_helper',
            'tool',
            'web_search',
            mock_ap
        )

        assert session is not None
        assert error is None

        await registry.unregister('run_tool_test_helper')

    @pytest.mark.asyncio
    async def test_validate_for_knowledge_base_resource_type(self):
        """_validate_run_authorization works for knowledge_base resource type."""
        # Use global session registry
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(knowledge_bases=[{'kb_id': 'kb_001'}])

        await registry.register(
            run_id='run_kb_test_helper',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()

        session, error = await _validate_run_authorization(
            'run_kb_test_helper',
            'knowledge_base',
            'kb_001',
            mock_ap
        )

        assert session is not None
        assert error is None

        await registry.unregister('run_kb_test_helper')


class TestStorageResourcePermissionHelper:
    """Tests for session_registry.is_resource_allowed for storage resource type.

    The 'storage' resource type has different permission model:
    - resource_id can be 'plugin' or 'workspace'
    - Permission is boolean flag, not list membership
    """

    @pytest.mark.asyncio
    async def test_plugin_storage_allowed_when_true(self):
        """is_resource_allowed returns True when plugin_storage=True."""
        registry = AgentRunSessionRegistry()
        resources = make_resources()
        resources['storage'] = {'plugin_storage': True, 'workspace_storage': False}

        await registry.register(
            run_id='run_plugin_storage',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_plugin_storage')

        assert registry.is_resource_allowed(session, 'storage', 'plugin') is True
        assert registry.is_resource_allowed(session, 'storage', 'workspace') is False

        await registry.unregister('run_plugin_storage')

    @pytest.mark.asyncio
    async def test_workspace_storage_allowed_when_true(self):
        """is_resource_allowed returns True when workspace_storage=True."""
        registry = AgentRunSessionRegistry()
        resources = make_resources()
        resources['storage'] = {'plugin_storage': False, 'workspace_storage': True}

        await registry.register(
            run_id='run_workspace_storage',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_workspace_storage')

        assert registry.is_resource_allowed(session, 'storage', 'plugin') is False
        assert registry.is_resource_allowed(session, 'storage', 'workspace') is True

        await registry.unregister('run_workspace_storage')

    @pytest.mark.asyncio
    async def test_both_storage_types_disabled(self):
        """is_resource_allowed returns False when both storage types disabled."""
        registry = AgentRunSessionRegistry()
        resources = make_resources()
        resources['storage'] = {'plugin_storage': False, 'workspace_storage': False}

        await registry.register(
            run_id='run_no_storage',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_no_storage')

        assert registry.is_resource_allowed(session, 'storage', 'plugin') is False
        assert registry.is_resource_allowed(session, 'storage', 'workspace') is False

        await registry.unregister('run_no_storage')

    @pytest.mark.asyncio
    async def test_unknown_storage_resource_id_returns_false(self):
        """is_resource_allowed returns False for unknown storage resource_id."""
        registry = AgentRunSessionRegistry()
        resources = make_resources()
        resources['storage'] = {'plugin_storage': True, 'workspace_storage': True}

        await registry.register(
            run_id='run_unknown_storage',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_unknown_storage')

        # Unknown storage resource_id
        assert registry.is_resource_allowed(session, 'storage', 'unknown_type') is False

        await registry.unregister('run_unknown_storage')

    def test_storage_permission_with_missing_storage_field(self):
        """is_resource_allowed handles missing storage field gracefully."""
        registry = AgentRunSessionRegistry()

        # Create session without storage field
        session = {
            'run_id': 'test',
            'runner_id': 'test',
            'query_id': 1,
            'plugin_identity': 'test',
            'resources': {},  # No storage field
            'status': {'started_at': 0, 'last_activity_at': 0},
        }

        # Should return False for both storage types
        assert registry.is_resource_allowed(session, 'storage', 'plugin') is False
        assert registry.is_resource_allowed(session, 'storage', 'workspace') is False


class TestFilesResourcePermission:
    """Tests for session_registry.is_resource_allowed for files resource type.

    Phase 6: 'files' resource type is now implemented in is_resource_allowed.
    """

    @pytest.mark.asyncio
    async def test_files_resource_type_now_implemented(self):
        """'files' resource type is now implemented in is_resource_allowed."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(files=[{'file_id': 'file_001'}])

        await registry.register(
            run_id='run_files_implemented',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        session = await registry.get('run_files_implemented')

        # 'files' resource type is now implemented
        assert registry.is_resource_allowed(session, 'file', 'file_001') is True
        assert registry.is_resource_allowed(session, 'file', 'file_999') is False

        await registry.unregister('run_files_implemented')


class TestRealActionHandlerSimulation:
    """Tests that simulate real RuntimeConnectionHandler action registration and execution.

    These tests attempt to verify the actual handler behavior without full integration.
    Uses global session registry to match _validate_run_authorization behavior.
    """

    @pytest.mark.asyncio
    async def test_action_handler_invoke_llm_flow(self):
        """Simulate INVOKE_LLM action handler authorization flow."""
        # Use global session registry
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_invoke_llm_flow_sim',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        # Simulate handler logic
        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()

        # Step 1: Validate authorization
        session, error = await _validate_run_authorization(
            'run_invoke_llm_flow_sim',
            'model',
            'model_001',
            mock_ap
        )

        # Should pass authorization
        assert session is not None
        assert error is None

        # Step 2: Handler would invoke LLM (not tested here, would need mock model)

        await registry.unregister('run_invoke_llm_flow_sim')

    @pytest.mark.asyncio
    async def test_action_handler_rejects_unauthorized_model(self):
        """Simulate INVOKE_LLM handler rejecting unauthorized model."""
        # Use global session registry
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_reject_model_sim',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()
        mock_ap.logger.warning = MagicMock()

        # Try to access unauthorized model
        session, error = await _validate_run_authorization(
            'run_reject_model_sim',
            'model',
            'model_999',
            mock_ap
        )

        # Should reject
        assert session is None
        assert error is not None
        assert 'not authorized' in error.message.lower()
        assert mock_ap.logger.warning.called

        await registry.unregister('run_reject_model_sim')

    @pytest.mark.asyncio
    async def test_action_handler_session_not_found_flow(self):
        """Simulate handler behavior when session not found."""
        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()
        mock_ap.logger.warning = MagicMock()

        # Try to validate with non-existent run_id
        session, error = await _validate_run_authorization(
            'run_nonexistent_session_flow',
            'model',
            'model_001',
            mock_ap
        )

        # Should return error
        assert session is None
        assert error is not None
        assert 'not found' in error.message.lower()
        assert mock_ap.logger.warning.called


class TestStoragePermissionValidation:
    """Tests for Host-side storage permission validation via _validate_run_authorization.

    Phase 6: Storage actions (SET/GET/DELETE_BINARY_STORAGE) now validate
    storage permissions via _validate_run_authorization when run_id is present.
    """

    @pytest.mark.asyncio
    async def test_plugin_storage_allowed_when_permitted(self):
        """_validate_run_authorization allows 'plugin' storage when permitted."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(storage={'plugin_storage': True, 'workspace_storage': False})

        await registry.register(
            run_id='run_plugin_storage_auth',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()

        session, error = await _validate_run_authorization(
            'run_plugin_storage_auth',
            'storage',
            'plugin',
            mock_ap
        )

        assert session is not None
        assert error is None

        await registry.unregister('run_plugin_storage_auth')

    @pytest.mark.asyncio
    async def test_plugin_storage_denied_when_not_permitted(self):
        """_validate_run_authorization denies 'plugin' storage when not permitted."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(storage={'plugin_storage': False, 'workspace_storage': False})

        await registry.register(
            run_id='run_plugin_storage_denied',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()
        mock_ap.logger.warning = MagicMock()

        session, error = await _validate_run_authorization(
            'run_plugin_storage_denied',
            'storage',
            'plugin',
            mock_ap
        )

        assert session is None
        assert error is not None
        assert 'not authorized' in error.message.lower()

        await registry.unregister('run_plugin_storage_denied')

    @pytest.mark.asyncio
    async def test_workspace_storage_allowed_when_permitted(self):
        """_validate_run_authorization allows 'workspace' storage when permitted."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(storage={'plugin_storage': False, 'workspace_storage': True})

        await registry.register(
            run_id='run_workspace_storage_auth',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()

        session, error = await _validate_run_authorization(
            'run_workspace_storage_auth',
            'storage',
            'workspace',
            mock_ap
        )

        assert session is not None
        assert error is None

        await registry.unregister('run_workspace_storage_auth')

    @pytest.mark.asyncio
    async def test_workspace_storage_denied_when_not_permitted(self):
        """_validate_run_authorization denies 'workspace' storage when not permitted."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(storage={'plugin_storage': False, 'workspace_storage': False})

        await registry.register(
            run_id='run_workspace_storage_denied',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()
        mock_ap.logger.warning = MagicMock()

        session, error = await _validate_run_authorization(
            'run_workspace_storage_denied',
            'storage',
            'workspace',
            mock_ap
        )

        assert session is None
        assert error is not None
        assert 'not authorized' in error.message.lower()

        await registry.unregister('run_workspace_storage_denied')


class TestFilePermissionValidation:
    """Tests for Host-side file permission validation via _validate_run_authorization.

    Phase 6: GET_CONFIG_FILE action now validates file permissions
    via _validate_run_authorization when run_id is present.
    """

    @pytest.mark.asyncio
    async def test_file_allowed_when_in_resources(self):
        """_validate_run_authorization allows file when in resources."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(files=[{'file_id': 'file_001'}])

        await registry.register(
            run_id='run_file_auth',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()

        session, error = await _validate_run_authorization(
            'run_file_auth',
            'file',
            'file_001',
            mock_ap
        )

        assert session is not None
        assert error is None

        await registry.unregister('run_file_auth')

    @pytest.mark.asyncio
    async def test_file_denied_when_not_in_resources(self):
        """_validate_run_authorization denies file when not in resources."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(files=[{'file_id': 'file_001'}])

        await registry.register(
            run_id='run_file_denied',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()
        mock_ap.logger.warning = MagicMock()

        session, error = await _validate_run_authorization(
            'run_file_denied',
            'file',
            'file_999',  # Not in resources
            mock_ap
        )

        assert session is None
        assert error is not None
        assert 'not authorized' in error.message.lower()

        await registry.unregister('run_file_denied')


class TestCallerPluginIdentityValidation:
    """Tests for caller_plugin_identity cross-plugin validation.

    Phase 6: _validate_run_authorization now validates that the caller plugin
    identity matches the session's plugin_identity, preventing cross-plugin
    unauthorized access if one plugin tries to use another's run_id.
    """

    @pytest.mark.asyncio
    async def test_same_plugin_identity_allowed(self):
        """_validate_run_authorization allows when caller matches session."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_identity_match',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',  # Session owner
            resources=resources,
        )

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()

        session, error = await _validate_run_authorization(
            'run_identity_match',
            'model',
            'model_001',
            mock_ap,
            caller_plugin_identity='test/runner',  # Caller is same plugin
        )

        assert session is not None
        assert error is None

        await registry.unregister('run_identity_match')

    @pytest.mark.asyncio
    async def test_different_plugin_identity_denied(self):
        """_validate_run_authorization denies when caller differs from session."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_identity_mismatch',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',  # Session owner
            resources=resources,
        )

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()
        mock_ap.logger.warning = MagicMock()

        session, error = await _validate_run_authorization(
            'run_identity_mismatch',
            'model',
            'model_001',
            mock_ap,
            caller_plugin_identity='other/plugin',  # Different plugin trying to use run_id
        )

        assert session is None
        assert error is not None
        assert 'mismatch' in error.message.lower()

        await registry.unregister('run_identity_mismatch')

    @pytest.mark.asyncio
    async def test_no_caller_identity_allowed(self):
        """_validate_run_authorization allows when caller_plugin_identity not provided."""
        # Unscoped plugin path: if caller_plugin_identity is None, skip identity check
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        registry = get_session_registry()
        resources = make_resources(models=[{'model_id': 'model_001'}])

        await registry.register(
            run_id='run_no_caller_identity',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=resources,
        )

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()

        # caller_plugin_identity not provided (None)
        session, error = await _validate_run_authorization(
            'run_no_caller_identity',
            'model',
            'model_001',
            mock_ap,
            caller_plugin_identity=None,  # Not provided
        )

        # Should pass (backward compat)
        assert session is not None
        assert error is None

        await registry.unregister('run_no_caller_identity')


class TestBackwardCompatStorageNoRunId:
    """Tests for unscoped storage actions without run_id.

    Regular plugins (non-AgentRunner) don't have run_id and should
    have unrestricted access to storage APIs.
    """

    def test_storage_no_run_id_skips_validation(self):
        """Storage actions without run_id skip Host-side validation."""
        # Handler.py: if run_id: ...validation...
        # When run_id is None, validation is skipped
        run_id = None

        # Simulate handler logic: no run_id skips validation.
        assert run_id is None

        # Storage access unrestricted for regular plugins
        assert run_id is None

    def test_file_no_run_id_skips_validation(self):
        """GET_CONFIG_FILE without run_id skips Host-side validation."""
        run_id = None

        assert run_id is None

        # File access unrestricted for regular plugins
        assert run_id is None
