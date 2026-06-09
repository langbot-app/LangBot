"""Agent runner registry for discovering and caching runner descriptors."""

from __future__ import annotations

import typing
import asyncio

from ...core import app
from .descriptor import AgentRunnerDescriptor
from .id import parse_runner_id, format_runner_id
from .errors import RunnerNotFoundError, RunnerNotAuthorizedError


class AgentRunnerRegistry:
    """Registry for discovering and managing agent runners.

    Responsibilities:
    - Discover runners from plugin runtime via LIST_AGENT_RUNNERS
    - Validate runner manifests (kind, metadata, spec)
    - Cache discovered runners for performance
    - Filter runners by bound plugins
    - Handle manifest errors gracefully (log warning, skip runner)
    """

    ap: app.Application

    _cache: dict[str, AgentRunnerDescriptor] | None
    """Cached runner descriptors keyed by runner ID"""

    _cache_lock: asyncio.Lock
    """Lock for cache refresh operations"""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self._cache = None
        self._cache_lock = asyncio.Lock()

    async def _discover_runners(self) -> dict[str, AgentRunnerDescriptor]:
        """Discover runners from plugin runtime.

        Always discovers ALL runners (no bound_plugins filter).
        The cache should contain unfiltered discovery results.

        Returns:
            Dict of runner descriptors keyed by runner ID
        """
        if not self.ap.plugin_connector.is_enable_plugin:
            return {}

        runners: dict[str, AgentRunnerDescriptor] = {}

        try:
            # Always list all runners (bound_plugins=None)
            plugin_runners = await self.ap.plugin_connector.list_agent_runners(None)

            for runner_data in plugin_runners:
                try:
                    descriptor = self._validate_and_build_descriptor(runner_data)
                    if descriptor is not None:
                        runners[descriptor.id] = descriptor
                except Exception as e:
                    plugin_author = runner_data.get('plugin_author', 'unknown')
                    plugin_name = runner_data.get('plugin_name', 'unknown')
                    runner_name = runner_data.get('runner_name', 'unknown')
                    self.ap.logger.warning(
                        f'Invalid runner manifest for plugin:{plugin_author}/{plugin_name}/{runner_name}: {e}'
                    )
                    continue

        except Exception as e:
            self.ap.logger.warning(f'Failed to list agent runners from plugin runtime: {e}')
            return {}

        return runners

    def _validate_and_build_descriptor(self, runner_data: dict[str, typing.Any]) -> AgentRunnerDescriptor | None:
        """Validate runner manifest and build descriptor.

        Args:
            runner_data: Raw runner data from plugin runtime with fields:
                - plugin_author, plugin_name, runner_name
                - manifest (full component manifest dict)
                - capabilities, permissions, config (extracted from spec)

        Returns:
            AgentRunnerDescriptor if valid, None if invalid
        """
        plugin_author = runner_data.get('plugin_author', '')
        plugin_name = runner_data.get('plugin_name', '')
        runner_name = runner_data.get('runner_name', '')

        if not plugin_author or not plugin_name or not runner_name:
            return None

        manifest = runner_data.get('manifest', {})

        # Validate kind
        kind = manifest.get('kind', '')
        if kind != 'AgentRunner':
            return None

        # Validate metadata
        metadata = manifest.get('metadata', {})
        name = metadata.get('name', '')
        if not name:
            return None

        # metadata.label must exist
        label = metadata.get('label', {})
        if not label:
            label = {name: name}  # fallback

        spec = manifest.get('spec', {})

        # SDK now provides these directly extracted from spec. Fall back to
        # manifest.spec for older runtimes/tests that return the raw manifest.
        config_schema = runner_data.get('config') or spec.get('config', [])
        capabilities = runner_data.get('capabilities') or spec.get('capabilities', {})
        permissions = runner_data.get('permissions') or spec.get('permissions', {})

        # Build descriptor
        runner_id = format_runner_id(
            source='plugin',
            plugin_author=plugin_author,
            plugin_name=plugin_name,
            runner_name=runner_name,
        )

        return AgentRunnerDescriptor(
            id=runner_id,
            source='plugin',
            label=label,
            description=metadata.get('description') or runner_data.get('runner_description'),
            plugin_author=plugin_author,
            plugin_name=plugin_name,
            runner_name=runner_name,
            plugin_version=runner_data.get('plugin_version'),
            config_schema=config_schema,
            capabilities=capabilities,
            permissions=permissions,
            raw_manifest=manifest,
        )

    async def refresh(self) -> None:
        """Refresh runner cache.

        Always discovers ALL runners (no bound_plugins filter).
        The cache contains unfiltered discovery results.
        """
        async with self._cache_lock:
            self._cache = await self._discover_runners()

    async def list_runners(
        self,
        bound_plugins: list[str] | None = None,
        use_cache: bool = True,
    ) -> list[AgentRunnerDescriptor]:
        """List available runners.

        Args:
            bound_plugins: Optional filter for bound plugins (applied locally)
            use_cache: Use cached data if available

        Returns:
            List of runner descriptors
        """
        if use_cache and self._cache is not None:
            # Filter from cache
            return self._filter_runners_by_bound_plugins(self._cache, bound_plugins)

        # Discover fresh (always full list)
        runners = await self._discover_runners()

        # Update cache (full list, unfiltered)
        async with self._cache_lock:
            self._cache = runners

        # Filter locally
        return self._filter_runners_by_bound_plugins(runners, bound_plugins)

    def _filter_runners_by_bound_plugins(
        self,
        runners: dict[str, AgentRunnerDescriptor],
        bound_plugins: list[str] | None,
    ) -> list[AgentRunnerDescriptor]:
        """Filter runners by bound plugins.

        Args:
            runners: Dict of runner descriptors
            bound_plugins: Optional filter (None means all plugins allowed)

        Returns:
            Filtered list of runner descriptors
        """
        if bound_plugins is None:
            # All plugins allowed
            return list(runners.values())

        allowed_plugin_ids = set(bound_plugins)
        filtered = []
        for descriptor in runners.values():
            plugin_id = descriptor.get_plugin_id()
            if plugin_id in allowed_plugin_ids:
                filtered.append(descriptor)

        return filtered

    async def get(
        self,
        runner_id: str,
        bound_plugins: list[str] | None = None,
    ) -> AgentRunnerDescriptor:
        """Get a specific runner descriptor.

        Args:
            runner_id: Runner ID to lookup
            bound_plugins: Optional bound plugins filter

        Returns:
            AgentRunnerDescriptor

        Raises:
            RunnerNotFoundError: If runner not found
            RunnerNotAuthorizedError: If runner not in bound plugins
        """
        # Parse and validate runner ID format
        try:
            parse_runner_id(runner_id)
        except ValueError as e:
            raise RunnerNotFoundError(runner_id) from e

        # Get from cache or discover (always full list)
        if self._cache is None:
            await self.refresh()

        if self._cache is None:
            raise RunnerNotFoundError(runner_id)

        descriptor = self._cache.get(runner_id)
        if descriptor is None:
            raise RunnerNotFoundError(runner_id)

        # Check authorization
        if bound_plugins is not None:
            plugin_id = descriptor.get_plugin_id()
            if plugin_id not in bound_plugins:
                raise RunnerNotAuthorizedError(runner_id, bound_plugins)

        return descriptor

    async def get_runner_metadata_for_pipeline(self) -> list[dict[str, typing.Any]]:
        """Get runner metadata for pipeline configuration UI.

        Returns runner options and their config schemas for the DynamicForm.
        """
        # Get all runners (no bound plugin filter for metadata listing)
        runners = await self.list_runners(bound_plugins=None)

        options = []
        stages = []

        for descriptor in runners:
            config_schema = []
            for index, config_item in enumerate(descriptor.config_schema):
                item = dict(config_item)
                if not item.get('id'):
                    item_name = item.get('name') or str(index)
                    item['id'] = f'{descriptor.id}.{item_name}'
                config_schema.append(item)

            # Add runner option
            options.append(
                {
                    'name': descriptor.id,
                    'label': descriptor.label,
                    'description': descriptor.description,
                }
            )

            # Add config schema as stage if not empty
            if descriptor.config_schema:
                stages.append(
                    {
                        'name': descriptor.id,
                        'label': descriptor.label,
                        'description': descriptor.description,
                        'config': config_schema,
                    }
                )

        return options, stages
