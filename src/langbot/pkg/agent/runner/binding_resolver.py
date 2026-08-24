"""Resolve host events to one effective Agent binding."""

from __future__ import annotations

from .host_models import AgentConfig, AgentBinding, AgentEventEnvelope, BindingScope


class AgentBindingResolutionError(Exception):
    """Raised when an event cannot resolve to exactly one Agent binding."""


class AgentBindingResolver:
    """Resolve an event to a single AgentBinding.

    The target product model is one bot / IM channel -> one Agent. Fan-out,
    observer agents, or multi-runner arbitration require separate delivery and
    state semantics and are intentionally not hidden in this resolver.
    """

    def resolve_one(
        self,
        event: AgentEventEnvelope,
        agents: list[AgentConfig],
    ) -> AgentBinding:
        """Resolve exactly one enabled Agent for the event.

        Callers that source agents from bot/workspace/global configuration must
        pre-filter candidates to the event scope before calling this resolver.
        The current AgentConfig model represents one already-selected product
        Agent and does not carry enough scope metadata to make that decision
        safely here.
        """
        matches = [agent for agent in agents if agent.enabled and event.event_type in agent.event_types]

        if not matches:
            raise AgentBindingResolutionError(f'No Agent binding matches event_type={event.event_type}')

        if len(matches) > 1:
            agent_ids = ', '.join(agent.agent_id or '<anonymous>' for agent in matches)
            raise AgentBindingResolutionError(
                f'Multiple Agent bindings match event_type={event.event_type}: {agent_ids}'
            )

        return self._to_binding(matches[0])

    def _to_binding(self, agent: AgentConfig) -> AgentBinding:
        """Project product-level Agent config into the run-time binding model."""
        scope = BindingScope(
            scope_type='agent',
            scope_id=agent.agent_id,
        )

        return AgentBinding(
            binding_id=f'agent_{agent.agent_id or "default"}_{agent.runner_id}',
            scope=scope,
            event_types=list(agent.event_types),
            runner_id=agent.runner_id,
            runner_config=agent.runner_config,
            resource_policy=agent.resource_policy,
            state_policy=agent.state_policy,
            delivery_policy=agent.delivery_policy,
            enabled=agent.enabled,
            agent_id=agent.agent_id,
            processor_type=agent.processor_type,
            processor_id=agent.processor_id or agent.agent_id,
        )
