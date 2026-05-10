"""Agent run orchestrator for coordinating runner execution."""
from __future__ import annotations

import typing
import traceback

from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query

from ...core import app
from .descriptor import AgentRunnerDescriptor
from .registry import AgentRunnerRegistry
from .context_builder import AgentRunContextBuilder, AgentRunContextV1
from .resource_builder import AgentResourceBuilder
from .result_normalizer import AgentResultNormalizer
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

        # Run via plugin connector
        async for result_dict in self._invoke_runner(descriptor, context):
            # Normalize result
            result = await self.result_normalizer.normalize(result_dict, descriptor)
            if result is not None:
                yield result

    async def _invoke_runner(
        self,
        descriptor: AgentRunnerDescriptor,
        context: AgentRunContextV1,
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
            async for result_dict in self.ap.plugin_connector.run_agent(
                plugin_author=descriptor.plugin_author,
                plugin_name=descriptor.plugin_name,
                runner_name=descriptor.runner_name,
                context=context,
            ):
                yield result_dict

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

    def resolve_runner_id_for_telemetry(self, query: pipeline_query.Query) -> str | None:
        """Resolve runner ID for telemetry/logging without full execution.

        Args:
            query: Pipeline query

        Returns:
            Runner ID string, or None
        """
        return ConfigMigration.resolve_runner_id(query.pipeline_config)