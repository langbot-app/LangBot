"""Pipeline Query bridge for Runner execution."""

from __future__ import annotations

import dataclasses
import typing

from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query

from .binding_resolver import AgentBindingResolver
from .config_resolver import RunnerConfigResolver
from .errors import RunnerNotFoundError
from .host_models import AgentBinding, AgentEventEnvelope
from .query_entry_adapter import QueryEntryAdapter


@dataclasses.dataclass(frozen=True)
class QueryRunPlan:
    """Projected event-first execution request for a Query-backed run."""

    event: AgentEventEnvelope
    binding: AgentBinding
    bound_plugins: list[str] | None
    adapter_context: dict[str, typing.Any]


class QueryRunBridge:
    """Project the current Pipeline Query entry point into Protocol v1 inputs."""

    binding_resolver: AgentBindingResolver

    def __init__(self, binding_resolver: AgentBindingResolver):
        self.binding_resolver = binding_resolver

    def build_plan(self, query: pipeline_query.Query) -> QueryRunPlan:
        """Build an event-first run plan from a Pipeline Query."""
        runner_id = RunnerConfigResolver.resolve_runner_id(query.pipeline_config)
        if not runner_id:
            if self._has_legacy_runner_config(query.pipeline_config):
                raise RunnerNotFoundError(
                    'no runner configured; legacy (pre-4.11) pipelines must be migrated with the pipeline '
                    'migration assistant'
                )
            raise RunnerNotFoundError("no runner selected; choose a Runner in this pipeline's AI settings")
        legacy_target = RunnerConfigResolver.legacy_runner_target(runner_id)
        if legacy_target:
            raise RunnerNotFoundError(
                f'{runner_id} is a pre-4.11 runner name; migrate this pipeline with the pipeline migration '
                f'assistant or select {legacy_target}'
            )

        event = QueryEntryAdapter.query_to_event(query)
        agent_config = QueryEntryAdapter.config_to_agent_config(query, runner_id)
        binding = self.binding_resolver.resolve_one(event, [agent_config])
        bound_plugins = query.variables.get('_pipeline_bound_plugins')
        adapter_context = QueryEntryAdapter.build_adapter_context(query, binding)

        return QueryRunPlan(
            event=event,
            binding=binding,
            bound_plugins=bound_plugins,
            adapter_context=adapter_context,
        )

    @staticmethod
    def _has_legacy_runner_config(pipeline_config: typing.Any) -> bool:
        """Whether a Pipeline still carries a pre-4.11 runner selection or section."""
        from ...pipeline.legacy_config_migration import _TARGETS

        ai_config = pipeline_config.get('ai') if isinstance(pipeline_config, dict) else None
        if not isinstance(ai_config, dict):
            return False
        runner = ai_config.get('runner')
        if isinstance(runner, str) and runner:
            return True
        if isinstance(runner, dict) and runner.get('runner'):
            return True
        return any(name in ai_config for name in _TARGETS)

    def resolve_runner_id_for_telemetry(self, query: pipeline_query.Query) -> str | None:
        """Resolve runner ID for telemetry/logging without full execution."""
        return RunnerConfigResolver.resolve_runner_id(query.pipeline_config)
