"""ContextAccess and related entities as defined in Protocol v1.

ContextAccess tells the runner what context Host has inlined and
what APIs are available for pulling more context.
"""

from __future__ import annotations

import typing
import pydantic


class InlineContextPolicy(pydantic.BaseModel):
    """Describes what context Host has inlined."""

    mode: typing.Literal["none", "current_event", "recent_tail", "summary_tail"] = (
        "current_event"
    )
    """Inline mode used."""

    delivered_count: int = 0
    """Number of items delivered."""

    source_total_count: int | None = None
    """Total items available from source."""

    messages_complete: bool = False
    """Whether all relevant messages are included."""

    reason: str | None = None
    """Reason for the policy (e.g., 'current_event_only')."""


class ContextAPICapabilities(pydantic.BaseModel):
    """Available context APIs for the runner."""

    box: bool = False
    """Whether invocation Box binding and file APIs are available."""

    input_attachments: bool = False
    """Whether input attachment bytes can be read by ref with read_input_attachment."""

    reply_stream: bool = False
    """Whether explicit streaming replies are available (independent of model streaming)."""

    prompt_get: bool = False
    """Whether the effective prompt API is available."""

    history_page: bool = False
    """Whether history.page API is available."""

    history_search: bool = False
    """Whether history.search API is available."""

    event_get: bool = False
    """Whether events.get API is available."""

    event_page: bool = False
    """Whether events.page API is available."""

    state: bool = False
    """Whether state API is available."""

    storage: bool = False
    """Whether storage API is available."""

    steering_pull: bool = False
    """Whether run-scoped steering/follow-up pull API is available."""

    run_get: bool = False
    """Whether run.get API is available."""

    run_list: bool = False
    """Whether run.list API is available."""

    run_events_page: bool = False
    """Whether run.events.page API is available."""

    run_cancel: bool = False
    """Whether run.cancel API is available."""

    run_append_result: bool = False
    """Whether run.append_result API is available."""

    run_finalize: bool = False
    """Whether run.finalize API is available."""


class ContextAccess(pydantic.BaseModel):
    """Context access descriptor for the runner.

    Tells the runner:
    - Where the current event is in conversation/thread
    - What cursor to use for pulling more history
    - What Host has inlined vs not inlined
    - What context APIs are available
    """

    conversation_id: str | None = None
    """Current conversation ID."""

    thread_id: str | None = None
    """Current thread ID."""

    latest_cursor: str | None = None
    """Cursor for the latest event (use for history.page before_cursor)."""

    event_seq: int | None = None
    """Current event sequence number."""

    transcript_seq: int | None = None
    """Current transcript sequence number."""

    has_history_before: bool = False
    """Whether there's history before the inlined content."""

    inline_policy: InlineContextPolicy = pydantic.Field(
        default_factory=InlineContextPolicy
    )
    """What Host has inlined."""

    available_apis: ContextAPICapabilities = pydantic.Field(
        default_factory=ContextAPICapabilities
    )
    """What context APIs are available."""
