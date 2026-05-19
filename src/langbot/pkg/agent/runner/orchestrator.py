"""Agent run orchestrator for coordinating runner execution."""
from __future__ import annotations

import typing
import traceback
import asyncio
import time

from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query
from langbot_plugin.entities.io.errors import ActionCallTimeoutError

from ...core import app
from .descriptor import AgentRunnerDescriptor
from .registry import AgentRunnerRegistry
from .context_builder import AgentRunContextBuilder, AgentRunContextPayload
from .resource_builder import AgentResourceBuilder
from .result_normalizer import AgentResultNormalizer
from .state_store import get_state_store, RunnerScopedStateStore
from .session_registry import get_session_registry, AgentRunSessionRegistry
from .config_migration import ConfigMigration
from .errors import (
    RunnerNotFoundError,
    RunnerExecutionError,
)


class AgentRunOrchestrator:
    """Orchestrator for agent runner execution.

    Responsibilities:
    - Resolve runner ID from pipeline config (new or old format)
    - Get runner descriptor from registry
    - Build AgentRunContext from Query
    - Build AgentResources with permission filtering
    - Invoke plugin runtime RUN_AGENT action
    - Normalize AgentRunResult to Pipeline messages
    - Handle errors, timeouts, protocol errors
    - Maintain streaming card behavior

    This is the main entry point for ChatMessageHandler.
    """

    ap: app.Application

    registry: AgentRunnerRegistry

    context_builder: AgentRunContextBuilder

    resource_builder: AgentResourceBuilder

    result_normalizer: AgentResultNormalizer

    # Cached singleton references (set in __init__)
    _session_registry: AgentRunSessionRegistry
    _state_store: RunnerScopedStateStore

    def __init__(
        self,
        ap: app.Application,
        registry: AgentRunnerRegistry,
    ):
        self.ap = ap
        self.registry = registry
        self.context_builder = AgentRunContextBuilder(ap)
        self.resource_builder = AgentResourceBuilder(ap)
        self.result_normalizer = AgentResultNormalizer(ap)
        # Cache singleton references to avoid per-request getter calls
        self._session_registry = get_session_registry()
        self._state_store = get_state_store()

    async def run_from_query(
        self,
        query: pipeline_query.Query,
    ) -> typing.AsyncGenerator[provider_message.Message | provider_message.MessageChunk, None]:
        """Run agent runner from pipeline query.

        This is the main entry point called by ChatMessageHandler.

        Args:
            query: Pipeline query with pipeline_config, session, messages, etc.

        Yields:
            Message or MessageChunk for pipeline response

        Raises:
            RunnerNotFoundError: If runner not found
            RunnerNotAuthorizedError: If runner not authorized
            RunnerExecutionError: If runner execution failed
        """
        # Resolve runner ID
        runner_id = ConfigMigration.resolve_runner_id(query.pipeline_config)
        if not runner_id:
            raise RunnerNotFoundError('no runner configured')

        # Get bound plugins for authorization
        bound_plugins = query.variables.get('_pipeline_bound_plugins')

        # Get runner descriptor
        descriptor = await self.registry.get(runner_id, bound_plugins)

        # Build resources
        resources = await self.resource_builder.build_resources(query, descriptor)

        # Build context
        context = await self.context_builder.build_context(query, descriptor, resources)

        # Register session for proxy action permission validation
        run_id = context['run_id']
        await self._session_registry.register(
            run_id=run_id,
            runner_id=descriptor.id,
            query_id=query.query_id,
            plugin_identity=descriptor.get_plugin_id(),
            resources=resources,
        )

        try:
            # Run via plugin connector
            async for result_dict in self._invoke_runner(descriptor, context):
                # Handle state.updated first - consume before normalizer
                if result_dict.get('type') == 'state.updated':
                    self._handle_state_updated(result_dict, query, descriptor)
                    # Pass to normalizer for logging, but don't yield to pipeline
                    await self.result_normalizer.normalize(result_dict, descriptor)
                    continue

                # Normalize result for other types
                result = await self.result_normalizer.normalize(result_dict, descriptor)
                if result is not None:
                    yield result
        finally:
            # Unregister session after run completes (success or error)
            await self._session_registry.unregister(run_id)

    async def _invoke_runner(
        self,
        descriptor: AgentRunnerDescriptor,
        context: AgentRunContextPayload,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Invoke runner via plugin connector.

        Args:
            descriptor: Runner descriptor
            context: AgentRunContext dict

        Yields:
            Raw result dicts from plugin runtime

        Raises:
            RunnerExecutionError: If plugin system disabled or runtime error
        """
        if not self.ap.plugin_connector.is_enable_plugin:
            raise RunnerExecutionError(
                descriptor.id,
                'Plugin system is disabled',
                retryable=False,
            )

        try:
            gen = self.ap.plugin_connector.run_agent(
                plugin_author=descriptor.plugin_author,
                plugin_name=descriptor.plugin_name,
                runner_name=descriptor.runner_name,
                context=context,
            )

            while True:
                try:
                    result_dict = await self._next_with_deadline(gen, descriptor, context)
                except StopAsyncIteration:
                    break
                yield result_dict

        except asyncio.TimeoutError as e:
            raise RunnerExecutionError(
                descriptor.id,
                'Runner timed out (code: runner.timeout)',
                retryable=True,
            ) from e
        except ActionCallTimeoutError as e:
            raise RunnerExecutionError(
                descriptor.id,
                f'{e} (code: runner.timeout)',
                retryable=True,
            ) from e
        except RunnerExecutionError:
            raise
        except Exception as e:
            # Wrap unexpected errors
            self.ap.logger.error(
                f'Runner {descriptor.id} unexpected error: {traceback.format_exc()}'
            )
            raise RunnerExecutionError(
                descriptor.id,
                str(e),
                retryable=False,
            )

    async def _next_with_deadline(
        self,
        gen: typing.AsyncGenerator[dict[str, typing.Any], None],
        descriptor: AgentRunnerDescriptor,
        context: AgentRunContextPayload,
    ) -> dict[str, typing.Any]:
        """Read the next runner result while enforcing the run deadline."""
        remaining = self._remaining_deadline_seconds(context)
        if remaining is not None and remaining <= 0:
            await self._close_generator(gen, descriptor)
            raise asyncio.TimeoutError

        try:
            if remaining is None:
                return await anext(gen)
            return await asyncio.wait_for(anext(gen), timeout=remaining)
        except StopAsyncIteration:
            if self._is_deadline_exhausted(context):
                raise asyncio.TimeoutError
            raise
        except asyncio.TimeoutError:
            await self._close_generator(gen, descriptor)
            raise

    def _remaining_deadline_seconds(
        self,
        context: AgentRunContextPayload,
    ) -> float | None:
        runtime = context.get('runtime') or {}
        deadline_at = runtime.get('deadline_at')
        if deadline_at is None:
            return None
        try:
            return float(deadline_at) - time.time()
        except (TypeError, ValueError):
            return None

    def _is_deadline_exhausted(self, context: AgentRunContextPayload) -> bool:
        remaining = self._remaining_deadline_seconds(context)
        return remaining is not None and remaining <= 0

    async def _close_generator(
        self,
        gen: typing.AsyncGenerator[dict[str, typing.Any], None],
        descriptor: AgentRunnerDescriptor,
    ) -> None:
        try:
            await gen.aclose()
        except Exception as e:
            self.ap.logger.warning(f'Failed to close timed-out runner {descriptor.id}: {e}')

    def resolve_runner_id_for_telemetry(self, query: pipeline_query.Query) -> str | None:
        """Resolve runner ID for telemetry/logging without full execution.

        Args:
            query: Pipeline query

        Returns:
            Runner ID string, or None
        """
        return ConfigMigration.resolve_runner_id(query.pipeline_config)

    def _handle_state_updated(
        self,
        result_dict: dict[str, typing.Any],
        query: pipeline_query.Query,
        descriptor: AgentRunnerDescriptor,
    ) -> None:
        """Handle state.updated result - apply to state store.

        Args:
            result_dict: Raw result dict with type='state.updated'
            query: Pipeline query
            descriptor: Runner descriptor
        """
        data = result_dict.get('data', {})

        # Extract scope (default to 'conversation' for backward compat)
        scope = data.get('scope', 'conversation')

        # Extract key and value
        key = data.get('key')
        value = data.get('value')

        if not key:
            self.ap.logger.warning(
                f'Runner {descriptor.id} state.updated missing key, ignoring'
            )
            return

        # Apply update to state store
        success = self._state_store.apply_update(
            query=query,
            descriptor=descriptor,
            scope=scope,
            key=key,
            value=value,
            logger=self.ap.logger,
        )

        if success:
            self.ap.logger.debug(
                f'Runner {descriptor.id} state.updated: scope={scope}, key={key}, value={value}'
            )
        # Invalid scope is already logged by state_store.apply_update
