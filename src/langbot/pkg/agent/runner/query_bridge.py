"""Pipeline Query bridge for AgentRunner execution."""

from __future__ import annotations

import dataclasses
import typing

from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query

from .binding_resolver import AgentBindingResolver
from .config_migration import ConfigMigration
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
        runner_id = ConfigMigration.resolve_runner_id(query.pipeline_config)
        if not runner_id:
            raise RunnerNotFoundError('no runner configured')

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

    def resolve_runner_id_for_telemetry(self, query: pipeline_query.Query) -> str | None:
        """Resolve runner ID for telemetry/logging without full execution."""
        return ConfigMigration.resolve_runner_id(query.pipeline_config)
