"""Runner manifest as defined in Protocol v1."""

from __future__ import annotations

import typing
import pydantic


# I18n object: maps locale code to localized string
I18nObject = dict[str, str]


class DynamicFormItemSchema(pydantic.BaseModel):
    """Schema for a dynamic form configuration item.

    Represents a form field in the runner's config schema.
    """

    type: str
    """Field type (text, select, llm-model-selector, etc.)."""

    name: str
    """Field name/key."""

    label: I18nObject = pydantic.Field(default_factory=dict)
    """Localized label."""

    description: I18nObject | None = None
    """Localized description."""

    required: bool = False
    """Whether the field is required."""

    default: typing.Any = None
    """Default value."""

    options: list[dict[str, typing.Any]] | None = None
    """Options for select/radio types."""

    allow_custom: bool = False
    """Allow an editable value alongside select presets."""

    # Allow additional properties for form item flexibility
    model_config = pydantic.ConfigDict(extra="allow")


class RunnerCapabilities(pydantic.BaseModel):
    """Capabilities declared by a Runner component."""

    streaming: bool = False
    """Runner may output message.delta events."""

    tool_calling: bool = False
    """Runner needs host tool detail/call operations."""

    knowledge_retrieval: bool = False
    """Runner needs host knowledge base retrieval operations."""

    multimodal_input: bool = False
    """Runner can process non-text input contents or attachments."""

    skill_authoring: bool = False
    """Runner wants Host-provided skill authoring tools when available."""

    interrupt: bool = False
    """Runner supports cancel or interrupt operations."""

    steering: bool = False
    """Runner can pull run-scoped steering/follow-up input at turn boundaries."""

    interactions: bool = False
    """Runner can request Host-owned structured interactions and consume submissions."""

    model_config = pydantic.ConfigDict(extra="forbid")


class RunnerPermissions(pydantic.BaseModel):
    """LangBot resource permissions requested by a Runner component.

    These declarations are only an upper bound for LangBot-managed resources.
    The Host must intersect them with the binding policy for the current run.
    They do not constrain native capabilities of an external harness.
    """

    models: list[typing.Literal["invoke", "stream", "rerank", "count_tokens"]] = (
        pydantic.Field(default_factory=list)
    )
    """Model operations allowed."""

    tools: list[typing.Literal["detail", "call"]] = pydantic.Field(default_factory=list)
    """Tool operations allowed."""

    knowledge_bases: list[typing.Literal["list", "retrieve"]] = pydantic.Field(
        default_factory=list
    )
    """Knowledge base operations allowed."""

    history: list[typing.Literal["page", "search"]] = pydantic.Field(
        default_factory=list
    )
    """History operations allowed."""

    events: list[typing.Literal["get", "page"]] = pydantic.Field(default_factory=list)
    """Event operations allowed."""

    storage: list[typing.Literal["plugin", "workspace"]] = pydantic.Field(
        default_factory=list
    )
    """Storage scopes allowed."""

    interactions: list[typing.Literal["request"]] = pydantic.Field(default_factory=list)
    """Structured interaction operations allowed."""

    model_config = pydantic.ConfigDict(extra="forbid")


class RunnerManifest(pydantic.BaseModel):
    """Stable Runner descriptor returned during LIST_RUNNERS."""

    id: str
    """Unique runner ID. Recommended format: plugin:author/plugin_name/runner_name."""

    name: str
    """Runner name within the plugin (e.g., 'default')."""

    label: I18nObject

    component_kind: typing.Literal["Runner"] = "Runner"
    usages: list[typing.Literal["agent", "event"]] = pydantic.Field(min_length=1)
    supported_event_patterns: list[str] = pydantic.Field(default_factory=lambda: ["*"])
    """Localized display name."""

    description: I18nObject | None = None
    """Localized description."""

    capabilities: RunnerCapabilities = pydantic.Field(
        default_factory=RunnerCapabilities
    )
    """Runner capabilities."""

    permissions: RunnerPermissions = pydantic.Field(default_factory=RunnerPermissions)
    """Requested LangBot resource permissions."""

    config_schema: list[DynamicFormItemSchema] = pydantic.Field(default_factory=list)
    """Configuration form schema for Agent/runner config."""

    metadata: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Additional metadata for display, diagnostics, non-stable extensions."""

    model_config = pydantic.ConfigDict(extra="forbid")
