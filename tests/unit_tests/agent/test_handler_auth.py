"""Tests for shared Runner resource authorization helpers and registry contracts."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from langbot.pkg.agent.runner.descriptor import RunnerDescriptor
from langbot.pkg.agent.runner.session_registry import AgentRunSessionRegistry
from langbot.pkg.plugin.handler import _get_pipeline_knowledge_base_uuids
from langbot.pkg.api.http.context import ExecutionContext

# Import shared test fixtures from conftest.py
from .conftest import make_resources, make_session


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
        self.pipeline_uuid = 'pipeline-001'
        self.query_uuid = f'query-{query_id}'
        self._execution_context = ExecutionContext(
            instance_uuid='instance-test',
            workspace_uuid='workspace-test',
            placement_generation=1,
            bot_uuid=self.bot_uuid,
            pipeline_uuid=self.pipeline_uuid,
            query_uuid=self.query_uuid,
        )
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


class FakeRunnerRegistry:
    async def get(self, context, runner_id, bound_plugins=None):
        return RunnerDescriptor(
            usages=['agent'],
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
        app.runner_registry = FakeRunnerRegistry()
        query = MockQuery()
        query.variables = {}

        kb_uuids = await _get_pipeline_knowledge_base_uuids(app, query)

        assert kb_uuids == ['kb_001', 'kb_002']


class MockDisconnectCallback:
    """Mock disconnect callback for testing."""

    async def __call__(self):
        return True


@pytest.mark.asyncio
async def test_tool_manager_get_tool_detail_returns_uniform_schema():
    """ToolManager.get_tool_detail returns a uniform host-level tool detail shape.

    All loaders normalize to resource_tool.LLMTool, so GET_TOOL_DETAIL no longer
    needs a handler-local adapter for plugin ComponentManifest objects.
    """
    import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
    from langbot.pkg.provider.tools.toolmgr import ToolManager

    tool = resource_tool.LLMTool(
        name='search',
        human_desc='Search public data',
        description='Search test data',
        parameters={'type': 'object', 'properties': {'q': {'type': 'string'}}},
        func=lambda **kwargs: {},
    )

    mgr = ToolManager.__new__(ToolManager)

    async def fake_get_tool_by_name(context, name):
        return tool if name == 'search' else None

    mgr.get_tool_by_name = fake_get_tool_by_name

    detail = await mgr.get_tool_detail('workspace-test', 'search')
    assert detail == {
        'name': 'search',
        'description': 'Search test data',
        'human_desc': 'Search public data',
        'parameters': {'type': 'object', 'properties': {'q': {'type': 'string'}}},
    }
    assert await mgr.get_tool_detail('workspace-test', 'missing') is None


class TestSDKRunnerAPIProxyFieldConsistency:
    """Tests for SDK RunnerAPIProxy field name consistency with Host handler.

    These tests verify that SDK sends field names that match what Host handler reads.
    """

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


class TestSessionExpiryAndCleanup:
    """Tests for session expiry and cleanup scenarios."""

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
        resources = make_resources(
            models=[
                {'model_id': 'model_001'},
                {'model_id': 'model_002'},
            ]
        )

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
        resources = make_resources(
            tools=[
                {'tool_name': 'web_search'},
                {'tool_name': 'image_gen'},
            ]
        )

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
        resources = make_resources(
            knowledge_bases=[
                {'kb_id': 'kb_001'},
                {'kb_id': 'kb_002'},
            ]
        )

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

        session = make_session(resources=resources)

        # Unknown resource type should return False
        assert registry.is_resource_allowed(session, 'unknown_type', 'any_id') is False


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
            mock_ap,
            caller_plugin_identity='test/runner',
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

        session, error = await _validate_run_authorization('run_nonexistent_helper', 'model', 'model_001', mock_ap)

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
            mock_ap,
            caller_plugin_identity='test/runner',
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
            mock_ap,
            caller_plugin_identity='test/runner',
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
            mock_ap,
            caller_plugin_identity='test/runner',
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

        session = make_session(resources={})

        # Should return False for both storage types
        assert registry.is_resource_allowed(session, 'storage', 'plugin') is False
        assert registry.is_resource_allowed(session, 'storage', 'workspace') is False


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
            mock_ap,
            caller_plugin_identity='test/runner',
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
            mock_ap,
            caller_plugin_identity='test/runner',
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
            mock_ap,
            caller_plugin_identity='test/runner',
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
            mock_ap,
            caller_plugin_identity='test/runner',
        )

        assert session is None
        assert error is not None
        assert 'not authorized' in error.message.lower()

        await registry.unregister('run_workspace_storage_denied')


class TestOperationPermissionValidation:
    """Tests operation-level Host-side run authorization."""

    @pytest.mark.asyncio
    async def test_model_operation_denied_when_resource_only_allows_invoke(self):
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        from langbot.pkg.plugin.handler import _validate_run_authorization

        registry = get_session_registry()
        await registry.register(
            run_id='run_model_operation_denied',
            runner_id='plugin:test/runner/default',
            query_id=1,
            plugin_identity='test/runner',
            resources=make_resources(models=[{'model_id': 'model_001', 'operations': ['invoke']}]),
        )

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()

        session, error = await _validate_run_authorization(
            'run_model_operation_denied',
            'model',
            'model_001',
            mock_ap,
            caller_plugin_identity='test/runner',
            operation='stream',
        )

        assert session is None
        assert error is not None
        assert 'operation stream' in error.message

        await registry.unregister('run_model_operation_denied')


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
    async def test_run_id_requires_caller_identity(self):
        """Run-scoped authorization requires caller_plugin_identity."""
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

        session, error = await _validate_run_authorization(
            'run_no_caller_identity',
            'model',
            'model_001',
            mock_ap,
            caller_plugin_identity=None,
        )

        assert session is None
        assert error is not None
        assert 'caller_plugin_identity is required' in error.message

        await registry.unregister('run_no_caller_identity')

    @pytest.mark.asyncio
    async def test_session_missing_plugin_identity_denied(self):
        """Malformed legacy sessions without plugin_identity fail closed."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        registry = get_session_registry()
        resources = make_resources(models=[{'model_id': 'model_001'}])
        session = make_session(
            run_id='run_missing_session_identity',
            runner_id='plugin:test/runner/default',
            plugin_identity='',
            resources=resources,
        )
        async with registry._lock:
            registry._sessions['run_missing_session_identity'] = session

        from langbot.pkg.plugin.handler import _validate_run_authorization

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()

        session, error = await _validate_run_authorization(
            'run_missing_session_identity',
            'model',
            'model_001',
            mock_ap,
            caller_plugin_identity='test/runner',
        )

        assert session is None
        assert error is not None
        assert 'no plugin_identity' in error.message

        await registry.unregister('run_missing_session_identity')

    @pytest.mark.asyncio
    async def test_pull_api_session_missing_plugin_identity_denied(self):
        """Pull API validation also fails closed for missing session identity."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        registry = get_session_registry()
        session = make_session(
            run_id='run_missing_pull_identity',
            runner_id='plugin:test/runner/default',
            plugin_identity='',
            available_apis={'history_page': True},
        )
        async with registry._lock:
            registry._sessions['run_missing_pull_identity'] = session

        from langbot.pkg.plugin.handler import _validate_agent_run_session

        mock_ap = MagicMock()
        mock_ap.logger = MagicMock()

        session, error = await _validate_agent_run_session(
            'run_missing_pull_identity',
            'test/runner',
            mock_ap,
            'HISTORY_PAGE',
            'history_page',
        )

        assert session is None
        assert error is not None
        assert 'no plugin_identity' in error.message

        await registry.unregister('run_missing_pull_identity')
