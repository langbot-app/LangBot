"""Agent runtime context as defined in Protocol v1."""

from __future__ import annotations

import typing
import pydantic


class AgentRuntimeContext(pydantic.BaseModel):
    """Runtime context for an agent run.

    Provides host/environment information for the agent.
    """

    langbot_version: str | None = None
    """LangBot host version."""

    trace_id: str | None = None
    """Trace ID for observability."""

    deadline_at: float | None = None
    """Deadline timestamp (epoch seconds) for timeout."""

    metadata: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Additional runtime metadata."""
