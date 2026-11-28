"""Agent resources entity as defined in Protocol v1."""

from __future__ import annotations

import typing

import pydantic


class ModelResource(pydantic.BaseModel):
    """Model resource available to the agent."""

    model_id: str
    """Model identifier."""

    model_type: str | None = None
    """Model type (chat, embedding, etc.)."""

    provider: str | None = None
    """Model provider name."""

    operations: list[typing.Literal["invoke", "stream", "rerank", "count_tokens"]] = (
        pydantic.Field(default_factory=list)
    )
    """Model operations authorized for this run."""


class ToolResource(pydantic.BaseModel):
    """Tool resource available to the agent."""

    tool_name: str
    """Tool name."""

    tool_type: str | None = None
    """Tool type, including ``platform`` for Host-authorized platform actions."""

    description: str | None = None
    """Tool description."""

    operations: list[typing.Literal["detail", "call"]] = pydantic.Field(
        default_factory=list
    )
    """Tool operations authorized for this run."""

    parameters: dict[str, typing.Any] | None = None
    """Full JSON schema of the tool's parameters. Prefilled by the host so the
    runner can build LLM tool definitions without a separate get_tool_detail
    round-trip. None when the host did not inline the schema."""


class KnowledgeBaseResource(pydantic.BaseModel):
    """Knowledge base resource available to the agent."""

    kb_id: str
    """Knowledge base identifier."""

    kb_name: str | None = None
    """Knowledge base display name."""

    kb_type: str | None = None
    """Knowledge base type."""

    operations: list[typing.Literal["list", "retrieve"]] = pydantic.Field(
        default_factory=list
    )
    """Knowledge-base operations authorized for this run."""


class SkillResource(pydantic.BaseModel):
    """Skill resource available to the agent."""

    skill_name: str
    """Skill name used by the activate tool."""

    display_name: str | None = None
    """Skill display name."""

    description: str | None = None
    """Skill description."""


class StorageResource(pydantic.BaseModel):
    """Storage resources available to the agent."""

    plugin_storage: bool = False
    """Whether plugin storage is accessible."""

    workspace_storage: bool = False
    """Whether workspace storage is accessible."""


class WorkspaceOperationResource(pydantic.BaseModel):
    """Workspace operation resource available to the agent."""

    id: str
    """Unique operation identifier (e.g. 'domain.operation')."""

    domain: str | None = None
    """Domain category."""

    label: dict[str, str] = pydantic.Field(default_factory=dict)
    """Localized labels."""

    summary: str | None = None
    """Brief summary for model and UI."""

    description: str | None = None
    """Detailed operation documentation."""

    risk: str | None = None
    """Risk tier: 'read', 'write', 'dangerous'."""

    side_effect: bool | None = None
    """Whether invoking causes side effects."""

    permission: str | None = None
    """Required permission node."""

    input_schema: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """JSON schema for operation input."""

    output_schema: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """JSON schema for operation output."""

    model_config = pydantic.ConfigDict(extra="allow")


class AgentResources(pydantic.BaseModel):
    """Resources available to an agent run.

    Represents what LangBot has authorized for this run.
    LangBot host must still validate actual calls.
    """

    models: list[ModelResource] = pydantic.Field(default_factory=list)
    """Available models."""

    tools: list[ToolResource] = pydantic.Field(default_factory=list)
    """Available tools."""

    knowledge_bases: list[KnowledgeBaseResource] = pydantic.Field(default_factory=list)
    """Available knowledge bases."""

    skills: list[SkillResource] = pydantic.Field(default_factory=list)
    """Available skills."""

    storage: StorageResource = pydantic.Field(default_factory=StorageResource)
    """Storage access."""

    platform_capabilities: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Platform capabilities available."""

    workspace_operations: list[WorkspaceOperationResource] = pydantic.Field(
        default_factory=list
    )
    """Authorized Application API operations for this run."""
