"""Agent event envelope and binding models for LangBot Host.

These are Host-internal models, not exposed to SDK.
"""

from __future__ import annotations

import typing
import pydantic

from langbot_plugin.api.entities.builtin.agent_runner.event import (
    ActorContext,
    SubjectContext,
    RawEventRef,
)
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext


class AgentEventEnvelope(pydantic.BaseModel):
    """Event envelope for LangBot Host event gateway.

    This is the unified input model that replaces Query-first approach.
    IM / WebUI / API / EventRouter all produce this envelope.
    """

    event_id: str
    """Unique event identifier."""

    event_type: str
    """Event type (message.received, message.recalled, etc.)."""

    event_time: int | None = None
    """Event timestamp (epoch seconds)."""

    source: str
    """Event source (platform, webui, api, scheduler, system)."""

    source_event_type: str | None = None
    """Original source event type, when available."""

    bot_id: str | None = None
    """Bot UUID handling this event."""

    workspace_id: str | None = None
    """Workspace ID (for multi-tenant)."""

    conversation_id: str | None = None
    """Conversation ID."""

    thread_id: str | None = None
    """Thread ID (for platforms supporting threads)."""

    actor: ActorContext | None = None
    """Actor (who triggered the event)."""

    subject: SubjectContext | None = None
    """Subject (what the event is about)."""

    input: AgentInput
    """Event input."""

    delivery: DeliveryContext
    """Delivery context."""

    raw_ref: RawEventRef | None = None
    """Reference to raw event payload."""

    data: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Small structured event payload. Large payloads should be referenced via raw_ref."""


# Binding scope types
class BindingScope(pydantic.BaseModel):
    """Scope for agent binding."""

    scope_type: typing.Literal['agent', 'bot', 'workspace', 'global'] = 'agent'
    """Scope type."""

    scope_id: str | None = None
    """Scope identifier (agent_id, bot_uuid, etc.)."""


class ResourcePolicy(pydantic.BaseModel):
    """Resource policy for agent binding.

    Controls what resources the runner can access.
    """

    allowed_model_uuids: list[str] | None = None
    """Additional model UUID grants. None means no additional model grants."""

    allowed_tool_names: list[str] | None = None
    """Additional tool name grants. None means no additional tool grants."""

    allowed_tool_sources: dict[str, dict[str, str | None]] | None = None
    """Host-resolved implementation identity for each allowed tool name."""

    allow_all_tools: bool = False
    """Whether all tools visible to the current Host scope are granted."""

    allowed_kb_uuids: list[str] | None = None
    """Additional knowledge base UUID grants. None means no additional KB grants."""

    allowed_skill_names: list[str] | None = None
    """Allowed skill names. None means all currently visible skills are allowed."""

    allow_plugin_storage: bool = True
    """Whether plugin storage is allowed."""

    allow_workspace_storage: bool = False
    """Whether workspace storage is allowed."""


class StatePolicy(pydantic.BaseModel):
    """State policy for agent binding.

    Controls state management behavior.
    """

    enable_state: bool = True
    """Whether host-owned state is enabled."""

    state_scopes: list[typing.Literal['conversation', 'actor', 'subject', 'runner']] = pydantic.Field(
        default_factory=lambda: ['conversation', 'actor']
    )
    """Enabled state scopes."""


class DeliveryPolicy(pydantic.BaseModel):
    """Delivery policy for agent binding.

    Controls how results are delivered.
    """

    enable_streaming: bool = True
    """Whether streaming output is enabled."""

    enable_reply: bool = True
    """Whether reply is enabled."""

    enable_interactions: bool = False
    """Whether the binding permits structured interaction delivery."""

    max_message_size: int | None = None
    """Maximum message size."""


class AgentConfig(pydantic.BaseModel):
    """Host-side Agent configuration.

    Product-level Agents are independent from Pipelines. A Pipeline entry path
    can project its config into this runtime-only model without creating or
    updating a persisted Agent.
    """

    agent_id: str | None = None
    """Host-side Agent/config identifier."""

    processor_type: typing.Literal['agent', 'pipeline'] = 'agent'
    """Product processor kind represented by this runtime config."""

    processor_id: str | None = None
    """Stable product processor identifier."""

    runner_id: str
    """Runner ID to invoke."""

    runner_config: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Agent/runner binding configuration."""

    resource_policy: ResourcePolicy = pydantic.Field(default_factory=ResourcePolicy)
    """Resource policy for this Agent."""

    state_policy: StatePolicy = pydantic.Field(default_factory=StatePolicy)
    """State policy for this Agent."""

    delivery_policy: DeliveryPolicy = pydantic.Field(default_factory=DeliveryPolicy)
    """Delivery policy for this Agent."""

    event_types: list[str] = pydantic.Field(default_factory=lambda: ['message.received'])
    """Event types this Agent handles."""

    enabled: bool = True
    """Whether this Agent can be selected by a binding resolver."""

    metadata: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Non-protocol diagnostic metadata, such as legacy config source."""


class AgentBinding(pydantic.BaseModel):
    """Binding configuration for mapping events to runners.

    This is a Host-internal, runtime-only model for event-to-runner binding.
    Projecting Pipeline config into it is not a persistence migration.
    """

    binding_id: str
    """Unique binding identifier."""

    scope: BindingScope = pydantic.Field(default_factory=BindingScope)
    """Binding scope."""

    event_types: list[str] = pydantic.Field(default_factory=lambda: ['message.received'])
    """Event types this binding handles."""

    runner_id: str
    """Runner ID to invoke."""

    runner_config: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Current Agent/runner configuration."""

    resource_policy: ResourcePolicy = pydantic.Field(default_factory=ResourcePolicy)
    """Resource policy."""

    state_policy: StatePolicy = pydantic.Field(default_factory=StatePolicy)
    """State policy."""

    delivery_policy: DeliveryPolicy = pydantic.Field(default_factory=DeliveryPolicy)
    """Delivery policy."""

    enabled: bool = True
    """Whether binding is enabled."""

    agent_id: str | None = None
    """Host-side Agent/config identifier for this binding."""

    processor_type: typing.Literal['agent', 'pipeline'] = 'agent'
    """Product processor kind selected for this binding."""

    processor_id: str | None = None
    """Stable product processor identifier used for callback resume."""
