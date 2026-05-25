"""Agent event envelope and binding models for LangBot Host.

These are Host-internal models, not exposed to SDK.
"""
from __future__ import annotations

import typing
import pydantic

from langbot_plugin.api.entities.builtin.agent_runner.event import (
    AgentEventContext,
    ConversationContext,
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
    """Small structured event payload. Large payloads should be referenced via raw_ref/artifacts."""


# Binding scope types
class BindingScope(pydantic.BaseModel):
    """Scope for agent binding."""

    scope_type: typing.Literal["bot", "pipeline", "workspace", "global"] = "pipeline"
    """Scope type."""

    scope_id: str | None = None
    """Scope identifier (bot_uuid, pipeline_uuid, etc.)."""


class ResourcePolicy(pydantic.BaseModel):
    """Resource policy for agent binding.

    Controls what resources the runner can access.
    """

    allowed_model_uuids: list[str] | None = None
    """Allowed model UUIDs. None means all authorized."""

    allowed_tool_names: list[str] | None = None
    """Allowed tool names. None means all authorized."""

    allowed_kb_uuids: list[str] | None = None
    """Allowed knowledge base UUIDs. None means all authorized."""

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

    state_scopes: list[typing.Literal["conversation", "actor", "subject", "runner"]] = (
        pydantic.Field(default_factory=lambda: ["conversation", "actor"])
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

    max_message_size: int | None = None
    """Maximum message size."""


class AgentBinding(pydantic.BaseModel):
    """Binding configuration for mapping events to runners.

    This is Host-internal model for event-to-runner binding.
    It replaces the old Pipeline runner config role.
    """

    binding_id: str
    """Unique binding identifier."""

    scope: BindingScope = pydantic.Field(default_factory=BindingScope)
    """Binding scope."""

    event_types: list[str] = pydantic.Field(default_factory=lambda: ["message.received"])
    """Event types this binding handles."""

    runner_id: str
    """Runner ID to invoke."""

    runner_config: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Runner instance configuration."""

    resource_policy: ResourcePolicy = pydantic.Field(default_factory=ResourcePolicy)
    """Resource policy."""

    state_policy: StatePolicy = pydantic.Field(default_factory=StatePolicy)
    """State policy."""

    delivery_policy: DeliveryPolicy = pydantic.Field(default_factory=DeliveryPolicy)
    """Delivery policy."""

    enabled: bool = True
    """Whether binding is enabled."""

    # Fields for Pipeline adapter
    pipeline_uuid: str | None = None
    """Pipeline UUID (for Pipeline adapter)."""

    max_round: int | None = None
    """max-round (for Pipeline adapter bootstrap, not Protocol v1)."""
