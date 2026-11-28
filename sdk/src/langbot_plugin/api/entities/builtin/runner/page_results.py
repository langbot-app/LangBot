"""History and Event page result entities."""

from __future__ import annotations

import typing
import pydantic

from .transcript import TranscriptItem
from langbot_plugin.api.entities.builtin.runner.compat import HOST_RESPONSE_MODEL_CONFIG


class HistoryPage(pydantic.BaseModel):
    """Paged result for history.page API.

    Returns Transcript items ordered by sequence/cursor.
    Used by Runner to pull conversation history.
    """

    items: list[TranscriptItem] = pydantic.Field(default_factory=list)
    """Transcript items in this page."""

    next_cursor: str | None = None
    """Cursor for the next page (forward direction)."""

    prev_cursor: str | None = None
    """Cursor for the previous page (backward direction)."""

    has_more: bool = False
    """Whether more items are available."""

    total_count: int | None = None
    """Total count if available (may be None for large conversations)."""

    model_config = HOST_RESPONSE_MODEL_CONFIG


class HistorySearchResult(pydantic.BaseModel):
    """Result for history.search API.

    Returns matching transcript items ranked by relevance.
    Basic implementation may use simple LIKE filtering.
    """

    items: list[TranscriptItem] = pydantic.Field(default_factory=list)
    """Matching transcript items."""

    total_count: int | None = None
    """Total matching count if available."""

    query: str
    """The search query that was executed."""

    model_config = HOST_RESPONSE_MODEL_CONFIG


class AgentEventRecord(pydantic.BaseModel):
    """Event record returned by event.get and event.page APIs.

    This is a stable, auditable representation of events stored in EventLog.
    It does not include large raw payload bodies.
    """

    event_id: str
    """Unique event identifier."""

    event_type: str
    """Event type (message.received, tool.call.started, etc.)."""

    event_time: int | None = None
    """Unix timestamp when the event occurred."""

    source: str
    """Event source (platform, webui, api, scheduler, system)."""

    bot_id: str | None = None
    """Bot UUID that handled this event."""

    workspace_id: str | None = None
    """Workspace ID for multi-tenant deployments."""

    conversation_id: str | None = None
    """Conversation ID this event belongs to."""

    thread_id: str | None = None
    """Thread ID if applicable."""

    actor_type: str | None = None
    """Actor type (user, system, runner)."""

    actor_id: str | None = None
    """Actor identifier."""

    actor_name: str | None = None
    """Actor display name."""

    subject_type: str | None = None
    """Subject type (message, tool_call, attachment, etc.)."""

    subject_id: str | None = None
    """Subject identifier."""

    input_summary: str | None = None
    """Brief summary of input (truncated text)."""

    input_ref: str | None = None
    """Reference to full input payload if available."""

    raw_ref: str | None = None
    """Reference to raw event payload if available."""

    seq: int | None = None
    """Sequence number for pagination."""

    cursor: str | None = None
    """Cursor string for pagination."""

    created_at: int | None = None
    """Unix timestamp when the record was created."""

    metadata: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Additional metadata."""

    model_config = HOST_RESPONSE_MODEL_CONFIG


class EventPage(pydantic.BaseModel):
    """Paged result for event.page API.

    Returns event records ordered by sequence/cursor.
    Used by Runner to access non-message events.
    """

    items: list[AgentEventRecord] = pydantic.Field(default_factory=list)
    """Event records in this page."""

    next_cursor: str | None = None
    """Cursor for the next page."""

    prev_cursor: str | None = None
    """Cursor for the previous page."""

    has_more: bool = False
    """Whether more items are available."""

    total_count: int | None = None
    """Total count if available."""

    model_config = HOST_RESPONSE_MODEL_CONFIG
