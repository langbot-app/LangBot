"""Run ledger entities for Runtime Control Plane v2."""

from __future__ import annotations

import enum
import typing

import pydantic
from langbot_plugin.api.entities.builtin.runner.compat import HOST_RESPONSE_MODEL_CONFIG


class AgentRunStatus(str, enum.Enum):
    """Host-owned run lifecycle status."""

    CREATED = "created"
    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class AgentRun(pydantic.BaseModel):
    """Persisted Host-owned Runner execution record."""

    id: int | None = None
    run_id: str
    event_id: str | None = None
    agent_id: str | None = None
    binding_id: str | None = None
    runner_id: str | None = None
    conversation_id: str | None = None
    thread_id: str | None = None
    workspace_id: str | None = None
    bot_id: str | None = None
    status: AgentRunStatus | str
    status_reason: str | None = None
    created_at: int | None = None
    started_at: int | None = None
    finished_at: int | None = None
    updated_at: int | None = None
    deadline_at: int | None = None
    cancel_requested_at: int | None = None
    queue_name: str | None = None
    priority: int | None = None
    requested_runtime_id: str | None = None
    claimed_by_runtime_id: str | None = None
    claim_token: str | None = None
    claim_lease_expires_at: int | None = None
    dispatch_attempts: int | None = None
    last_claimed_at: int | None = None
    usage: dict[str, typing.Any] | None = None
    cost: dict[str, typing.Any] | None = None
    metadata: dict[str, typing.Any] = pydantic.Field(default_factory=dict)

    model_config = HOST_RESPONSE_MODEL_CONFIG


class AgentRunEvent(pydantic.BaseModel):
    """Persisted result event emitted by one Runner execution."""

    id: int | None = None
    run_id: str
    sequence: int
    type: str
    data: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    usage: dict[str, typing.Any] | None = None
    created_at: int | None = None
    source: str | None = None
    metadata: dict[str, typing.Any] = pydantic.Field(default_factory=dict)

    model_config = HOST_RESPONSE_MODEL_CONFIG


class RunPage(pydantic.BaseModel):
    """Paged result for run.list APIs."""

    items: list[AgentRun] = pydantic.Field(default_factory=list)
    next_cursor: str | None = None
    prev_cursor: str | None = None
    has_more: bool = False
    total_count: int = 0

    model_config = HOST_RESPONSE_MODEL_CONFIG


class RunEventPage(pydantic.BaseModel):
    """Paged result for run.events.page APIs."""

    items: list[AgentRunEvent] = pydantic.Field(default_factory=list)
    next_cursor: str | None = None
    prev_cursor: str | None = None
    has_more: bool = False
    total_count: int | None = None

    model_config = HOST_RESPONSE_MODEL_CONFIG
