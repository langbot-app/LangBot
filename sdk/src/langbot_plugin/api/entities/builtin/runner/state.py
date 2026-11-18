"""AgentRunState - scoped state snapshot for Runner.

State is managed by LangBot host, readable/writable by runner,
isolated by scope, and durable across runs.
"""

from __future__ import annotations

import typing
import pydantic


class AgentRunState(pydantic.BaseModel):
    """Scoped state snapshot passed to Runner.run().

    State is host-managed, runner-readable/writable, scope-isolated, and durable.
    Host should populate state snapshot from persistent storage before each run,
    and persist state updates from state.updated results after run completes.

    Scopes:
    - conversation: State scoped to current conversation + current runner.
      Example: external platform conversation/thread ID, conversation-level context.
    - actor: State scoped to current user across all conversations.
      Example: user preferences, long-term memory, user profile data.
    - subject: State scoped to current group/channel/object.
      Example: group settings, channel context, shared state.
    - runner: State scoped to runner instance across all conversations/users.
      Use sparingly - typically for runner-level configuration or caching.

    Key naming convention:
    - Use namespace prefixes: external.*, memory.*, config.*, cache.*
    - Example: external.conversation_id, external.thread_id, memory.summary

    Important:
    - State is NOT config (static runner configuration).
    - State is NOT params (single-run business parameters).
    - State is NOT runtime.metadata (host observability info).
    - State changes should be requested via RunnerResult.state_updated().
    """

    conversation: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """State scoped to current conversation + current runner."""

    actor: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """State scoped to current user across all conversations."""

    subject: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """State scoped to current group/channel/object."""

    runner: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """State scoped to runner instance. Use sparingly."""


# Valid scope names for state.updated
STATE_SCOPE_LITERAL = typing.Literal["conversation", "actor", "subject", "runner"]

VALID_STATE_SCOPES: tuple[str, ...] = ("conversation", "actor", "subject", "runner")
