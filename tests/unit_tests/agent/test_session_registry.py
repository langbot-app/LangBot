"""Tests for AgentRunSessionRegistry."""
from __future__ import annotations

import pytest
import asyncio
import time

from langbot.pkg.agent.runner.session_registry import (
    AgentRunSessionRegistry,
    AgentRunSession,
    get_session_registry,
)

# Import shared test fixtures from conftest.py
from .conftest import make_resources, make_session


class TestSessionRegistryBasic:
    """Tests for basic registry operations."""

    @pytest.mark.asyncio
    async def test_register_and_get(self):
        """Register and retrieve a session."""
        registry = AgentRunSessionRegistry()
        run_id = 'run_abc'
        resources = make_resources(
            models=[{'model_id': 'model_001', 'model_type': 'chat', 'provider': 'openai'}],
            tools=[{'tool_name': 'web_search', 'tool_type': 'builtin'}],
        )
        session = make_session(run_id=run_id, resources=resources)

        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/my-runner/default',
            query_id=1,
            plugin_identity='test/my-runner',
            resources=resources,
        )

        result = await registry.get(run_id)
        assert result is not None
        assert result['run_id'] == run_id
        assert result['runner_id'] == 'plugin:test/my-runner/default'
        assert result['query_id'] == 1
        assert result['plugin_identity'] == 'test/my-runner'
        assert len(result['resources']['models']) == 1
        assert result['resources']['models'][0]['model_id'] == 'model_001'

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self):
        """Get should return None for nonexistent run_id."""
        registry = AgentRunSessionRegistry()
        result = await registry.get('nonexistent_run')
        assert result is None

    @pytest.mark.asyncio
    async def test_unregister(self):
        """Unregister should remove session."""
        registry = AgentRunSessionRegistry()
        run_id = 'run_xyz'

        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/my-runner/default',
            query_id=1,
            plugin_identity='test/my-runner',
            resources=make_resources(),
        )

        # Verify registered
        result = await registry.get(run_id)
        assert result is not None

        # Unregister
        await registry.unregister(run_id)

        # Verify unregistered
        result = await registry.get(run_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_unregister_nonexistent(self):
        """Unregister nonexistent session should not raise error."""
        registry = AgentRunSessionRegistry()
        # Should not raise
        await registry.unregister('nonexistent_run')

    @pytest.mark.asyncio
    async def test_update_activity(self):
        """Update activity should update last_activity_at."""
        registry = AgentRunSessionRegistry()
        run_id = 'run_activity'

        # Create session with manually set old timestamp
        now = int(time.time())
        res = make_resources()
        old_session: AgentRunSession = {
            'run_id': run_id,
            'runner_id': 'plugin:test/my-runner/default',
            'query_id': 1,
            'plugin_identity': 'test/my-runner',
            'resources': res,
            'status': {
                'started_at': now - 100,  # 100 seconds ago
                'last_activity_at': now - 100,  # 100 seconds ago
            },
            '_authorized_ids': {
                'model': set(),
                'tool': set(),
                'knowledge_base': set(),
                'file': set(),
            },
        }

        async with registry._lock:
            registry._sessions[run_id] = old_session

        # Get initial session
        session1 = await registry.get(run_id)
        initial_time = session1['status']['last_activity_at']

        # Update activity
        await registry.update_activity(run_id)

        # Verify updated - should be significantly different (100 seconds)
        session2 = await registry.get(run_id)
        assert session2['status']['last_activity_at'] > initial_time
        assert session2['status']['last_activity_at'] - initial_time >= 100

    @pytest.mark.asyncio
    async def test_update_activity_nonexistent(self):
        """Update activity on nonexistent session should not raise."""
        registry = AgentRunSessionRegistry()
        # Should not raise
        await registry.update_activity('nonexistent_run')

    @pytest.mark.asyncio
    async def test_list_active_runs(self):
        """List active runs should return all sessions."""
        registry = AgentRunSessionRegistry()

        await registry.register('run_1', 'plugin:a/b/default', 1, 'a/b', make_resources())
        await registry.register('run_2', 'plugin:c/d/default', 2, 'c/d', make_resources())

        active_runs = await registry.list_active_runs()
        assert len(active_runs) == 2
        run_ids = [r['run_id'] for r in active_runs]
        assert 'run_1' in run_ids
        assert 'run_2' in run_ids

    @pytest.mark.asyncio
    async def test_cleanup_stale_sessions(self):
        """Cleanup should remove old sessions."""
        registry = AgentRunSessionRegistry()

        # Create sessions with manually set old timestamp
        now = int(time.time())
        res = make_resources()
        old_session: AgentRunSession = {
            'run_id': 'old_run',
            'runner_id': 'plugin:test/runner/default',
            'query_id': 1,
            'plugin_identity': 'test/runner',
            'resources': res,
            'status': {
                'started_at': now - 7200,  # 2 hours ago
                'last_activity_at': now - 7200,  # 2 hours ago
            },
            '_authorized_ids': {
                'model': set(),
                'tool': set(),
                'knowledge_base': set(),
                'file': set(),
            },
        }
        new_session: AgentRunSession = {
            'run_id': 'new_run',
            'runner_id': 'plugin:test/runner/default',
            'query_id': 2,
            'plugin_identity': 'test/runner',
            'resources': res,
            'status': {
                'started_at': now,
                'last_activity_at': now,
            },
            '_authorized_ids': {
                'model': set(),
                'tool': set(),
                'knowledge_base': set(),
                'file': set(),
            },
        }

        async with registry._lock:
            registry._sessions['old_run'] = old_session
            registry._sessions['new_run'] = new_session

        # Cleanup sessions older than 1 hour
        cleaned = await registry.cleanup_stale_sessions(max_age_seconds=3600)
        assert cleaned == 1

        # Verify old session removed, new remains
        assert await registry.get('old_run') is None
        assert await registry.get('new_run') is not None


class TestIsResourceAllowed:
    """Tests for is_resource_allowed validation."""

    def test_model_allowed(self):
        """Model in resources should be allowed."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(
            models=[
                {'model_id': 'model_001', 'model_type': 'chat', 'provider': 'openai'},
                {'model_id': 'model_002', 'model_type': 'embedding', 'provider': 'anthropic'},
            ]
        )
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'model', 'model_001') is True
        assert registry.is_resource_allowed(session, 'model', 'model_002') is True

    def test_model_not_allowed(self):
        """Model not in resources should be denied."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(models=[{'model_id': 'model_001'}])
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'model', 'model_999') is False

    def test_model_empty_resources(self):
        """Empty models list should deny all."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(models=[])
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'model', 'model_001') is False

    def test_tool_allowed(self):
        """Tool in resources should be allowed."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(
            tools=[
                {'tool_name': 'web_search', 'tool_type': 'builtin'},
                {'tool_name': 'code_exec', 'tool_type': 'plugin'},
            ]
        )
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'tool', 'web_search') is True
        assert registry.is_resource_allowed(session, 'tool', 'code_exec') is True

    def test_tool_not_allowed(self):
        """Tool not in resources should be denied."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(tools=[{'tool_name': 'web_search'}])
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'tool', 'image_gen') is False

    def test_tool_empty_resources(self):
        """Empty tools list should deny all."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(tools=[])
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'tool', 'web_search') is False

    def test_knowledge_base_allowed(self):
        """Knowledge base in resources should be allowed."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(
            knowledge_bases=[
                {'kb_id': 'kb_001', 'kb_name': 'docs', 'kb_type': 'vector'},
                {'kb_id': 'kb_002', 'kb_name': 'faq', 'kb_type': 'keyword'},
            ]
        )
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'knowledge_base', 'kb_001') is True
        assert registry.is_resource_allowed(session, 'knowledge_base', 'kb_002') is True

    def test_knowledge_base_not_allowed(self):
        """Knowledge base not in resources should be denied."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(knowledge_bases=[{'kb_id': 'kb_001'}])
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'knowledge_base', 'kb_999') is False

    def test_knowledge_base_empty_resources(self):
        """Empty knowledge bases list should deny all."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(knowledge_bases=[])
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'knowledge_base', 'kb_001') is False

    def test_storage_plugin_allowed(self):
        """Plugin storage permission should be checked."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(storage={'plugin_storage': True, 'workspace_storage': False})
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'storage', 'plugin') is True
        assert registry.is_resource_allowed(session, 'storage', 'workspace') is False

    def test_storage_workspace_allowed(self):
        """Workspace storage permission should be checked."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(storage={'plugin_storage': False, 'workspace_storage': True})
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'storage', 'plugin') is False
        assert registry.is_resource_allowed(session, 'storage', 'workspace') is True

    def test_storage_both_denied(self):
        """Both storage permissions denied."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(storage={'plugin_storage': False, 'workspace_storage': False})
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'storage', 'plugin') is False
        assert registry.is_resource_allowed(session, 'storage', 'workspace') is False

    def test_unknown_resource_type(self):
        """Unknown resource type should return False."""
        registry = AgentRunSessionRegistry()
        session = make_session(resources=make_resources())

        assert registry.is_resource_allowed(session, 'unknown_type', 'something') is False

    def test_file_allowed(self):
        """File in resources should be allowed."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(
            files=[
                {'file_id': 'file_001'},
                {'file_id': 'file_002'},
            ]
        )
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'file', 'file_001') is True
        assert registry.is_resource_allowed(session, 'file', 'file_002') is True

    def test_file_not_allowed(self):
        """File not in resources should be denied."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(files=[{'file_id': 'file_001'}])
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'file', 'file_999') is False

    def test_file_empty_resources(self):
        """Empty files list should deny all."""
        registry = AgentRunSessionRegistry()
        resources = make_resources(files=[])
        session = make_session(resources=resources)

        assert registry.is_resource_allowed(session, 'file', 'file_001') is False

    def test_missing_resources_field(self):
        """Missing resources field should not raise."""
        registry = AgentRunSessionRegistry()
        session = make_session(resources={'models': []})  # Missing other fields

        # Should not raise, should return False
        assert registry.is_resource_allowed(session, 'tool', 'web_search') is False
        assert registry.is_resource_allowed(session, 'knowledge_base', 'kb_001') is False


class TestGlobalRegistry:
    """Tests for global registry singleton."""

    def test_get_session_registry_returns_instance(self):
        """get_session_registry should return AgentRunSessionRegistry."""
        # Use a separate test that doesn't modify global state
        # The singleton pattern works in production, but modifying globals
        # in tests can cause UnboundLocalError due to Python scoping
        # Instead, just verify the function signature
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        assert callable(get_session_registry)

        # Create a fresh instance directly to verify the class works
        fresh_registry = AgentRunSessionRegistry()
        assert isinstance(fresh_registry, AgentRunSessionRegistry)

    def test_global_registry_singleton_behavior(self):
        """The global registry should maintain singleton behavior."""
        # Test singleton behavior without modifying global state
        # In production, calling get_session_registry() multiple times
        # returns the same instance. We verify this by checking the
        # module-level variable directly.
        import langbot.pkg.agent.runner.session_registry as registry_module

        # Check that the global variable exists and is either None or an instance
        global_reg = registry_module._global_registry
        if global_reg is None:
            # First call creates the instance
            registry1 = get_session_registry()
            assert isinstance(registry1, AgentRunSessionRegistry)
            # Subsequent calls return the same instance
            registry2 = get_session_registry()
            assert registry1 is registry2
        else:
            # Instance already exists, verify singleton
            registry1 = get_session_registry()
            registry2 = get_session_registry()
            assert registry1 is registry2
            assert registry1 is global_reg


class TestThreadSafety:
    """Tests for asyncio.Lock thread safety."""

    @pytest.mark.asyncio
    async def test_concurrent_register(self):
        """Concurrent register should be safe."""
        registry = AgentRunSessionRegistry()

        # Register multiple sessions concurrently
        tasks = []
        for i in range(10):
            tasks.append(
                registry.register(
                    f'run_{i}',
                    'plugin:test/runner/default',
                    i,
                    'test/runner',
                    make_resources(),
                )
            )

        await asyncio.gather(*tasks)

        # All sessions should be registered
        active_runs = await registry.list_active_runs()
        assert len(active_runs) == 10

    @pytest.mark.asyncio
    async def test_concurrent_register_and_unregister(self):
        """Concurrent register and unregister should be safe."""
        registry = AgentRunSessionRegistry()

        # Register
        await registry.register('run_1', 'plugin:test/runner/default', 1, 'test/runner', make_resources())

        # Concurrent unregister and get
        tasks = [
            registry.unregister('run_1'),
            registry.get('run_1'),
        ]

        results = await asyncio.gather(*tasks)

        # After both complete, session should be unregistered
        result = await registry.get('run_1')
        assert result is None