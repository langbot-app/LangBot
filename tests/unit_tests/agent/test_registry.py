"""Tests for agent runner registry."""

from __future__ import annotations

import pytest

from langbot.pkg.agent.runner.registry import AgentRunnerRegistry
from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.agent.runner.errors import RunnerNotFoundError, RunnerNotAuthorizedError


class FakeApplication:
    """Fake Application for testing."""

    def __init__(self):
        class FakeLogger:
            def info(self, msg):
                pass

            def debug(self, msg):
                pass

            def warning(self, msg):
                pass

            def error(self, msg):
                pass

        self.logger = FakeLogger()

        class FakePluginConnector:
            is_enable_plugin = True

            async def list_agent_runners(self, bound_plugins=None):
                # Return sample runner data
                return [
                    {
                        'plugin_author': 'langbot',
                        'plugin_name': 'local-agent',
                        'runner_name': 'default',
                        'manifest': {
                            'kind': 'AgentRunner',
                            'metadata': {
                                'name': 'default',
                                'label': {'en_US': 'Local Agent'},
                            },
                            'spec': {
                                'config': [],
                                'capabilities': {'streaming': True},
                                'permissions': {},
                            },
                        },
                    },
                    {
                        'plugin_author': 'alice',
                        'plugin_name': 'my-agent',
                        'runner_name': 'custom',
                        'manifest': {
                            'kind': 'AgentRunner',
                            'metadata': {
                                'name': 'custom',
                                'label': {'en_US': 'Custom Agent'},
                            },
                            'spec': {
                                'config': [{'name': 'param1', 'type': 'string'}],
                                'capabilities': {},
                                'permissions': {},
                            },
                        },
                    },
                    # Invalid runner - wrong kind
                    {
                        'plugin_author': 'bad',
                        'plugin_name': 'wrong-kind',
                        'runner_name': 'default',
                        'manifest': {
                            'kind': 'Tool',  # Wrong kind
                            'metadata': {},
                            'spec': {},
                        },
                    },
                    # Invalid runner - missing name
                    {
                        'plugin_author': 'bad',
                        'plugin_name': 'missing-name',
                        'runner_name': 'default',
                        'manifest': {
                            'kind': 'AgentRunner',
                            'metadata': {},  # No name
                            'spec': {},
                        },
                    },
                ]

        self.plugin_connector = FakePluginConnector()


class TestRegistryDiscovery:
    """Tests for runner discovery."""

    @pytest.mark.asyncio
    async def test_discover_valid_runners(self):
        """Discover valid runners from plugin runtime."""
        ap = FakeApplication()
        registry = AgentRunnerRegistry(ap)

        runners = await registry.list_runners(use_cache=False)

        # Should find 2 valid runners (langbot/local-agent and alice/my-agent)
        assert len(runners) == 2

        ids = [r.id for r in runners]
        assert 'plugin:langbot/local-agent/default' in ids
        assert 'plugin:alice/my-agent/custom' in ids

    @pytest.mark.asyncio
    async def test_discover_caches_results(self):
        """Discovery should cache results."""
        ap = FakeApplication()
        registry = AgentRunnerRegistry(ap)

        # First discovery
        runners1 = await registry.list_runners(use_cache=True)

        # Second call should use cache
        runners2 = await registry.list_runners(use_cache=True)

        assert registry._cache is not None
        assert len(runners1) == len(runners2)

    @pytest.mark.asyncio
    async def test_discover_handles_plugin_disabled(self):
        """Discovery returns empty when plugin system disabled."""
        ap = FakeApplication()
        ap.plugin_connector.is_enable_plugin = False
        registry = AgentRunnerRegistry(ap)

        runners = await registry.list_runners(use_cache=False)

        assert runners == []

    @pytest.mark.asyncio
    async def test_cache_not_polluted_by_bound_plugins(self):
        """Cache should contain ALL runners, not filtered by bound_plugins.

        Regression test: get(bound_plugins=["a/b"]) should not pollute cache,
        so subsequent list_runners(bound_plugins=None) should return all runners.
        """
        ap = FakeApplication()
        registry = AgentRunnerRegistry(ap)

        # First: get with bound_plugins filter (should not pollute cache)
        descriptor = await registry.get(
            'plugin:langbot/local-agent/default',
            bound_plugins=['langbot/local-agent'],
        )
        assert descriptor.id == 'plugin:langbot/local-agent/default'

        # Cache should contain ALL runners (both langbot and alice)
        assert registry._cache is not None
        assert len(registry._cache) == 2  # Both runners in cache
        assert 'plugin:langbot/local-agent/default' in registry._cache
        assert 'plugin:alice/my-agent/custom' in registry._cache

        # Second: list_runners without filter should return ALL runners
        all_runners = await registry.list_runners(bound_plugins=None, use_cache=True)
        assert len(all_runners) == 2  # Both runners returned

        # Third: list_runners with different filter should work correctly
        alice_runners = await registry.list_runners(bound_plugins=['alice/my-agent'], use_cache=True)
        assert len(alice_runners) == 1
        assert alice_runners[0].id == 'plugin:alice/my-agent/custom'


class TestRegistryGet:
    """Tests for getting specific runner."""

    @pytest.mark.asyncio
    async def test_get_existing_runner(self):
        """Get existing runner by ID."""
        ap = FakeApplication()
        registry = AgentRunnerRegistry(ap)

        descriptor = await registry.get('plugin:langbot/local-agent/default')

        assert descriptor.id == 'plugin:langbot/local-agent/default'
        assert descriptor.plugin_author == 'langbot'
        assert descriptor.plugin_name == 'local-agent'
        assert descriptor.runner_name == 'default'

    @pytest.mark.asyncio
    async def test_get_nonexistent_runner(self):
        """Get nonexistent runner raises RunnerNotFoundError."""
        ap = FakeApplication()
        registry = AgentRunnerRegistry(ap)

        with pytest.raises(RunnerNotFoundError) as exc_info:
            await registry.get('plugin:notexist/unknown/default')

        assert exc_info.value.runner_id == 'plugin:notexist/unknown/default'

    @pytest.mark.asyncio
    async def test_get_runner_with_bound_plugins_filter(self):
        """Get runner with bound plugins authorization."""
        ap = FakeApplication()
        registry = AgentRunnerRegistry(ap)

        # Authorized - langbot plugin in bound list
        descriptor = await registry.get(
            'plugin:langbot/local-agent/default',
            bound_plugins=['langbot/local-agent'],
        )
        assert descriptor is not None

        # Not authorized - plugin not in bound list
        with pytest.raises(RunnerNotAuthorizedError):
            await registry.get(
                'plugin:alice/my-agent/custom',
                bound_plugins=['langbot/local-agent'],
            )


class TestRegistryMetadataForPipeline:
    """Tests for get_runner_metadata_for_pipeline."""

    @pytest.mark.asyncio
    async def test_get_metadata_options_and_stages(self):
        """Get metadata options and stages for pipeline UI."""
        ap = FakeApplication()
        registry = AgentRunnerRegistry(ap)

        options, stages = await registry.get_runner_metadata_for_pipeline()

        # Should have options for each runner
        assert len(options) == 2
        option_ids = [o['name'] for o in options]
        assert 'plugin:langbot/local-agent/default' in option_ids
        assert 'plugin:alice/my-agent/custom' in option_ids

        # Should fall back to manifest.spec.config when runtime does not return
        # extracted config at top level.
        assert len(stages) == 1
        assert stages[0]['name'] == 'plugin:alice/my-agent/custom'
        assert stages[0]['config'] == [{
            'name': 'param1',
            'type': 'string',
            'id': 'plugin:alice/my-agent/custom.param1',
        }]


class TestDescriptorValidation:
    """Tests for descriptor validation."""

    def test_validate_runner_descriptor(self):
        """Validate correctly built descriptor."""
        descriptor = AgentRunnerDescriptor(
            id='plugin:test/my-runner/default',
            source='plugin',
            label={'en_US': 'Test Runner'},
            plugin_author='test',
            plugin_name='my-runner',
            runner_name='default',
        )

        assert descriptor.id == 'plugin:test/my-runner/default'
        assert descriptor.get_plugin_id() == 'test/my-runner'
        assert 'protocol_version' not in AgentRunnerDescriptor.model_fields

    def test_descriptor_capabilities(self):
        """Descriptor capability helper methods."""
        descriptor = AgentRunnerDescriptor(
            id='plugin:test/my-runner/default',
            source='plugin',
            label={'en_US': 'Test Runner'},
            plugin_author='test',
            plugin_name='my-runner',
            runner_name='default',
            capabilities={'streaming': True, 'tool_calling': False},
        )

        assert descriptor.supports_streaming() is True
        assert descriptor.supports_tool_calling() is False
        assert descriptor.supports_knowledge_retrieval() is False
