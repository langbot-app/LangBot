"""Agent API error model for run-scoped Host APIs."""

from __future__ import annotations

import typing

import pydantic
from langbot_plugin.api.entities.builtin.runner.compat import HOST_RESPONSE_MODEL_CONFIG


class AgentAPIError(pydantic.BaseModel):
    """Structured error returned or raised by RunnerAPIProxy operations."""

    code: str
    message: str
    retryable: bool = False
    details: dict[str, typing.Any] = pydantic.Field(default_factory=dict)

    model_config = HOST_RESPONSE_MODEL_CONFIG


class AgentAPIException(Exception):
    """Exception wrapper carrying a stable AgentAPIError payload."""

    def __init__(self, error: AgentAPIError | str):
        if isinstance(error, str):
            error = AgentAPIError(code="runner_error", message=error)
        self.error = error
        super().__init__(error.message)
