"""Run steering pull API entities."""

from __future__ import annotations

import typing

import pydantic

from langbot_plugin.api.entities.builtin.runner.compat import HOST_RESPONSE_MODEL_CONFIG
from langbot_plugin.api.entities.builtin.runner.event import (
    ActorContext,
    AgentEventContext,
    ConversationContext,
    SubjectContext,
)
from langbot_plugin.api.entities.builtin.runner.input import AgentInput


class SteeringInputItem(pydantic.BaseModel):
    """One follow-up input claimed by an active run."""

    claimed_run_id: str
    runner_id: str
    claimed_at: int | None = None
    event: AgentEventContext
    input: AgentInput
    conversation: ConversationContext | None = None
    actor: ActorContext | None = None
    subject: SubjectContext | None = None
    metadata: dict[str, typing.Any] = pydantic.Field(default_factory=dict)

    model_config = HOST_RESPONSE_MODEL_CONFIG


class SteeringPullResult(pydantic.BaseModel):
    """Result returned by RunnerAPIProxy.steering_pull()."""

    items: list[SteeringInputItem] = pydantic.Field(default_factory=list)

    model_config = HOST_RESPONSE_MODEL_CONFIG
